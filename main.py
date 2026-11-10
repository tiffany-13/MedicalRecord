import json
import sys
from pathlib import Path
from src.api_client import call_llm  # <--- 从 src 文件夹里导入

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "input.json"
OUTPUT_FILE = BASE_DIR / "output.json"
TEMP_FILE = BASE_DIR / "output_tmp.json"

def main():
    # ...(省略读取 input.json 的代码)...

    for case in cases:
        case_id = case.get("case_id")
        
        try:
            # 这里先随便拼一个 Prompt，等队员 D 提供正式的
            messages = [
                {"role": "system", "content": "你是一个医生。请返回JSON格式。"},
                {"role": "user", "content": str(case.get("sources"))}
            ]
            
            # 调用 src/api_client.py 里的函数
            raw_response = call_llm(messages)
            
            # TODO: 解析 raw_response (开发B负责)
            # 暂时伪造一个成功的结果
            medical_record = {
                "case_features": "这里是病例特点...",
                "diagnostic_discussion": "这里是拟诊讨论...",
                "plan": "这里是诊疗计划...",
                "evidence": [],
                "review_items": []
            }
            
            results.append({
                "case_id": case_id,
                "status": "success",
                "medical_record": medical_record,
                "error": None
            })
            
        except Exception as e:
            # 如果 call_llm 报错抛出异常，这里会被捕获
            results.append({
                "case_id": case_id,
                "status": "failed",
                "medical_record": None,
                "error": {"code": "MODEL_ERROR", "message": str(e)}
            })

    # ...(省略写入 output.json 的代码)...

if __name__ == "__main__":
    main()