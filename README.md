[English](README.md) | [中文](README.zh-CN.md)

# Safety Reports Skill

Two independent skills for safety incident analysis:

| Skill | Input | Output | Package |
|---|---|---|---|
| **Pipeline A** | Safety report (PDF/DOCX/TXT/MD/pasted) | Accident summary + chain items | `safety_reports_skill` |
| **Pipeline B** | Phrase set JSON | Cause taxonomy tree | `phrase_taxonomy_skill` |

## How It Works

```mermaid
flowchart TD
    subgraph A["Pipeline A: Report → Accident Chain"]
        A1["📄 Input
        PDF / DOCX / TXT / MD / Text"] --> A2["📖 Read Document
        auto-detect format"]
        A2 --> A3{"🛡️ Safety Relevance?
        quick LLM check"}
        A3 -- "no" --> A3R["⛔ Rejected
        {rejected: true}"]
        A3 -- "yes" --> A4["🔗 LLM Chain Extraction
        actor / action / condition
        violation / equipment
        environment / outcome / measure"]
        A4 --> A5["📝 LLM Summary
        bilingual zh + en"]
        A5 --> A6["✅ Normalize & Deduplicate"]
        A6 --> A7["📦 Output
        .result.json + .result.md"]
    end

    subgraph B["Pipeline B: Phrases → Taxonomy Tree"]
        B1["🏷️ Phrase Set
        .json / .jsonl"] --> B2["📋 Rule-Based Classify
        guess layer & granularity"]
        B2 --> B3["🧠 LLM Refinement
        resolve ambiguous phrases"]
        B3 --> B4["🌳 Build Hierarchy
        core nodes + parent edges"]
        B4 --> B5["📐 Compress to 6 Levels
        depth-limited taxonomy"]
        B5 --> B6["🔁 Resolve Cycles"]
        B6 --> B7["📊 Output
        taxonomy.json + .mmd + .md"]
    end

    A7 --> C["🎯 Safety Analysis Ready"]
    B7 --> C
```

## Taxonomy Structure

The taxonomy organizes accident causes into **4 layers**, building a tree from root causes down to specific surface-level phrases:

```mermaid
flowchart TD
    ROOT{"🏠 Root
    安全生产事故原因"} --> H{"👤 人 Human
    unsafe behaviors"}
    ROOT --> O{"🔧 物 Equipment
    facility defects"}
    ROOT --> M{"📋 管 Management
    system deficiencies"}
    ROOT --> E{"🌤️ 环 Environment
    site conditions"}

    H --> H1["未佩戴防护用品
    missing PPE"]
    H --> H2["违规操作
    rule violation"]
    H --> H3["无证上岗
    unlicensed operation"]

    O --> O1["设备失效
    equipment failure"]
    O --> O2["防护设施缺失
    missing guardrails"]
    O --> O3[" scaffolding 不规范
    improper scaffolding"]

    M --> M1["安全制度未落实
    unenforced policy"]
    M --> M2["监管缺失
    lack of supervision"]
    M --> M3["培训不足
    insufficient training"]

    E --> E1["照明不足
    poor lighting"]
    E --> E2["恶劣天气
    severe weather"]
    E --> E3["场地狭窄
    confined space"]
```

Each node carries metadata: `layer`, `granularity_level` (1=root → 6=specific), `is_root`, and `node_kind` (phrase / core / group).

## Install

```bash
pip install -e .
# Or with file format support (PDF, DOCX):
pip install -e ".[file]"
```

## CLI Commands

```bash
# Pipeline A: safety report → accident chain
safety-reports-skill --file example/dongguan-0001.pdf --output-dir outputs --model deepseek-chat

# Or with pasted text:
safety-reports-skill --text "accident report content..." --output-dir outputs --model deepseek-chat

# Pipeline B: phrases → taxonomy tree
accident-phrase-taxonomy-skill --input data/taxonomy_phrases_unique.json --output outputs/taxonomy.json
```

## Environment Variables

- `ACCIDENT_NLP_LLM_MODEL` (or `OPENAI_MODEL`)
- `ACCIDENT_NLP_LLM_API_KEY` (or `OPENAI_API_KEY`)
- `ACCIDENT_NLP_LLM_BASE_URL` (or `OPENAI_BASE_URL`)

## Project Structure

```
├── src/
│   ├── safety_reports_skill/    # Pipeline A
│   └── phrase_taxonomy_skill/   # Pipeline B
├── scripts/
│   ├── run_safety_reports_skill.py
│   ├── run_phrase_taxonomy_skill.py
│   ├── clean_taxonomy_benchmark.py
│   └── fix_benchmark_prompt.py
├── tests/
│   ├── test_safety_reports_skill.py
│   └── test_taxonomy_skill.py
├── data/
│   ├── taxonomy_phrases_unique.json
│   └── taxonomy_phrases_benchmark.cleaned.jsonl
├── example/
│   └── dongguan-0001.*
└── outputs/
```

## Tests

```bash
python -m pytest tests/ -v
```
