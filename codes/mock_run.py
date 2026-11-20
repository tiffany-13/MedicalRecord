import argparse
import concurrent.futures
import hashlib
import json
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import main
import src.api_client as api
import src.run_config as run_config
from prompts.prompt_v1 import PROMPT_VERSION

LABEL = "fixture, not a submission result"
SOURCE_TRANSPORT = "stub"

RECORD = {
    "case_features": "成人，近2周乏力、活动后心悸，结膜苍白，双下肢轻度水肿。血红蛋白 82 g/L，肌酐 185 μmol/L；血压和尿量未提供。",
    "diagnostic_discussion": "现有资料支持贫血及肾功能异常，需要分别明确原因及两者关系；单次肌酐升高不足以确定急慢性过程。病因待查。",
    "plan": "建议补充既往检查、用药史，核实血压和尿量；拟复查血常规及肾功能，观察症状和指标变化。",
    "evidence": [
        {"statement": "近2周乏力、活动后心悸", "source_ids": ["S01"], "kind": "fact"},
        {"statement": "血红蛋白 82 g/L，肌酐 185 μmol/L", "source_ids": ["S03"], "kind": "fact"},
        {
            "statement": "血压和尿量未提供，急慢性过程及贫血原因尚不能确定",
            "source_ids": ["S02", "S03", "S04"],
            "kind": "inference",
        },
    ],
    "review_items": ["既往肾功能及贫血病程", "血压、尿量及用药史"],
}

captured = {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def envelope(payload):
    return {
        "label": LABEL,
        "source_transport": SOURCE_TRANSPORT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_version": PROMPT_VERSION,
        "payload": payload,
    }


def has_transport_field(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"choices", "message", "usage"}:
                return True
            if has_transport_field(item):
                return True
    elif isinstance(value, list):
        return any(has_transport_field(item) for item in value)
    return False


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        captured["headers"] = {k: v for k, v in self.headers.items()}
        captured["payload"] = json.loads(body)
        response = json.dumps(
            {"choices": [{"message": {"content": json.dumps(RECORD, ensure_ascii=False)}}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *args):
        pass


def run(use_env):
    print("python_version=", sys.version.split()[0])
    print("python_is_3_11=", sys.version_info[:2] == (3, 11))
    if sys.version_info[:2] != (3, 11):
        print("WARNING: competition runtime is Python 3.11; current is", sys.version.split()[0])

    env_path = REPO_ROOT / ".env"
    if use_env and env_path.exists():
        print("refused_env_exists= true")
        print("FIXTURE: not a submission result")
        return 2

    fixtures = REPO_ROOT / "fixtures"
    fixtures.mkdir(exist_ok=True)
    output_path = fixtures / "output.json"
    output_temp = fixtures / "output_tmp.json"
    log_path = fixtures / "run_log.json"
    log_temp = fixtures / "run_log_tmp.json"

    root_files = [REPO_ROOT / "output.json", REPO_ROOT / "run_log.json"]
    root_before = {path.name: digest(path) for path in root_files}
    env_before = env_path.read_bytes() if env_path.exists() else None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    if use_env:
        api._CONFIG = None
        env_path.write_text(
            f"MODEL_NAME=mock-model\nENDPOINT=http://127.0.0.1:{port}\n",
            encoding="utf-8",
        )
    else:
        api._CONFIG = ("mock-model", f"http://127.0.0.1:{port}")

    exit_code = None
    try:
        with open(REPO_ROOT / "input.json", "r", encoding="utf-8") as handle:
            cases = json.load(handle)
        main.validate_input(cases)
        if use_env:
            api.get_config()
        main.RUN_LOGS.clear()
        run_config.start_run()
        with concurrent.futures.ThreadPoolExecutor(max_workers=main.MAX_WORKERS) as executor:
            results = list(executor.map(main.process_case, cases))
        for entry in main.RUN_LOGS:
            entry["prompt_version"] = PROMPT_VERSION
            for key, value in run_config.envelope_for_log().items():
                entry.setdefault(key, value)
        main.write_json_atomic(output_path, output_temp, envelope(results))
        main.write_json_atomic(log_path, log_temp, envelope(main.RUN_LOGS))
        exit_code = 0
    except SystemExit as exc:
        exit_code = exc.code
    except Exception as exc:
        print("mock_run_error=", exc)
        exit_code = 1
    finally:
        server.shutdown()
        if use_env and env_path.exists():
            env_path.unlink()
        for temp_path in (output_temp, log_temp):
            if temp_path.exists():
                temp_path.unlink()

    root_after = {path.name: digest(path) for path in root_files}
    env_after = env_path.read_bytes() if env_path.exists() else None

    output_doc = json.loads(output_path.read_text(encoding="utf-8"))
    log_doc = json.loads(log_path.read_text(encoding="utf-8"))
    record = output_doc["payload"][0]
    run_log = log_doc["payload"]
    medical_record = record["medical_record"]
    combined = (
        len(medical_record["case_features"])
        + len(medical_record["diagnostic_discussion"])
        + len(medical_record["plan"])
    )

    checks = {
        "exit_zero": exit_code == 0,
        "status_success": record["status"] == "success",
        "five_fields": sorted(medical_record.keys())
        == ["case_features", "diagnostic_discussion", "evidence", "plan", "review_items"],
        "evidence_at_least_one": len(medical_record["evidence"]) >= 1,
        "run_log_present": len(run_log) >= 1,
        "prompt_version": all(entry.get("prompt_version") == "v1-draft" for entry in run_log),
        "model_in_log": all(entry.get("model") == "mock-model" for entry in run_log),
        "no_authorization": "Authorization" not in captured.get("headers", {}),
        "content_type": captured.get("headers", {}).get("Content-Type") == "application/json",
        "payload_keys": sorted(captured.get("payload", {}).keys())
        == ["messages", "model", "seed", "stream", "temperature"],
        "root_untouched": root_before == root_after,
        "env_clean": env_after == env_before,
        "output_envelope_keys": sorted(output_doc.keys())
        == ["generated_at", "label", "payload", "prompt_version", "source_transport"],
        "log_envelope_keys": sorted(log_doc.keys())
        == ["generated_at", "label", "payload", "prompt_version", "source_transport"],
        "label_exact": output_doc["label"] == LABEL and log_doc["label"] == LABEL,
        "source_transport": output_doc["source_transport"] == SOURCE_TRANSPORT
        and log_doc["source_transport"] == SOURCE_TRANSPORT,
        "output_payload_array": isinstance(output_doc["payload"], list),
        "log_payload_array": isinstance(log_doc["payload"], list),
        "envelope_prompt_version": output_doc["prompt_version"] == "v1-draft"
        and log_doc["prompt_version"] == "v1-draft",
        "no_transport_field": not has_transport_field(output_doc)
        and not has_transport_field(log_doc),
        "no_secret_text": "Authorization" not in json.dumps(output_doc)
        and "Authorization" not in json.dumps(log_doc)
        and "sk-" not in json.dumps(output_doc)
        and "sk-" not in json.dumps(log_doc),
    }

    for name, passed in checks.items():
        print(f"{name}={'PASS' if passed else 'FAIL'}")
    print("config_mode=", "env" if use_env else "injected")
    print("fixture_output=", output_path)
    print("fixture_log=", log_path)
    print("fixture_label=", LABEL)
    print("fixture_generated_at=", output_doc["generated_at"])
    print("body_length=", combined, "(stub payload defect, not a quality result)")
    print("FIXTURE: not a submission result")
    return 0 if all(checks.values()) else 1


def main_cli():
    parser = argparse.ArgumentParser(
        description="Non-production mock test. No API key, no real endpoint, fixtures only."
    )
    parser.add_argument(
        "--env",
        action="store_true",
        help="Temporarily write a local .env to test the dotenv loading path; refuses if .env exists.",
    )
    args = parser.parse_args()
    return run(use_env=args.env)


if __name__ == "__main__":
    raise SystemExit(main_cli())