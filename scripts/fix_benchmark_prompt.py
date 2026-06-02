"""One-time fix: replace "分值越高代表越抽象" with "分值越高代表越具体" in all benchmark files.

The original prompt text says "higher score = more abstract", but the labels
follow "higher score = more specific". This script fixes the prompt text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


OLD_TEXT = "分值越高代表越抽象"
NEW_TEXT = "分值越高代表越具体"


def fix_file(path: Path) -> int:
    """Replace old text with new text in file. Returns number of replacements."""
    content = path.read_text(encoding="utf-8")
    count = content.count(OLD_TEXT)
    if count:
        new_content = content.replace(OLD_TEXT, NEW_TEXT)
        path.write_text(new_content, encoding="utf-8")
    return count


def remove_empty_completion(path: Path) -> int:
    """Remove lines where completion is an empty string. Returns number removed."""
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = []
    removed = 0
    for line in lines:
        if not line.strip():
            kept.append(line)
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            kept.append(line)
            continue
        completion = row.get("completion", "")
        if isinstance(completion, str) and completion.strip() == "":
            removed += 1
            continue
        kept.append(line)
    if removed:
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return removed


def main() -> int:
    data_dir = Path("data")

    files_to_fix = [
        data_dir / "taxonomy_phrases_benchmark评测.jsonl",
        data_dir / "test_set.jsonl",
    ]

    total = 0
    for path in files_to_fix:
        if path.is_file():
            count = fix_file(path)
            total += count
            print(f"Fixed {count} occurrence(s) in {path}")

    # Also fix the generated cleaned file if it exists
    cleaned = data_dir / "taxonomy_phrases_benchmark.cleaned.jsonl"
    if cleaned.is_file():
        count = fix_file(cleaned)
        total += count
        print(f"Fixed {count} occurrence(s) in {cleaned}")

    # Remove lines with empty completion from test_set.jsonl
    test_set = data_dir / "test_set.jsonl"
    if test_set.is_file():
        removed = remove_empty_completion(test_set)
        print(f"Removed {removed} empty-completion line(s) from {test_set}")

    print(f"\nTotal replacements: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
