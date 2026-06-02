from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import tempfile

from safety_reports_skill.pipeline import (
    _build_markdown_report,
    _clean_json_block,
    _prepare_prompt_text,
    _read_document,
)


class SafetyReportsSkillTests(unittest.TestCase):
    def test_clean_json_block_strips_fence(self) -> None:
        result = _clean_json_block('```json\n{"key": "value"}\n```')
        self.assertEqual(result, '{"key": "value"}')

    def test_clean_json_block_strips_bare_fence(self) -> None:
        result = _clean_json_block('```\n{"key": "value"}\n```')
        self.assertEqual(result, '{"key": "value"}')

    def test_clean_json_block_preserves_plain_json(self) -> None:
        result = _clean_json_block('{"key": "value"}')
        self.assertEqual(result, '{"key": "value"}')

    def test_prepare_prompt_text_returns_short_text_as_is(self) -> None:
        short_text = "This is a short accident report."
        result = _prepare_prompt_text(short_text, max_chars=30000)
        self.assertEqual(result, short_text)

    def test_prepare_prompt_text_truncates_long_text(self) -> None:
        long_text = "A" * 40000
        result = _prepare_prompt_text(long_text, max_chars=30000)
        self.assertIn("[TEXT TRUNCATED]", result)
        self.assertLess(len(result), 40000)

    def test_build_markdown_report_includes_summary_and_chain(self) -> None:
        report = _build_markdown_report(
            record_id="test-001",
            title="Test Report",
            summary_payload={"zh": "测试摘要", "en": "Test summary"},
            chain_payload={
                "items": [
                    {
                        "item_id": "E1",
                        "item_type": "action",
                        "role": "unsafe_action",
                        "summary_text_zh": "未佩戴安全带",
                        "summary_text_en": "missing safety belt",
                    }
                ]
            },
        )
        self.assertIn("test-001", report)
        self.assertIn("测试摘要", report)
        self.assertIn("Test summary", report)
        self.assertIn("未佩戴安全带", report)
        self.assertIn("missing safety belt", report)

    def test_read_document_reads_txt(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("这是安全事故报告内容。\n第二行文字。")
            tmp_path = Path(f.name)
        try:
            result = _read_document(tmp_path)
            self.assertEqual(result, "这是安全事故报告内容。\n第二行文字。")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_build_markdown_report_escapes_pipe_in_text(self) -> None:
        report = _build_markdown_report(
            record_id="test-002",
            title="Pipe | Test",
            summary_payload={"zh": "摘要", "en": "Summary"},
            chain_payload={
                "items": [
                    {
                        "item_id": "E1",
                        "item_type": "action",
                        "role": "unsafe_action",
                        "summary_text_zh": "text | with pipe",
                        "summary_text_en": "text | with pipe",
                    }
                ]
            },
        )
        self.assertIn(r"text \| with pipe", report)


if __name__ == "__main__":
    unittest.main()
