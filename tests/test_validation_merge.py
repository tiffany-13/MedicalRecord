"""合并后针对已复现漏检、误拦和日志交接的回归测试。"""

import json
from copy import deepcopy

import pytest

import main
from src.validation import validate_record
from tests.conftest import make_valid_medical_record, make_valid_sources


@pytest.mark.parametrize("plan", [
    "暂不启动铁剂，需进一步评估。",
    "不调整促红素，需补充检查。",
    "观察尿量，若低于500 mL，应及时报告。",
    "核实是否已完成尿检，尚未给予治疗。",
])
def test_qualified_plan_passes(plan):
    record = make_valid_medical_record()
    record["plan"] = plan
    validate_record(record, make_valid_sources())


@pytest.mark.parametrize("text", [
    "血红蛋白82。",
    "血红蛋白185 μmol/L。",
    "血糖2 mmol/L。",
    "血红蛋白82 g/L，标高；肌酐185 μmol/L，标低。",
])
def test_unsupported_measurement_fails(text):
    record = make_valid_medical_record()
    record["case_features"] = text
    with pytest.raises(ValueError, match="VAL-301"):
        validate_record(record, make_valid_sources())


def test_documented_normal_does_not_allow_another_missing_item_to_be_normal():
    sources = make_valid_sources() + [{"source_id": "S05", "content": "体温正常。"}]
    record = make_valid_medical_record()
    record["case_features"] = "乏力，体温正常，血压正常。"
    with pytest.raises(ValueError, match="VAL-302"):
        validate_record(record, sources)


def test_different_metrics_with_same_number_are_not_a_conflict():
    sources = make_valid_sources() + [{"source_id": "S05", "content": "心率82次/分。"}]
    findings = []
    validate_record(make_valid_medical_record(), sources, findings=findings)
    assert not any(item["rule_id"] == "VAL-603" for item in findings)


def test_documented_ckd_can_be_fact_without_inference():
    record = make_valid_medical_record()
    record["evidence"] = [
        {"statement": "既往已明确CKD", "source_ids": ["S05"], "kind": "fact"},
    ]
    sources = make_valid_sources() + [{"source_id": "S05", "content": "既往已明确CKD。"}]
    findings = []
    validate_record(record, sources, findings=findings)
    assert not any(item["rule_id"] == "VAL-602" for item in findings)


def test_new_derived_term_needs_corresponding_evidence_even_with_other_inference():
    record = make_valid_medical_record()
    record["diagnostic_discussion"] += "需进一步评估eGFR。"
    findings = []
    validate_record(record, make_valid_sources(), findings=findings)
    assert any(item["rule_id"] == "VAL-602" and item["field"] == "diagnostic_discussion" for item in findings)


def test_multiple_results_are_advisory_with_field():
    record = make_valid_medical_record()
    sources = make_valid_sources() + [{"source_id": "S05", "content": "次日血红蛋白90 g/L。"}]
    findings = []
    validate_record(record, sources, findings=findings)
    assert any(item["rule_id"] == "VAL-603" and item["field"] == "review_items" for item in findings)


def test_gap_statement_does_not_hide_empty_evidence():
    record = make_valid_medical_record()
    record["evidence"] = []
    record["review_items"] = ["资料不足"]
    with pytest.raises(ValueError, match="VAL-201"):
        validate_record(record, make_valid_sources())


def test_invalid_evidence_type_is_a_validation_error():
    record = make_valid_medical_record()
    record["evidence"] = 123
    with pytest.raises(ValueError, match="evidence"):
        validate_record(record, make_valid_sources())


def test_main_mixed_batch_and_case_specific_advisories(monkeypatch, tmp_path):
    cases = [
        {"case_id": case_id, "record_cutoff": "T0", "sources": make_valid_sources()}
        for case_id in ("VALID", "INVALID", "ADVISORY")
    ]
    cases[2]["sources"].append({"source_id": "S05", "content": "次日血红蛋白90 g/L。"})
    replies = {case["case_id"]: make_valid_medical_record() for case in cases}
    replies["INVALID"]["evidence"][1]["statement"] = "血红蛋白92 g/L"
    original_replies = deepcopy(replies)

    def transport(case_id, messages):
        main.RUN_LOGS.append({"case_id": case_id, "status": "success"})
        return json.dumps(replies[case_id], ensure_ascii=False)

    monkeypatch.setattr(main, "call_llm", transport)
    monkeypatch.setattr(main, "get_config", lambda: ("mock-model", "http://localhost"))
    monkeypatch.setattr(main, "MAX_WORKERS", 3)
    for name, filename in {
        "INPUT_FILE": "input.json", "OUTPUT_FILE": "output.json",
        "TEMP_FILE": "output_tmp.json", "LOG_FILE": "run_log.json",
        "LOG_TEMP_FILE": "run_log_tmp.json",
    }.items():
        monkeypatch.setattr(main, name, tmp_path / filename)
    main.INPUT_FILE.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit) as exit_info:
        main.main()
    assert exit_info.value.code == 0
    results = json.loads(main.OUTPUT_FILE.read_text(encoding="utf-8"))
    assert [row["case_id"] for row in results] == ["VALID", "INVALID", "ADVISORY"]
    assert [row["status"] for row in results] == ["success", "failed", "success"]
    assert results[1]["error"]["code"] == "VALIDATION_ERROR"
    logs = json.loads(main.LOG_FILE.read_text(encoding="utf-8"))
    by_case = {row["case_id"]: row for row in logs}
    assert not any(item["rule_id"] == "VAL-603" for item in by_case["VALID"]["validation_findings"])
    advice = by_case["ADVISORY"]["validation_findings"]
    assert any(item["rule_id"] == "VAL-603" and item["case_id"] == "ADVISORY" for item in advice)
    assert all("field" in item and item["case_id"] == "ADVISORY" for item in advice)
    assert replies == original_replies
