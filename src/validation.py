"""
病程记录校验组件（C 角色）。

对外仅暴露 validate_record(medical_record, original_sources)：
  校验通过 -> 直接 return
  校验失败 -> raise ValueError("错误原因")

编排顺序：Schema -> 溯源 -> 数值回溯(收集) -> 红线1..5 -> 红线6(汇总) -> 红线7
首个命中即抛出，纯标准库实现，不修改入参。
"""

import re


# 赛规校验规则标识。内部检测保留原有红线编号，同时暴露稳定规则 ID。
VR_RULE_IDS = {
    "schema": "VR-1",
    "source_trace": "VR-2",
    "negation": "VR-14",
    "fabrication": "VR-8",
    "plan_done": "VR-13",
    "specific_medication": "VR-5",
    "timing": "VR-9",
    "insufficient": "VR-7",
    "numeric": "VR-10",
    "patient_denial": "VR-11",
    "generic": "VR-15",
}


# ---------------------------------------------------------------------------
# 一、模块级常量
# ---------------------------------------------------------------------------

# medical_record 固定五字段
REQUIRED_FIELDS = (
    "case_features",
    "diagnostic_discussion",
    "plan",
    "evidence",
    "review_items",
)

# evidence 条数约束：至少 1 条，建议不超过 5 条
EVIDENCE_MIN = 1
EVIDENCE_SUGGEST_MAX = 5

# 违规片段截断长度，错误信息中引用的片段不超过该长度
MAX_SNIPPET_LEN = 50

# 数值+单位提取正则：匹配"数值 + 常见医学单位"，单位含中文与英文混合
# 示例：82 g/L、185 μmol/L、3.5×10^12/L、120 mmHg
NUMERIC_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?(?:[×x]\d+\^?\d+)?)"
    r"\s*"
    r"(?P<unit>g/L|mg/dL|mmol/L|μmol/L|umol/L|×10\^?\d+/L|10\^?\d+/L|"
    r"mmHg|cmH2O|kPa|U/L|IU/L|ng/mL|μg/L|ug/L|pg/mL|"
    r"mmol/L|mol/L|%|mmol/L|g/dL|mg/L|"
    r"次/分|次/min|bpm|"
    r"cm|mm|kg|g|mg|μg|ug|ng|"
    r"L|mL|dL|μL|uL|"
    r"°C|度|"
    r"mmol/mmol|"
    r"fl|fL|pg|"
    r"万|亿|/|"
    r"mmHg|cmH2O)"
)

# 方向/阴阳性标签集合，用于检测标签错位
DIRECTION_TAGS = ("标低", "标高", "阳性", "阴性", "升高", "降低", "偏高", "偏低")

# 方向标签同义组：同组内任一词在 sources 出现，生成文本用同组其他词视为合法
DIRECTION_SYNONYMS = (
    {"标高", "升高", "偏高"},
    {"标低", "降低", "偏低"},
    {"阳性"},
    {"阴性"},
)


def _direction_allowed(tag, source_tags):
    """判断生成文本中的方向标签是否在 sources 中有同义表达。"""
    if tag in source_tags:
        return True
    for group in DIRECTION_SYNONYMS:
        if tag in group and group & source_tags:
            return True
    return False

# 红线1：否定关系词表（原文出现这些词时，输出不得改成肯定表述）
NEGATION_TERMS = ("未", "未见", "未提供", "未发现", "无", "不详", "缺乏", "缺如", "未查")
# 红线1：肯定表述词表（若原文为否定，输出出现这些词视为改写）
AFFIRMATION_TERMS = ("正常", "否认", "无异常", "未见异常", "(-)", "阴性")

# 红线2：凭空补写检测的检查/病史/用药/操作关键词（命中且不在 sources 中视为补写）
# 这里用一个较保守的常见检查项词表，避免误判
KNOWN_EXAM_TERMS = (
    "血常规", "尿常规", "便常规", "肝功能", "肾功能", "电解质", "凝血",
    "心电图", "胸片", "胸部CT", "腹部B超", "腹部CT", "心脏彩超",
    "骨髓穿刺", "骨髓涂片", "网织红细胞", "铁代谢", "铁蛋白",
    "甲功", "肿瘤标志物", "免疫固定电泳", "蛋白电泳",
)
KNOWN_DRUG_TERMS = (
    "输血", "补铁", "促红素", "EPO", "利尿剂", "降压药",
    "抗生素", "激素", "免疫抑制剂", "化疗",
)

# 红线3：计划写成已实施的关键词
PLAN_DONE_TERMS = ("已予", "已完成", "已行", "已给", "已做", "已用", "已实施", "已执行")

# 红线4：时序颠倒/提前引入后续信息的标志词
FUTURE_INFO_TERMS = ("出院", "出院时", "出院诊断", "确诊", "确诊为", "随访", "出院后", "复查确诊")
# 常见时间词，用于简单时序检查
TIME_ORDER_TERMS = ("入院时", "入院前", "2周", "1周", "3天", "1天", "数天", "数周", "既往")

# 红线5：信息不足标志词（sources 出现时，输出应含不确定性表述）
INSUFFICIENT_TERMS = ("待查", "未提供", "不详", "缺乏", "未查", "资料不足", "未明确")
# 红线5：不确定性表述词（输出中应至少出现一个）
UNCERTAINTY_TERMS = (
    "需进一步检查", "需进一步检查明确", "病因待查", "原因待查",
    "尚不能确定", "不能确定", "不能排除", "尚不明确", "有待明确",
    "需完善", "需补充", "建议进一步",
)
# 红线5：确定结论标志词（输出出现这些且无不确定性表述时视为硬下结论）
DEFINITIVE_TERMS = ("确诊", "诊断为", "明确为", "就是", "即是", "确定是")

# 红线7：泛化套话模板片段（命中且无本例特异信息时判定）
GENERIC_PHRASES = (
    "患者有症状，需进一步检查",
    "需完善相关检查",
    "对症处理",
    "支持治疗",
)


# ---------------------------------------------------------------------------
# 二、辅助工具函数
# ---------------------------------------------------------------------------

def _truncate_snippet(text):
    """截断违规片段，避免错误信息过长。"""
    if not isinstance(text, str):
        return ""
    if len(text) <= MAX_SNIPPET_LEN:
        return text
    return text[:MAX_SNIPPET_LEN] + "…"


def _rule_error(rule_key, red_line, detail):
    rule_id = VR_RULE_IDS[rule_key]
    return ValueError(f"[{rule_id}] {red_line}: {detail}")


def _log_debug(rule_name, detail):
    """输出统一格式的调试日志，便于排错。"""
    print(f"[validation] {rule_name}: {detail}")


def _extract_numbers(text):
    """从文本中提取所有"数值+单位"组合，返回结构化 token 列表。

    每项为 dict: {"value": str, "unit": str, "span": (start, end)}
    """
    if not isinstance(text, str) or not text:
        return []
    results = []
    for match in NUMERIC_PATTERN.finditer(text):
        results.append({
            "value": match.group("value"),
            "unit": match.group("unit"),
            "span": match.span(),
        })
    return results


def _all_text_values(medical_record):
    """收集 medical_record 中所有字符串值（含 evidence.statement、review_items）。"""
    texts = []
    for field in ("case_features", "diagnostic_discussion", "plan"):
        value = medical_record.get(field)
        if isinstance(value, str):
            texts.append(value)
    for item in medical_record.get("evidence", []) or []:
        if isinstance(item, dict):
            stmt = item.get("statement")
            if isinstance(stmt, str):
                texts.append(stmt)
    for item in medical_record.get("review_items", []) or []:
        if isinstance(item, str):
            texts.append(item)
    return texts


def _joined_sources_text(original_sources):
    """拼接所有 sources 的 content，用于比对。"""
    parts = []
    for source in original_sources or []:
        if isinstance(source, dict):
            content = source.get("content")
            if isinstance(content, str):
                parts.append(content)
    return "".join(parts)


# ---------------------------------------------------------------------------
# 三、Schema 结构校验（spec 5.1）
# ---------------------------------------------------------------------------

def _check_schema(medical_record):
    """校验 medical_record 的结构与类型。"""
    if not isinstance(medical_record, dict):
        raise ValueError("medical_record 必须为对象")

    # 1. 五字段存在性
    for field in REQUIRED_FIELDS:
        if field not in medical_record:
            raise ValueError(f"缺少字段: {field}")

    # 2. 额外字段检测
    for key in medical_record:
        if key not in REQUIRED_FIELDS:
            raise ValueError(f"额外字段: {key}")

    # 3. 三段正文类型与非空
    for field in ("case_features", "diagnostic_discussion", "plan"):
        value = medical_record[field]
        if not isinstance(value, str):
            raise ValueError(f"{field} 必须为字符串")
        if not value.strip():
            raise ValueError(f"{field} 非空")

    # 4. evidence 嵌套结构
    evidence = medical_record["evidence"]
    if not isinstance(evidence, list):
        raise ValueError("evidence 必须为数组")
    for i, item in enumerate(evidence):
        if not isinstance(item, dict):
            raise ValueError(f"evidence[{i}] 必须为对象")
        # 4a. 三字段存在性
        for sub_field in ("statement", "source_ids", "kind"):
            if sub_field not in item:
                raise ValueError(f"evidence[{i}] 缺少字段: {sub_field}")
        # 4b. 额外字段
        for key in item:
            if key not in ("statement", "source_ids", "kind"):
                raise ValueError(f"evidence[{i}] 额外字段: {key}")
        # 4c. statement 非空字符串
        stmt = item["statement"]
        if not isinstance(stmt, str) or not stmt.strip():
            raise ValueError(f"evidence[{i}] statement 非空字符串")
        # 4d. source_ids 非空字符串数组
        source_ids = item["source_ids"]
        if not isinstance(source_ids, list) or not source_ids:
            raise ValueError(f"evidence[{i}] source_ids 非空数组")
        for sid in source_ids:
            if not isinstance(sid, str) or not sid.strip():
                raise ValueError(f"evidence[{i}] source_ids 元素必须为非空字符串")
        # 4e. kind 取值
        if item["kind"] not in ("fact", "inference"):
            raise ValueError(f"evidence[{i}] kind 取值非法")

    # 5. review_items 结构
    review_items = medical_record["review_items"]
    if not isinstance(review_items, list):
        raise ValueError("review_items 必须为数组")
    for i, item in enumerate(review_items):
        if not isinstance(item, str):
            raise ValueError(f"review_items[{i}] 必须为字符串")

    # 6. 代码围栏扫描
    for text in _all_text_values(medical_record):
        if "```" in text:
            raise ValueError("代码围栏: 输出含 Markdown 代码围栏")

    _log_debug("schema", "结构校验通过")


# ---------------------------------------------------------------------------
# 四、source_ids 溯源校验（spec 5.2）
# ---------------------------------------------------------------------------

def _check_source_trace(medical_record, original_sources):
    """校验 evidence[].source_ids 均来自当前病例。"""
    # 收集当前病例所有合法 source_id
    valid_ids = set()
    for source in original_sources or []:
        if isinstance(source, dict):
            sid = source.get("source_id")
            if isinstance(sid, str) and sid.strip():
                valid_ids.add(sid)

    evidence = medical_record.get("evidence", []) or []

    # 1. evidence 条数
    if len(evidence) < EVIDENCE_MIN:
        raise ValueError("evidence 至少 1 条")
    if len(evidence) > EVIDENCE_SUGGEST_MAX:
        _log_debug("source_trace", f"evidence 条数偏多: {len(evidence)}")

    # 2. source_ids 子集校验
    for i, item in enumerate(evidence):
        for sid in item.get("source_ids", []) or []:
            if sid not in valid_ids:
                raise ValueError(f"来源不存在: {sid}")

    _log_debug("source_trace", f"溯源校验通过，合法来源 {len(valid_ids)} 个")


# ---------------------------------------------------------------------------
# 五、数值回溯校验（spec 5.3）—— 收集错误，不直接抛出
# ---------------------------------------------------------------------------

def _check_numeric_trace(medical_record, original_sources):
    """比对生成文本与 sources 中的数值，返回错误列表（不抛出）。

    每项错误为 dict: {"kind": str, "detail": str}
    """
    errors = []

    # sources 中的数值集合（基准）
    sources_text = _joined_sources_text(original_sources)
    source_numbers = _extract_numbers(sources_text)
    # 数值字符串集合，用于快速判定"数值是否在 sources 中出现过"
    source_value_set = {n["value"] for n in source_numbers}
    # 数值+单位组合集合
    source_pair_set = {(n["value"], n["unit"]) for n in source_numbers}

    # 生成文本中的数值
    for field in ("case_features", "diagnostic_discussion", "plan"):
        text = medical_record.get(field, "")
        if not isinstance(text, str):
            continue
        gen_numbers = _extract_numbers(text)
        for n in gen_numbers:
            value = n["value"]
            unit = n["unit"]
            # 单位缺失检测：若单位为空或仅为分隔符
            if not unit or unit in ("/",):
                errors.append({
                    "kind": "unit_missing",
                    "detail": f"{field} 中数值 {value} 缺少单位",
                })
                continue
            # 数值抄错：数值未在 sources 任一处出现
            if value not in source_value_set:
                errors.append({
                    "kind": "value_mismatch",
                    "detail": f"{field} 中数值 {value} {unit} 未见于原始资料",
                })
                continue
            # 数值+单位组合不匹配
            if (value, unit) not in source_pair_set:
                errors.append({
                    "kind": "value_mismatch",
                    "detail": f"{field} 中 {value} {unit} 与原始资料单位不符",
                })

    # 方向标签错位检测
    _detect_label_mismatch(medical_record, sources_text, errors)

    if errors:
        _log_debug("numeric_trace", f"发现 {len(errors)} 处数值/单位/标签问题")
    else:
        _log_debug("numeric_trace", "数值回溯通过")
    return errors


def _detect_label_mismatch(medical_record, sources_text, errors):
    """检测方向标签错位（如原文"标低"被写为"标高"）。"""
    # 统计 sources 中出现的方向标签
    source_tags = {tag for tag in DIRECTION_TAGS if tag in sources_text}
    if not source_tags:
        return

    for field in ("case_features", "diagnostic_discussion", "plan"):
        text = medical_record.get(field, "")
        if not isinstance(text, str):
            continue
        for tag in DIRECTION_TAGS:
            if tag in text and not _direction_allowed(tag, source_tags):
                # 生成文本出现了 sources 中没有（且无同义表达）的方向标签
                errors.append({
                    "kind": "label_mismatch",
                    "detail": f"{field} 中方向标签 '{tag}' 未见于原始资料",
                })


# ---------------------------------------------------------------------------
# 六、医学红线拦截（spec 5.4）
# ---------------------------------------------------------------------------

def _check_red_line_1(medical_record, original_sources):
    """红线1：否定关系被改写。"""
    sources_text = _joined_sources_text(original_sources)
    gen_text = " ".join(_all_text_values(medical_record))

    # 患者否认是主观陈述，不得改写为客观阴性或正常检查结果。
    if "患者否认" in sources_text:
        for affirm in ("阴性", "客观阴性", "正常", "无异常"):
            if affirm in gen_text:
                raise _rule_error(
                    "patient_denial",
                    "红线1",
                    f"患者否认不得改写为客观表述 '{affirm}'",
                )

    # 明确正常的资料应被保留为正常，不按缺失处理。
    explicitly_normal = any(
        phrase in sources_text
        for phrase in ("明确正常", "正常", "无异常", "未见异常")
    )
    if explicitly_normal:
        return

    # 找出 sources 中的否定表述片段
    negation_phrases = []
    for term in NEGATION_TERMS:
        if term in sources_text:
            negation_phrases.append(term)

    if not negation_phrases:
        return

    # 检查生成文本是否将否定改成肯定
    gen_text = " ".join(_all_text_values(medical_record))
    # 简化策略：若 sources 含"未提供X"且生成文本对应位置出现肯定表述，判定改写
    # 这里采用保守检测：若 sources 含"未提供"且生成文本对同一概念用"正常/否认"表述
    for affirm in AFFIRMATION_TERMS:
        if affirm in gen_text:
            # 进一步确认：生成文本中肯定表述附近是否对应 sources 中的否定项
            # 保守起见，仅当 sources 明确含"未提供/不详"且生成文本含"正常/否认"时告警
            for neg in ("未提供", "不详", "未见", "未"):
                if neg in sources_text and affirm in ("正常", "否认", "无异常", "未见异常"):
                    raise _rule_error(
                        "negation",
                        "红线1",
                        f"否定关系被改写: 原文含 '{neg}'，输出出现 '{affirm}'",
                    )

    _log_debug("red_line_1", "否定关系保留")


def _check_red_line_2(medical_record, original_sources):
    """红线2：凭空补写（输出出现资料中没有的检查/病史/用药）。

    仅扫描事实性陈述字段（case_features、diagnostic_discussion），
    不扫描 plan——计划中提出新检查是合理的。
    """
    sources_text = _joined_sources_text(original_sources)
    fact_text = " ".join([
        medical_record.get("case_features", "") or "",
        medical_record.get("diagnostic_discussion", "") or "",
    ])

    # 检查项：生成文本出现但 sources 未提及
    for term in KNOWN_EXAM_TERMS:
        if term in fact_text and term not in sources_text:
            raise _rule_error(
                "fabrication",
                "红线2",
                f"凭空补写: 检查项 '{term}' 未见于原始资料",
            )

    # 用药/操作：生成文本出现但 sources 未提及
    for term in KNOWN_DRUG_TERMS:
        if term in fact_text and term not in sources_text:
            raise _rule_error(
                "fabrication",
                "红线2",
                f"凭空补写: 用药/操作 '{term}' 未见于原始资料",
            )

    _log_debug("red_line_2", "无凭空补写")


def _check_red_line_3(medical_record, original_sources):
    """红线3：计划写成已实施。"""
    plan = medical_record.get("plan", "")
    if not isinstance(plan, str):
        return
    # 具体药物启动、停用、调整、替换及剂量/给药方案不允许。
    medication_actions = ("启动", "停用", "调整", "替换", "剂量", "给药途径", "给药速度", "给药频率")
    medication_names = tuple(term for term in KNOWN_DRUG_TERMS if term in plan)
    if medication_names or any(action in plan for action in medication_actions):
        raise _rule_error(
            "specific_medication",
            "红线3",
            "计划包含具体药物启动、停用、调整、替换或给药方案",
        )
    for term in PLAN_DONE_TERMS:
        if term in plan:
            idx = plan.find(term)
            snippet = _truncate_snippet(plan[max(0, idx - 10):idx + len(term) + 10])
            raise _rule_error("plan_done", "红线3", f"计划写成已实施: {snippet}")
    _log_debug("red_line_3", "计划表述合规")


def _check_red_line_4(medical_record, original_sources):
    """红线4：时序颠倒/提前引入后续信息。"""
    gen_text = " ".join(_all_text_values(medical_record))
    for term in FUTURE_INFO_TERMS:
        if term in gen_text:
            raise _rule_error(
                "timing",
                "红线4",
                f"时序颠倒: 提前引入后续信息 '{term}'",
            )
    _log_debug("red_line_4", "时序正常")


def _check_red_line_5(medical_record, original_sources):
    """红线5：信息不足硬下结论。"""
    sources_text = _joined_sources_text(original_sources)

    # 判断 sources 是否提示信息不足
    insufficient = any(term in sources_text for term in INSUFFICIENT_TERMS)
    if not insufficient:
        _log_debug("red_line_5", "资料充分，跳过信息不足检测")
        return

    gen_text = " ".join(_all_text_values(medical_record))
    # 输出是否含不确定性表述
    has_uncertainty = any(term in gen_text for term in UNCERTAINTY_TERMS)
    if has_uncertainty:
        _log_debug("red_line_5", "已包含不确定性表述")
        return

    # 输出是否含确定结论且无不确定性表述
    for term in DEFINITIVE_TERMS:
        if term in gen_text:
            raise _rule_error(
                "insufficient",
                "红线5",
                f"信息不足硬下结论: 出现 '{term}' 但无不确定性表述",
            )

    # 资料明显不足但输出完全没有不确定性表述，也视为硬下结论
    raise _rule_error("insufficient", "红线5", "信息不足硬下结论: 缺少不确定性表述")


def _check_red_line_6(numeric_errors):
    """红线6：数值/单位/方向错误汇总入口。"""
    if numeric_errors:
        first = numeric_errors[0]
        detail = _truncate_snippet(first.get("detail", ""))
        raise _rule_error("numeric", "红线6", f"数值/单位/方向错误: {detail}")
    _log_debug("red_line_6", "数值/单位/方向无误")


def _check_red_line_7(medical_record, original_sources):
    """红线7：泛化套话（缺少本例特异信息）。"""
    sources_text = _joined_sources_text(original_sources)
    gen_text = " ".join(_all_text_values(medical_record))

    # 提取本例特异数值
    source_numbers = _extract_numbers(sources_text)
    specific_values = [n["value"] for n in source_numbers]

    # 若生成文本不含任一特异数值，且不含 sources 中的特异症状词，判定为泛化
    has_specific_value = any(v in gen_text for v in specific_values)

    # 从 sources 提取一些特异症状词（简单取 2 字以上的中文片段）
    specific_terms = []
    for term in ("乏力", "心悸", "水肿", "苍白", "黑便", "血尿", "出血"):
        if term in sources_text:
            specific_terms.append(term)
    has_specific_term = any(term in gen_text for term in specific_terms)

    if not has_specific_value and not has_specific_term:
        # 进一步确认是否为泛化模板
        for phrase in GENERIC_PHRASES:
            if phrase in gen_text:
                raise _rule_error("generic", "红线7", f"泛化套话: 含 '{phrase}' 且无本例特异信息")
        # 即使没有模板短语，但完全无特异信息也告警
        if specific_values or specific_terms:
            raise _rule_error("generic", "红线7", "泛化套话: 缺少本例特异信息")

    _log_debug("red_line_7", "含本例特异信息")


# ---------------------------------------------------------------------------
# 七、入口编排
# ---------------------------------------------------------------------------

def validate_record(medical_record, original_sources):
    """
    校验单条病例的 medical_record 是否合规。

    校验通过：直接 return。
    校验失败：raise ValueError("错误原因")。

    参数：
        medical_record: 模型生成并解析后的病历对象（五字段）
        original_sources: 当前病例的 sources 列表（用于溯源与比对）
    """
    evidence_count = len(medical_record.get("evidence", []) or []) if isinstance(medical_record, dict) else 0
    sources_count = len(original_sources or [])
    _log_debug("entry", f"开始校验: evidence={evidence_count} 条, sources={sources_count} 条")

    # 1. Schema 结构校验
    _check_schema(medical_record)

    # 2. source_ids 溯源校验
    _check_source_trace(medical_record, original_sources)

    # 3. 数值回溯（收集错误，不抛出）
    numeric_errors = _check_numeric_trace(medical_record, original_sources)

    # 4. 红线 1-5（顺序判定，首个命中即抛出）
    _check_red_line_1(medical_record, original_sources)
    _check_red_line_2(medical_record, original_sources)
    _check_red_line_3(medical_record, original_sources)
    _check_red_line_4(medical_record, original_sources)
    _check_red_line_5(medical_record, original_sources)

    # 5. 红线6：数值/单位/方向错误汇总
    _check_red_line_6(numeric_errors)

    # 6. 红线7：泛化套话
    _check_red_line_7(medical_record, original_sources)

    _log_debug("entry", "全部校验通过")
