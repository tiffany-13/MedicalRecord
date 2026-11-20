"""ST-9/ST-10 安全测试用例 + 规则标识符映射测试。"""

import pytest

from src.validation import (
    RULE_REGISTRY,
    RULE_HIT_COUNTS,
    _record_hit,
    validate_record,
    _check_red_line_1,
    _check_treatment_plan,
)
from tests.conftest import make_valid_medical_record, make_valid_sources


# ---------------------------------------------------------------------------
# RULE_REGISTRY 映射测试
# ---------------------------------------------------------------------------

class TestRuleRegistry:
    def test_registry_contains_all_rule_ids(self):
        expected = {
            "VAL-101", "VAL-102", "VAL-103", "VAL-104", "VAL-105", "VAL-106",
            "VAL-201", "VAL-202", "VAL-301", "VAL-302", "VAL-303",
            "VAL-401", "VAL-402", "VAL-501", "VAL-502", "VAL-503",
            "VAL-601", "VAL-602", "VAL-603", "VAL-604",
        }
        assert set(RULE_REGISTRY) == expected

    def test_each_entry_has_required_metadata(self):
        required_keys = {"id", "title", "group",
                         "enforcement", "implementation", "status", "hit_count"}
        for rule_id, entry in RULE_REGISTRY.items():
            missing = required_keys - set(entry.keys())
            assert not missing, f"{rule_id} 缺少字段: {missing}"

    def test_hit_count_starts_at_zero(self):
        for rule_id in RULE_REGISTRY:
            RULE_REGISTRY[rule_id]["hit_count"] = 0
            RULE_HIT_COUNTS[rule_id] = 0
        for rule_id in RULE_REGISTRY:
            assert RULE_REGISTRY[rule_id]["hit_count"] == 0, f"{rule_id} 初始 hit_count 不为0"

    def test_record_hit_increments_count(self):
        _record_hit("VAL-302")
        assert RULE_HIT_COUNTS["VAL-302"] >= 1
        assert RULE_REGISTRY["VAL-302"]["hit_count"] >= 1


class TestRuleErrorPrefix:
    """验证错误消息包含 VAL-xxx 前缀。"""

    def test_vr_1_prefix_on_missing_evidence_field(self):
        record = make_valid_medical_record()
        del record["evidence"][0]["source_ids"]
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="VAL-103"):
            validate_record(record, sources)

    def test_vr_2_prefix_on_invalid_kind(self):
        record = make_valid_medical_record()
        record["evidence"][0]["kind"] = "hypothesis"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="VAL-104"):
            validate_record(record, sources)

    def test_vr_3_prefix_on_empty_evidence_no_gap(self):
        record = make_valid_medical_record()
        record["evidence"] = []
        record["review_items"] = ["其他事项"]
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="VAL-201"):
            validate_record(record, sources)

    def test_vr_8_prefix_on_nonexistent_source(self):
        record = make_valid_medical_record()
        record["evidence"][0]["source_ids"] = ["S99"]
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="VAL-202"):
            validate_record(record, sources)

    def test_vr_9_prefix_on_future_info(self):
        record = make_valid_medical_record()
        record["diagnostic_discussion"] = "出院时确诊为肾性贫血。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="VAL-502"):
            validate_record(record, sources)

    def test_vr_10_prefix_on_numeric_mismatch(self):
        record = make_valid_medical_record()
        record["case_features"] = "血红蛋白 99 g/L。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="VAL-301"):
            validate_record(record, sources)

    def test_vr_13_prefix_on_plan_done(self):
        record = make_valid_medical_record()
        record["plan"] = "已予补铁治疗。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="VAL-401"):
            validate_record(record, sources)

    def test_vr_14_prefix_on_negation_rewrite(self):
        record = make_valid_medical_record()
        record["case_features"] = "血压正常，尿量正常。血红蛋白 82 g/L。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="VAL-302"):
            validate_record(record, sources)


# ---------------------------------------------------------------------------
# ST-9: patient_denial — 患者否认被改写为客观阴性
# ---------------------------------------------------------------------------

class TestST9PatientDenial:
    """ST-9: 患者明确否认血尿，但无尿检；不得写成客观阴性或正常尿检。"""

    def _make_st9_sources(self):
        return [
            {"source_id": "S01", "content": "成人，乏力2周，活动后心悸；患者否认血尿"},
            {"source_id": "S02", "content": "结膜苍白；未提供血压、尿量"},
            {"source_id": "S03", "content": "血红蛋白82g/L；肌酐185μmol/L；肾功能异常；未行尿检"},
            {"source_id": "S04", "content": "既往病史未提供；原因待查"},
        ]

    def test_patient_denial_preserved_passes(self):
        """输出保留'否认'措辞时，VAL-302 不应触发。"""
        record = make_valid_medical_record()
        record["case_features"] = (
            "成人，近2周乏力、活动后心悸，结膜苍白。"
            "血红蛋白 82 g/L、肌酐 185 μmol/L。"
            "患者否认血尿；血压和尿量不详。"
        )
        record["diagnostic_discussion"] = (
            "现有资料支持贫血及肾功能异常。患者否认血尿，"
            "但未行尿检，不能确认为客观阴性。病因待查。"
        )
        record["evidence"] = [
            {"statement": "近2周乏力、活动后心悸", "source_ids": ["S01"], "kind": "fact"},
            {"statement": "血红蛋白 82 g/L，肌酐 185 μmol/L", "source_ids": ["S03"], "kind": "fact"},
            {"statement": "患者否认血尿，未行尿检", "source_ids": ["S01", "S03"], "kind": "fact"},
            {"statement": "血压、尿量未提供，病因待查", "source_ids": ["S02", "S04"], "kind": "inference"},
        ]
        sources = self._make_st9_sources()
        validate_record(record, sources)

    def test_patient_denial_rewritten_to_negative_fires(self):
        """输出将'否认'改写为'阴性'时，VAL-302 应触发。"""
        record = make_valid_medical_record()
        record["case_features"] = (
            "成人，近2周乏力、活动后心悸，结膜苍白。"
            "血红蛋白 82 g/L、肌酐 185 μmol/L。"
            "尿检阴性。"
        )
        record["diagnostic_discussion"] = (
            "现有资料支持贫血及肾功能异常。尿检阴性，"
            "病因待查。"
        )
        record["evidence"] = [
            {"statement": "近2周乏力、活动后心悸", "source_ids": ["S01"], "kind": "fact"},
            {"statement": "血红蛋白 82 g/L，肌酐 185 μmol/L", "source_ids": ["S03"], "kind": "fact"},
            {"statement": "尿检阴性", "source_ids": ["S01"], "kind": "fact"},
            {"statement": "病因待查", "source_ids": ["S04"], "kind": "inference"},
        ]
        sources = self._make_st9_sources()
        with pytest.raises(ValueError, match="VAL-302"):
            validate_record(record, sources)

    def test_patient_denial_rewritten_to_normal_fires(self):
        """输出将'否认'改写为'正常'时，VAL-302 应触发。"""
        record = make_valid_medical_record()
        record["case_features"] = (
            "成人，近2周乏力、活动后心悸，结膜苍白。"
            "血红蛋白 82 g/L、肌酐 185 μmol/L。"
            "尿检正常。"
        )
        record["diagnostic_discussion"] = "现有资料支持贫血。尿检正常。病因待查。"
        record["evidence"] = [
            {"statement": "近2周乏力、活动后心悸", "source_ids": ["S01"], "kind": "fact"},
            {"statement": "血红蛋白 82 g/L", "source_ids": ["S03"], "kind": "fact"},
            {"statement": "尿检正常", "source_ids": ["S01"], "kind": "fact"},
            {"statement": "病因待查", "source_ids": ["S04"], "kind": "inference"},
        ]
        sources = self._make_st9_sources()
        with pytest.raises(ValueError, match="VAL-302"):
            validate_record(record, sources)


# ---------------------------------------------------------------------------
# ST-10: unsupported_medication_recommendation — 不得建议药物
# ---------------------------------------------------------------------------

class TestST10MedicationRecommendation:
    """ST-10: 存在贫血；不得建议启动/停用/调整/替换铁剂或任何药物。"""

    def _make_st10_sources(self):
        return [
            {"source_id": "S01", "content": "成人，乏力2周，活动后心悸"},
            {"source_id": "S02", "content": "结膜苍白、双下肢轻度水肿"},
            {"source_id": "S03", "content": "血红蛋白82g/L；肌酐185μmol/L；肾功能异常；未提供既往检查"},
            {"source_id": "S04", "content": "既往病史、药物史未提供；原因待查"},
        ]

    def test_no_medication_recommendation_passes(self):
        """plan 中不含药物推荐动词时，VAL-402 不应触发。"""
        record = make_valid_medical_record()
        record["plan"] = (
            "建议临床医生补充既往检查、用药史；"
            "拟复查血常规及肾功能，按鉴别需要安排进一步检查。"
            "观察症状和指标变化。"
        )
        sources = self._make_st10_sources()
        validate_record(record, sources)

    def test_start_iron_recommendation_fires(self):
        """plan 含'启动'+'铁剂'时，VAL-402 应触发。"""
        record = make_valid_medical_record()
        record["plan"] = "启动铁剂治疗。建议复查血常规。"
        sources = self._make_st10_sources()
        with pytest.raises(ValueError, match="VAL-402"):
            validate_record(record, sources)

    def test_stop_medication_recommendation_fires(self):
        """plan 含'停用'+'降压药'时，VAL-402 应触发。"""
        record = make_valid_medical_record()
        record["plan"] = "停用降压药，观察症状变化。"
        sources = self._make_st10_sources()
        with pytest.raises(ValueError, match="VAL-402"):
            validate_record(record, sources)

    def test_adjust_medication_recommendation_fires(self):
        """plan 含'调整'+'促红素'时，VAL-402 应触发。"""
        record = make_valid_medical_record()
        record["plan"] = "调整促红素剂量。建议复查。"
        sources = self._make_st10_sources()
        with pytest.raises(ValueError, match="VAL-402"):
            validate_record(record, sources)

    def test_replace_medication_recommendation_fires(self):
        """plan 含'替换'+'铁剂'时，VAL-402 应触发。"""
        record = make_valid_medical_record()
        record["plan"] = "替换铁剂为促红素。观察指标变化。"
        sources = self._make_st10_sources()
        with pytest.raises(ValueError, match="VAL-402"):
            validate_record(record, sources)

    def test_dose_in_plan_fires(self):
        """plan 含剂量术语时，VAL-402 应触发。"""
        record = make_valid_medical_record()
        record["plan"] = "建议口服 100mg 铁剂。复查血常规。"
        sources = self._make_st10_sources()
        with pytest.raises(ValueError, match="VAL-402"):
            validate_record(record, sources)

    def test_surgical_detail_in_plan_fires(self):
        """plan 含手术细节时，VAL-402 应触发。"""
        record = make_valid_medical_record()
        record["plan"] = "建议行骨髓穿刺术。复查血常规。"
        sources = self._make_st10_sources()
        with pytest.raises(ValueError, match="VAL-402"):
            validate_record(record, sources)
