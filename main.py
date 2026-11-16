import concurrent.futures
import json
import os
import sys
from pathlib import Path

from prompts.prompt_v1 import PROMPT_VERSION, build_messages, load_system_prompt
from src.api_client import RUN_LOGS, call_llm, get_config, parse_json_response

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "input.json"
OUTPUT_FILE = BASE_DIR / "output.json"
TEMP_FILE = BASE_DIR / "output_tmp.json"
LOG_FILE = BASE_DIR / "run_log.json"
LOG_TEMP_FILE = BASE_DIR / "run_log_tmp.json"
MAX_WORKERS = 3


def write_json_atomic(path, temp_path, data):
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def validate_input(cases):
    if not isinstance(cases, list):
        raise ValueError("input.json 顶层必须是数组")
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("input.json 的每个病例必须是对象")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("病例标识缺失")
        if case_id in seen:
            raise ValueError(f"病例标识重复: {case_id}")
        seen.add(case_id)


def case_error(case_id, code, message):
    return {
        "case_id": case_id,
        "status": "failed",
        "medical_record": None,
        "error": {"code": code, "message": message},
    }


def validate_case_content(case):
    case_id = case.get("case_id", "")
    record_cutoff = case.get("record_cutoff")
    if not isinstance(record_cutoff, str) or not record_cutoff.strip():
        return None, case_error(case_id, "CASE_CONTENT_ERROR", "记录截止时间无效")
    sources = case.get("sources")
    if not isinstance(sources, list) or not sources:
        return None, case_error(case_id, "CASE_CONTENT_ERROR", "资料片段缺失")
    seen = set()
    for source in sources:
        if not isinstance(source, dict):
            return None, case_error(case_id, "CASE_CONTENT_ERROR", "资料片段格式无效")
        source_id = source.get("source_id")
        content = source.get("content")
        if not isinstance(source_id, str) or not source_id.strip():
            return None, case_error(case_id, "CASE_CONTENT_ERROR", "资料片段标识缺失")
        if source_id in seen:
            return None, case_error(case_id, "CASE_CONTENT_ERROR", "资料片段标识重复")
        if not isinstance(content, str) or not content.strip():
            return None, case_error(case_id, "CASE_CONTENT_ERROR", "资料片段内容为空")
        seen.add(source_id)
    return {"case_id": case_id, "record_cutoff": record_cutoff, "sources": sources}, None


def process_case(case):
    case_data, error = validate_case_content(case)
    if error is not None:
        return error

    case_id = case_data["case_id"]
    messages = build_messages(case_id, case_data["record_cutoff"], case_data["sources"])

    try:
        raw_text = call_llm(case_id, messages)
    except Exception as exc:
        return case_error(case_id, "MODEL_ERROR", str(exc))

    try:
        medical_record = parse_json_response(raw_text)
    except Exception:
        return case_error(case_id, "JSON_PARSE_ERROR", "模型返回的内容无法解析为合法 JSON")

    try:
        from src.validation import validate_record

        validate_record(medical_record, case_data["sources"])
    except Exception as exc:
        return case_error(case_id, "VALIDATION_ERROR", str(exc))

    return {
        "case_id": case_id,
        "status": "success",
        "medical_record": medical_record,
        "error": None,
    }


def main():
    RUN_LOGS.clear()
    get_config()

    try:
        system_prompt = load_system_prompt()
    except Exception as exc:
        print(f"任务级错误：加载提示词失败 -> {exc}")
        sys.exit(1)

    if not system_prompt.strip():
        print("任务级错误：提示词为空")
        sys.exit(1)

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as handle:
            cases = json.load(handle)
        validate_input(cases)
    except Exception as exc:
        print(f"任务级错误：读取或校验 input.json 失败 -> {exc}")
        sys.exit(2)

    try:
        if len(cases) == 0:
            write_json_atomic(OUTPUT_FILE, TEMP_FILE, [])
            write_json_atomic(LOG_FILE, LOG_TEMP_FILE, [])
            print("输入为空，已生成空的 output.json")
            sys.exit(0)

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            results = list(executor.map(process_case, cases))

        for entry in RUN_LOGS:
            entry["prompt_version"] = PROMPT_VERSION

        write_json_atomic(OUTPUT_FILE, TEMP_FILE, results)
        write_json_atomic(LOG_FILE, LOG_TEMP_FILE, RUN_LOGS)
        success = sum(1 for record in results if record["status"] == "success")
        failed = len(results) - success
        print(f"处理完成！成功: {success} 例，失败: {failed} 例。")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"任务级错误：结果写入失败 -> {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()