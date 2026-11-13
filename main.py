import json
import sys
import concurrent.futures
from pathlib import Path
from dotenv import load_dotenv
from src.api_client import mock_llm_success, parse_json_response, RUN_LOGS
from prompts.prompt_v1 import SYSTEM_PROMPT

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
INPUT_FILE = BASE_DIR / "input.json"
OUTPUT_FILE = BASE_DIR / "output.json"
TEMP_FILE = BASE_DIR / "output_tmp.json"
LOG_FILE = BASE_DIR / "run_log.json"

# 并发上限 (根据赛方规定调整，暂定为3)
MAX_WORKERS = 3

def process_case(case):
    import json
    import re
    from prompts.prompt_v1 import PROMPT_STEP1, PROMPT_STEP2  # D负责写这两个变量
    from src.validation import validate_record # C负责写这个函数

    case_id = case.get("case_id", "UNKNOWN")
    sources = case.get("sources", [])

    # 1. 拼装资料 (给 D 的输入)
    sources_text = ""
    for src in sources:
        s_id = src.get("source_id", "")
        s_content = src.get("content", "")
        sources_text += f"[{s_id}] {s_content}\n"

    # 2. 流水线调用（写死用 D 的 Prompt）
    try:
        msg1 = [
            {"role": "system", "content": PROMPT_STEP1},
            {"role": "user", "content": f"资料：\n{sources_text}"}
        ]
        features_text = "【模拟】病例特点文本"
        
        msg2 = [
            {"role": "system", "content": PROMPT_STEP2},
            {"role": "user", "content": f"原始资料：\n{sources_text}\n\n病例特点：\n{features_text}\n\n请输出符合赛方要求的 JSON。"}
        ]
        raw_text = mock_llm_success(case_id, msg2)
        
    except Exception as e:
        return {
            "case_id": case_id, "status": "failed", "medical_record": None,
            "error": {"code": "API_ERROR", "message": str(e)}
        }

    # 3. 解析 JSON
    try:
        medical_record = parse_json_response(raw_text)
    except Exception as e:
        return {
            "case_id": case_id, "status": "failed", "medical_record": None,
            "error": {"code": "JSON_PARSE_ERROR", "message": "模型没吐合法的JSON"}
        }

    # 4. 交给 C 去校验（C 如果校验不过，会抛异常，B 直接拦截）
    try:
        # C 的代码必须在这个函数里完成所有的溯源、红线拦截
        validate_record(medical_record, sources) 
    except Exception as e:
        return {
            "case_id": case_id, "status": "failed", "medical_record": None,
            "error": {"code": "VALIDATION_ERROR", "message": str(e)}
        }

    # 5. 校验全过，返回成功
    return {
        "case_id": case_id, "status": "success", "medical_record": medical_record, "error": None
    }

def main():
    # 1. 读取输入文件
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            cases = json.load(f)
            if not isinstance(cases, list):
                raise ValueError("input.json 顶层必须是数组")
    except Exception as e:
        print(f"任务级错误：读取 input.json 失败 -> {e}")
        sys.exit(1)

    # 处理空输入情况
    if len(cases) == 0:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        print("输入为空，已生成空的 output.json")
        sys.exit(0)

    # 2. 多线程并发处理病例
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # executor.map 会保持输入和输出的顺序一致
        results = list(executor.map(process_case, cases))

    # 3. 安全落盘：先写临时文件，再替换正式文件
    try:
        with open(TEMP_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        import os
        os.replace(TEMP_FILE, OUTPUT_FILE)
        
        # 4. 写入运行日志 run_log.json
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(RUN_LOGS, f, ensure_ascii=False, indent=2)
            
        print(f"处理完成！成功: {sum(1 for r in results if r['status']=='success')} 例，失败: {sum(1 for r in results if r['status']=='failed')} 例。")
        sys.exit(0) # 退出码 0
        
    except Exception as e:
        print(f"任务级错误：结果写入失败 -> {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()