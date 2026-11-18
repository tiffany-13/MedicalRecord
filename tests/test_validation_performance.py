"""性能与约束验证测试。"""

import copy
import time
import pytest

from src.validation import validate_record
from tests.conftest import make_valid_medical_record, make_valid_sources


class TestPerformance:
    def test_single_record_under_200ms(self):

        record = make_valid_medical_record()

        record["case_features"] = record["case_features"] + " 测试" * 100
        record["diagnostic_discussion"] = record["diagnostic_discussion"] + " 病因待查" * 100
        record["plan"] = record["plan"] + " 拟复查" * 100

        while len(record["evidence"]) < 5:
            record["evidence"].append({
                "statement": "补充证据项",
                "source_ids": ["S01"],
                "kind": "fact",
            })

        sources = make_valid_sources()
        for i in range(5, 11):
            sources.append({
                "source_id": f"S{i:02d}",
                "content": f"补充资料片段 {i}",
            })

        start = time.perf_counter()
        validate_record(record, sources)
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed < 200, f"单条校验耗时 {elapsed:.1f}ms 超过 200ms"


class TestReadOnly:
    def test_input_not_mutated_on_failure(self):
        record = make_valid_medical_record()
        del record["plan"]
        sources = make_valid_sources()
        record_before = copy.deepcopy(record)
        sources_before = copy.deepcopy(sources)
        with pytest.raises(ValueError):
            validate_record(record, sources)
        assert record == record_before
        assert sources == sources_before


class TestErrorMessageSpec:
    def test_error_messages_are_chinese(self):
        record = make_valid_medical_record()
        del record["plan"]
        sources = make_valid_sources()
        with pytest.raises(ValueError) as exc_info:
            validate_record(record, sources)
        msg = str(exc_info.value)
        assert len(msg) > 0

        assert any("\u4e00" <= ch <= "\u9fff" for ch in msg)
