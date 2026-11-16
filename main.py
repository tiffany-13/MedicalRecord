import json
import sys
import concurrent.futures
from pathlib import Path
from src.api_client import call_llm, parse_json_response, RUN_LOGS

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "input.json"
OUTPUT_FILE = BASE_DIR / "output.json"
TEMP_FILE = BASE_DIR / "output_tmp.json"
LOG_FILE = BASE_DIR / "run_log.json"

# 并发上限 (根据赛方规定调整，暂定为3)
MAX_WORKERS = 3 

def process_case(case):
    """处理单个病例的核心逻辑"""
    case_id = case.get("case_id")
    
    # 提取原始资料
    sources_text = ""
    for src in case.get("sources", []):
        sources_text += f"[{src.get('source_id')}] {src.get('content')}\n"
    
    # 构造 Prompt (后续由队员D替换为高级Prompt)
    messages = [
        {"role": "system", "content": "你是一个医生。请仅输出合法的JSON格式，不要包含Markdown标记。"},
        {"role": "user", "content": f"资料如下：\n{sources_text}\n请生成：case_features, diagnostic_discussion, plan, evidence, review_items 字段。"}
    ]
    
    try:
        # 1. 请求模型
        raw_response = call_llm(case_id, messages)
        
        # 2. 解析 JSON
        parsed_data = parse_json_response(raw_response)
        
        # 3. 基础字段缺失防御 (兜底)
        for key in ["case_features", "diagnostic_discussion", "plan", "evidence", "review_items"]:
            if key not in parsed_data:
                parsed_data[key] = "" if key != "evidence" and key != "review_items" else []
                
        return {
            "case_id": case_id,
            "status": "success",
            "medical_record": parsed_data,
            "error": None
        }
    except Exception as e:
        # 捕获异常，返回失败结构
        return {
            "case_id": case_id,
            "status": "failed",
            "medical_record": None,
            "error": {"code": "PROCESS_ERROR", "message": str(e)}
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