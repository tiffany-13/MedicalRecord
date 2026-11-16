import argparse
import hashlib
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import main
import src.api_client as api

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

    fixtures = REPO_ROOT / "fixtures"
    fixtures.mkdir(exist_ok=True)
    main.INPUT_FILE = REPO_ROOT / "input.json"
    main.OUTPUT_FILE = fixtures / "output_stub.json"
    main.TEMP_FILE = fixtures / "output_stub_tmp.json"
    main.LOG_FILE = fixtures / "run_log_stub.json"
    main.LOG_TEMP_FILE = fixtures / "run_log_stub_tmp.json"

    root_files = [REPO_ROOT / "output.json", REPO_ROOT / "run_log.json"]
    root_before = {path.name: digest(path) for path in root_files}

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    env_path = REPO_ROOT / ".env"
    original_env = env_path.read_bytes() if env_path.exists() else None
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
        try:
            main.main()
        except SystemExit as exc:
            exit_code = exc.code
    finally:
        server.shutdown()
        if use_env:
            if original_env is None:
                if env_path.exists():
                    env_path.unlink()
            else:
                env_path.write_bytes(original_env)

    root_after = {path.name: digest(path) for path in root_files}
    env_after = env_path.read_bytes() if env_path.exists() else None

    record = json.loads((fixtures / "output_stub.json").read_text(encoding="utf-8"))[0]
    run_log = json.loads((fixtures / "run_log_stub.json").read_text(encoding="utf-8"))
    medical_record = record["medical_record"]

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
        "payload_keys": sorted(captured.get("payload", {}).keys()) == ["messages", "model", "stream"],
        "root_untouched": root_before == root_after,
        "env_clean": env_after == original_env,
    }

    for name, passed in checks.items():
        print(f"{name}={'PASS' if passed else 'FAIL'}")
    print("config_mode=", "env" if use_env else "injected")
    print("fixture_output=", main.OUTPUT_FILE)
    print("fixture_log=", main.LOG_FILE)
    print("FIXTURE: not a submission result")
    return 0 if all(checks.values()) else 1


def main_cli():
    parser = argparse.ArgumentParser(
        description="Non-production mock test. No API key, no real endpoint, fixtures only."
    )
    parser.add_argument(
        "--env",
        action="store_true",
        help="Temporarily write a local .env to test the dotenv loading path, then restore it.",
    )
    args = parser.parse_args()
    return run(use_env=args.env)


if __name__ == "__main__":
    raise SystemExit(main_cli())