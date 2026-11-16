"""source_ids 溯源校验单元测试。"""

import pytest

from src.validation import _check_source_trace
from tests.conftest import make_valid_medical_record, make_valid_sources


class TestCheckSourceTrace:
    def test_all_exist_passes(self):
        record = make_valid_medical_record()
        sources = make_valid_sources()
        _check_source_trace(record, sources)

    def test_source_not_exist(self):
        record = make_valid_medical_record()
        record["evidence"][0]["source_ids"] = ["S99"]
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="来源不存在: S99"):
            _check_source_trace(record, sources)

    def test_evidence_zero_fails(self):
        record = make_valid_medical_record()
        record["evidence"] = []
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="evidence 至少 1 条"):
            _check_source_trace(record, sources)

    def test_evidence_two_passes(self):
        record = make_valid_medical_record()
        record["evidence"] = record["evidence"][:2]
        sources = make_valid_sources()
        _check_source_trace(record, sources)

    def test_evidence_five_passes(self):
        record = make_valid_medical_record()
        # 补到 5 条
        while len(record["evidence"]) < 5:
            record["evidence"].append({
                "statement": "补充证据",
                "source_ids": ["S01"],
                "kind": "fact",
            })
        sources = make_valid_sources()
        _check_source_trace(record, sources)

    def test_evidence_six_passes_with_warning(self, capsys):
        record = make_valid_medical_record()
        while len(record["evidence"]) < 6:
            record["evidence"].append({
                "statement": "补充证据",
                "source_ids": ["S01"],
                "kind": "fact",
            })
        sources = make_valid_sources()
        _check_source_trace(record, sources)  # 不抛异常
        captured = capsys.readouterr()
        assert "条数偏多" in captured.out
