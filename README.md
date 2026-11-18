# 临床智录 MedicalRecord

## 使用范围

本仓库用于教学和竞赛场景中的结构化临床记录生成示例。它不是诊断或治疗工具；生成内容必须由合格临床人员复核，所有病例信息均须以人工核实为准。

## 运行方式

运行要求：

- Python 3.11 为赛方目标运行环境。
- 使用 `python -m pip install -r requires.txt` 安装依赖。
- 在项目根目录创建免密钥的 `.env`，内容为：

```text
MODEL_NAME=
ENDPOINT=
```

项目不读取 API 密钥，也不发送 `Authorization` 请求头；模型名称和端点仅通过 `.env` 配置。

运行：

```text
python main.py
```

程序读取 `input.json`，加载 `prompts/system_v1.txt`，并发处理病例，并通过原子替换写入 `output.json` 和 `run_log.json`。每条运行日志都会记录提示词版本。

## 仅夹具验证

Mock 测试使用本地 HTTP 服务器，并且只写入 `fixtures/`：

```text
python codes/mock_run.py
python -m pytest -q
python codes/safety_suite.py --mode stub
python codes/check_deliverables.py
```

这些命令不能证明真实模型可用、医学结论正确、输出具有确定性，也不能证明 Python 3.11 兼容性。Mock 结果仅是夹具，不是提交结果。

## 请求参数

参数信封以 `src/run_config.py` 为唯一来源。请求包含 `model`、`messages` 和 `stream=false`；仅在参数已配置且端点支持时，才发送 `seed`、`temperature`、`response_format` 或 `chat_template_kwargs.enable_thinking=false`。

当前配置值如下：

- `seed=42`，仅用于降低方差，不保证确定性
- `temperature=0.1`
- `response_format=null`（不发送）
- Thinking 使用服务端默认值（不发送 Thinking 字段）
- 不发送前缀缓存标记

固定 seed 不保证逐字相同。端点不支持的参数必须以参数拒绝码清晰失败，不得静默忽略；本项目尚未实测端点是否接受这些参数。

## 输出

`output.json` 是 JSON 数组，每个输入病例对应一条记录。模型响应会重构为包含五个字段的 `medical_record` 对象。`run_log.json` 包含每次尝试的状态和参数信封，但不包含提示词文本、原始响应正文、病例文本、API 密钥或凭据。

## 局限

- 尚未配置真实端点或 API 密钥。
- 尚未实测真实端点是否支持 seed、temperature、response_format 和 Thinking。
- 本工作区尚未完成 Python 3.11 彩排。
- 企业赛仅包含一个官方病例，因此不做均值、比例、方差、百分比或批量提升声称。
- 在真实运行或操作人员批准的运行生成之前，根目录下不存在 `output.json` 和 `run_log.json`。
