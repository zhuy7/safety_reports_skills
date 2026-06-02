[English](README.md) | [中文](README.zh-CN.md)

# 安全事故报告分析技能

两个独立的安全事故分析技能：

| 技能 | 输入 | 输出 | 包名 |
|---|---|---|---|
| **流水线 A** | 安全事故报告（PDF/DOCX/TXT/MD/粘贴文本） | 事故摘要 + 事故链要素 | `safety_reports_skill` |
| **流水线 B** | 短语集 JSON | 原因分类树 | `phrase_taxonomy_skill` |

## 工作流程

```mermaid
flowchart TD
    subgraph A["流水线 A：事故报告 → 事故链"]
        A1["📄 输入
        PDF / DOCX / TXT / MD / 文本"] --> A2["📖 读取文档
        自动识别格式"]
        A2 --> A3{"🛡️ 安全相关性？
        LLM 快速判断"}
        A3 -- "否" --> A3R["⛔ 拒绝
        {rejected: true}"]
        A3 -- "是" --> A4["🔗 LLM 事故链提取
        actor / action / condition
        violation / equipment
        environment / outcome / measure"]
        A4 --> A5["📝 LLM 双语摘要
        中文 + 英文"]
        A5 --> A6["✅ 标准化 & 去重"]
        A6 --> A7["📦 输出
        .result.json + .result.md"]
    end

    subgraph B["流水线 B：短语集 → 分类树"]
        B1["🏷️ 短语集
        .json / .jsonl"] --> B2["📋 规则分类
        推测层级 & 粒度"]
        B2 --> B3["🧠 LLM 精炼
        处理歧义短语"]
        B3 --> B4["🌳 构建层级
        核心节点 + 父子关系"]
        B4 --> B5["📐 压缩至6层
        深度限制分类树"]
        B5 --> B6["🔁 消解循环引用"]
        B6 --> B7["📊 输出
        taxonomy.json + .mmd + .md"]
    end

    A7 --> C["🎯 安全分析结果"]
    B7 --> C
```

## 分类树结构

分类树将事故原因组织为 **4 个层面**，从根原因向下展开至具体表层短语：

```mermaid
flowchart TD
    ROOT{"🏠 根节点
    安全生产事故原因"} --> H{"👤 人
    不安全行为"}
    ROOT --> O{"🔧 物
    设备设施缺陷"}
    ROOT --> M{"📋 管
    管理制度缺失"}
    ROOT --> E{"🌤️ 环
    场地环境条件"}

    H --> H1["未佩戴防护用品"]
    H --> H2["违规操作"]
    H --> H3["无证上岗"]

    O --> O1["设备失效"]
    O --> O2["防护设施缺失"]
    O --> O3["脚手架搭设不规范"]

    M --> M1["安全制度未落实"]
    M --> M2["现场监管缺失"]
    M --> M3["安全培训不足"]

    E --> E1["照明不足"]
    E --> E2["恶劣天气"]
    E --> E3["场地狭窄"]
```

每个节点包含元数据：`layer`（所属层面）、`granularity_level`（1=根节点 → 6=最具体）、`is_root`、`node_kind`（phrase / core / group）。

## 安装

```bash
pip install -e .
# 如需文件格式支持（PDF、DOCX）：
pip install -e ".[file]"
```

## CLI 命令

```bash
# 流水线 A：安全事故报告 → 事故链提取
safety-reports-skill --file example/dongguan-0001.pdf --output-dir outputs --model deepseek-chat

# 或直接粘贴文本：
safety-reports-skill --text "事故报告内容..." --output-dir outputs --model deepseek-chat

# 流水线 B：短语集 → 分类树
accident-phrase-taxonomy-skill --input data/taxonomy_phrases_unique.json --output outputs/taxonomy.json
```

## 环境变量

- `ACCIDENT_NLP_LLM_MODEL`（或 `OPENAI_MODEL`）
- `ACCIDENT_NLP_LLM_API_KEY`（或 `OPENAI_API_KEY`）
- `ACCIDENT_NLP_LLM_BASE_URL`（或 `OPENAI_BASE_URL`）

## 项目结构

```
├── src/
│   ├── safety_reports_skill/    # 流水线 A
│   └── phrase_taxonomy_skill/   # 流水线 B
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

## 测试

```bash
python -m pytest tests/ -v
```
