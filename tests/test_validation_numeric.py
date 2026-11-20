"""数值回溯校验单元测试。"""

import pytest

from src.validation import _check_numeric_trace
from tests.conftest import make_valid_medical_record, make_valid_sources


class TestCheckNumericTrace:
    def test_consistent_passes(self):
        record = make_valid_medical_record()
        sources = make_valid_sources()
        errors = _check_numeric_trace(record, sources)
        # 数值一致，不应有 value_mismatch
        value_errors = [e for e in errors if e["kind"] == "value_mismatch"]
        assert value_errors == []

    def test_value_mismatch(self):
        record = make_valid_medical_record()
        # 把 82 改成 90（抄错）
        record["case_features"] = record["case_features"].replace("82 g/L", "90 g/L")
        sources = make_valid_sources()
        errors = _check_numeric_trace(record, sources)
        kinds = {e["kind"] for e in errors}
        assert "value_mismatch" in kinds

    def test_unit_missing(self):
        record = make_valid_medical_record()
        record["case_features"] = record["case_features"].replace("82 g/L", "82")
        errors = _check_numeric_trace(record, make_valid_sources())
        assert any(error["kind"] == "unit_missing" and "血红蛋白" in error["detail"] for error in errors)

    @pytest.mark.parametrize("value", [
        "血红蛋白 185 μmol/L",
        "血红蛋白 82 mg/dL",
        "血压 120/90 mmHg",
    ])
    def test_measurement_must_match_its_own_metric_and_full_value(self, value):
        record = make_valid_medical_record()
        record["case_features"] = value
        sources = make_valid_sources() + [{"source_id": "S05", "content": "血压 120/80 mmHg"}]
        errors = _check_numeric_trace(record, sources)
        assert any(error["kind"] == "value_mismatch" for error in errors)

    def test_labels_follow_their_own_measurements(self):
        record = make_valid_medical_record()
        record["case_features"] = "血红蛋白 82 g/L，标高；肌酐 185 μmol/L，标低。"
        errors = _check_numeric_trace(record, make_valid_sources())
        assert [error["kind"] for error in errors] == ["label_mismatch", "label_mismatch"]

    @pytest.mark.parametrize(("statement", "source_ids"), [
        ("血红蛋白 92 g/L", ["S03"]),
        ("血红蛋白 82 g/L", ["S02"]),
        ("血红蛋白 82", ["S02"]),
    ])
    def test_evidence_numbers_are_checked_against_cited_sources(self, statement, source_ids):
        record = make_valid_medical_record()
        record["evidence"][1].update(statement=statement, source_ids=source_ids)
        errors = _check_numeric_trace(record, make_valid_sources())
        assert len(errors) == 1
        assert "evidence[1].statement" in errors[0]["detail"]

    def test_equivalent_writing_and_hypothetical_threshold(self):
        record = make_valid_medical_record()
        record["case_features"] = "Hb ８２.０ g/L，偏低；肌酐185 umol/L。"
        record["plan"] = "若血红蛋白低于 70 g/L，建议进一步评估。"
        assert _check_numeric_trace(record, make_valid_sources()) == []

    def test_label_mismatch(self):
        record = make_valid_medical_record()
        # sources 含"标低""标高"，生成文本出现 sources 没有的"阳性"
        record["case_features"] = record["case_features"] + " 实验室阳性"
        sources = make_valid_sources()
        errors = _check_numeric_trace(record, sources)
        kinds = {e["kind"] for e in errors}
        assert "label_mismatch" in kinds

    def test_no_numbers_passes(self):
        record = make_valid_medical_record()
        record["case_features"] = "患者乏力，无具体数值"
        record["diagnostic_discussion"] = "病因待查"
        record["plan"] = "建议进一步检查"
        sources = make_valid_sources()
        errors = _check_numeric_trace(record, sources)
        # 生成文本无数值，不应报错
        assert errors == []
