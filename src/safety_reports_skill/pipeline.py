from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LLMConfig:
    model: str
    api_key: str
    base_url: str | None = None
    temperature: float = 0.1
    timeout: float = 120.0
    max_retries: int = 2


def _read_pdf(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "Reading .pdf requires pypdf. Install with: pip install 'safety-reports-skill[file]'"
        )
    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append(text)
    if not pages:
        raise RuntimeError("No extractable text found in PDF.")
    return "\n\n".join(pages)


def _read_document(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(file_path)
    if suffix == ".docx":
        try:
            import docx
        except ImportError:
            raise ImportError(
                "Reading .docx requires python-docx. Install with: pip install 'safety-reports-skill[file]'"
            )
        doc = docx.Document(str(file_path))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if not paragraphs:
            raise RuntimeError("No extractable text found in DOCX.")
        return "\n\n".join(paragraphs)
    # .txt, .md, and unknown extensions 鈫 read as plain text
    text = file_path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("No extractable text found in file.")
    return text


def _check_safety_relevance(text: str, llm_config: LLMConfig) -> bool:
    snippet = text[:3000]
    prompt = f"这段文字是否属于安全事故报告？只回答 yes 或 no。\n\n{snippet}"
    raw = _chat_completion(
        messages=[{"role": "user", "content": prompt}],
        llm_config=llm_config,
    )
    return raw.strip().lower().startswith("yes")


def _prepare_prompt_text(raw_text: str, max_chars: int = 30000) -> str:
    text = raw_text.strip()
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.65)]
    tail = text[-int(max_chars * 0.35) :]
    return f"{head}\n\n[TEXT TRUNCATED]\n\n{tail}"


def _clean_json_block(text: str) -> str:
    block = text.strip()
    if "```json" in block:
        block = block.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in block:
        block = block.split("```", 1)[1].split("```", 1)[0].strip()
    return block


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = _clean_json_block(text)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("LLM response does not contain a JSON object.")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON root must be an object.")
    return parsed


def _chat_completion(
    *,
    messages: list[dict[str, str]],
    llm_config: LLMConfig,
) -> str:
    import time

    import httpx

    base_url = (llm_config.base_url or "https://api.openai.com").rstrip("/")
    url = f"{base_url}/v1/chat/completions"
    payload = {
        "model": llm_config.model,
        "messages": messages,
        "temperature": llm_config.temperature,
    }
    headers = {
        "Authorization": f"Bearer {llm_config.api_key}",
        "Content-Type": "application/json",
    }

    last_exc = None
    for attempt in range(llm_config.max_retries + 1):
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=llm_config.timeout)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            last_exc = exc
            if attempt < llm_config.max_retries:
                time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"LLM request failed after {llm_config.max_retries + 1} attempts: {last_exc}")


def _invoke_llm_for_chain_items(*, source_text: str, llm_config: LLMConfig) -> dict[str, Any]:
    prompt = ("""
        你是安全事故调查和分析专家。请根据给定的事故报告上下文，提取事故链要素项。

你的任务：
从报告上下文中提取事故链相关要素，并整理为一组可追溯的结构化要素项。
每一个要素项都必须同时返回：
- item_type：必须是 actor、action、condition、violation、equipment、environment、outcome、measure 之一
- role：该要素在事故链中的具体角色，例如 worker、unsafe_action、hazardous_condition、management_defect、accident_result
- surface_text：尽量贴近原文、保留证据性的表述
- summary_text：对该要素做高度概括的短语级总结，用于归类和后续统计
- summary_text_en：对该要素概括短语的英文翻译，同样要求是短语
- support_unit_ids：该要素主要依据的上下文单元 ID 列表


输出格式要求：
1. 只返回一个 JSON object
2. JSON object 只能包含一个字段：
   - chain_items
3. chain_items 必须是数组
4. 每个数组项必须是 object，结构固定为：
   - item_type: string
   - role: string
   - surface_text: string
   - summary_text: string
   - summary_text_en: string
   - support_unit_ids: string[]
5. 如果上下文中没有明确事故链信息，返回空数组 []

item_type 定义：
- actor：事故参与主体或责任主体
- action：行为、操作、动作
- condition：现场状态、制度缺陷、技术缺陷、管理缺陷等条件
- violation：明确违规行为
- equipment：关键设备、设施、工具、构件
- environment：环境条件、场地条件
- outcome：事故结果、伤害结果
- measure：整改措施或防范措施

summary_text 规则：
1. 必须比 surface_text 更短、更抽象、更通用
2. 尽量写成短语，不要写成长句
3. 去掉公司名、人名、地名、日期、项目名、案号、楼栋号等具体信息
4. 不要写"某公司""某人""某地"这类占位词
5. 保留行为本质、风险本质、条件本质、结果本质或措施本质

summary_text_en 规则：
1. 尽量用短语表达
2. 保留语义核心，不要翻成完整句子

support_unit_ids 规则：
1. 必须从给定上下文里的 unit_id 中选择
2. 一条要素可以对应一个或多个 unit_id
3. 只返回最关键的支持单元，不要无关扩展
4. 不要编造不存在的 unit_id

禁止事项：
1. 不要编造原文没有明确提到的要素
2. 不要输出解释文字
3. 不要输出 JSON 之外的任何内容

示例：
surface_text: "龚某某未佩戴安全带进入井道作业"
summary_text: "未佩戴安全带"
summary_text_en: "missing safety belt"
item_type: "action"
role: "unsafe_action"

surface_text: "坠落至井道底坑后死亡"
summary_text: "高处坠落致死"
summary_text_en: "fatal fall from height"
item_type: "outcome"
role: "accident_result" """
        f"事故报告原文如下：\n{source_text}"
    )
    raw_text = _chat_completion(
        messages=[{"role": "user", "content": prompt}],
        llm_config=llm_config,
    )
    return _extract_json_object(raw_text)


def _invoke_llm_for_summary(
    *,
    source_text: str,
    chain_items: list[dict[str, Any]],
    llm_config: LLMConfig,
) -> dict[str, Any]:
    summary_prompt = (
        "你是安全事故调查和分析专家。请基于事故报告原文和事故链要素，生成双语事故总结。\n"
        "只返回一个 JSON object，格式固定为："
        '{"summary":{"zh":"...","en":"..."}}。\n'
        "summary.zh 使用中文，100~220字；summary.en 为对应英文摘要。\n"
        "不得输出 JSON 以外的内容。\n\n"
        f"事故链要素（JSON）:\n{json.dumps(chain_items, ensure_ascii=False)}\n\n"
        f"事故报告原文如下：\n{source_text}"
    )
    raw_text = _chat_completion(
        messages=[{"role": "user", "content": summary_prompt}],
        llm_config=llm_config,
    )
    return _extract_json_object(raw_text)


def _normalize_llm_result(
    *,
    chain_result: dict[str, Any],
    summary_result: dict[str, Any] | None,
) -> dict[str, Any]:
    summary = (summary_result or {}).get("summary") or {}
    chain = chain_result.get("accident_chain") or {}

    def _text(*candidates: Any) -> str:
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""

    if not isinstance(summary, dict):
        summary = {}

    items: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    if isinstance(chain_result, dict):
        raw_items = (
            chain_result.get("chain_items")
            or chain_result.get("items")
            or chain_result.get("accident_chain", {}).get("items")
            or chain_result.get("accident_chain_items")
            or []
        )
    elif isinstance(chain, dict):
        raw_items = chain.get("items") or chain.get("chain_items") or []
    elif isinstance(chain, list):
        raw_items = chain
    else:
        raw_items = []

    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue
        normalized = {
            "item_id": str(item.get("item_id") or item.get("id") or f"E{index}"),
            "item_type": str(item.get("item_type") or item.get("type") or "event"),
            "role": str(item.get("role") or item.get("chain_role") or "unknown"),
            "summary_text_zh": _text(
                item.get("summary_text_zh"),
                item.get("summary_text"),
                item.get("surface_text_zh"),
                item.get("surface_text"),
            ),
            "summary_text_en": _text(
                item.get("summary_text_en"),
                item.get("summary_en"),
            ),
        }
        key = (
            normalized["item_type"],
            normalized["role"],
            normalized["summary_text_zh"],
            normalized["summary_text_en"],
        )
        if key in seen:
            continue
        seen.add(key)
        if normalized["summary_text_zh"] or normalized["summary_text_en"]:
            items.append(normalized)

    return {
        "summary": {
            "zh": _text(
                summary.get("zh"),
                summary.get("summary_zh"),
                (summary_result or {}).get("summary_zh"),
                (summary_result or {}).get("zh_summary"),
            ),
            "en": _text(
                summary.get("en"),
                summary.get("summary_en"),
                (summary_result or {}).get("summary_en"),
                (summary_result or {}).get("en_summary"),
            ),
        },
        "accident_chain": {"items": items},
    }


def _build_markdown_report(
    *,
    record_id: str,
    title: str,
    summary_payload: dict[str, str],
    chain_payload: dict[str, Any],
) -> str:
    lines = [
        "# Accident Summary and Chain",
        "",
        f"- record_id: `{record_id}`",
        f"- title: `{title}`",
        "",
        "## 中文摘要",
        summary_payload.get("zh", ""),
        "",
        "## English Summary",
        summary_payload.get("en", ""),
        "",
        "## 事故链 / Accident Chain",
        "| item_id | item_type | role | summary_text_zh | summary_text_en |",
        "| --- | --- | --- | --- | --- |",
    ]

    for item in chain_payload.get("items", []):
        lines.append(
            "| {item_id} | {item_type} | {role} | {zh} | {en} |".format(
                item_id=item.get("item_id", ""),
                item_type=item.get("item_type", ""),
                role=item.get("role", ""),
                zh=str(item.get("summary_text_zh", "")).replace("|", "\\|"),
                en=str(item.get("summary_text_en", "")).replace("|", "\\|"),
            )
        )

    return "\n".join(lines).strip() + "\n"


def run_pipeline(
    *,
    source_path: Path | None = None,
    source_text: str | None = None,
    output_dir: Path,
    llm_config: LLMConfig,
    record_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    if (source_path is None) == (source_text is None):
        raise ValueError("Exactly one of source_path or source_text must be provided.")

    output_dir.mkdir(parents=True, exist_ok=True)

    if source_path is not None:
        raw_text = _read_document(source_path)
        resolved_record_id = record_id or source_path.stem
        resolved_title = title or source_path.stem
        suffix = source_path.suffix.lower()
        if suffix == ".pdf":
            parse_method = "pypdf_text_layer"
        elif suffix == ".docx":
            parse_method = "python-docx"
        else:
            parse_method = "plain_text"
    else:
        assert source_text is not None
        raw_text = source_text
        resolved_record_id = record_id or "pasted-text"
        resolved_title = title or "pasted-text"
        parse_method = "pasted_text"

    if not _check_safety_relevance(raw_text, llm_config):
        return {
            "record_id": resolved_record_id,
            "rejected": True,
            "reason": "content_not_safety_report",
        }

    prompt_text = _prepare_prompt_text(raw_text)

    chain_raw = _invoke_llm_for_chain_items(source_text=prompt_text, llm_config=llm_config)
    normalized = _normalize_llm_result(chain_result=chain_raw, summary_result=None)

    # Retry once if chain extraction returned empty items.
    if not normalized["accident_chain"]["items"]:
        chain_raw = _invoke_llm_for_chain_items(source_text=prompt_text, llm_config=llm_config)
        normalized = _normalize_llm_result(chain_result=chain_raw, summary_result=None)

    summary_raw = _invoke_llm_for_summary(
        source_text=prompt_text,
        chain_items=normalized["accident_chain"]["items"],
        llm_config=llm_config,
    )
    normalized = _normalize_llm_result(chain_result=chain_raw, summary_result=summary_raw)

    # Retry once if summary generation returned empty strings.
    if not normalized["summary"]["zh"] and not normalized["summary"]["en"]:
        summary_raw = _invoke_llm_for_summary(
            source_text=prompt_text,
            chain_items=normalized["accident_chain"]["items"],
            llm_config=llm_config,
        )
        normalized = _normalize_llm_result(chain_result=chain_raw, summary_result=summary_raw)

    json_output_path = output_dir / f"{resolved_record_id}.result.json"
    markdown_output_path = output_dir / f"{resolved_record_id}.result.md"

    final_payload = {
        "record_id": resolved_record_id,
        "title": resolved_title,
        "summary": normalized["summary"],
        "accident_chain": normalized["accident_chain"],
        "metadata": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "parse_method": parse_method,
            "llm": {
                "model": llm_config.model,
                "base_url": llm_config.base_url,
            },
        },
    }

    json_output_path.write_text(
        json.dumps(final_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    markdown_report = _build_markdown_report(
        record_id=resolved_record_id,
        title=resolved_title,
        summary_payload=normalized["summary"],
        chain_payload=normalized["accident_chain"],
    )
    markdown_output_path.write_text(markdown_report, encoding="utf-8")

    return {
        "record_id": resolved_record_id,
        "json_output": str(json_output_path),
        "markdown_output": str(markdown_output_path),
    }


def _resolve_llm_config(args: argparse.Namespace) -> LLMConfig:
    model = args.model or os.getenv("ACCIDENT_NLP_LLM_MODEL") or os.getenv("OPENAI_MODEL")
    api_key = args.api_key or os.getenv("ACCIDENT_NLP_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = args.base_url or os.getenv("ACCIDENT_NLP_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")

    if not model:
        raise ValueError("Missing LLM model. Use --model or set ACCIDENT_NLP_LLM_MODEL.")
    if not api_key:
        raise ValueError("Missing LLM API key. Use --api-key or set ACCIDENT_NLP_LLM_API_KEY.")

    return LLMConfig(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=args.temperature,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract accident summary and accident chain from a safety report.",
    )
    parser.add_argument("--file", help="Path to a safety report file (.pdf, .docx, .txt, .md).")
    parser.add_argument("--text", help="Raw safety report text pasted directly.")
    parser.add_argument("--output-dir", default="outputs", help="Output directory for .json/.md results.")
    parser.add_argument("--record-id", help="Optional output record_id override.")
    parser.add_argument("--title", help="Optional report title override.")
    parser.add_argument("--model", help="LLM model name.")
    parser.add_argument("--api-key", help="LLM API key.")
    parser.add_argument("--base-url", help="LLM base URL for OpenAI-compatible providers.")
    parser.add_argument("--temperature", type=float, default=0.1, help="LLM temperature.")
    parser.add_argument("--timeout", type=float, default=120.0, help="LLM timeout in seconds.")
    parser.add_argument("--max-retries", type=int, default=2, help="LLM max retries.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.file and not args.text:
        parser.error("One of --file or --text is required.")
    if args.file and args.text:
        parser.error("Only one of --file or --text can be provided.")

    llm_config = _resolve_llm_config(args)

    source_path = Path(args.file) if args.file else None
    source_text = args.text or None

    result = run_pipeline(
        source_path=source_path,
        source_text=source_text,
        output_dir=Path(args.output_dir),
        llm_config=llm_config,
        record_id=args.record_id,
        title=args.title,
    )

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
