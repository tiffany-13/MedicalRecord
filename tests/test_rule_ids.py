"""验证真实输入错误的规则编号及计数，防止新增规则复用已有编号。"""

from copy import deepcopy

import pytest

from src.validation import RULE_HIT_COUNTS, RULE_REGISTRY, validate_record
from tests.conftest import make_valid_medical_record, make_valid_sources


@pytest.mark.parametrize(("mutation", "expected"), [
    ("not_object", "VAL-101"),
    ("extra_field", "VAL-101"),
    ("empty_body", "VAL-102"),
    ("invalid_evidence", "VAL-103"),
    ("invalid_kind", "VAL-104"),
    ("missing_review", "VAL-105"),
    ("invalid_review", "VAL-105"),
    ("fence", "VAL-106"),
    ("empty_evidence", "VAL-201"),
    ("unknown_source", "VAL-202"),
])
def test_actual_error_has_registered_id_and_counts_once(mutation, expected):
    record = make_valid_medical_record()
    if mutation == "not_object":
        record = None
    elif mutation == "extra_field":
        record["extra"] = "text"
    elif mutation == "empty_body":
        record["plan"] = " "
    elif mutation == "invalid_evidence":
        record["evidence"] = 1
    elif mutation == "invalid_kind":
        record["evidence"][0]["kind"] = "other"
    elif mutation == "missing_review":
        del record["review_items"]
    elif mutation == "invalid_review":
        record["review_items"] = "text"
    elif mutation == "fence":
        record["case_features"] += "```"
    elif mutation == "empty_evidence":
        record["evidence"] = []
    elif mutation == "unknown_source":
        record["evidence"][0]["source_ids"] = ["S99"]

    before = RULE_HIT_COUNTS[expected]
    original = deepcopy(record)
    with pytest.raises(ValueError) as error:
        validate_record(record, make_valid_sources())
    assert str(error.value).startswith(expected + " [")
    assert RULE_REGISTRY[expected]["title"] in str(error.value)
    assert RULE_HIT_COUNTS[expected] == before + 1
    assert record == original


def test_advisory_ids_have_separate_group_and_log_field():
    record = make_valid_medical_record()
    record["diagnostic_discussion"] += "需进一步评估eGFR。"
    findings = []
    validate_record(record, make_valid_sources(), findings=findings)
    assert findings
    for finding in findings:
        assert finding["rule_id"].startswith("VAL-6")
        assert RULE_REGISTRY[finding["rule_id"]]["enforcement"] == "advisory"
        assert "vr_id" not in finding
