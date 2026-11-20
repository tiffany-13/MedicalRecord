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
│   └── validation.py               # 校验结构、来源、数值、否定、时序、计划和医学红线；使用 VAL-xxx 编号
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
│   ├── test_rule_ids.py            # VAL 规则编号、注册表和异常标识测试
│   ├── test_validation_merge.py    # 数值合并、派生指标和复核提醒测试
│   ├── test_validation_st.py        # 安全场景和医学边界测试
│   ├── test_validation_helpers.py  # 校验辅助函数测试
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
python -m pip install pytest
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
- 将调用状态、参数、prompt 版本和病例复核提醒写入根目录 `run_log.json`。

正式模式还需要确认主办方参数限制、并发、超时、重试、调用预算、响应协议和提交限制。拿到正式环境前，不能声称真实端点已验收、参数已接受或正式产物已生成。

## 请求参数

请求参数统一在 `src/run_config.py` 配置。默认请求包含 `model`、`messages`、`stream=false`、`seed=42` 和 `temperature=0.1`。程序按配置直接发送参数，接口支持情况需要联调确认。把 seed 或 temperature 配为 None 可停止发送对应参数。response_format 和 Thinking 扩展参数按各自配置决定是否发送。

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
- 包内公开教学样例数量有限，真实模型质量及改进收益仍需同条件对比验证。
- 在真实运行或操作人员批准的运行生成之前，根目录下不存在 `output.json` 和 `run_log.json`。

## 当前代码可以做到

- 读取并校验 `input.json` 顶层数组、病例编号、资料截止点及资料片段。
- 保持输入病例顺序，并发处理病例；单个病例失败时保留失败记录且继续处理后续病例。
- 按提示词资产和病例来源组装 system/user 消息。
- 从 `.env` 读取 `MODEL_NAME` 和完整 `ENDPOINT`，不读取 API 密钥、不发送 `Authorization`。
- 构建包含 `model`、`messages` 和 `stream=false` 的请求，并按配置添加 seed、temperature、response_format 或 Thinking 参数。
- 参数拒绝时返回清晰的 `PARAMETER_REJECTED` 状态，不静默忽略或重复发送被拒绝参数。
- 对鉴权、限流、超时、连接、服务端、HTTP 响应和响应结构错误返回稳定的模型错误码。
- 解析模型返回的 `choices[0].message.content`，并重构为约定的五字段病历对象。
- 校验五字段结构、证据来源、数值、单位、方向、否定语境、时序、计划和信息不足。
- 校验中强制拦截规则返回固定的 `VAL-*` 编号、规则名称和具体原因；编号由 `RULE_REGISTRY` 统一管理。
- 鉴别方向、派生术语、多结果指标和因果归因作为复核提醒收集，不直接替代强制校验。
- 将复核提醒写入运行日志的 `validation_findings`，并保留字段、编号、说明和 advisory 状态。
- 原子写入临时文件后再替换 `output.json` 和 `run_log.json`。
- 在运行日志中记录 prompt 版本、参数状态、attempt、运行编号、模型标识和每次请求的校验结果。
- 在每次 API 尝试中保存当时的参数状态，补充最终元数据不会覆盖该次观察。
- 使用本地 Mock 验证请求结构、响应解析、校验、日志、容错和文件写入，不会访问真实模型。
- 当前可直接运行的本地测试共 **145 项**；本地 HTTP Mock 校验通过。安全夹具脚本可执行十例安全 Stub 流程，但未量化真实模型或错误输出的检出率。

上述本地测试与 Mock 成果只能证明工程链路和代码校验，不代表真实模型质量、临床正确性或比赛成绩。

## 当前尚未完成

- 尚未接入企业赛正式模型和主办方指定端点。
- 尚未取得正式的企业赛 `.env`、正式 `input.json` 和正式响应协议。
- 尚未实测真实端点是否接受 seed、temperature、response_format 和 Thinking，或是否静默忽略参数。
- 尚未实测真实并发、超时、重试、调用预算和错误重试规则。
- 尚未完成真实 API 响应形状、限流、鉴权和服务端错误的企业赛联调。
- 尚未生成真实比赛的根目录 `output.json` 和 `run_log.json`。
- 尚未生成和复核正式的 `results.json` 与企业赛算法/结果 ZIP 包。
- 尚未完成企业赛统一环境中的最终彩排和现场复现。
- 尚未完成公开练习病例上的基线与改进版同条件对比，以及真实模型检出率或误报率统计。
- 尚未实现独立的资料截止点过滤模块；目前只校验截止点字段并将全部资料组装至 Prompt。
- 部分关键词和启发式医学规则仍需公开案例验证及临床口径复核。
- 若团队选择内部 Prompt 签署，尚未绑定具名审查人和最终文本 exact hash；这不是赛方 PDF 明确要求。
- 临床批准、提示词冻结、确定性或真实医学质量仍不能声明。

企业赛拿到正式配置后，测试端点和运行正式算法可使用：

```text
python codes/check_endpoint.py
python main.py
```

## 合并后的校验与日志约定

C 校验接入指标、数值、单位和高低方向核对。evidence 中的数值分别与该条 source_ids 引用的片段核对。
“尚未确诊”“核实是否已完成”等否定及待核语境保留。患者否认与客观检查结果分别核对。
明确违规抛出 ValueError，主程序将该病例写为 VALIDATION_ERROR。派生术语及同指标多个结果等疑点生成复核提醒。
validate_record(record, sources) 继续通过时返回 None，也可用 findings=[] 接收提醒。

复核提醒写入该病例最后一次 API 尝试日志的 validation_findings，含 case_id、rule_id、field、detail、advisory。
API 调用成功表示取得回复，病例是否通过校验以 output.json 为准。
每次 API 尝试保存当时的参数状态，结束时补充元数据不会覆盖该次观察。

编号按六个检查类别固定分段，新规则在所属段追加。每条报错从 RULE_REGISTRY 取得名称。
复核提醒的编号字段统一为 rule_id；旧版本日志中的 vr_id 字段保留在历史文件中。

| 编号段 | 类别 |
|---|---|
| VAL-1xx | 结构 |
| VAL-2xx | 证据数量与来源编号 |
| VAL-3xx | 事实核对 |
| VAL-4xx | 诊疗计划 |
| VAL-5xx | 判断、时序与个体化 |
| VAL-6xx | 复核提醒 |

| 规则编号 | 检查内容 | 处理 |
|---|---|---|
| VAL-101 | 病历对象与五字段完整性 | 拦截 |
| VAL-102 | 三段正文类型与非空 | 拦截 |
| VAL-103 | 证据条目结构 | 拦截 |
| VAL-104 | 事实与推断标签取值 | 拦截 |
| VAL-105 | 待核事项字段与类型 | 拦截 |
| VAL-106 | 正文含代码围栏 | 拦截 |
| VAL-201 | 证据至少一条 | 拦截 |
| VAL-202 | 来源编号属于当前病例 | 拦截 |
| VAL-301 | 数值、指标、单位与方向溯源 | 拦截 |
| VAL-302 | 缺失、否认与客观结果 | 拦截 |
| VAL-303 | 词表内事实无来源支持 | 拦截 |
| VAL-401 | 计划写成已完成 | 拦截 |
| VAL-402 | 具体药物与侵入性计划 | 拦截 |
| VAL-501 | 信息不足却使用确定性判断 | 拦截 |
| VAL-502 | 提前写入后续结果 | 拦截 |
| VAL-503 | 缺少病例特征的泛化文本 | 拦截 |
| VAL-601 | 鉴别方向复核 | 提醒 |
| VAL-602 | 派生术语复核 | 提醒 |
| VAL-603 | 同指标多个结果复核 | 提醒 |
| VAL-604 | 因果归因复核 | 提醒 |

accepted-on-endpoint 表示携带相应参数的请求成功返回，服务端是否实际执行该参数仍需核实。
本地 Mock 返回成功只验证请求和日志接线。真实 Qwen 接口与 Python 3.11 比赛环境仍待验收。
