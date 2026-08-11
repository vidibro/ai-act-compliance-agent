#!/usr/bin/env python3
"""Keep a held-out authoring session blind.

A held-out case is only worth its score if whoever wrote it did not know how the classifier
behaves. That is not something an assistant can promise — it has already read the roadmap in some
other session, or will reason its way to "just a peek at the format". So it is enforced here
instead: Claude Code runs this before every read-shaped tool call, and exit 2 rejects the call.

BLOCKED are the files that record how the model performed, or that contain worked examples of the
very cases being authored. ALLOWED, deliberately, is everything needed to do the job: the enacted
text, the schemas, and the held-out file itself.

Delete `.claude/settings.json` when the authoring session is over — this guard makes ordinary work
on the project impossible, which is the point.
"""

import json
import re
import sys

# Substring match against any path mentioned in the tool call. Deliberately broad: a false block
# costs one rephrase, a false pass silently destroys the only number worth reporting.
BLOCKED = [
    ("ROADMAP", "records how the classifier scored, live, case by case"),
    ("classification_cases.yaml", "the DEV cases — worked examples of exactly this task"),
    ("test_annex_i", "test names and docstrings spell out the traps"),
    ("README", "explains the two doors and which systems fall through"),
    ("test_classification_graph", "asserts expected routing per case"),
    ("test_classification_cases", "asserts properties of the answer key"),
    ("test_pipeline", "worked gate examples"),
    (".jsonl", "session transcripts"),
    ("scratchpad", "prior working notes"),
]

READ_TOOLS = {"Read", "Grep", "Glob", "NotebookRead"}
# A shell can read a file too. Catch the obvious readers rather than trying to parse shell.
SHELL_READERS = re.compile(r"\b(cat|head|tail|less|more|bat|sed|awk|grep|rg|strings|open)\b")


def offending(text: str) -> tuple[str, str] | None:
    for needle, why in BLOCKED:
        if needle.lower() in text.lower():
            return needle, why
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool = payload.get("tool_name", "")
    args = payload.get("tool_input", {}) or {}

    if tool in READ_TOOLS:
        haystack = " ".join(str(v) for v in args.values())
    elif tool == "Bash":
        command = str(args.get("command", ""))
        haystack = command if SHELL_READERS.search(command) else ""
    else:
        return 0

    hit = offending(haystack)
    if hit:
        needle, why = hit
        print(
            f"BLOCKED: this session is authoring HELD-OUT cases and must stay blind.\n"
            f"`{needle}` {why}.\n"
            f"Work from the enacted text and the source PDFs only. Do not look for another way "
            f"to read it — the block is the task, not an obstacle to it.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
