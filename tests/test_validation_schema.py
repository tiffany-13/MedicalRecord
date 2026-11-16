"""Schema 结构校验单元测试。"""

import copy
import pytest

from src.validation import _check_schema
from tests.conftest import make_valid_medical_record


class TestCheckSchema:
    def test_valid_record_passes(self):
        record = make_valid_medical_record()
        _check_schema(record)  # 不抛异常

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="必须为对象"):
            _check_schema([])

    def test_missing_field(self):
        record = make_valid_medical_record()
        del record["plan"]
        with pytest.raises(ValueError, match="缺少字段: plan"):
            _check_schema(record)

    def test_extra_field(self):
        record = make_valid_medical_record()
        record["extra"] = "x"
        with pytest.raises(ValueError, match="额外字段"):
            _check_schema(record)

    def test_field_not_string(self):
        record = make_valid_medical_record()
        record["case_features"] = 123
        with pytest.raises(ValueError, match="必须为字符串"):
            _check_schema(record)

    def test_field_empty(self):
        record = make_valid_medical_record()
        record["case_features"] = "   "
        with pytest.raises(ValueError, match="非空"):
            _check_schema(record)

    def test_evidence_not_list(self):
        record = make_valid_medical_record()
        record["evidence"] = "x"
        with pytest.raises(ValueError, match="evidence 必须为数组"):
            _check_schema(record)

    def test_evidence_item_not_dict(self):
        record = make_valid_medical_record()
        record["evidence"] = ["x"]
        with pytest.raises(ValueError, match="必须为对象"):
            _check_schema(record)

    def test_evidence_missing_kind(self):
        record = make_valid_medical_record()
        del record["evidence"][0]["kind"]
        with pytest.raises(ValueError, match="缺少字段: kind"):
            _check_schema(record)

    def test_evidence_kind_invalid(self):
        record = make_valid_medical_record()
        record["evidence"][0]["kind"] = "guess"
        with pytest.raises(ValueError, match="kind 取值非法"):
            _check_schema(record)

    def test_evidence_source_ids_empty(self):
        record = make_valid_medical_record()
        record["evidence"][0]["source_ids"] = []
        with pytest.raises(ValueError, match="source_ids 非空数组"):
            _check_schema(record)

    def test_evidence_extra_field(self):
        record = make_valid_medical_record()
        record["evidence"][0]["extra"] = "x"
        with pytest.raises(ValueError, match="额外字段"):
            _check_schema(record)

    def test_review_items_not_list(self):
        record = make_valid_medical_record()
        record["review_items"] = None
        with pytest.raises(ValueError, match="review_items 必须为数组"):
            _check_schema(record)

    def test_review_items_empty_passes(self):
        record = make_valid_medical_record()
        record["review_items"] = []
        _check_schema(record)  # 空数组允许

    def test_review_items_non_string(self):
        record = make_valid_medical_record()
        record["review_items"] = [123]
        with pytest.raises(ValueError, match="review_items.*必须为字符串"):
            _check_schema(record)

    def test_code_fence_in_case_features(self):
        record = make_valid_medical_record()
        record["case_features"] = "```json\nxxx\n```"
        with pytest.raises(ValueError, match="代码围栏"):
            _check_schema(record)

    def test_code_fence_in_evidence_statement(self):
        record = make_valid_medical_record()
        record["evidence"][0]["statement"] = "含 ``` 围栏"
        with pytest.raises(ValueError, match="代码围栏"):
            _check_schema(record)
