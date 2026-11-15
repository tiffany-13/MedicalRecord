import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent

import requests
from dotenv import dotenv_values

DEFAULT_MODEL = "qwen3.8 27b"
DIAGNOSTIC_PROMPT = "Reply with the single word OK."


def load_config():
    config = dotenv_values(REPO_ROOT / ".env")
    model = (config.get("MODEL_NAME") or "").strip()
    endpoint = (config.get("ENDPOINT") or "").strip()
    return model, endpoint


def main():
    parser = argparse.ArgumentParser(
        description="One-shot organizer endpoint diagnostic. No patient data, no API key, no file writes."
    )
    parser.add_argument("--model", default=None, help="Override MODEL_NAME")
    parser.add_argument("--endpoint", default=None, help="Override ENDPOINT")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds")
    args = parser.parse_args()

    env_model, env_endpoint = load_config()
    if args.model:
        model, model_source = args.model, "cli"
    elif env_model:
        model, model_source = env_model, ".env"
    else:
        model, model_source = DEFAULT_MODEL, "default (user-provided, confirm with organizer)"

    if args.endpoint:
        endpoint, endpoint_source = args.endpoint, "cli"
    elif env_endpoint:
        endpoint, endpoint_source = env_endpoint, ".env"
    else:
        print("ERROR: ENDPOINT missing. Set .env or pass --endpoint.")
        return 2

    print("model=", model)
    print("model_source=", model_source)
    print("endpoint_host=", urlparse(endpoint).netloc or "(invalid/empty)")
    print("endpoint_source=", endpoint_source)
    if model_source.startswith("default"):
        print("WARNING: default model is user-provided; confirm the exact MODEL_NAME with the organizer.")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": DIAGNOSTIC_PROMPT}],
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}

    session = requests.Session()
    session.trust_env = False
    started = time.time()

    try:
        response = session.post(endpoint, json=payload, timeout=args.timeout, headers=headers)
    except requests.exceptions.Timeout:
        print("RESULT: TIMEOUT - endpoint did not respond in time.")
        return 1
    except requests.exceptions.ConnectionError as exc:
        print("RESULT: UNREACHABLE -", exc.__class__.__name__)
        return 1
    except requests.exceptions.RequestException as exc:
        print("RESULT: REQUEST_ERROR -", exc.__class__.__name__, str(exc)[:200])
        return 1

    elapsed = round(time.time() - started, 2)
    print("status_code=", response.status_code)
    print("elapsed_seconds=", elapsed)
    print("content_type=", response.headers.get("Content-Type"))
    print("authorization_sent=False")

    if response.status_code in (401, 403):
        print("RESULT: AUTH_ERROR - endpoint is not keyless; ask the organizer. Do not add a key.")
        return 1
    if response.status_code == 404:
        print("RESULT: NOT_FOUND - check the ENDPOINT path.")
        return 1
    if response.status_code == 429:
        print("RESULT: RATE_LIMIT - retry per organizer rules.")
        return 1
    if response.status_code >= 500:
        print("RESULT: SERVER_ERROR - retry per organizer rules.")
        return 1
    if response.status_code < 200 or response.status_code >= 300:
        print("RESULT: HTTP_ERROR - unexpected status.")
        return 1

    try:
        data = response.json()
    except ValueError:
        print("RESULT: NON_JSON_RESPONSE - response body is not JSON.")
        return 1

    if isinstance(data, dict):
        print("response_keys=", sorted(data.keys()))
    else:
        print("response_type=", type(data).__name__)
        print("RESULT: RESPONSE_SHAPE_ERROR - expected an object.")
        return 1

    content = None
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        pass

    if not isinstance(content, str) or not content.strip():
        print("RESULT: RESPONSE_SHAPE_ERROR - missing choices[0].message.content.")
        return 1

    preview = " ".join(content.strip().split())[:120]
    print("content_preview=", preview)
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())