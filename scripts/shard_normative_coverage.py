"""Split monolithic normative-coverage authoring inputs into per-document YAML shards."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

from aiact.yaml_loader import load_yaml_mapping

ROOT = Path(__file__).resolve().parents[1]


def _shard_path(kind: str, document: str) -> Path:
    if kind == "article":
        match = re.fullmatch(r"(\d+)([a-z]?)", document)
        if match is None:
            raise ValueError(f"invalid article identifier {document!r}")
        return Path("articles") / f"{int(match.group(1)):03d}{match.group(2)}.yaml"
    return Path("annexes") / f"{document}.yaml"


def _record_document(source: str) -> tuple[str, str]:
    annex = re.match(r"^ANNEX-([IVXLCDM]+)-", source)
    if annex is not None:
        return "annex", annex.group(1)
    article = re.match(r"^A(\d{3})([A-Z]?)-", source)
    if article is None:
        raise ValueError(f"cannot derive document from source {source!r}")
    return "article", f"{int(article.group(1))}{article.group(2).lower()}"


def _write(path: Path, mapping: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(mapping, sort_keys=False, width=100), encoding="utf-8")


def shard_version(version: str) -> None:
    coverage_root = ROOT / "data" / "policy" / "normative-coverage" / version
    segment_source = load_yaml_mapping(
        coverage_root / "segments.yaml", description="reviewed document inventory"
    )
    norm_source = load_yaml_mapping(
        coverage_root / "source-records.yaml", description="norm source inventory"
    )

    segment_root = coverage_root / "segments"
    norm_root = coverage_root / "source-records"
    if segment_root.exists() or norm_root.exists():
        raise ValueError("shard destination already exists")

    documents = segment_source.pop("documents")
    _write(segment_root / "manifest.yaml", segment_source)
    for document in documents:
        path = segment_root / _shard_path(str(document["kind"]), str(document["number"]))
        _write(path, {"documents": [document]})

    records = norm_source.pop("records")
    _write(norm_root / "manifest.yaml", norm_source)
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for record in records:
        grouped.setdefault(_record_document(str(record["source"])), []).append(record)
    for (kind, document), document_records in grouped.items():
        path = norm_root / _shard_path(kind, document)
        _write(path, {"records": document_records})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--act-version", required=True)
    args = parser.parse_args()
    shard_version(args.act_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
