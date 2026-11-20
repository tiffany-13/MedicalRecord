"""辅助工具单元测试：_truncate_snippet / _log_debug / _extract_numbers。"""

from src.validation import _truncate_snippet, _log_debug, _extract_numbers, MAX_SNIPPET_LEN


class TestTruncateSnippet:
    def test_normal_length(self):
        assert _truncate_snippet("短文本") == "短文本"

    def test_exact_boundary(self):
        text = "a" * MAX_SNIPPET_LEN
        assert _truncate_snippet(text) == text

    def test_over_length_truncated(self):
        text = "a" * (MAX_SNIPPET_LEN + 10)
        result = _truncate_snippet(text)
        assert result.endswith("…")
        assert len(result) == MAX_SNIPPET_LEN + 1

    def test_none_input(self):
        assert _truncate_snippet(None) == ""

    def test_non_string_input(self):
        assert _truncate_snippet(123) == ""


class TestLogDebug:
    def test_log_format(self, capsys):
        _log_debug("schema", "结构校验通过")
        captured = capsys.readouterr()
        assert "[validation] schema: 结构校验通过" in captured.out


class TestExtractNumbers:
    def test_with_unit(self):
        result = _extract_numbers("血红蛋白 82 g/L")
        assert len(result) == 1
        assert result[0]["value"] == "82"
        assert result[0]["unit"] == "g/L"

    def test_multiple_numbers(self):
        result = _extract_numbers("Hb 82 g/L，肌酐 185 μmol/L")
        assert len(result) == 2
        assert result[0]["value"] == "82"
        assert result[1]["value"] == "185"

    def test_no_unit_not_matched(self):

        result = _extract_numbers("肌酐 185 之后")

        assert len(result) == 0

    def test_empty_text(self):
        assert _extract_numbers("") == []

    def test_none_text(self):
        assert _extract_numbers(None) == []

    def test_no_numbers(self):
        assert _extract_numbers("无数值文本") == []

    def test_percentage(self):
        result = _extract_numbers("占比 95%")
        assert len(result) == 1
        assert result[0]["unit"] == "%"
