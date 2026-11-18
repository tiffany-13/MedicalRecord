"""测试共享夹具：构造合规的 medical_record 与 original_sources。"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def make_valid_medical_record():
    """构造一份完整合规的 medical_record（参照 api_client.mock_llm_success）。"""
    return {
        "case_features": (
            "成人，近2周乏力、活动后心悸，现有记录显示结膜苍白和双下肢轻度水肿。"
            "血红蛋白 82 g/L、肌酐 185 μmol/L。"
            "现有记录未见明确出血表现；血压和尿量不详。"
        ),
        "diagnostic_discussion": (
            "现有资料支持贫血及肾功能异常。贫血需结合红细胞指数等进一步分析，"
            "不能排除隐匿失血；单次肌酐升高不足以确定急慢性过程，"
            "不能直接归因为肾性贫血。病因待查。"
        ),
        "plan": (
            "建议临床医生补充既往检查、用药史，核实血压和容量状态；"
            "拟复查血常规及肾功能，按鉴别需要安排进一步检查。观察症状和指标变化。"
        ),
        "evidence": [
            {
                "statement": "近 2 周乏力、活动后心悸",
                "source_ids": ["S01"],
                "kind": "fact",
            },
            {
                "statement": "血红蛋白 82 g/L，肌酐 185 μmol/L",
                "source_ids": ["S03"],
                "kind": "fact",
            },
            {
                "statement": "血压、尿量及既往肾功能资料未提供，急慢性过程及贫血原因尚不能确定",
                "source_ids": ["S02", "S03", "S04"],
                "kind": "inference",
            },
        ],
        "review_items": [
            "既往肾功能及贫血病程",
            "血压、尿量及用药史",
        ],
    }


def make_valid_sources():
    """构造 DEMO001 的 sources。"""
    return [
        {"source_id": "S01", "content": "成人，乏力2周，活动后心悸；现有记录未见明确黑便、肉眼血尿或其他出血表现"},
        {"source_id": "S02", "content": "结膜苍白、双下肢轻度水肿；未提供血压、尿量及其他体征"},
        {"source_id": "S03", "content": "血红蛋白82g/L，实验室标低；肌酐185μmol/L，实验室标高；未提供既往肌酐、红细胞指数、网织红细胞或尿检"},
        {"source_id": "S04", "content": "既往病史、药物史、肾功能基线和贫血既往检查未提供；入院初步判断为贫血及肾功能异常，原因待查"},
    ]
