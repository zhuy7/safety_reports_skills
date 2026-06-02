---
name: safety-reports-skill
description: Extract accident summary and accident chain from a safety report using an LLM. Supports .pdf, .docx, .txt, .md files and pasted text. Includes a safety-relevance gate that rejects non-accident content before expensive LLM extraction.
---

# Safety Reports Skill (Pipeline A)

## Goal

Take a single safety accident report and produce:
1. A bilingual accident summary (Chinese + English)
2. A structured accident chain with typed items

## Input

A safety incident/accident report in any of these formats:

| Format | Source | How it's read |
|--------|--------|---------------|
| `.pdf` | `--file` | pypdf text layer extraction |
| `.docx` | `--file` | python-docx paragraph extraction |
| `.txt` / `.md` | `--file` | plain text (UTF-8) |
| pasted text | `--text` | raw string |

Unknown file extensions are read as plain text (UTF-8).

## Safety Relevance Gate

Before running expensive LLM extraction, the pipeline performs a quick relevance check:
- The first ~3000 characters of the document are sent to the LLM with the prompt: "这段文字是否属于安全事故报告？只回答 yes 或 no。"
- If the LLM does NOT answer "yes", the pipeline stops early and returns `{"rejected": true, "reason": "content_not_safety_report"}` without writing output files.

## Output

Two files written to the output directory (only if the input passes the relevance check):

- `<record_id>.result.json` — JSON with `summary.zh`, `summary.en`, and `accident_chain.items[]`
- `<record_id>.result.md` — Markdown with bilingual summary and accident-chain table

Each chain item has:
- `item_id`, `item_type` (actor/action/condition/violation/equipment/environment/outcome/measure)
- `role`, `summary_text_zh`, `summary_text_en`

## Execution

The pipeline:
1. Reads the document (format auto-detected from extension, or raw text from `--text`)
2. Runs the safety relevance check (quick LLM call on first ~3k chars)
3. Truncates to ~30k chars (head 65% + tail 35%) if needed
4. Calls LLM to extract chain items from the report
5. Calls LLM to generate bilingual summary
6. Normalizes and de-duplicates items
7. Writes JSON + Markdown output

Retries once if chain items or summary come back empty.

## Running

### CLI

```bash
# From a file (.pdf, .docx, .txt, .md):
safety-reports-skill --file example/dongguan-0001.pdf --output-dir outputs --model deepseek-chat --api-key $DEEPSEEK_API_KEY --base-url https://api.deepseek.com

# From pasted text:
safety-reports-skill --text "事故报告内容..." --output-dir outputs --model deepseek-chat
```

### Script

```bash
python scripts/run_safety_reports_skill.py --file example/dongguan-0001.pdf --output-dir outputs --model deepseek-chat
```

### Python

```python
from safety_reports_skill.pipeline import run_pipeline, LLMConfig
from pathlib import Path

config = LLMConfig(model="deepseek-chat", api_key="...", base_url="https://api.deepseek.com")

# From file:
result = run_pipeline(
    source_path=Path("example/dongguan-0001.pdf"),
    output_dir=Path("outputs"),
    llm_config=config,
)

# From pasted text:
result = run_pipeline(
    source_text="事故报告内容...",
    output_dir=Path("outputs"),
    llm_config=config,
)
```

## Environment Variables

- `ACCIDENT_NLP_LLM_MODEL` (or `OPENAI_MODEL`)
- `ACCIDENT_NLP_LLM_API_KEY` (or `OPENAI_API_KEY`)
- `ACCIDENT_NLP_LLM_BASE_URL` (or `OPENAI_BASE_URL`)

## Repository Files

- Skill workflow: `src/safety_reports_skill/SKILL.md`
- Core implementation: `src/safety_reports_skill/pipeline.py`
- Runnable script: `scripts/run_safety_reports_skill.py`
- Example input: `example/dongguan-0001.pdf`
- Example output: `example/dongguan-0001.result.json`, `example/dongguan-0001.result.md`
