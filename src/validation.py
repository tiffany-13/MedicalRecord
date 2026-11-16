def validate_record(medical_record, original_sources):
    """
    C 负责在这里写严苛的校验规则。
    如果校验通过，什么都不做（直接 return）。
    如果校验失败，直接 raise ValueError("错误原因")。
    """
    # 这里先放一个最基本的 5 字段校验，保证 B 的代码能跑通
    required_fields = ["case_features", "diagnostic_discussion", "plan", "evidence", "review_items"]
    for field in required_fields:
        if field not in medical_record:
            raise ValueError(f"缺少字段: {field}")
            
    # C 后面自己在这里加上：Pydantic校验、source_ids溯源、数值回溯、医学红线拦截
    pass