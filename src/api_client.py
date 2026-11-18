import json
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values
import src.run_config as run_config

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


class ParameterRejectedError(Exception):
    code = "PARAMETER_REJECTED"

    def __init__(self, parameter, detail):
        self.parameter = parameter
        self.detail = detail
        super().__init__(f"PARAMETER_REJECTED: endpoint rejected parameter '{parameter}': {detail}")


class ModelRequestError(Exception):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(f"{code}: {detail}")


def _build_payload(model_name, messages):
    payload = {
        "model": model_name,
        "messages": messages,
    }
    payload.update(run_config.request_parameters())
    return payload


def _response_text(response):
    try:
        text = response.text
    except Exception:
        text = ""
    return text or ""


def _find_rejected_parameter(response_text, payload):
    text = response_text.lower()
    candidates = []
    for field in ("seed", "temperature", "response_format", "chat_template_kwargs", "stream"):
        if field in payload and (field.lower() in text or field.replace("_", "-") in text):
            candidates.append(field)
    aliases = ("enable_thinking", "thinking")
    if "chat_template_kwargs" in payload:
        if any(alias in text for alias in aliases):
            candidates.append("thinking")
    if not candidates:
        return None
    return candidates[0]


def _raise_parameter_rejection(response, payload):
    status_code = getattr(response, "status_code", 0)
    if status_code < 400:
        return
    response_text = _response_text(response)
    text = response_text.lower()
    parameter_error = any(
        phrase in text
        for phrase in (
            "unsupported parameter",
            "unknown parameter",
            "unrecognized",
            "does not support",
            "not supported",
            "invalid parameter",
            "unexpected keyword",
            "extra inputs",
        )
    )
    parameter = _find_rejected_parameter(response_text, payload)
    if parameter_error or parameter:
        if parameter is None:
            parameter = "unknown"
        run_config.record_rejection(parameter)
        raise ParameterRejectedError(parameter, response_text.strip() or f"HTTP {status_code}")


def _record_sent_parameters(payload):
    for field in ("seed", "temperature", "response_format", "chat_template_kwargs", "stream"):
        if field in payload:
            param = "thinking" if field == "chat_template_kwargs" else field
            run_config.record_acceptance(param)


def _run_log_entry(case_id, call_index, attempt, model_name, start_time, status, error=None, error_code=None):
    entry = {
        "case_id": case_id,
        "call_index": call_index,
        "attempt": attempt,
        "model": model_name,
        "timestamp": start_time,
        "duration_seconds": round(time.time() - start_time, 2),
        "status": status,
    }
    if error is not None:
        entry["error"] = error
    if error_code is not None:
        entry["error_code"] = error_code
    entry.update(run_config.envelope_for_log())
    return entry


def call_llm(case_id, messages, retries=3, timeout=120):
    model_name, endpoint = get_config()

    session = requests.Session()
    session.trust_env = False

    payload = _build_payload(model_name, messages)

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
            _raise_parameter_rejection(response, payload)
            if response.status_code == 401 or response.status_code == 403:
                raise ModelRequestError("MODEL_AUTH_ERROR", "endpoint requires authentication or denies keyless access")
            if response.status_code == 429:
                raise ModelRequestError("MODEL_RATE_LIMIT", "endpoint rate limit reached")
            if response.status_code >= 500:
                raise ModelRequestError("MODEL_SERVER_ERROR", f"HTTP {response.status_code}")
            if response.status_code < 200 or response.status_code >= 300:
                raise ModelRequestError("MODEL_HTTP_ERROR", f"HTTP {response.status_code}")
            try:
                response_data = response.json()
                content = response_data["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError):
                raise ModelRequestError("MODEL_RESPONSE_ERROR", "missing choices[0].message.content")
            _record_sent_parameters(payload)

            RUN_LOGS.append(
                _run_log_entry(
                    case_id, call_index, attempt + 1, model_name, start_time, "success"
                )
            )
            return content

        except Exception as exc:
            if isinstance(exc, requests.exceptions.Timeout):
                exc = ModelRequestError("MODEL_TIMEOUT", "model request timed out")
            elif isinstance(exc, requests.exceptions.ConnectionError):
                exc = ModelRequestError("MODEL_CONNECTION_ERROR", "endpoint is unreachable")
            elif isinstance(exc, requests.exceptions.RequestException):
                exc = ModelRequestError("MODEL_REQUEST_ERROR", exc.__class__.__name__)
            error_code = getattr(exc, "code", None)
            RUN_LOGS.append(
                _run_log_entry(
                    case_id,
                    call_index,
                    attempt + 1,
                    model_name,
                    start_time,
                    "failed",
                    error=str(exc),
                    error_code=error_code,
                )
            )
            if isinstance(exc, ParameterRejectedError):
                raise
            if attempt == retries - 1:
                if isinstance(exc, ModelRequestError):
                    raise exc
                raise Exception(f"MODEL_ERROR: {exc}") from exc


def mock_llm_success(case_id, messages):
    RUN_LOGS.append(
        _run_log_entry(case_id, 1, 1, "fixture", time.time(), "success")
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