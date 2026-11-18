import pytest
import main

import src.api_client as api
import src.run_config as run_config


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    response = None
    captured = None
    post_count = 0

    def __init__(self):
        self.trust_env = True

    def post(self, endpoint, json, timeout, headers):
        FakeSession.post_count += 1
        FakeSession.captured = {"endpoint": endpoint, "json": json, "headers": headers}
        return FakeSession.response


@pytest.fixture(autouse=True)
def reset_envelope(monkeypatch):
    run_config.start_run()
    monkeypatch.setattr(api, "_CONFIG", ("test-model", "http://fixture.invalid"))
    monkeypatch.setattr(api.requests, "Session", FakeSession)
    api.RUN_LOGS.clear()
    monkeypatch.setattr(run_config, "SEED", 42)
    monkeypatch.setattr(run_config, "TEMPERATURE", 0.1)
    monkeypatch.setattr(run_config, "RESPONSE_FORMAT", None)
    monkeypatch.setattr(run_config, "THINKING", "server-default")
    FakeSession.captured = None
    FakeSession.post_count = 0


def test_accepted_parameter_is_payload_and_log(monkeypatch):
    monkeypatch.setattr(run_config, "RESPONSE_FORMAT", run_config.JSON_OBJECT_RESPONSE_FORMAT)
    monkeypatch.setattr(run_config, "THINKING", "disabled")
    FakeSession.response = FakeResponse(
        payload={"choices": [{"message": {"content": "ok"}}]}
    )

    assert api.call_llm("C1", [{"role": "user", "content": "test"}], retries=1) == "ok"

    payload = FakeSession.captured["json"]
    assert payload["model"] == "test-model"
    assert payload["messages"][0]["role"] == "user"
    assert payload["stream"] is False
    assert payload["seed"] == 42
    assert payload["temperature"] == 0.1
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert "Authorization" not in FakeSession.captured["headers"]
    assert api.RUN_LOGS[0]["run_id"]
    status = api.RUN_LOGS[0]["parameter_status"]
    assert status["seed"]["endpoint"] == "accepted-on-endpoint"
    assert status["temperature"]["endpoint"] == "accepted-on-endpoint"

    main.add_run_log_metadata()
    assert api.RUN_LOGS[0]["prompt_version"] == "v1-draft"
    assert "parameter_status" in api.RUN_LOGS[0]


def test_rejected_parameter_fails_visibly(monkeypatch):
    FakeSession.response = FakeResponse(
        status_code=400,
        text='{"error":{"message":"Unsupported parameter: temperature"}}',
    )

    with pytest.raises(api.ParameterRejectedError) as exc:
        api.call_llm("C1", [{"role": "user", "content": "test"}], retries=3)

    assert exc.value.code == "PARAMETER_REJECTED"
    assert "temperature" in str(exc.value)
    assert FakeSession.post_count == 1
    assert api.RUN_LOGS[-1]["error_code"] == "PARAMETER_REJECTED"
    assert api.RUN_LOGS[-1]["parameter_status"]["temperature"]["endpoint"] == "rejected-on-endpoint"


def test_omitted_parameters_are_not_sent(monkeypatch):
    monkeypatch.setattr(run_config, "SEED", None)
    monkeypatch.setattr(run_config, "TEMPERATURE", None)
    monkeypatch.setattr(run_config, "RESPONSE_FORMAT", None)
    monkeypatch.setattr(run_config, "THINKING", "server-default")
    FakeSession.response = FakeResponse(
        payload={"choices": [{"message": {"content": "ok"}}]}
    )

    api.call_llm("C1", [{"role": "user", "content": "test"}], retries=1)

    payload = FakeSession.captured["json"]
    assert set(payload) == {"model", "messages", "stream"}
    status = api.RUN_LOGS[0]["parameter_status"]
    assert status["seed"]["endpoint"] == "not-sent"
    assert status["temperature"]["endpoint"] == "not-sent"
    assert status["response_format"]["endpoint"] == "withheld-pending-acceptance"
    assert status["thinking"]["endpoint"] == "not-sent"
