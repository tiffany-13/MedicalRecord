"""validate_record 端到端测试。"""

import copy
import pytest

from src.validation import validate_record
from tests.conftest import make_valid_medical_record, make_valid_sources


class TestValidateRecordE2E:
    def test_valid_record_passes(self):
        record = make_valid_medical_record()
        sources = make_valid_sources()
        validate_record(record, sources)

    def test_missing_field_raises(self):
        record = make_valid_medical_record()
        del record["plan"]
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="缺少字段"):
            validate_record(record, sources)

    def test_source_not_exist_raises(self):
        record = make_valid_medical_record()
        record["evidence"][0]["source_ids"] = ["S99"]
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="来源不存在"):
            validate_record(record, sources)

    def test_plan_done_raises(self):
        record = make_valid_medical_record()
        record["plan"] = "已予补铁治疗。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="红线3"):
            validate_record(record, sources)

    def test_future_info_raises(self):
        record = make_valid_medical_record()
        record["diagnostic_discussion"] = "出院时确诊为肾性贫血。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="红线4"):
            validate_record(record, sources)

    def test_read_only_does_not_mutate(self):
        record = make_valid_medical_record()
        sources = make_valid_sources()
        record_before = copy.deepcopy(record)
        sources_before = copy.deepcopy(sources)
        validate_record(record, sources)
        assert record == record_before
        assert sources == sources_before

    def test_deterministic(self):
        record = make_valid_medical_record()
        sources = make_valid_sources()

        validate_record(record, sources)
        validate_record(record, sources)
