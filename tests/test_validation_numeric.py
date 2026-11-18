"""数值回溯校验单元测试。"""

import pytest

from src.validation import _check_numeric_trace
from tests.conftest import make_valid_medical_record, make_valid_sources


class TestCheckNumericTrace:
    def test_consistent_passes(self):
        record = make_valid_medical_record()
        sources = make_valid_sources()
        errors = _check_numeric_trace(record, sources)

        value_errors = [e for e in errors if e["kind"] == "value_mismatch"]
        assert value_errors == []

    def test_value_mismatch(self):
        record = make_valid_medical_record()

        record["case_features"] = record["case_features"].replace("82 g/L", "90 g/L")
        sources = make_valid_sources()
        errors = _check_numeric_trace(record, sources)
        kinds = {e["kind"] for e in errors}
        assert "value_mismatch" in kinds

    def test_unit_missing(self):
        record = make_valid_medical_record()



        record["case_features"] = record["case_features"] + " 血糖 8 mmol/L"
        sources = make_valid_sources()
        errors = _check_numeric_trace(record, sources)

        kinds = {e["kind"] for e in errors}
        assert "value_mismatch" in kinds

    def test_label_mismatch(self):
        record = make_valid_medical_record()

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

        assert errors == []
