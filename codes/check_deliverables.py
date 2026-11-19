import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKS = []

V12_SHA = "355c2daf233ec2188524ae9025501efe719ad7a17bc8579f650692c4b4fe89ea"
V12_CHARS = 3204
V12_BYTES = 7980
INPUT_SHA = "aac6389a9e781ea498b84da1c9a50062b5f5d7ea2f433acc7c06c3d3ad23a13c"


def add(name, ok, detail="", blocking=True):
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail, "blocking": blocking})


def read(path):
    path = ROOT / path
    return path.read_text(encoding="utf-8") if path.exists() else ""


def has_all(text, values):
    return [v for v in values if v not in text]


def runs(text, size=10):
    return {text[i:i + size] for i in range(0, max(0, len(text) - size + 1))}


def collect_strings(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from collect_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from collect_strings(item)
    elif isinstance(value, str):
        yield value


def check_prompt():
    path = ROOT / "prompts/candidates/system_v1_2_candidate.txt"
    raw = path.read_bytes() if path.exists() else b""
    text = raw.decode("utf-8") if raw else ""
    add("prompt_v12_exists", bool(text), "prompts/candidates/system_v1_2_candidate.txt")
    add("prompt_v12_char_count", len(text.rstrip("\n")) == V12_CHARS, str(len(text.rstrip("\n"))))
    add("prompt_v12_byte_count", len(raw) == V12_BYTES, str(len(raw)))
    add("prompt_v12_sha256", hashlib.sha256(raw).hexdigest() == V12_SHA, hashlib.sha256(raw).hexdigest()[:16])
    crlf_count = raw.count(b"\r\n")
    add("prompt_v12_lf_only", b"\r\n" not in raw, f"crlf={crlf_count}")
    add("prompt_v12_le_4000", 0 < len(text.rstrip("\n")) <= 4000, str(len(text.rstrip("\n"))))

    markers = ["# 角色", "# 资料边界", "# 输出内容", "# 事实与推断", "# 输出格式", "# 五条医学红线"]
    add("six_blocks", all(text.count(m) == 1 for m in markers))
    add("five_red_lines", all(text.count(c) == 1 for c in "①②③④⑤"))
    add("five_fields", all(f in text for f in ["case_features", "diagnostic_discussion", "plan", "evidence", "review_items"]))
    add("prompt_static", not any(x in text for x in ["{case_id}", "{record_cutoff}", "{sources}"]))
    add("v12_five_classes", all(x in text for x in ["未提供", "未查", "明确阴性或正常", "无记录", "患者否认"]))
    add("v12_medication_lock", all(x in text for x in ["启动", "停用", "调整", "替换", "剂量", "给药途径", "给药速度", "给药频率"]))
    add("v12_zero_differential", "也可以不列具体鉴别方向" in text)
    add("v12_diagnostic_evidence", "单一异常值不得直接确立疾病、分期、并发症或因果关系" in text)
    add("v12_no_binding_2000", "2,000" not in text and "2000" not in text)


def check_prompt_loader():
    sys.path.insert(0, str(ROOT))
    try:
        import prompts.prompt_v1 as module

        assets = module.load_assets()
        add("loader_version", assets.version == "v1-draft")
        add("loader_status", assets.status == "draft" and module.PROMPT_STATUS == "draft")
        add("loader_max_4000", module.PROMPT_MAX_CHARS == 4000, str(module.PROMPT_MAX_CHARS))
        add(
            "loader_identity",
            (assets.char_count, assets.byte_count, assets.sha256[:8]) == (1248, 3082, "5121dd88"),
            str((assets.char_count, assets.byte_count, assets.sha256[:8])),
        )
        add(
            "loader_no_strip",
            module.load_system_prompt() == assets.text
            and len(module.load_system_prompt()) == assets.char_count,
        )
        add(
            "loader_fewshot_valid",
            len(assets.examples) == 1 and module.FEW_SHOT_INJECTION_ENABLED is False,
        )
        add("loader_candidate_guard", module.assert_candidate_not_runtime() is True)
        with tempfile.TemporaryDirectory() as tmp:
            over = Path(tmp) / "over.txt"
            over.write_text("x" * 4100, encoding="utf-8")
            try:
                module.load_assets(path=over)
            except module.PromptAssetError as exc:
                add("loader_over_budget", exc.reason == "over_budget", exc.reason)
            else:
                add("loader_over_budget", False, "no error")
    except Exception as exc:
        add("loader_import", False, repr(exc))


def check_environment_and_hosts():
    d30 = read("documents/临床智录_D_复现说明.md")
    fields = [
        "interpreter",
        "dependency_file",
        "accelerator",
        "network",
        "os_cpu_memory_storage",
        "runtime_limit_seconds",
        "package_size_limit",
        "rehearsal_state",
    ]
    add("env_block_fields", all(f in d30 for f in fields))
    add("env_tbd_oi49", "OI-49" in d30 and d30.count("TBD") >= 4, str(d30.count("TBD")))
    add(
        "env_311_static_only",
        "3.11" in d30 and ("static review only" in d30 or "静态审查" in d30),
    )
    add(
        "env_no_sizing_claim",
        "不得写成具体数字" in d30 or "不得当作对未知上限的合规" in d30,
    )
    refs = [
        "documents/临床智录_D_知识资源登记表.md",
        "documents/临床智录_D_单例评测与改进验证说明.md",
        "documents/临床智录_D_结果命名与打包对照说明.md",
        "documents/临床智录_D_大模型使用声明.md",
        "documents/临床智录_D_检索资料来源与版本声明.md",
    ]
    add("env_referenced", all("D30 §4" in read(path) for path in refs))

    forbidden = re.compile(r"\b(dashscope|aliyuncs|openai|huggingface|torch|tensorflow|onnxruntime|CUDA|NPU)\b", re.I)
    targets = [ROOT / "main.py"]
    targets += sorted((ROOT / "src").glob("*.py"))
    targets += sorted((ROOT / "prompts").glob("*.py"))
    targets += [p for p in sorted((ROOT / "codes").glob("*.py")) if p.name != "check_deliverables.py"]
    hits = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if forbidden.search(line) and "禁止" not in line:
                hits.append(f"{path.relative_to(ROOT)}:{line_no}")
    add("hosts_no_third_party_or_accelerator", not hits, ",".join(hits[:5]))
    urls = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if re.search(r"https?://", line) and "127.0.0.1" not in line and "localhost" not in line:
                urls.append(f"{path.relative_to(ROOT)}:{line_no}")
    add("hosts_no_external_url", not urls, ",".join(urls[:5]))


def _has_key(value, keys):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys:
                return True
            if _has_key(item, keys):
                return True
    elif isinstance(value, list):
        return any(_has_key(item, keys) for item in value)
    return False


def check_fixture_envelopes():
    paths = ["fixtures/output.json", "fixtures/run_log.json"]
    for path in paths:
        raw = read(path)
        try:
            data = json.loads(raw)
        except Exception as exc:
            add(f"fixture_parse_{Path(path).stem}", False, str(exc))
            continue
        stem = Path(path).stem
        add(
            f"fixture_envelope_{stem}",
            sorted(data) == ["generated_at", "label", "payload", "prompt_version", "source_transport"],
            str(sorted(data)) if isinstance(data, dict) else type(data).__name__,
        )
        add(f"fixture_label_{stem}", data.get("label") == "fixture, not a submission result")
        add(f"fixture_transport_{stem}", data.get("source_transport") == "stub")
        add(f"fixture_version_{stem}", data.get("prompt_version") == "v1-draft")
        add(f"fixture_payload_array_{stem}", isinstance(data.get("payload"), list))
        add(f"fixture_no_transport_{stem}", not _has_key(data, {"choices", "message", "usage"}))
    try:
        log_doc = json.loads(read("fixtures/run_log.json"))
        entries = log_doc.get("payload", [])
        add("fixture_log_versions", all(e.get("prompt_version") == "v1-draft" for e in entries))
    except Exception as exc:
        add("fixture_log_versions_parse", False, str(exc))


def check_registry_docs():
    d33 = read("documents/临床智录_D_知识资源登记表.md")
    add("d33_no_resource", "无 / 未使用额外知识库或规则库" in d33 and "OI-44" in d33)

    d36 = read("documents/临床智录_D_单例评测与改进验证说明.md")
    add("d36_anecdote", ("恰好 1" in d36 or "1 个官方病例" in d36) and "个案" in d36)
    add("d36_tbd_discipline", "TBD" in d36 and not re.search(r"\d+%", d36))

    d37 = read("documents/临床智录_D_结果命名与打包对照说明.md")
    add(
        "d37_naming",
        all(x in d37 for x in ["output.json", "results.json", "OI-46", "H-4", "内容保持"]),
    )

    d34 = read("documents/临床智录_D_赛题规则答疑对照表.md")
    add("d34_three_classes", all(x in d34 for x in ["已发布事实", "已收窄", "仍未公布"]))


def check_runtime():
    runtime = read("main.py") + read("src/api_client.py") + read("prompts/prompt_v1.py")
    add("no_prompt_step", "PROMPT_STEP" not in runtime)
    add("no_authorization", "Authorization" not in runtime and "DASHSCOPE_API_KEY" not in runtime)
    add("run_config_wired", "run_config" in read("src/api_client.py"), "H-1: run_config.py unintegrated")
    add("validator_vr_mapping", "VR-" in read("src/validation.py"), "H-2: 7 red lines, no VR IDs")


def check_deliverables():
    docs = {
        "D25": "prompts/PROMPT_v1.md",
        "D26": "documents/临床智录_D_临床审核记录.md",
        "D27": "documents/临床智录_D_临床安全测试用例.md",
        "D28": "documents/临床智录_D_校验规则说明.md",
        "D29": "documents/临床智录_D_模型配置说明.md",
        "D30": "documents/临床智录_D_复现说明.md",
        "D31": "documents/临床智录_D_临床需求对照表.md",
        "D32": "fixtures/safety_cases/clinical_safety_cases.json",
        "D33": "documents/临床智录_D_知识资源登记表.md",
        "D34": "documents/临床智录_D_赛题规则答疑对照表.md",
        "D35": "documents/临床智录_D_模型参数与运行控制说明.md",
        "D36": "documents/临床智录_D_单例评测与改进验证说明.md",
        "D37": "documents/临床智录_D_结果命名与打包对照说明.md",
    }
    missing = [k for k, v in docs.items() if not (ROOT / v).exists()]
    add("deliverable_paths", not missing, "missing=" + ",".join(missing) if missing else "")

    d25 = read("prompts/PROMPT_v1.md")
    add("d25_review_only", "review-only" in d25)
    add("d25_hash_match", "355c2daf" in d25 and "3,204" in d25)
    add("d25_no_binding_2000", "2,000" not in d25)

    d26 = read("documents/临床智录_D_临床审核记录.md")
    add("d26_hash_match", "355c2daf" in d26 and "acce17433" in d26)
    add("d26_signoff_null", "signoff_state" in d26 and "null" in d26)
    add("d26_re_review", "re_review_required" in d26 and "true" in d26)
    add("d26_no_approval", "clinically approved" not in d26 and "已获临床批准" not in d26)

    d29 = read("documents/临床智录_D_模型配置说明.md")
    add("d29_placeholder", "placeholder" in d29 or "待主办方确认" in d29)
    add("d29_none_sent", "none sent" in d29 and "H-1" in d29)

    d30 = read("documents/临床智录_D_复现说明.md")
    add("d30_seed_status", "seed_status" in d30 and "not-sent" in d30)
    add("d30_dataset_sha256", INPUT_SHA in d30)
    add("d30_twelve_fields", all(f in d30 for f in [
        "model_identifier", "endpoint_protocol", "prompt_version", "prompt_sha256",
        "sampling_parameters", "seed_status", "dataset_id", "dataset_sha256",
        "rule_versions", "run_timestamps", "case_mapping", "environment", "operator",
    ]))
    add("d30_no_determinism", "不承诺逐字一致" in d30 or "不承诺确定性" in d30)

    d35 = read("documents/临床智录_D_模型参数与运行控制说明.md")
    add("d35_rc_12", all(f"RC-{i}" in d35 for i in range(1, 13)))
    add("d35_none_sent", "none sent" in d35 and "H-1" in d35)
    add("d35_no_typo", "cach emark" not in d35)
    add("d35_no_determinism", "不保证相同输出" in d35 or "不承诺确定性" in d35)

    d34 = read("documents/临床智录_D_赛题规则答疑对照表.md")
    add("d34_oi50", "OI-50" in d34 and "closed-by-correction" in d34)
    add("d34_three_lists", all(x in d34 for x in ["已发布事实", "已收窄", "仍未公布"]))


def check_task12_docs():
    d9 = read("documents/临床智录_D_医学红线清单.md")
    add("d9_supplementary_5", all(f"S-{i}" in d9 for i in range(1, 6)))
    add("d9_core_7", all(f"VR-{i}" in d9 for i in [14, 8, 13, 9, 7, 15, 10, 11, 5]))
    add("d9_five_classes", all(x in d9 for x in ["NOT_PROVIDED", "NOT_PERFORMED", "DOCUMENTED_NORMAL", "NO_RECORD", "PATIENT_DENIAL"]))
    add("d9_h2_h3", "H-2" in d9 and "H-3" in d9 and "69" in d9)

    d12 = read("documents/临床智录_D_改进点及局限.md")
    d12_ids = {int(x) for x in re.findall(r"D-I(\d+)", d12)}
    add("d12_di_15_31", set(range(15, 32)) <= d12_ids, f"missing={sorted(set(range(15, 32)) - d12_ids)}")
    add("d12_single_case", "1 个官方病例" in d12 or "恰好 1 个病例" in d12)

    d13 = read("documents/临床智录_D_五维得分点对齐表.md")
    add("d13_cr_vr_rc", "CR-" in d13 and "VR-" in d13 and all(f"RC-{i}" in d13 for i in range(1, 13)))
    add("d13_di25", "D-I25" in d13)
    add("d13_no_batch_assumption", "批量均值" not in d13 and "批次" not in d13)

    d14 = read("documents/临床智录_D_DEMO001校准结论.md")
    add("d14_dp4", "DP-4" in d14 and "ST-8" in d14 and "条件" in d14)

    d23 = read("documents/临床智录_D_超越合规改进清单.md")
    d23_ids = {int(x) for x in re.findall(r"D-I(\d+)", d23)}
    add("d23_di_1_31", set(range(1, 32)) <= d23_ids, f"missing={sorted(set(range(1, 32)) - d23_ids)}")
    add("d23_status_vocab", "已验证" not in d23 and "提示词已写入" not in d23)


def check_documents():
    d4 = read("documents/临床智录_D_提示词设计章节.md")
    add("d4_v12", "v1.2-clinical-candidate" in d4 and "355c2daf" in d4)
    add("d4_no_binding_2000", "≤2,000" not in d4 and "≤2000" not in d4)

    d5 = read("documents/临床智录_D_大模型使用声明.md")
    add("d5_envelope", "none sent" in d5 and "D35" in d5)
    add("d5_placeholder", "placeholder" in d5 or "待主办方确认" in d5)
    add("d5_no_determinism", "不承诺" in d5)

    d6 = read("documents/临床智录_D_检索资料来源与版本声明.md")
    add("d6_no_retrieval", "未使用外部检索资料" in d6)
    add("d6_registry", "无 / 未使用额外知识库或规则库" in d6 and "D33" in d6)

    changelog = read("prompts/CHANGELOG.md")
    add("changelog_no_1117", "2026-11-17" not in changelog)
    add("changelog_freeze_target", "2026-11-24" in changelog and "2026-11-23" in changelog)

    d10 = read("documents/临床智录_D_Prompt冻结说明.md")
    add("d10_4000", "4,000" in d10 and "≤2,000" not in d10)

    handover = read("documents/临床智录_D_交接与真实运行清单.md")
    add("handover_dp_h", all(f"DP-{i}" in handover for i in range(1, 7)) and all(f"H-{i}" in handover for i in range(1, 6)))
    add("handover_no_binding_2000", "≤2,000" not in handover)

    package = read("documents/临床智录_D_临床审核包.md")
    add("package_dates", "2026-11-17" not in package and "2026-11-23" in package and "2026-11-24" in package)
    add("package_five_classes", "五类语境" in package)
    add("package_clinician", "具名临床医生" in package)

    d19 = read("documents/临床智录_D交付物补齐与集成变更记录.md")
    add("d19_record", "## 13." in d19 and "0e4e636" in d19 and "本轮没有" in d19)


def check_safety():
    fixture = read("fixtures/safety_cases/clinical_safety_cases.json")
    try:
        data = json.loads(fixture)
        cases = data.get("cases", [])
        add("safety_fixture_10", len(cases) == 10, str(len(cases)))
        add("safety_case_ids", [c.get("case_id") for c in cases] == [f"ST-{i}" for i in range(1, 11)])
    except Exception as exc:
        add("safety_fixture_json", False, str(exc))

    d27 = read("documents/临床智录_D_临床安全测试用例.md")
    add("d27_not_implemented_10", d27.count("not-implemented") == 10, str(d27.count("not-implemented")))
    add("d27_unique_st_ids_10", len(set(re.findall(r"ST-\d+", d27))) >= 10, str(len(set(re.findall(r"ST-\d+", d27)))))

    d28 = read("documents/临床智录_D_校验规则说明.md")
    d31 = read("documents/临床智录_D_临床需求对照表.md")
    vr28 = set(re.findall(r"VR-\d+", d28))
    vr31 = set(re.findall(r"VR-\d+", d31))
    add("d28_vr_1_17", {f"VR-{i}" for i in range(1, 18)} <= vr28)
    add("d31_vr_match", vr28 == vr31, f"{sorted(vr28 - vr31)} / {sorted(vr31 - vr28)}")
    add("d31_cr_1_10", all(f"CR-{i}" in d31 for i in range(1, 11)))


def check_env_and_claims():
    env = read(".env.example").strip().splitlines()
    add("env_example_two_lines", env == ["MODEL_NAME=", "ENDPOINT="], str(env))
    add("env_example_no_secret", not any(x in read(".env.example") for x in ["KEY=", "TOKEN=", "SECRET="]))

    claims = read("documents/临床智录_D_临床审核记录.md") + read("prompts/PROMPT_v1.md")
    add("no_clinical_approval_claim", "clinically approved" not in claims and "已获临床批准" not in claims)

    try:
        input_text = "\n".join(collect_strings(json.loads(read("input.json"))))
        fixture_text = "\n".join(collect_strings(json.loads(read("fixtures/safety_cases/clinical_safety_cases.json"))))
        v12_text = read("prompts/candidates/system_v1_2_candidate.txt")
        v12_overlap = runs(v12_text) & runs(input_text)
        fixture_overlap = runs(fixture_text) & runs(input_text)
        add("overlap_v12_input", len(v12_overlap) == 0, f"{len(v12_overlap)} semantic 10-char runs")
        add("overlap_fixture_input", len(fixture_overlap) == 0, f"{len(fixture_overlap)} semantic 10-char runs")
    except Exception as exc:
        add("overlap_input_parse", False, str(exc))


def check_artifacts():
    readme = ROOT / "README.md"
    add("readme_nonempty", readme.exists() and readme.stat().st_size > 0, "README.md is 0 bytes")
    add("root_output_exists", (ROOT / "output.json").exists(), "absent")
    add("root_run_log_exists", (ROOT / "run_log.json").exists(), "absent")


def run_checks():
    check_prompt()
    check_prompt_loader()
    check_runtime()
    check_environment_and_hosts()
    check_fixture_envelopes()
    check_registry_docs()
    check_deliverables()
    check_task12_docs()
    check_documents()
    check_safety()
    check_env_and_claims()
    check_artifacts()


def main():
    parser = argparse.ArgumentParser(description="Read-only deliverables checker")
    parser.add_argument("--check", default="all", help="comma-separated name substrings, or 'all'")
    parser.add_argument("--list", action="store_true", help="list check names")
    args = parser.parse_args()

    run_checks()
    if args.list:
        for check in CHECKS:
            print(check["name"])
        return 0

    aliases = {
        "registry": ["deliverable_paths", "d33_", "d34_", "d35_", "d36_", "d37_"],
        "prompt": ["prompt_", "loader_", "six_blocks", "five_red_lines", "five_fields", "v12_"],
        "keyless": ["no_authorization", "no_prompt_step", "env_example_no_secret"],
        "candidate": ["d25_"],
        "review": ["d26_"],
        "safety": ["safety_", "d27_"],
        "rules": ["d28_", "d9_"],
        "requirements": ["d31_", "d13_"],
        "reproducibility": ["d30_", "d29_"],
        "fixtures": ["fixture_", "safety_fixture", "safety_case"],
        "environment": ["env_"],
        "hosts": ["host_"],
        "overlap": ["overlap_"],
        "claims": ["no_clinical_approval_claim", "changelog_", "d26_no_approval"],
        "record": ["d19_"],
    }
    selected = CHECKS
    if args.check != "all":
        tokens = [t.strip() for t in args.check.split(",") if t.strip()]
        patterns = []
        for token in tokens:
            patterns.extend(aliases.get(token, [token]))
        selected = [c for c in CHECKS if any(p in c["name"] for p in patterns)]

    failed = 0
    for check in selected:
        status = "PASS" if check["ok"] else "FAIL"
        if not check["ok"] and check["blocking"]:
            failed += 1
        print(f"{check['name']}={status}" + (f" :: {check['detail']}" if check["detail"] else ""))
    print(f"summary: {len(selected) - failed}/{len(selected)} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())