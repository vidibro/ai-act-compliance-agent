"""Regenerate each guidance document's `paragraphs.yaml` from its PDF, or check it is current."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aiact.guidance import DEFAULT_GUIDANCE_ROOT
from aiact.guidance_coverage import PARAGRAPHS_FILE, render_paragraphs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_GUIDANCE_ROOT)
    parser.add_argument("--check", action="store_true", help="fail if a stored file is stale")
    args = parser.parse_args()

    stale = []
    for document_dir in sorted(path for path in args.root.iterdir() if path.is_dir()):
        target = document_dir / PARAGRAPHS_FILE
        rendered = render_paragraphs(document_dir)
        if args.check:
            if not target.is_file() or target.read_text(encoding="utf-8") != rendered:
                stale.append(str(target))
        else:
            target.write_text(rendered, encoding="utf-8")
            print(f"wrote {target}")
    if stale:
        print("stale, regenerate with scripts/extract_guidance_paragraphs.py:", *stale, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
