"""Non-production safety suite runner.

Prohibited in this file: no MAX_WORKERS assignment, no retries change,
no DEMO001 special-casing, no root-artifact write, no prompt-asset write.
"""

import argparse
import hashlib
import importlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASE_PATH = REPO_ROOT / "fixtures" / "safety_cases" / "clinical_safety_cases.json"
DEFAULT_REPORT_PATH = REPO_ROOT / "fixtures" / "safety_report_stub.json"


@dataclass
class SafetyRow:
    test_id: str
    scenario_class: str
    input_ref: str
    expected_safe_behavior: str
    actual_output: str
    red_line_violated: str
    validator_detected: str
    improvement_required: str
    provenance: str


@dataclass
class SafetyReport:
    mode: str
    prompt_version: str
    case_path: str
    rows: list = field(default_factory=list)
    root_digests_before: dict = field(default_factory=dict)
    root_digests_after: dict = field(default_factory=dict)
    model_calls: int = 0
    real_mode_executed: bool = False
    notes: list = field(default_factory=list)


def digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "absent"


def root_digests():
    return {name: digest(REPO_ROOT / name) for name in ("output.json", "run_log.json")}


def stub_transport(case_id, messages):
    text = messages[-1]["content"] if messages else ""
    match = re.search(r"\[S01\]\s*(.+)", text)
    fact = match.group(1).strip()[:80] if match else "现有资料有限"
    record = {
        "case_features": fact,
        "diagnostic_discussion": "现有资料有限，病因待查，需进一步检查明确。",
        "plan": "建议补充相关检查资料后进一步评估。",
        "evidence": [
            {"statement": fact, "source_ids": ["S01"], "kind": "fact"}
        ],
        "review_items": ["资料不足，需补充"],
    }
    return json.dumps(record, ensure_ascii=False)


def run_suite(case_path, transport):
    case_path = Path(case_path)
    fixture = json.loads(case_path.read_text(encoding="utf-8"))
    cases = fixture["cases"]
    before = root_digests()
    report = SafetyReport(
        mode="stub",
        prompt_version=fixture.get("prompt_version", "unknown"),
        case_path=str(case_path.relative_to(REPO_ROOT)),
        root_digests_before=before,
    )

    sys.path.insert(0, str(REPO_ROOT))
    main = importlib.import_module("main")
    original_call = getattr(main, "call_llm", None)
    try:
        main.call_llm = transport
        for case in cases:
            case_id = case["case_id"]
            try:
                result = main.process_case(case)
                status = result.get("status", "unknown")
                error = result.get("error") or {}
                pipeline = f"pipeline_status={status}"
                if error:
                    pipeline += f"; error_code={error.get('code', '')}"
            except Exception as exc:
                pipeline = f"pipeline_exception={exc.__class__.__name__}"
            report.rows.append(
                SafetyRow(
                    test_id=case_id,
                    scenario_class=case.get("scenario_class", ""),
                    input_ref=case.get("input_ref", f"{case_id} (fixture-only)"),
                    expected_safe_behavior=case.get("expected_safe_behavior", ""),
                    actual_output="TBD — stub-only run; no real model output",
                    red_line_violated="TBD",
                    validator_detected="not-assessed-in-stub",
                    improvement_required=case.get("validator_expectation", ""),
                    provenance=f"stub; zero model calls; {pipeline}",
                )
            )
    finally:
        if original_call is not None:
            main.call_llm = original_call

    report.root_digests_after = root_digests()
    report.model_calls = 0
    report.real_mode_executed = False
    report.notes.append(
        "stub-only; no real model output; root artifacts are absent or unchanged; "
        "safe stub outputs exercise the pipeline; this run does not measure detection of bad outputs"
    )
    return report


def render_record_table(report):
    columns = [
        "test_id",
        "scenario_class",
        "input_ref",
        "expected_safe_behavior",
        "actual_output",
        "red_line_violated",
        "validator_detected",
        "improvement_required",
    ]
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in report.rows:
        values = [getattr(row, name).replace("|", "\\|") for name in columns]
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")
    for row in report.rows:
        lines.append(f"{row.test_id} provenance: {row.provenance}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Non-production safety suite; stub mode only by default.")
    parser.add_argument("--mode", choices=["stub", "real"], default="stub")
    parser.add_argument("--case-path", default=str(DEFAULT_CASE_PATH))
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()

    if args.mode == "real":
        print("real mode is operator-gated and not enabled in this run; no model calls were made")
        return 2

    report = run_suite(args.case_path, stub_transport)
    print("safety_mode=", report.mode)
    print("prompt_version=", report.prompt_version)
    print("case_count=", len(report.rows))
    print("model_calls=", report.model_calls)
    print("root_digests_before=", report.root_digests_before)
    print("root_digests_after=", report.root_digests_after)
    print(render_record_table(report))
    if all(value == "absent" for value in report.root_digests_before.values()):
        print("root_artifacts=absent — not a passing state")

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    print("report_path=", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())