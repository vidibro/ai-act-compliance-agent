"""Strict YAML loading shared by assurance artifacts and their reviewed inputs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects mappings with duplicate keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_yaml_mapping(path: str | Path, *, description: str) -> dict[str, Any]:
    """Load one YAML mapping without permitting silent duplicate-key replacement."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"{description} not found: {source}")
    raw = yaml.load(source.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    if not isinstance(raw, dict):
        raise ValueError(f"{source} must contain a YAML mapping")
    return raw


def load_yaml_mapping_or_shards(path: str | Path, *, description: str) -> dict[str, Any]:
    """Load one mapping or merge a directory of mapping shards without silent conflicts."""
    source = Path(path)
    if source.is_file():
        return load_yaml_mapping(source, description=description)
    if not source.is_dir():
        raise FileNotFoundError(f"{description} not found: {source}")

    def shard_sort_key(item: Path) -> tuple[int, int, str]:
        relative = item.relative_to(source)
        if relative == Path("manifest.yaml"):
            return 0, 0, ""
        group = 1 if relative.parts[0] == "articles" else 2
        if group == 1:
            match = re.fullmatch(r"(\d+)([a-z]?)", item.stem)
            if match is not None:
                return group, int(match.group(1)), match.group(2)
        return group, 0, item.stem

    files = sorted(source.rglob("*.yaml"), key=shard_sort_key)
    if not files:
        raise FileNotFoundError(f"{description} has no YAML shards: {source}")

    merged: dict[str, Any] = {}
    origins: dict[str, Path] = {}
    for shard in files:
        mapping = load_yaml_mapping(shard, description=f"{description} shard")
        for key, value in mapping.items():
            if key not in merged:
                merged[key] = value
                origins[key] = shard
                continue
            current = merged[key]
            if isinstance(current, list) and isinstance(value, list):
                current.extend(value)
            elif isinstance(current, dict) and isinstance(value, dict):
                duplicates = sorted(set(current) & set(value))
                if duplicates:
                    raise ValueError(
                        f"{description} shards duplicate {key} entries {duplicates}: "
                        f"{origins[key]} and {shard}"
                    )
                current.update(value)
            elif current != value:
                raise ValueError(
                    f"{description} shards disagree on {key!r}: {origins[key]} and {shard}"
                )
    return merged
