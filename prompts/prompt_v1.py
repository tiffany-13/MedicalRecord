import json
from pathlib import Path

PROMPT_VERSION = "v1-draft"
FEW_SHOT_INJECTION_ENABLED = False

PROMPT_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_FILE = PROMPT_DIR / "system_v1.txt"
FEW_SHOT_FILE = PROMPT_DIR / "few_shot_v1.json"

_SYSTEM_PROMPT = None


def load_system_prompt():
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
    return _SYSTEM_PROMPT


def load_few_shot():
    if not FEW_SHOT_INJECTION_ENABLED:
        return []
    data = json.loads(FEW_SHOT_FILE.read_text(encoding="utf-8"))
    return data.get("examples", [])


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