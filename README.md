# 临床智录 MedicalRecord

## 使用范围

本仓库用于教学和竞赛场景中的结构化临床记录生成示例。它不是诊断或治疗工具；生成内容必须由合格临床人员复核，所有病例信息均须以人工核实为准。

## 文件结构

```text
临床智录/
├── main.py                         # 唯一正式启动入口；读取配置和输入，协调并发、校验和输出
├── input.json                      # 输入病例；正式模式读取比赛病例，Mock 模式读取教学案例
├── .env                            # 本地占位配置；正式模式保存主办方提供的 MODEL_NAME 和 ENDPOINT
├── .env.example                    # 配置模板；仅包含两个空配置项
├── requires.txt                    # Python 依赖清单
├── README.md                       # 项目说明、运行方式、能力边界和局限
├── src/
│   ├── api_client.py               # 调用真实或 Mock 服务；构建请求、解析响应、记录 attempt 和参数拒绝
│   ├── run_config.py               # 参数信封唯一来源；管理 seed、temperature、response_format 和 Thinking 状态
│   └── validation.py               # 校验五字段、来源、数值、否定、时序、计划和医学红线；返回 VR-* 异常
├── prompts/
│   ├── system_v1.txt               # 当前 runtime 系统提示词资产
│   ├── prompt_v1.py                # 加载 Prompt；按病例组装 system/user 消息
│   ├── few_shot_v1.json            # 少样本资产；当前未注入模型
│   └── candidates/                 # 借阅型候选提示词，不直接作为 runtime 加载
│       ├── system_v1_1_candidate.txt
│       ├── system_v1_2_candidate.txt
│       └── system_v1_3_candidate.txt
├── codes/
│   ├── mock_run.py                 # 启动本地 HTTP Stub；固定响应并验证 Mock 工程链路
│   ├── check_endpoint.py           # 对正式端点进行一次无病例、无密钥、无文件写入的协议检查
│   ├── safety_suite.py             # 执行 ST-1 至 ST-10 安全夹具；stub 模式不调用真实模型
│   └── check_deliverables.py       # 只读检查交付物、密钥、Fixture、重叠和状态声明
├── fixtures/
│   ├── output.json                 # Mock 生成的夹具输出；不是比赛提交结果
│   ├── run_log.json                # Mock 生成的夹具运行日志；不是比赛真实日志
│   ├── safety_report_stub.json     # Stub 安全套件报告
│   └── safety_cases/
│       └── clinical_safety_cases.json  # ST-1 至 ST-10 人工合成安全夹具
├── tests/
│   ├── conftest.py                 # 测试共享病例、来源和合规病历夹具
│   ├── test_parameter_envelope.py  # 参数接线、payload、无 Authorization 和日志信封测试
│   ├── test_validation_schema.py   # 五字段和 evidence/review_items 结构测试
│   ├── test_validation_trace.py    # evidence 来源回溯测试
│   ├── test_validation_numeric.py  # 数值、单位、方向和标签测试
│   ├── test_validation_redlines.py # 医学红线、明确正常和患者否认测试
│   ├── test_validation_e2e.py      # 校验入口端到端测试
│   └── test_validation_performance.py # 大文本和性能边界测试
└── output.json / run_log.json      # 正式运行产物；Mock 不写入或覆盖
```

## 运行方式

依赖安装：

```text
python -m pip install -r requires.txt
```

### 模式一：现在可运行的本地 Mock

当前环境不需要真实模型、API Key 或企业赛 `.env`。Mock 使用本地 HTTP 服务和固定模拟响应，验证工程链路：

```text
python codes/mock_run.py
python -m pytest -q
python codes/safety_suite.py --mode stub
python codes/check_deliverables.py
```

Mock 会：

- 启动随机本地 HTTP Stub。
- 临时使用 `mock-model` 和本地随机端口，不连接当前占位 `.env`。
- 读取并处理 `input.json` 中的教学病例。
- 使用固定的模拟病历响应，不调用真实 AI 分析病例。
- 校验结果结构、来源、医学规则、参数和运行日志。
- 只写入 [fixtures/output.json](./fixtures/output.json) 和 [fixtures/run_log.json](./fixtures/run_log.json)。
- 不覆盖根目录正式的 `output.json` 和 `run_log.json`。

Mock 不能证明真实模型可用、医学结论正确、输出具有确定性，也不能证明企业赛最终复现。Mock 结果仅是夹具，不是提交结果。

### 模式二：企业赛拿到正式环境后运行

企业赛拿到主办方提供的正式配置后，在项目根目录创建 `.env`：

```text
MODEL_NAME=<主办方提供的精确模型名>
ENDPOINT=<主办方提供的完整请求地址>
```

项目只读取这两项，不读取 API Key、不发送 `Authorization` 请求头，也不会自行拼接请求路径。

正式运行前先检查端点：

```text
python codes/check_endpoint.py
```

正式端点可用后运行唯一入口：

```text
python main.py
```

正式模式会：

- 从 `.env` 读取真实模型名和完整端点。
- 从根目录读取正式 `input.json`。
- 将病例信息发送给主办方指定模型，由真实模型分析。
- 校验并将五字段病历和失败记录写入根目录 `output.json`。
- 将调用状态、参数和 prompt 版本写入根目录 `run_log.json`。

正式模式还需要确认主办方参数限制、并发、超时、重试、调用预算、响应协议和提交限制。拿到正式环境前，不能声称真实端点已验收、参数已接受或正式产物已生成。

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

## 当前代码可以做到

- 读取并校验 `input.json` 顶层数组、病例编号、资料截止点及资料片段。
- 保持输入病例顺序，并发处理病例；单个病例失败时保留失败记录且继续处理后续病例。
- 按提示词资产和病例来源组装 system/user 消息。
- 从 `.env` 读取 `MODEL_NAME` 和完整 `ENDPOINT`，不读取 API 密钥、不发送 `Authorization`。
- 构建包含 `model`、`messages` 和 `stream=false` 的请求，并按配置添加 seed、temperature、response_format 或 Thinking 参数。
- 参数端点拒绝时返回清晰的 `PARAMETER_REJECTED` 状态，不静默忽略或重复发送被拒绝参数。
- 解析模型返回的 `choices[0].message.content`，并重构为约定的五字段病历对象。
- 校验五字段结构、依据来源、数值及部分否定、时序、计划、信息不足和泛化套话规则。
- 校验异常携带稳定的 `VR-*` 规则标识。
- 原子写入临时文件后再替换 `output.json` 和 `run_log.json`。
- 在运行日志中记录 prompt 版本、参数状态、attempt、运行编号和模型标识。
- 使用本地 Mock 验证请求结构、响应解析、校验、日志、容错和文件写入，不会访问真实模型。
- 通过 81 条本地自动化测试、Mock 端到端检查和 ST-1 至 ST-10 安全夹具。

上述本地测试与 Mock 成果只能证明工程链路和代码校验，不代表真实模型质量、临床正确性或比赛成绩。

## 当前尚未完成

- 尚未接入企业赛正式模型和主办方指定端点。
- 尚未取得正式的企业赛 `.env`、正式 `input.json` 和正式响应协议。
- 尚未实测 seed、temperature、response_format 和 Thinking 是否被真实端点接受。
- 尚未实测真实并发、超时、重试、调用预算和错误重试规则。
- 尚未生成真实比赛的根目录 `output.json` 和 `run_log.json`。
- 尚未生成和复核正式的 `results.json` 与企业赛算法/结果 ZIP 包。
- 尚未完成企业赛统一环境中的 Python 3.11 最终彩排和现场复现。
- 尚未完成公开练习病例上的基线与改进版同条件对比。
- 截止点过滤、数据提取和部分医疗启发式规则仍需更完整的实现与临床口径验证。
- 提示词候选尚未由具名临床人员签署；若团队选择内部签署，需绑定最终文本 exact hash。
- 临床批准、提示词冻结、确定性或真实医学质量仍不能声明。

企业赛拿到正式配置后，测试端点和运行正式算法可使用：

```text
python codes/check_endpoint.py
python main.py
```
