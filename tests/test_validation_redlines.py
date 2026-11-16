"""七条医学红线单元测试。"""

import pytest

from src.validation import (
    _check_red_line_1, _check_red_line_2, _check_red_line_3,
    _check_red_line_4, _check_red_line_5, _check_red_line_6,
    _check_red_line_7,
)
from tests.conftest import make_valid_medical_record, make_valid_sources


class TestRedLine1:
    def test_passes_when_negation_preserved(self):
        record = make_valid_medical_record()
        sources = make_valid_sources()
        _check_red_line_1(record, sources)  # 不抛

    def test_violation_normal(self):
        record = make_valid_medical_record()
        # sources 含"未提供"，输出改成"正常"
        record["case_features"] = "血压正常，尿量正常。血红蛋白 82 g/L。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="红线1"):
            _check_red_line_1(record, sources)


class TestRedLine2:
    def test_passes_when_no_fabrication(self):
        record = make_valid_medical_record()
        sources = make_valid_sources()
        _check_red_line_2(record, sources)

    def test_violation_fabricated_exam(self):
        record = make_valid_medical_record()
        # sources 未提及"骨髓穿刺"，输出凭空补写（放在事实性字段）
        record["diagnostic_discussion"] = "骨髓穿刺提示巨幼细胞性贫血。病因待查。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="红线2"):
            _check_red_line_2(record, sources)

    def test_violation_fabricated_drug(self):
        record = make_valid_medical_record()
        record["case_features"] = "已予促红素治疗。血红蛋白 82 g/L。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="红线2"):
            _check_red_line_2(record, sources)


class TestRedLine3:
    def test_passes_when_plan_uses_suggest(self):
        record = make_valid_medical_record()
        sources = make_valid_sources()
        _check_red_line_3(record, sources)

    def test_violation_done_term(self):
        record = make_valid_medical_record()
        record["plan"] = "已予补铁治疗，已完成血常规复查。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="红线3"):
            _check_red_line_3(record, sources)


class TestRedLine4:
    def test_passes_no_future_info(self):
        record = make_valid_medical_record()
        sources = make_valid_sources()
        _check_red_line_4(record, sources)

    def test_violation_future_discharge(self):
        record = make_valid_medical_record()
        record["diagnostic_discussion"] = "出院时诊断明确为肾性贫血。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="红线4"):
            _check_red_line_4(record, sources)

    def test_violation_confirmed(self):
        record = make_valid_medical_record()
        record["diagnostic_discussion"] = "确诊为急性肾损伤。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="红线4"):
            _check_red_line_4(record, sources)


class TestRedLine5:
    def test_passes_with_uncertainty(self):
        record = make_valid_medical_record()
        sources = make_valid_sources()
        _check_red_line_5(record, sources)  # 含"病因待查"

    def test_violation_hard_conclusion(self):
        record = make_valid_medical_record()
        # 清掉所有字段的不确定性表述，加入确定结论
        record["case_features"] = "血红蛋白 82 g/L，肌酐 185 μmol/L。"
        record["diagnostic_discussion"] = "诊断为肾性贫血，明确为慢性肾功能不全所致。"
        record["plan"] = "予补铁及促红素治疗。"
        record["evidence"] = [
            {"statement": "血红蛋白 82 g/L", "source_ids": ["S03"], "kind": "fact"},
        ]
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="红线5"):
            _check_red_line_5(record, sources)

    def test_skip_when_sufficient(self):
        record = make_valid_medical_record()
        # sources 不含信息不足词（构造一个"充分"的 sources）
        sources = [
            {"source_id": "S01", "content": "血红蛋白 82 g/L，肌酐 185 μmol/L，诊断明确"},
        ]
        _check_red_line_5(record, sources)  # 不抛


class TestRedLine6:
    def test_passes_no_errors(self):
        _check_red_line_6([])

    def test_violation_with_errors(self):
        errors = [{"kind": "value_mismatch", "detail": "数值 90 g/L 未见于原始资料"}]
        with pytest.raises(ValueError, match="红线6"):
            _check_red_line_6(errors)


class TestRedLine7:
    def test_passes_with_specific_info(self):
        record = make_valid_medical_record()
        sources = make_valid_sources()
        _check_red_line_7(record, sources)  # 含 82、185 等特异数值

    def test_violation_generic(self):
        record = make_valid_medical_record()
        # 去掉所有特异数值和症状词，只留泛化套话
        record["case_features"] = "患者有症状，需进一步检查。"
        record["diagnostic_discussion"] = "对症处理，支持治疗。"
        record["plan"] = "需完善相关检查。"
        record["evidence"] = [
            {"statement": "患者有症状", "source_ids": ["S01"], "kind": "fact"},
        ]
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="红线7"):
            _check_red_line_7(record, sources)


class TestRedLineOrder:
    def test_red_line_2_before_red_line_3(self):
        """同时命中红线2与红线3，编排中红线2先判定先抛出。"""
        from src.validation import validate_record
        record = make_valid_medical_record()
        # 红线2：case_features 凭空补写骨髓穿刺；红线3：plan 含已予
        record["case_features"] = "骨髓穿刺提示巨幼细胞性贫血。血红蛋白 82 g/L。"
        record["plan"] = "已予补铁，已完成复查。"
        sources = make_valid_sources()
        with pytest.raises(ValueError, match="红线2"):
            validate_record(record, sources)
