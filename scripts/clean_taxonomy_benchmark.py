from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


EXPECTED_LAYERS = {"人", "物", "环", "管"}
EXPECTED_SCORES = {1, 2, 3, 4, 5}
PHRASE_SPLIT_TOKEN = "是taxonomy里的元素吗"


@dataclass
class ParsedRow:
    source_line: int
    raw_line: str
    repaired_json: bool
    prompt: str
    phrase: str
    label: dict[str, Any]


def _load_row(line: str, line_number: int) -> tuple[dict[str, Any], bool]:
    try:
        return json.loads(line), False
    except json.JSONDecodeError:
        # Repair the one known malformed pattern in the benchmark:
        # `"completion" "{...}"` -> `"completion": "{...}"`
        repaired = re.sub(r'"completion"\s+"{', '"completion": "{', line)
        return json.loads(repaired), True


def _parse_label(row: dict[str, Any]) -> dict[str, Any]:
    completion = row["completion"]
    if not isinstance(completion, str):
        raise ValueError("completion must be a JSON string")

    label = json.loads(completion)
    normalized = {
        "in_taxonomy": label.get("in_taxonomy"),
        "layer": label.get("layer"),
        "score": label.get("score"),
    }

    if normalized["in_taxonomy"] is False:
        normalized["layer"] = None
        normalized["score"] = None

    if normalized["layer"] is not None and normalized["layer"] not in EXPECTED_LAYERS:
        raise ValueError(f"unexpected layer: {normalized['layer']!r}")
    if normalized["score"] is not None and normalized["score"] not in EXPECTED_SCORES:
        raise ValueError(f"unexpected score: {normalized['score']!r}")
    if normalized["in_taxonomy"] is True and normalized["layer"] is None:
        raise ValueError("positive sample must have layer")
    if normalized["in_taxonomy"] is True and normalized["score"] is None:
        raise ValueError("positive sample must have score")

    return normalized


def _extract_phrase(prompt: str) -> str:
    if PHRASE_SPLIT_TOKEN not in prompt:
        raise ValueError(f"prompt missing split token: {prompt!r}")
    return prompt.split(PHRASE_SPLIT_TOKEN, 1)[0].strip()


def load_benchmark(path: Path) -> tuple[list[ParsedRow], dict[str, Any]]:
    parsed_rows: list[ParsedRow] = []
    issues: dict[str, Any] = {
        "source_path": str(path),
        "bad_json_lines": [],
        "negative_rows_normalized": [],
        "duplicate_rows_removed": [],
        "conflicting_duplicates": [],
    }

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue

        repaired_json = False
        try:
            row, repaired_json = _load_row(raw_line, line_number)
        except json.JSONDecodeError as exc:
            issues["bad_json_lines"].append(
                {
                    "line": line_number,
                    "error": str(exc),
                    "raw_line": raw_line,
                    "repaired": False,
                }
            )
            continue

        if repaired_json:
            issues["bad_json_lines"].append(
                {
                    "line": line_number,
                    "error": "missing colon between completion key and value",
                    "raw_line": raw_line,
                    "repaired": True,
                }
            )

        prompt = row["prompt"]
        phrase = _extract_phrase(prompt)
        label = _parse_label(row)

        if json.loads(row["completion"]).get("in_taxonomy") is False and (
            json.loads(row["completion"]).get("layer") is not None
            or json.loads(row["completion"]).get("score") is not None
        ):
            issues["negative_rows_normalized"].append(
                {
                    "line": line_number,
                    "phrase": phrase,
                    "normalized_label": label,
                    "original_completion": row["completion"],
                }
            )

        parsed_rows.append(
            ParsedRow(
                source_line=line_number,
                raw_line=raw_line,
                repaired_json=repaired_json,
                prompt=prompt,
                phrase=phrase,
                label=label,
            )
        )

    return parsed_rows, issues


def deduplicate_rows(rows: list[ParsedRow], issues: dict[str, Any]) -> list[ParsedRow]:
    deduped: list[ParsedRow] = []
    by_phrase: dict[str, ParsedRow] = {}

    for row in rows:
        previous = by_phrase.get(row.phrase)
        if previous is None:
            by_phrase[row.phrase] = row
            deduped.append(row)
            continue

        if previous.label == row.label:
            issues["duplicate_rows_removed"].append(
                {
                    "kept_line": previous.source_line,
                    "removed_line": row.source_line,
                    "phrase": row.phrase,
                    "label": row.label,
                }
            )
            continue

        issues["conflicting_duplicates"].append(
            {
                "phrase": row.phrase,
                "kept_line": previous.source_line,
                "removed_line": row.source_line,
                "kept_label": previous.label,
                "removed_label": row.label,
            }
        )

    return deduped


def write_clean_jsonl(rows: list[ParsedRow], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            record = {
                "prompt": row.prompt,
                "completion": json.dumps(row.label, ensure_ascii=False),
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_summary(rows: list[ParsedRow], issues: dict[str, Any]) -> dict[str, Any]:
    positives = [row for row in rows if row.label["in_taxonomy"]]
    negatives = [row for row in rows if not row.label["in_taxonomy"]]

    layer_counts: dict[str, int] = {}
    score_counts: dict[str, int] = {}
    for layer in sorted(EXPECTED_LAYERS):
        count = sum(1 for row in positives if row.label["layer"] == layer)
        if count:
            layer_counts[layer] = count
    for score in sorted(EXPECTED_SCORES):
        count = sum(1 for row in positives if row.label["score"] == score)
        if count:
            score_counts[str(score)] = count

    return {
        "source_path": issues["source_path"],
        "cleaning_policy": {
            "fixed_malformed_json_lines": True,
            "normalized_negative_samples_to_null_layer_and_score": True,
            "deduplicated_identical_phrases": True,
            "preserved_original_positive_labels": True,
        },
        "known_limitations": [
            "The prompt text says higher scores are more abstract, but the examples and labels are more consistent with higher scores being more specific/concrete.",
            "This cleaned dataset preserves original labels. Downstream training should document how score semantics are interpreted.",
            "The benchmark is imbalanced toward taxonomy-negative samples and management-layer positives.",
        ],
        "counts": {
            "clean_rows": len(rows),
            "positive_rows": len(positives),
            "negative_rows": len(negatives),
            "layer_counts": layer_counts,
            "score_counts": score_counts,
        },
        "issues": issues,
    }


def main() -> int:
    dataset_dir = Path("data")
    source_path = dataset_dir / "taxonomy_phrases_benchmark评测.jsonl"
    cleaned_path = dataset_dir / "taxonomy_phrases_benchmark.cleaned.jsonl"
    issues_path = dataset_dir / "taxonomy_phrases_benchmark.issues.json"

    rows, issues = load_benchmark(source_path)
    deduped_rows = deduplicate_rows(rows, issues)
    write_clean_jsonl(deduped_rows, cleaned_path)

    summary = build_summary(deduped_rows, issues)
    issues_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "source_path": str(source_path),
                "cleaned_path": str(cleaned_path),
                "issues_path": str(issues_path),
                "clean_rows": len(deduped_rows),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
