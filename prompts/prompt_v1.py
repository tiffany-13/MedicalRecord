import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

PROMPT_VERSION = "v1-draft"
PROMPT_STATUS = "draft"
PROMPT_MAX_CHARS = 4000
FEW_SHOT_INJECTION_ENABLED = False
FEW_SHOT_MAX_CHARS = 1200

PROMPT_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_FILE = PROMPT_DIR / "system_v1.txt"
FEW_SHOT_FILE = PROMPT_DIR / "few_shot_v1.json"
CANDIDATE_FILE = PROMPT_DIR / "candidates" / "system_v1_2_candidate.txt"

_REQUIRED_FIELDS = {
    "case_features",
    "diagnostic_discussion",
    "plan",
    "evidence",
    "review_items",
}
_ASSETS_CACHE = {}


class PromptAssetError(Exception):
    def __init__(self, reason, path=None, detail=""):
        self.reason = reason
        self.path = str(path) if path else ""
        self.detail = detail
        super().__init__(reason if not detail else f"{reason}: {detail}")


@dataclass(frozen=True)
class PromptAssets:
    version: str
    status: str
    text: str
    char_count: int
    byte_count: int
    sha256: str
    file_sha256: str
    line_ending: str
    examples: tuple


def _read_text(path):
    path = Path(path)
    if not path.exists():
        raise PromptAssetError("missing", path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PromptAssetError("unreadable", path, str(exc)) from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromptAssetError("unreadable", path, str(exc)) from exc
    return raw, text


def _lf_text(text):
    return text.replace("\r\n", "\n")


def _validate_few_shot():
    _, text = _read_text(FEW_SHOT_FILE)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PromptAssetError("few_shot_shape", FEW_SHOT_FILE, str(exc)) from exc
    if data.get("version") != PROMPT_VERSION:
        raise PromptAssetError(
            "few_shot_version_mismatch", FEW_SHOT_FILE, str(data.get("version"))
        )
    examples = data.get("examples")
    if not isinstance(examples, list) or not 1 <= len(examples) <= 2:
        raise PromptAssetError("few_shot_shape", FEW_SHOT_FILE, "examples must be 1-2")
    rendered = 0
    for example in examples:
        if not isinstance(example, dict):
            raise PromptAssetError("few_shot_shape", FEW_SHOT_FILE, "example is not an object")
        if not isinstance(example.get("case_input"), str) or not example["case_input"]:
            raise PromptAssetError("few_shot_shape", FEW_SHOT_FILE, "case_input")
        expected = example.get("expected_output")
        if not isinstance(expected, dict) or set(expected) != _REQUIRED_FIELDS:
            raise PromptAssetError("few_shot_shape", FEW_SHOT_FILE, "expected_output fields")
        if not isinstance(expected.get("evidence"), list):
            raise PromptAssetError("few_shot_shape", FEW_SHOT_FILE, "evidence")
        if not isinstance(expected.get("review_items"), list):
            raise PromptAssetError("few_shot_shape", FEW_SHOT_FILE, "review_items")
        rendered += len(json.dumps(example, ensure_ascii=False))
    if rendered > FEW_SHOT_MAX_CHARS:
        raise PromptAssetError("few_shot_shape", FEW_SHOT_FILE, f"rendered={rendered}")
    return tuple(examples)


def load_assets(path=None):
    target = Path(path) if path else SYSTEM_PROMPT_FILE
    key = str(target.resolve())
    if key in _ASSETS_CACHE:
        return _ASSETS_CACHE[key]
    raw, text = _read_text(target)
    lf = _lf_text(text)
    if not lf.strip():
        raise PromptAssetError("empty", target)
    char_count = len(lf)
    if char_count > PROMPT_MAX_CHARS:
        raise PromptAssetError("over_budget", target, f"{char_count}>{PROMPT_MAX_CHARS}")
    encoded = lf.encode("utf-8")
    if b"\r\n" in raw:
        line_ending = "crlf"
    elif b"\n" in raw:
        line_ending = "lf"
    else:
        line_ending = "none"
    assets = PromptAssets(
        version=PROMPT_VERSION,
        status=PROMPT_STATUS,
        text=lf,
        char_count=char_count,
        byte_count=len(encoded),
        sha256=hashlib.sha256(encoded).hexdigest(),
        file_sha256=hashlib.sha256(raw).hexdigest(),
        line_ending=line_ending,
        examples=_validate_few_shot(),
    )
    _ASSETS_CACHE[key] = assets
    return assets


def load_system_prompt():
    return load_assets().text


def load_few_shot():
    if not FEW_SHOT_INJECTION_ENABLED:
        return []
    return list(load_assets().examples)


def build_user_content(case_id, record_cutoff, sources):
    lines = [f"病例编号：{case_id}", f"记录截止时间：{record_cutoff}", "", "资料如下："]
    for source in sources:
        lines.append(f"[{source['source_id']}] {source['content']}")
    return "\n".join(lines)


def build_messages(case_id, record_cutoff, sources):
    messages = [{"role": "system", "content": load_system_prompt()}]
    for example in load_few_shot():
        messages.append({"role": "user", "content": example["case_input"]})
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(example["expected_output"], ensure_ascii=False),
            }
        )
    messages.append(
        {
            "role": "user",
            "content": build_user_content(case_id, record_cutoff, sources),
        }
    )
    return messages


def prompt_char_count():
    return load_assets().char_count


def assert_candidate_not_runtime():
    if CANDIDATE_FILE.resolve() == SYSTEM_PROMPT_FILE.resolve():
        raise PromptAssetError("candidate_is_runtime", CANDIDATE_FILE)
    if not CANDIDATE_FILE.exists():
        raise PromptAssetError("missing", CANDIDATE_FILE)
    return True


def reset_cache():
    _ASSETS_CACHE.clear()