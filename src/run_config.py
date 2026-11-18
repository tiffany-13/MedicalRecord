"""Per-run request-parameter envelope (single source of truth).

One envelope applies to every case of a run. Values are constants in this
module, not read from .env: .env.example carries only MODEL_NAME and ENDPOINT.

Status vocabulary used in parameter_status (and nowhere else):
  documented                  the organizer's Q&A describes the capability
  pending                     the endpoint's acceptance has not been observed
  accepted-on-endpoint        a dated observation exists (never set by code here)
  rejected-on-endpoint        the endpoint returned a parameter-class rejection
  not-sent                    the field is not placed in the request
  withheld-pending-acceptance the field is prepared but held back until accepted

A fixed seed is a variance-reduction aid only. It does not make the generated
text identical across runs or environments.
"""

import copy
import threading
import uuid

# --- Envelope values --------------------------------------------------------

# Request-level integer, sent at the top level of the JSON body.
SEED = 42
TEMPERATURE = 0.1
# None = not sent (withheld-pending-acceptance). Switch to
# JSON_OBJECT_RESPONSE_FORMAT only after a recorded decision. It constrains
# syntax only; the five-field schema and red lines are unchanged by it.
RESPONSE_FORMAT = None
JSON_OBJECT_RESPONSE_FORMAT = {"type": "json_object"}
# "server-default": send nothing, the server's configured mode applies.
# "disabled": send chat_template_kwargs.enable_thinking = false.
THINKING = "server-default"
STREAM = False
# No cache marker is ever placed in a request.
PREFIX_CACHE_MARKER = "none"

STATUS_VOCABULARY = (
    "documented",
    "pending",
    "accepted-on-endpoint",
    "rejected-on-endpoint",
    "not-sent",
    "withheld-pending-acceptance",
)

_THINKING_MODES = ("server-default", "disabled")

# Names an endpoint error may use for each parameter.
_PARAM_ALIASES = {
    "chat_template_kwargs": "thinking",
    "enable_thinking": "thinking",
}

_LOCK = threading.Lock()
_RUN_ID = None
_OBSERVED = {}


# --- Run identity -----------------------------------------------------------

def start_run():
    """Begin a run: new run_id, observations cleared. Returns the run_id."""
    global _RUN_ID
    with _LOCK:
        _RUN_ID = uuid.uuid4().hex[:12]
        _OBSERVED.clear()
        return _RUN_ID


def get_run_id():
    with _LOCK:
        run_id = _RUN_ID
    return run_id if run_id is not None else start_run()


def record_rejection(field):
    """Record an observed parameter-class rejection for a request field."""
    param = _PARAM_ALIASES.get(field, field)
    with _LOCK:
        _OBSERVED[param] = "rejected-on-endpoint"


# --- Envelope views ---------------------------------------------------------

def request_parameters():
    """Top-level body fields contributed by the envelope (model/messages excluded)."""
    if THINKING not in _THINKING_MODES:
        raise ValueError(f"THINKING must be one of {_THINKING_MODES}, got {THINKING!r}")
    params = {"stream": STREAM}
    if SEED is not None:
        params["seed"] = SEED
    if TEMPERATURE is not None:
        params["temperature"] = TEMPERATURE
    if RESPONSE_FORMAT is not None:
        params["response_format"] = copy.deepcopy(RESPONSE_FORMAT)
    if THINKING == "disabled":
        params["chat_template_kwargs"] = {"enable_thinking": False}
    return params


def _endpoint_state(param, sent, withheld=False):
    with _LOCK:
        observed = _OBSERVED.get(param)
    if observed is not None:
        return observed
    if not sent:
        return "withheld-pending-acceptance" if withheld else "not-sent"
    return "pending"


def parameter_status():
    """Per-parameter capability and endpoint status, vocabulary-restricted."""
    return {
        "seed": {
            "capability": "documented",
            "endpoint": _endpoint_state("seed", SEED is not None),
            "value": SEED,
        },
        "temperature": {
            "capability": "documented",
            "endpoint": _endpoint_state("temperature", TEMPERATURE is not None),
            "value": TEMPERATURE,
        },
        "response_format": {
            "capability": "documented",
            "endpoint": _endpoint_state(
                "response_format", RESPONSE_FORMAT is not None, withheld=True
            ),
            "value": copy.deepcopy(RESPONSE_FORMAT),
        },
        "thinking": {
            "capability": "documented",
            "endpoint": _endpoint_state("thinking", THINKING == "disabled"),
            "value": THINKING,
        },
        "stream": {
            "capability": "documented",
            "endpoint": _endpoint_state("stream", True),
            "value": STREAM,
        },
        "prefix_cache_marker": {
            "capability": "documented",
            "endpoint": "not-sent",
            "value": PREFIX_CACHE_MARKER,
        },
    }


def envelope_summary():
    """Compact envelope for run-log entries. No prompt, case text or secret."""
    return {
        "run_id": get_run_id(),
        "seed": SEED,
        "temperature": TEMPERATURE,
        "response_format": copy.deepcopy(RESPONSE_FORMAT),
        "thinking": THINKING,
        "stream": STREAM,
        "prefix_cache_marker": PREFIX_CACHE_MARKER,
    }


def envelope_for_log():
    """Full envelope: summary plus per-parameter status."""
    envelope = envelope_summary()
    envelope["parameter_status"] = parameter_status()
    return envelope
