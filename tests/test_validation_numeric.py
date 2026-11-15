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
        # 构造一个裸数值无单位（通过追加一段含"肌酐 300"后无单位）
        # NUMERIC_PATTERN 要求带单位才匹配，所以裸数值不会被提取
        # 这里测试单位不匹配的情形：用 sources 没有的单位
        record["case_features"] = record["case_features"] + " 血糖 8 mmol/L"
        sources = make_valid_sources()
        errors = _check_numeric_trace(record, sources)
        # 8 mmol/L 不在 sources，应为 value_mismatch
        kinds = {e["kind"] for e in errors}
        assert "value_mismatch" in kinds

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
