import json
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent.parent
RUN_LOGS = []
_CONFIG = None


def get_config():
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    config = dotenv_values(BASE_DIR / ".env")
    model_name = (config.get("MODEL_NAME") or "").strip()
    endpoint = (config.get("ENDPOINT") or "").strip()

    if not model_name or not endpoint:
        print("错误：.env 必须提供非空的 MODEL_NAME 和 ENDPOINT")
        sys.exit(2)

    _CONFIG = (model_name, endpoint)
    return _CONFIG


def parse_json_response(raw_text):
    raw_text = raw_text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]

    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError("模型返回的内容无法解析为合法 JSON")


def _next_call_index(case_id):
    return sum(1 for entry in RUN_LOGS if entry.get("case_id") == case_id) + 1


def call_llm(case_id, messages, retries=3, timeout=120):
    model_name, endpoint = get_config()

    session = requests.Session()
    session.trust_env = False

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
    }

    headers = {"Content-Type": "application/json"}

    for attempt in range(retries):
        start_time = time.time()
        call_index = _next_call_index(case_id)
        try:
            response = session.post(
                endpoint,
                json=payload,
                timeout=timeout,
                headers=headers,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]

            RUN_LOGS.append(
                {
                    "case_id": case_id,
                    "call_index": call_index,
                    "attempt": attempt + 1,
                    "model": model_name,
                    "timestamp": start_time,
                    "duration_seconds": round(time.time() - start_time, 2),
                    "status": "success",
                }
            )
            return content

        except Exception as exc:
            RUN_LOGS.append(
                {
                    "case_id": case_id,
                    "call_index": call_index,
                    "attempt": attempt + 1,
                    "model": model_name,
                    "timestamp": start_time,
                    "duration_seconds": round(time.time() - start_time, 2),
                    "status": "failed",
                    "error": str(exc),
                }
            )
            if attempt == retries - 1:
                raise Exception(f"MODEL_ERROR: {exc}") from exc


def mock_llm_success(case_id, messages):
    RUN_LOGS.append(
        {
            "case_id": case_id,
            "call_index": 1,
            "attempt": 1,
            "model": "fixture",
            "timestamp": time.time(),
            "duration_seconds": 0.1,
            "status": "success",
        }
    )

    mock_response_json = """
    {
      "case_features": "成人，近2周乏力、活动后心悸，现有记录显示结膜苍白和双下肢轻度水肿。血红蛋白 82 g/L、肌酐 185 μmol/L。现有记录未见明确出血表现；血压和尿量不详。",
      "diagnostic_discussion": "现有资料支持贫血及肾功能异常。贫血需结合红细胞指数等进一步分析，不能排除隐匿失血；单次肌酐升高不足以确定急慢性过程，不能直接归因为肾性贫血。病因待查。",
      "plan": "建议临床医生补充既往检查、用药史，核实血压和容量状态；拟复查血常规及肾功能，按鉴别需要安排进一步检查。观察症状和指标变化。",
      "evidence": [
        {
          "statement": "近 2 周乏力、活动后心悸",
          "source_ids": ["S01"],
          "kind": "fact"
        },
        {
          "statement": "血红蛋白 82 g/L，肌酐 185 μmol/L",
          "source_ids": ["S03"],
          "kind": "fact"
        },
        {
          "statement": "血压、尿量及既往肾功能资料未提供，急慢性过程及贫血原因尚不能确定",
          "source_ids": ["S02", "S03", "S04"],
          "kind": "inference"
        }
      ],
      "review_items": [
        "既往肾功能及贫血病程",
        "血压、尿量及用药史"
      ]
    }
    """
    return mock_response_json