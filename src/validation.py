"""
病程记录校验组件（C 角色）。

对外仅暴露 validate_record(medical_record, original_sources)：
  校验通过 -> 直接 return
  校验失败 -> raise ValueError("VAL-xxx: 错误原因")

编排顺序：结构、来源、数值回溯、语境与计划、治疗与时序、数值错误、个体化。
派生术语、同指标多结果、鉴别方向及因果归因作为复核提醒。
可用 findings 列表收集提醒，原有双参数调用和通过时返回 None 的约定保持兼容。
首个 fail-class 命中即抛出，advisory 只记录不抛出，纯标准库实现，不修改入参。
"""

import re
import threading
import unicodedata
from decimal import Decimal


# 规则编号按检查类别分段。已分配编号保持固定，新规则在所属段追加。
RULE_REGISTRY = {
    "VAL-101": {
        "id": "VAL-101",
        "title": "病历对象与五字段完整性",
        "group": "结构",
        "enforcement": "fail",
        "implementation": "_check_schema",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-102": {
        "id": "VAL-102",
        "title": "三段正文类型与非空",
        "group": "结构",
        "enforcement": "fail",
        "implementation": "_check_schema",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-103": {
        "id": "VAL-103",
        "title": "证据条目结构",
        "group": "结构",
        "enforcement": "fail",
        "implementation": "_check_schema",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-104": {
        "id": "VAL-104",
        "title": "事实与推断标签取值",
        "group": "结构",
        "enforcement": "fail",
        "implementation": "_check_schema",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-105": {
        "id": "VAL-105",
        "title": "待核事项字段与类型",
        "group": "结构",
        "enforcement": "fail",
        "implementation": "_check_schema",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-106": {
        "id": "VAL-106",
        "title": "正文含代码围栏",
        "group": "结构",
        "enforcement": "fail",
        "implementation": "_check_schema",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-201": {
        "id": "VAL-201",
        "title": "证据至少一条",
        "group": "证据",
        "enforcement": "fail",
        "implementation": "_check_source_trace",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-202": {
        "id": "VAL-202",
        "title": "来源编号属于当前病例",
        "group": "证据",
        "enforcement": "fail",
        "implementation": "_check_source_trace",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-301": {
        "id": "VAL-301",
        "title": "数值、指标、单位与方向溯源",
        "group": "事实",
        "enforcement": "fail",
        "implementation": "_check_red_line_6",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-302": {
        "id": "VAL-302",
        "title": "缺失、否认与客观结果",
        "group": "事实",
        "enforcement": "fail",
        "implementation": "_check_red_line_1, _check_missing_exams",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-303": {
        "id": "VAL-303",
        "title": "词表内事实无来源支持",
        "group": "事实",
        "enforcement": "fail",
        "implementation": "_check_red_line_2",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-401": {
        "id": "VAL-401",
        "title": "计划写成已完成",
        "group": "计划",
        "enforcement": "fail",
        "implementation": "_check_red_line_3",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-402": {
        "id": "VAL-402",
        "title": "具体药物与侵入性计划",
        "group": "计划",
        "enforcement": "fail",
        "implementation": "_check_treatment_plan",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-501": {
        "id": "VAL-501",
        "title": "信息不足却使用确定性判断",
        "group": "判断与时序",
        "enforcement": "fail",
        "implementation": "_check_red_line_5",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-502": {
        "id": "VAL-502",
        "title": "提前写入后续结果",
        "group": "判断与时序",
        "enforcement": "fail",
        "implementation": "_check_red_line_4",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-503": {
        "id": "VAL-503",
        "title": "缺少病例特征的泛化文本",
        "group": "判断与时序",
        "enforcement": "fail",
        "implementation": "_check_red_line_7",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-601": {
        "id": "VAL-601",
        "title": "鉴别方向复核",
        "group": "复核提醒",
        "enforcement": "advisory",
        "implementation": "_check_differential_review",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-602": {
        "id": "VAL-602",
        "title": "派生术语复核",
        "group": "复核提醒",
        "enforcement": "advisory",
        "implementation": "_check_derived_review",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-603": {
        "id": "VAL-603",
        "title": "同指标多个结果复核",
        "group": "复核提醒",
        "enforcement": "advisory",
        "implementation": "_check_multiple_results_review",
        "status": "implemented",
        "hit_count": 0,
    },
    "VAL-604": {
        "id": "VAL-604",
        "title": "因果归因复核",
        "group": "复核提醒",
        "enforcement": "advisory",
        "implementation": "_check_causality_review",
        "status": "implemented",
        "hit_count": 0,
    },
}

_RULE_LOCK = threading.Lock()
RULE_HIT_COUNTS = {rule_id: 0 for rule_id in RULE_REGISTRY}


def _record_hit(rule_id):
    with _RULE_LOCK:
        RULE_HIT_COUNTS[rule_id] += 1
        RULE_REGISTRY[rule_id]["hit_count"] = RULE_HIT_COUNTS[rule_id]


def _rule_error(rule_id, detail):
    rule = RULE_REGISTRY[rule_id]
    _record_hit(rule_id)
    return ValueError(f"{rule_id} [{rule['title']}]: {detail}")


# ---------------------------------------------------------------------------
# 一、模块级常量
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = (
    "case_features",
    "diagnostic_discussion",
    "plan",
    "evidence",
    "review_items",
)

EVIDENCE_MIN = 1
EVIDENCE_SUGGEST_MAX = 5

MAX_SNIPPET_LEN = 50

UNIT = (
    r"(?:[×x*]10\^?\d+/L|10\^?\d+/L|mmHg|cmH2O|kPa|"
    r"mmol/mmol|(?:[munμµ]?mol|[munμµ]?g)/(?:dL|mL|L)|"
    r"(?:IU|U)/L|mL/(?:24\s*h|h|d|min|天|小时)|"
    r"次/(?:分钟|分|min)|bpm|°C|度|%|cm|mm|kg|mg|[μµu]g|ng|g|"
    r"mL|dL|[μµu]L|L|fL|pg|万|亿)(?![A-Za-zμµ/])"
)
NUMBER = r"[+−-]?\d+(?:\.\d+)?"
VALUE = rf"{NUMBER}(?:\s*[/~–—至-]\s*{NUMBER})?(?![\d.])"
NUMERIC_PATTERN = re.compile(rf"(?P<value>{VALUE})\s*(?P<unit>{UNIT})", re.IGNORECASE)

METRIC_NAMES = {
    "血红蛋白": ("Hb", "HGB"),
    "肌酐": ("血清肌酐", "血肌酐", "SCr", "Cr"),
    "血压": ("BP",),
    "收缩压": ("SBP",),
    "舒张压": ("DBP",),
    "尿量": (),
    "心率": ("HR",),
    "呼吸频率": ("RR",),
    "脉搏": (),
    "体温": (),
    "白细胞计数": ("白细胞", "WBC"),
    "血小板计数": ("血小板", "PLT"),
    "血氧饱和度": ("SpO2",),
    "血糖": ("空腹血糖", "随机血糖"),
    "血钾": (),
    "血钠": (),
}
METRIC_ALIASES = {
    alias.casefold(): name
    for name, aliases in METRIC_NAMES.items()
    for alias in (name, *aliases)
}
METRIC = "|".join(re.escape(alias) for alias in sorted(METRIC_ALIASES, key=len, reverse=True))
MEASUREMENT = re.compile(
    rf"(?<![A-Za-z])(?P<metric>{METRIC})\s*(?:[:=为]\s*)?(?P<value>{VALUE})"
    rf"\s*(?P<unit>{UNIT})?"
    r"(?:\s*[,，(（]?\s*(?:实验室)?(?:标记为|标|偏)?"
    r"(?P<direction>升高|降低|高|低|↑|↓)(?!于))?",
    re.IGNORECASE,
)
DIRECTIONS = {"高": "高", "升高": "高", "↑": "高", "低": "低", "降低": "低", "↓": "低"}
LAB_RESULT = re.compile(r"实验室(?:结果)?\s*(?:标为|为|提示)?\s*(阳性|阴性)")
SENTENCE_BREAK = re.compile(r"[。；;！？!?\n]")
CLAUSE_BREAK = re.compile(r"[，,。；;！？!?\n]")
NONFACT_PREFIX = re.compile(
    r"(?:尚未|仍未|并未|未曾|未能|未|无|否认|暂不|不|暂缓|避免|无需)\s*$|"
    r"(?:尚待|待|能否|是否|核实|确认|若|如果|一旦|不能|无法|不足以|不宜|不应|不可|不考虑|尚无依据)"
    r".{0,16}$"
)
NUMERIC_CONTEXT = re.compile(r"若|如果|一旦|阈值|目标值|参考范围|参考值|拟|建议")
OBSERVATION = r"血压|收缩压|舒张压|尿量|体温|心率|呼吸频率|脉搏|血氧饱和度"
OBSERVATIONS = rf"(?:{OBSERVATION})(?:(?:、|和|及|与|或)(?:{OBSERVATION}))*"
MISSING_STATE = r"未提供|未记录|未测量|未测|未查|未行|未做|无记录|不详|缺失"
MISSING_OBSERVATION = re.compile(
    rf"(?:{MISSING_STATE})\s*(?P<before>{OBSERVATIONS})|"
    rf"(?P<after>{OBSERVATIONS})(?:数据|结果|资料)?\s*(?:均)?(?:{MISSING_STATE})"
)
NORMAL_OBSERVATION = re.compile(
    rf"(?P<items>{OBSERVATIONS})\s*(?:均|基本|为|在)?\s*(?:正常(?:范围)?|无异常|未见异常|阴性)"
)

# 红线2: 凭空补写检测词表
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

# VAL-402: 不安全治疗/药物推荐
MEDICATION_RECOMMENDATION_VERBS = (
    "启动", "停用", "调整", "替换", "给予", "加用", "换用",
    "已开始", "已予", "已给", "已用",
)
MEDICATION_NAMES = (
    "铁剂", "补铁", "促红素", "EPO", "输血", "利尿剂", "降压药",
    "抗生素", "激素", "免疫抑制剂", "化疗",
)
DOSE_ROUTE_FREQ_TERMS = (
    "mg", "μg", "ug", "mL", "bid", "tid", "qd", "qn",
    "静脉", "口服", "肌注", "皮下", "静滴", "泵入",
)
SURGICAL_DETAIL_TERMS = (
    "手术", "穿刺术", "活检术", "切除术", "置管术", "引流术",
)

# VAL-401: 计划写成已实施的关键词
PLAN_DONE = re.compile(r"已(?:经)?(?:予|完成|行(?!走)|给|做|用|实施|执行|复查|接受)")

# VAL-502: 时序颠倒/提前引入后续信息的标志词
FUTURE_INFO = re.compile(r"出院诊断|出院时|出院后|已出院|随访(?:显示|发现|提示|结果)|(?:复查)?确诊")
PROSPECTIVE = re.compile(r"拟|计划|建议|待|将|若|如果|一旦|可考虑")
DISCHARGE_PLAN = re.compile(r"^\s*(?:拟|计划|建议|待|将|可考虑)")

# VAL-501: 信息不足标志词
INSUFFICIENT_TERMS = ("待查", "未提供", "不详", "缺乏", "未查", "资料不足", "未明确")
UNCERTAINTY_TERMS = (
    "需进一步检查", "需进一步检查明确", "病因待查", "原因待查",
    "尚不能确定", "不能确定", "不能排除", "尚不明确", "有待明确",
    "需完善", "需补充", "建议进一步",
)
DEFINITIVE_TERMS = ("确诊", "诊断为", "明确为", "就是", "即是", "确定是")

# VAL-601: 鉴别方向关键词
DIFFERENTIAL_KEYWORDS = ("考虑", "可能", "疑似", "待排除", "鉴别")
INSUFFICIENCY_STATEMENT_TERMS = ("资料不足", "信息不足", "证据不足", "需进一步")

# VAL-602: 派生值关键词
DERIVED_VALUE_TERMS = (
    "比值", "评分", "分期", "分级", "分类",
    "GFR", "eGFR", "肌酐清除率",
    "CKD", "AKI",
)

# VAL-604: 因果连接词
CAUSAL_CONNECTIVES = (
    "导致", "引起", "所致", "引发", "造成", "归于", "归因于",
)
CAUSAL_UNCERTAINTY_TERMS = (
    "关系未明", "关系不明", "需进一步检查", "尚不能确定",
)

# 红线7: 泛化套话模板片段
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
    if not isinstance(text, str):
        return ""
    if len(text) <= MAX_SNIPPET_LEN:
        return text
    return text[:MAX_SNIPPET_LEN] + "…"


def _log_debug(rule_name, detail):
    print(f"[validation] {rule_name}: {detail}")


def _extract_numbers(text):
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
    return "；".join(parts)


# ---------------------------------------------------------------------------
# 三、Schema 结构校验（VAL-103, VAL-104, VAL-105 + L0 guard）
# ---------------------------------------------------------------------------

def _check_schema(medical_record):
    if not isinstance(medical_record, dict):
        raise _rule_error('VAL-101', 'medical_record 必须为对象')
    for field in REQUIRED_FIELDS:
        if field not in medical_record:
            raise _rule_error('VAL-105' if field == 'review_items' else 'VAL-101', f'缺少字段: {field}')
    for key in medical_record:
        if key not in REQUIRED_FIELDS:
            raise _rule_error('VAL-101', f'额外字段: {key}')
    for field in ('case_features', 'diagnostic_discussion', 'plan'):
        value = medical_record[field]
        if not isinstance(value, str):
            raise _rule_error('VAL-102', f'{field} 必须为字符串')
        if not value.strip():
            raise _rule_error('VAL-102', f'{field} 非空')
    evidence = medical_record['evidence']
    if not isinstance(evidence, list):
        raise _rule_error('VAL-103', 'evidence 必须为数组')
    for i, item in enumerate(evidence):
        if not isinstance(item, dict):
            raise _rule_error('VAL-103', f'evidence[{i}] 必须为对象')
        for sub_field in ('statement', 'source_ids', 'kind'):
            if sub_field not in item:
                raise _rule_error('VAL-103', f'evidence[{i}] 缺少字段: {sub_field}')
        for key in item:
            if key not in ('statement', 'source_ids', 'kind'):
                raise _rule_error('VAL-103', f'evidence[{i}] 额外字段: {key}')
        stmt = item['statement']
        if not isinstance(stmt, str) or not stmt.strip():
            raise _rule_error('VAL-103', f'evidence[{i}] statement 非空字符串')
        source_ids = item['source_ids']
        if not isinstance(source_ids, list) or not source_ids:
            raise _rule_error('VAL-103', f'evidence[{i}] source_ids 非空数组')
        for sid in source_ids:
            if not isinstance(sid, str) or not sid.strip():
                raise _rule_error('VAL-103', f'evidence[{i}] source_ids 元素必须为非空字符串')
        if item['kind'] not in ('fact', 'inference'):
            raise _rule_error('VAL-104', f'evidence[{i}] kind 取值非法')
    review_items = medical_record['review_items']
    if not isinstance(review_items, list):
        raise _rule_error('VAL-105', 'review_items 必须为数组')
    for i, item in enumerate(review_items):
        if not isinstance(item, str):
            raise _rule_error('VAL-105', f'review_items[{i}] 必须为字符串')
    for text in _all_text_values(medical_record):
        if '```' in text:
            raise _rule_error('VAL-106', '代码围栏: 输出含 Markdown 代码围栏')
    _log_debug('schema', '结构校验通过')


# ---------------------------------------------------------------------------
# 四、source_ids 溯源校验（VAL-202, VAL-201）
# ---------------------------------------------------------------------------

def _check_source_trace(medical_record, original_sources):
    valid_ids = set()
    for source in original_sources or []:
        if isinstance(source, dict):
            sid = source.get('source_id')
            if isinstance(sid, str) and sid.strip():
                valid_ids.add(sid)
    evidence = medical_record.get('evidence', []) or []
    if len(evidence) < EVIDENCE_MIN:
        raise _rule_error('VAL-201', 'evidence 至少 1 条')
    if len(evidence) > EVIDENCE_SUGGEST_MAX:
        _log_debug('source_trace', f'evidence 条数偏多: {len(evidence)}')
    for i, item in enumerate(evidence):
        for sid in item.get('source_ids', []) or []:
            if sid not in valid_ids:
                raise _rule_error('VAL-202', f'来源不存在: {sid}')
    _log_debug('source_trace', f'溯源校验通过，合法来源 {len(valid_ids)} 个')


# ---------------------------------------------------------------------------
# 五、数值回溯校验（VAL-301）—— 收集错误，不直接抛出
# ---------------------------------------------------------------------------


def _numeric_key(value, unit):
    parts = re.split(r"\s*([/~–—至-])\s*(?=[+−-]?\d)", value.lstrip("+−-"))
    if len(parts) == 1:
        values = (Decimal(value.replace("−", "-")),)
        separator = None
    else:
        sign = value[0] if value[0] in "+−-" else ""
        first, separator, second = parts
        values = (Decimal((sign + first).replace("−", "-")), Decimal(second.replace("−", "-")))
        separator = "/" if separator == "/" else "range"
    unit = re.sub(r"\s+", "", unit).casefold().replace("μ", "u")
    return (values, separator), unit


def _measurements(text, *, generated=False):
    """提取指标、数值和单位，同时保留无指标名称的带单位数字。"""
    for sentence in SENTENCE_BREAK.split(unicodedata.normalize("NFKC", text)):
        named = list(MEASUREMENT.finditer(sentence))
        for match in named:
            prefix = CLAUSE_BREAK.split(sentence[:match.start()])[-1]
            if generated and NUMERIC_CONTEXT.search(prefix):
                continue
            metric = METRIC_ALIASES[match["metric"].casefold()]
            value, unit = _numeric_key(match["value"], match["unit"] or "")
            yield metric, value, unit, DIRECTIONS.get(match["direction"])
        for token in _extract_numbers(sentence):
            start, end = token["span"]
            if any(start < match.end() and end > match.start() for match in named):
                continue
            prefix = CLAUSE_BREAK.split(sentence[:start])[-1]
            if generated and NUMERIC_CONTEXT.search(prefix):
                continue
            value, unit = _numeric_key(token["value"], token["unit"])
            yield None, value, unit, None


def _numeric_errors(text, field, measurements, metrics_with_units):
    for metric, value, unit, direction in _measurements(text, generated=True):
        candidates = [entry for entry in measurements if metric is None or entry[0] == metric]
        matching = [entry for entry in candidates if entry[1:3] == (value, unit)]
        if not matching and (unit or metric in metrics_with_units):
            kind = "value_mismatch" if unit else "unit_missing"
            separator = "–" if value[1] == "range" else value[1] or ""
            rendered = separator.join(format(number, "f") for number in value[0])
            name = metric or "数值"
            yield {"kind": kind, "detail": f"{field} 的{name} {rendered} {unit} 与资料数值、单位或来源不符"}
        markers = {entry[3] for entry in matching if entry[3]}
        if direction and markers and direction not in markers:
            yield {"kind": "label_mismatch", "detail": f"{field} 的{metric}高低标记与资料不符"}


def _asserted_matches(pattern, clause):
    for match in pattern.finditer(clause):
        if NONFACT_PREFIX.search(clause[:match.start()]):
            continue
        if clause[match.end():].lstrip().startswith(("与否", "吗")):
            continue
        yield match


EXAM = r"尿检|尿常规|血常规|心电图|胸片|肝功能|肾功能"
EXAM_GROUP = rf"(?:{EXAM})(?:(?:、|和|及|与)(?:{EXAM}))*"
EXAM_MISSING = re.compile(
    rf"(?:未提供|未行|未做|未查|无记录)\s*(?P<before>{EXAM_GROUP})|"
    rf"(?P<after>{EXAM_GROUP})(?:结果|资料)?(?:未提供|未行|未做|未查|无记录)"
)
EXAM_NORMAL = re.compile(
    rf"(?P<exam>{EXAM})\s*(?:结果|提示|显示)?\s*(?:为|均)?(?:正常|阴性|无异常|未见异常)"
)


def _check_numeric_trace(medical_record, original_sources):
    """正文对照当前病例，证据条目对照各自引用的片段。"""
    by_source = {
        source["source_id"]: list(_measurements(source["content"]))
        for source in original_sources
    }
    measurements = [entry for entries in by_source.values() for entry in entries]
    metrics_with_units = {metric for metric, _, unit, _ in measurements if metric and unit}
    sources_text = _joined_sources_text(original_sources)
    errors = []
    for field in ("case_features", "diagnostic_discussion", "plan"):
        text = medical_record[field]
        errors.extend(_numeric_errors(text, field, measurements, metrics_with_units))
        for result in LAB_RESULT.findall(text):
            if result not in sources_text:
                errors.append({"kind": "label_mismatch", "detail": f"{field} 的实验室{result}未见于资料"})
    for index, item in enumerate(medical_record["evidence"]):
        cited = [entry for sid in item["source_ids"] for entry in by_source.get(sid, ())]
        errors.extend(
            _numeric_errors(item["statement"], f"evidence[{index}].statement", cited, metrics_with_units)
        )
    _log_debug("numeric_trace", f"发现 {len(errors)} 处数值/单位/标签问题" if errors else "数值回溯通过")
    return errors


# ---------------------------------------------------------------------------
# 六、医学红线拦截（VAL-302, VAL-402, VAL-401, VAL-502, VAL-501, VAL-301, VAL-601, VAL-602, VAL-603, VAL-604）
# ---------------------------------------------------------------------------

NEGATIVE_CONTEXT_TERMS = ("不能确认", "不能排除", "否认", "未确认", "未排除", "无法确认", "无法排除")


def _check_red_line_1(medical_record, original_sources):
    """只有同一项目明确缺失且输出断言正常时才拦截。"""
    sources = unicodedata.normalize('NFKC', _joined_sources_text(original_sources))
    symptom = '胸痛|胸闷|咯血|黑便|肉眼血尿|血尿|发热|咳嗽|出血'
    denied = {match['symptom'] for match in re.finditer(f'(?:患者)?否认\\s*(?P<symptom>{symptom})', sources)}
    objective = re.compile(f'(?P<symptom>{symptom})\\s*(?:为|结果|检查|客观)?\\s*(?:阴性|正常|已排除)')
    for text in _all_text_values(medical_record):
        for clause in CLAUSE_BREAK.split(text):
            for match in _asserted_matches(objective, clause):
                if match['symptom'] in denied:
                    raise _rule_error('VAL-302', f"否认{match['symptom']}被改写为客观结果")
    missing = {
        item
        for match in MISSING_OBSERVATION.finditer(sources)
        for item in re.findall(OBSERVATION, match["before"] or match["after"])
    }
    for clause in CLAUSE_BREAK.split(sources):
        for match in _asserted_matches(NORMAL_OBSERVATION, clause):
            missing.difference_update(re.findall(OBSERVATION, match['items']))
    missing.difference_update((metric for metric, _, unit, _ in _measurements(sources) if unit))
    for text in _all_text_values(medical_record):
        for clause in CLAUSE_BREAK.split(unicodedata.normalize('NFKC', text)):
            for match in _asserted_matches(NORMAL_OBSERVATION, clause):
                contradicted = sorted(missing.intersection(re.findall(OBSERVATION, match['items'])))
                if contradicted:
                    raise _rule_error('VAL-302', f"{'、'.join(contradicted)}在资料中缺失，却被写为正常")
    _log_debug('VAL-302', '否定关系保留')


def _check_missing_exams(medical_record, original_sources):
    sources = _joined_sources_text(original_sources)
    missing = {exam for match in EXAM_MISSING.finditer(sources) for exam in re.findall(EXAM, match['before'] or match['after'])}
    if re.search('否认(?:肉眼)?血尿', sources) and (not re.search('(?:尿检|尿常规).{0,6}(?:正常|阴性)', sources)):
        missing.update(('尿检', '尿常规'))
    for clause in CLAUSE_BREAK.split(sources):
        for match in _asserted_matches(EXAM_NORMAL, clause):
            missing.discard(match['exam'])
    for text in _all_text_values(medical_record):
        for clause in CLAUSE_BREAK.split(text):
            for match in _asserted_matches(EXAM_NORMAL, clause):
                if match['exam'] in missing:
                    raise _rule_error('VAL-302', f"{match['exam']}缺少客观结果，却被写为正常或阴性")


def _check_red_line_2(medical_record, original_sources):
    """VAL-303：词表内事实缺少原始资料支持。"""
    sources_text = _joined_sources_text(original_sources)
    fact_text = " ".join([
        medical_record.get("case_features", "") or "",
        medical_record.get("diagnostic_discussion", "") or "",
    ])
    for term in KNOWN_EXAM_TERMS:
        if term in fact_text and term not in sources_text:
            raise _rule_error('VAL-303', f"凭空补写: 检查项 '{term}' 未见于原始资料")
    for term in KNOWN_DRUG_TERMS:
        if term in fact_text and term not in sources_text:
            raise _rule_error('VAL-303', f"凭空补写: 用药/操作 '{term}' 未见于原始资料")
    _log_debug('VAL-303', '无凭空补写')


def _check_treatment_plan(medical_record, original_sources):
    """检查明确的药物启停/剂量推荐，忽略否定、核实与其他指标的单位。"""
    drug_pattern = '|'.join((re.escape(term) for term in MEDICATION_NAMES))
    action = re.compile('|'.join((re.escape(term) for term in MEDICATION_RECOMMENDATION_VERBS)))
    dosing = re.compile('|'.join((re.escape(term) for term in DOSE_ROUTE_FREQ_TERMS)))
    for clause in CLAUSE_BREAK.split(medical_record['plan']):
        for match in _asserted_matches(action, clause):
            nearby = clause[max(0, match.start() - 15):match.end() + 15]
            if re.search(drug_pattern, nearby):
                raise _rule_error('VAL-402', f'不安全治疗推荐: {clause}')
        if re.search(drug_pattern, clause):
            for match in _asserted_matches(dosing, clause):
                raise _rule_error('VAL-402', f'药物剂量/途径/频次需要复核: {clause}')
        for term in SURGICAL_DETAIL_TERMS:
            pattern = re.compile(re.escape(term))
            for match in _asserted_matches(pattern, clause):
                raise _rule_error('VAL-402', f'手术/侵入性计划需要复核: {clause}')
    _log_debug('VAL-402', '未发现明确的药物启停、剂量或侵入性计划')


def _check_red_line_3(medical_record, original_sources):
    """拦截计划中对已实施操作的断言。"""
    for clause in CLAUSE_BREAK.split(medical_record['plan']):
        for match in _asserted_matches(PLAN_DONE, clause):
            snippet = _truncate_snippet(clause[max(0, match.start() - 10):match.end() + 10])
            raise _rule_error('VAL-401', f'计划写成已实施: {snippet}')
    _log_debug('VAL-401', '计划表述合规')


def _check_red_line_4(medical_record, original_sources):
    """检查明确写入草稿的后续结果，保留待核和计划表述。"""
    sources = _joined_sources_text(original_sources)
    for text in _all_text_values(medical_record):
        for clause in CLAUSE_BREAK.split(text):
            if clause.strip() and clause.strip() in sources:
                continue
            for match in _asserted_matches(FUTURE_INFO, clause):
                if PROSPECTIVE.search(clause[:match.start()]):
                    continue
                if match.group() in ('出院时', '出院后') and DISCHARGE_PLAN.match(clause[match.end():]):
                    continue
                raise _rule_error('VAL-502', f"提前引入后续信息 '{match.group()}'")
    _log_debug('VAL-502', '未发现明确的后续结果')


def _check_red_line_5(medical_record, original_sources):
    """VAL-501：信息不足却使用确定性判断。"""
    sources_text = _joined_sources_text(original_sources)
    insufficient = any((term in sources_text for term in INSUFFICIENT_TERMS))
    if not insufficient:
        _log_debug('VAL-501', '资料充分，跳过信息不足检测')
        return
    gen_text = ' '.join(_all_text_values(medical_record))
    has_uncertainty = any((term in gen_text for term in UNCERTAINTY_TERMS))
    if has_uncertainty:
        _log_debug('VAL-501', '已包含不确定性表述')
        return
    for term in DEFINITIVE_TERMS:
        if term in gen_text:
            raise _rule_error('VAL-501', f"信息不足硬下结论: 出现 '{term}' 但无不确定性表述")
    _log_debug('VAL-501', '无确定性措辞，不报')


def _check_red_line_6(numeric_errors):
    """VAL-301：数值核对错误汇总。"""
    if numeric_errors:
        first = numeric_errors[0]
        detail = first.get('detail', '')
        raise _rule_error('VAL-301', f'数值/单位/方向错误: {detail}')
    _log_debug('VAL-301', '数值/单位/方向无误')


def _check_red_line_7(medical_record, original_sources):
    """VAL-503：通过数字和症状词粗查个体化信息。"""
    sources_text = _joined_sources_text(original_sources)
    gen_text = ' '.join(_all_text_values(medical_record))
    source_numbers = _extract_numbers(sources_text)
    specific_values = [n['value'] for n in source_numbers]
    has_specific_value = any((v in gen_text for v in specific_values))
    specific_terms = []
    for term in ('乏力', '心悸', '水肿', '苍白', '黑便', '血尿', '出血'):
        if term in sources_text:
            specific_terms.append(term)
    has_specific_term = any((term in gen_text for term in specific_terms))
    if not has_specific_value and (not has_specific_term):
        for phrase in GENERIC_PHRASES:
            if phrase in gen_text:
                raise _rule_error('VAL-503', f"泛化套话: 含 '{phrase}' 且无本例特异信息")
        if specific_values or specific_terms:
            raise _rule_error('VAL-503', '泛化套话: 缺少本例特异信息')
    _log_debug('VAL-503', '含本例特异信息')


def _check_differential_review(medical_record, original_sources):
    """VAL-601: 鉴别方向过度生产（advisory，不 raise）。"""
    diagnostic_discussion = medical_record.get("diagnostic_discussion", "")
    if not isinstance(diagnostic_discussion, str) or not diagnostic_discussion:
        return []

    direction_count = 0
    for kw in DIFFERENTIAL_KEYWORDS:
        direction_count += diagnostic_discussion.count(kw)

    findings = []
    if direction_count == 0:
        has_insufficiency = any(
            term in diagnostic_discussion
            for term in INSUFFICIENCY_STATEMENT_TERMS
        )
        if not has_insufficiency:
            findings.append({
                "rule_id": "VAL-601", "field": "diagnostic_discussion",
                "detail": "鉴别方向数量为0且无不足说明",
                "advisory": True,
            })

    if direction_count > 3:
        findings.append({
            "rule_id": "VAL-601", "field": "diagnostic_discussion",
            "detail": f"鉴别方向数量偏多({direction_count}个)，可能为凑数",
            "advisory": True,
        })

    if findings:
        _record_hit("VAL-601")
    _log_debug("VAL-601", f"鉴别方向检查完成，findings={len(findings)}")
    return findings


def _check_derived_review(medical_record, original_sources):
    """来源已有的术语可作为事实。新派生结论需要对应的推断证据。"""
    sources_text = _joined_sources_text(original_sources)
    findings = []
    for term in DERIVED_VALUE_TERMS:
        if term in sources_text:
            continue
        for field in ("case_features", "diagnostic_discussion", "plan"):
            if term not in medical_record[field]:
                continue
            supported = any(
                term in item["statement"] and item["kind"] == "inference"
                for item in medical_record["evidence"]
            )
            if not supported:
                findings.append({
                    "rule_id": "VAL-602", "field": field, "advisory": True,
                    "detail": f"出现资料中未列出的派生术语 {term}，需复核依据及推断标注",
                })
    if findings:
        _record_hit("VAL-602")
    return findings


def _check_multiple_results_review(medical_record, original_sources):
    """对同指标同单位的多个结果提醒复核，时间信息不足时不自动判冲突。"""
    observations = {}
    for source in original_sources:
        for metric, value, unit, _ in _measurements(source["content"]):
            if metric and unit:
                observations.setdefault((metric, unit), set()).add(value)
    findings = []
    review_text = " ".join(medical_record["review_items"])
    for (metric, unit), values in observations.items():
        if len(values) < 2:
            continue
        if metric in review_text and re.search("冲突|不一致|矛盾|差异|不同|核实", review_text):
            continue
        findings.append({
            "rule_id": "VAL-603", "field": "review_items", "advisory": True,
            "detail": f"{metric}存在多个{unit}结果，需结合采样时间核对是否冲突",
        })
    if findings:
        _record_hit("VAL-603")
    return findings


def _check_causality_review(medical_record, original_sources):
    """VAL-604: 因果归因检测（advisory，不 raise）。"""
    gen_text = " ".join(_all_text_values(medical_record))

    findings = []
    for connective in CAUSAL_CONNECTIVES:
        if connective in gen_text:
            has_uncertainty = any(
                term in gen_text
                for term in CAUSAL_UNCERTAINTY_TERMS
            )
            if not has_uncertainty:
                findings.append({
                    "rule_id": "VAL-604", "field": "medical_record",
                    "detail": f"因果归因: 出现 '{connective}' 但无不确定性表述",
                    "advisory": True,
                })

    if findings:
        _record_hit("VAL-604")
    _log_debug("VAL-604", f"因果归因检查完成，findings={len(findings)}")
    return findings


# ---------------------------------------------------------------------------
# 七、入口编排
# ---------------------------------------------------------------------------

def validate_record(medical_record, original_sources, *, findings=None):
    """
    校验单条病例的 medical_record 是否合规。

    校验通过：直接 return。
    校验失败：raise ValueError("VAL-xxx: 错误原因")。

    参数：
        medical_record: 模型生成并解析后的病历对象（五字段）
        original_sources: 当前病例的 sources 列表（用于溯源与比对）
    """
    _check_schema(medical_record)
    evidence_count = len(medical_record['evidence'])
    sources_count = len(original_sources or [])
    _log_debug('entry', f'开始校验: evidence={evidence_count} 条, sources={sources_count} 条')
    _check_source_trace(medical_record, original_sources)
    numeric_errors = _check_numeric_trace(medical_record, original_sources)
    _check_red_line_1(medical_record, original_sources)
    _check_missing_exams(medical_record, original_sources)
    _check_red_line_2(medical_record, original_sources)
    _check_red_line_3(medical_record, original_sources)
    _check_treatment_plan(medical_record, original_sources)
    _check_red_line_4(medical_record, original_sources)
    _check_red_line_5(medical_record, original_sources)
    _check_red_line_6(numeric_errors)
    _check_red_line_7(medical_record, original_sources)
    for check in (_check_derived_review, _check_multiple_results_review, _check_differential_review, _check_causality_review):
        advice = check(medical_record, original_sources)
        if findings is not None:
            findings.extend(advice)
    _log_debug('entry', '全部校验通过')


