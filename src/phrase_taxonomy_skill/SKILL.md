---
name: safety-reports-skill
description: Build a four-stage accident-cause taxonomy draft from a deduplicated phrase set. Use when the input is already a collection of extracted accident phrases, and you need to decide which phrases belong in the taxonomy, classify them into 人/物/环/管, assign a granularity level, and attach candidate parent nodes into a hierarchy. When this skill is used by an agent in conversation, the agent should use its current model directly rather than requiring a separate API key.
---

# Accident Phrase Taxonomy Skill

## Execution Mode

This skill is primarily agent-driven.

That means:

- When an agent uses this skill in a live conversation, it should perform the four stages with its current configured model.
- It should not require the user to provide a separate OpenAI API key just to use the skill.
- Local scripts in this repository are helper prototypes and exporters. They are useful for previewing structure, rule behavior, and output formatting, but they are not the primary way the skill should reason.

Use the current agent model for:

- Stage 1 classification
- Stage 2 layer classification
- Stage 3 granularity judgment
- Stage 4 parent selection from filtered candidates

## Goal

Turn a deduplicated set of accident-related phrases into a first-pass taxonomy draft using four stages:

1. `in_taxonomy`
2. `layer`
3. `granularity_level`
4. `parent_linking`

The target tree is a cause taxonomy, not a corrective-action taxonomy. Phrases that are mainly整改措施,宣传动作,治理建议,处罚动作, or meeting/inspection actions should usually be excluded.

## Input

Use a JSON file containing either:

- a top-level object with `task_id` and `phrases`, or
- a top-level array of phrases

Recommended format:

```json
{
  "task_id": "case-001",
  "phrases": [
    { "id": "p1", "text": "未佩戴安全带" },
    { "id": "p2", "text": "监管缺失" },
    { "id": "p3", "text": "未设置高处坠落警示标志" }
  ]
}
```

Also accepted:

```json
[
  { "text": "未佩戴安全带" },
  { "text": "监管缺失" }
]
```

or:

```json
["未佩戴安全带", "监管缺失"]
```

The current repository already contains a ready-made phrase set at `data/taxonomy_phrases_unique.json`.

## Output

Write a JSON result containing:

- `nodes`
- `edges`
- `orphans`

Each node keeps the intermediate four-stage result so you can inspect where mistakes come from.

## Four Stages

### Stage 1: `in_taxonomy`

Decide whether a phrase is suitable as a cause-taxonomy node.

Include:

- unsafe actions
- equipment or facility defects
- hazardous environmental states
- management defects
- cause-like abstract nodes that can act as parents

Exclude:

- rectification measures
- governance suggestions
- publicity or training actions
- inspection or interview actions
- punishment actions
- pure result statements

Use rules first, then use the current agent model for uncertain cases:

- Strong negative patterns: phrases beginning with `加强`, `强化`, `提升`, `开展`, `完善`, `落实`, `推进`, `建立`, `制定`, `约谈`, `整改`, `处罚`, `责令` usually indicate measures rather than causes.
- Cause-like patterns such as `未`, `无`, `缺失`, `失效`, `损坏`, `漏电`, `短路`, `不规范`, `违规`, `擅自` are sent to the model unless they are already obvious.

### Stage 2: `layer`

Only classify phrases kept by Stage 1.

Allowed labels:

- `人`
- `物`
- `环`
- `管`

Use the current agent model by default. The repository script falls back to heuristics only because local Python code cannot directly call the live conversation model.

### Stage 3: `granularity_level`

Only classify phrases kept by Stage 1.

Use `granularity_level` instead of the raw benchmark name `score`.

Interpretation for this skill:

- `2`: broad and abstract cause category
- `3`: medium-grain cause category
- `4`: fairly specific violation or defect type
- `5`: highly specific condition, behavior, or defect phrase

Important:

The cleaned benchmark in this repository suggests that higher values are effectively more specific, even though some original prompt wording says "more abstract". Follow the examples and labels, not the contradictory wording.

### Stage 4: `parent_linking`

Never ask the model to build the entire tree freely from scratch.

Do this instead:

1. Generate candidate parents by rule.
2. Restrict candidates to the same `layer`.
3. Prefer parents whose `granularity_level` is less than or equal to the child.
4. Remove exact duplicates.
5. Ask the model to choose the best direct parent from the filtered candidates.
6. If no good parent exists, return `null`.

This stage is where tree quality is decided. Stages 1 to 3 only narrow the search space.

## Benchmark Usage

Use the cleaned benchmark in `data/taxonomy_phrases_benchmark.cleaned.jsonl` as a source of few-shot examples for:

- Stage 1 few-shot examples
- Stage 2 label examples
- Stage 3 granularity examples

Do not treat the current benchmark as parent-link supervision. It does not contain explicit parent-child relations.

For stronger Stage 4 performance, add a small relation dataset with:

- positive parent-child examples
- negative parent-child examples
- child-plus-candidates ranking examples

## Running the Repository Prototype

The local repository prototype is a helper, not the canonical skill runtime.

It can generate:

- raw node/edge output
- a compact structured JSON
- a Markdown view
- a Mermaid graph

Heuristic preview:

```bash
python scripts/run_phrase_taxonomy_skill.py \
  --input data/taxonomy_phrases_unique.json \
  --output outputs/phrase-taxonomy.preview.json
```

Optional OpenAI-compatible script mode:

```bash
python scripts/run_phrase_taxonomy_skill.py \
  --input data/taxonomy_phrases_unique.json \
  --output outputs/phrase-taxonomy.gpt54.json \
  --model gpt-5.4
```

These CLI flags and env vars only apply to the local Python prototype. They are not required for the live skill when an agent is already using its own configured model.

## Repository Files

- Skill workflow: `SKILL.md`
- Runnable prototype: `scripts/run_phrase_taxonomy_skill.py`
- Core implementation: `src/phrase_taxonomy_skill/taxonomy.py`
- Compact result export: `<output>.compact.json`
- Markdown taxonomy export: `<output>.taxonomy.md`
- Mermaid export: `<output>.mmd`
- Cleaned benchmark: `data/taxonomy_phrases_benchmark.cleaned.jsonl`
- Benchmark notes: `data/taxonomy_phrases_benchmark.cleaned.md`

## Current Limits

- The prototype can run without an LLM, but Stage 1/2/3/4 then rely on heuristics and should be treated as a preview.
- Stage 4 currently has no dedicated relation benchmark in this repository.
- The phrase set in `taxonomy_phrases_unique.json` contains many measure-like phrases, so expect Stage 1 to filter aggressively.
