# 项目完成度与赛规核对清单（D-状态）

> 文档编号：D-状态（状态/审计文档；不新增 D 编号）  
> 日期：2026-11-18  
> 适用范围：D 侧收尾、A/B/C/E 交接、提交前复核  
> 事实来源：`.codeartsdoer/specs/d_deliverables/spec.md`、`design.md`、`tasks.md`、D19、实测命令  
> 状态：**D 内容完成；项目尚未 submission-complete**  
> 哈希：`not-applicable`（状态文档，不绑定单一 prompt 字节）

## 0. 一句话结论

D 的提示词、文档、安全套件、loader guard、fixture envelope 和审计注册表已经完成；**项目还不能提交**，因为 A/C/E 的实现项、真实 `.env` 运行、Python 3.11 彩排、临床签署和 v1.3 决策仍未关闭。当前 checker 为 **110/115**，红色项恰好是 H-1、H-2、H-4、H-5。

## 1. 当前版本与身份（LF 口径）

| 资产 | 字符 | 字节 | SHA-256 | 状态 |
|---|---:|---:|---|---|
| runtime `prompts/system_v1.txt` | 1,248 | 3,082 | `5121dd88316510abd7ba1442c5f8edb906d065050ec2759c4391e5cb8d6ad1f1` | runtime `v1-draft`；未冻结 |
| `v1.1-clinical-candidate` | 2,856 | 7,028 | `acce17433cde615f344b043000d6faf6be7c2062ae7f7416fbaecc20258204aa` | advisory-reviewed；非 current |
| `v1.2-clinical-candidate` | 3,204 | 7,980 | `355c2daf233ec2188524ae9025501efe719ad7a17bc8579f650692c4b4fe89ea` | **current candidate**；review-only；待复审 |
| `v1.3-clinical-candidate` | 4,176 | 10,526 | `f038dce3d2812deedcafa243229a0c3db61a256ab5cea3ddcd43a85baec4bd6d` | **staged only**；超 4,000；loader 拒绝；未采纳 |

- `v1.3` 的 loader 实际错误：`over_budget 4176>4000`。
- 任何候选都**没有**写入 `prompts/system_v1.txt`；runtime 仍是 `v1-draft`。
- 任何候选都**没有**临床批准、没有冻结、没有确定性承诺。

## 2. 已完成（D 侧）

### 2.1 文档与状态

- D25–D37 已存在：D25 候选记录、D26 临床审核记录、D27 10 例安全用例、D28 VR 规则、D29 模型配置、D30 复现说明、D31 CR 需求表、D32 安全 fixture、D33 知识登记、D34 答疑对照、D35 参数/RC 表、D36 单例评测、D37 命名/打包。
- D4/D5/D6/D9/D12/D13/D14/D23 已从 v1-draft 文本改写为 v1.2 + `ST-1…ST-10` 口径。
- D7/D8/D10/D11/D-交接/D-审核包 已统一 header（id、prompt 版本、状态、哈希/`not-applicable`、日期、消费者、范围）。
- D29/D30/D35 已记录 `none sent`/H-1；D30 §4 已记录环境块（OS/CPU/内存/存储/时限/包大小 = `TBD` + OI-49）。
- D19 §13–§15 记录：T12 文档补齐、强 checker、v1.2 核验、T13 fixture、T16.4–T16.6 注册表、T22 环境、v1.3 评估。
- D19 当前：**71 行 `OI-` / 53 个唯一 OI ID**；DP-1…DP-6 表；G1–G11 + H-1…H-5 表。
- OI-13…OI-24 的原始定义已不在现行 spec/design/tasks 中，D19 以 `carried-unverified` 记录，**没有编造**。

### 2.2 工具与安全

- `prompts/prompt_v1.py`：`PROMPT_MAX_CHARS=4000`、`PromptAssets`、LF 摘要、`PromptAssetError`、4,100 临时副本 `over_budget` 实证、candidate guard、`reset_cache()`。
- `codes/check_deliverables.py`：90+ 项只读检查，含 prompt/loader/registry/D9/D12/D13/D14/D23/D29/D30/D33–D37/env/hosts/fixtures/overlap/claims；支持 `--check` 与 `--list`。
- `codes/mock_run.py`：fixture 为 envelope（`label`/`source_transport`/`generated_at`/`prompt_version`/`payload`）；不再给 `main` 的路径常量赋值；`--env` 遇到既有 `.env` 先拒绝、运行后删除。
- `codes/safety_suite.py`：ST-1…ST-10，stub 默认，真实模式门控。
- `fixtures/output_stub.json` SHA-256 `a878cecc…`；`fixtures/run_log_stub.json` `8b62247c…`；根产物仍 absent。

### 2.3 实测结果

| 命令 | 结果 |
|---|---|
| `python codes/check_deliverables.py` | **110/115**；exit 1；红项仅 H-1/H-2/H-4/H-5 |
| `python -m pytest -q` | **69 passed** |
| `python codes/mock_run.py` | **21/21** checks；exit 0 |
| `python codes/mock_run.py --env` | **21/21**；`.env` 运行后 absent |
| `python codes/safety_suite.py --mode stub` | 10 行；0 次模型调用；exit 0 |
| `py_compile` | exit 0 |
| `.env` | absent |
| root `output.json`/`run_log.json` | absent / absent |
| `README.md` | **0 bytes** |

## 3. 仍未完成

### 3.1 D 可执行（审计完整性，无新输入）

| 任务 | 缺口 | 要做什么 |
|---|---|---|
| **T15** 交接注册表 | D19 中 `requires-owner` 为 **0** | 为 A/B/C/E/O/R 建 15.1–15.18 行：需求、证据、blocked-by、owner；O 的确认请求写日期 |
| **T23** W-sec | RC-1…RC-12 在 D35，但 D19 无安全/日志完整性汇总 | 加静态扫描、无 key/无第三方 host、日志不含响应体/提示词/病例原文、attempt 计数、H-4 等值阻塞 |
| **T17.6 / T26** Final audit | D19 §14.7 有“最终审计”，但不是 T17.6 要求的独立节 | 汇总 transcript、冻结文件 digest、claim sweep、blocked/residual list、owner split、limitation block |
| **T14.2** registry | 只查 D25–D37 | 补 D1–D23 路径/header；D24 明确未注册 |
| **T14.8** D28 | 只查 15 个 ID 存在 | 断言全部 `specified-not-implemented`；启发式规则有误报说明；无代码行 |
| **T14.9** D31 | 只查 10 个 ID | 每行有 `VR-` 或 `human-review` 引用；状态不超过 `specified` |
| **T14.12** overlap | 只查 D32/v1.2 | 补 few-shot 资产 vs `input.json` 的语义 overlap |
| **T14.13 / T25.6** claims | 只有 `no_clinical_approval_claim` | 冻结/批准/强制/实测/已回答/已发送参数/`.env.example` 缺失/2,000 约束/“D25–D37 全缺失” |
| **T25.1 / T25.2** D33–D37 细节 | 部分 | 补 D33 登记/TBD、D34 conditioning、D35 fail-visible、D36 anecdote、D37 equality |
| **T12.17 / T12.18** | 仅文字 | claims sweep 与反重复（D31 唯一 CR、D28 唯一规则、D3 唯一 changelog）做成可执行检查 |

### 3.2 需要决策

| 决策 | 现状 | 影响 |
|---|---|---|
| **v1.3 A/B/C** | 4,176 > 4,000；新增紧急升级/既往诊断 | A=压缩 ≥176；B=提高 ceiling（重开 DP-1）；C=保留 v1.2。A/B 需 Requirement Generation |
| **D24** | `codes/fixture_metrics.py` 未注册 | 注册或明确不注册；不得虚构 |
| **DP-3** | `qwen3.8 27b` placeholder | 精确模型 ID 未确认 |
| **DP-6** | `signoff_state=null` | 具名医生按 exact hash 签署 |

### 3.3 非 D（阻塞提交）

| 所有者 | 任务 | 当前缺口 |
|---|---|---|
| **A** | T27 | `src/run_config.py` 未接入 `src/api_client.py`（H-1） |
| **C** | T28 | 7 条内部检查无 `VR-1…VR-15` 映射；69 测试未映射（H-2/H-3） |
| **E** | T29/T30 | 根产物 absent（H-4）；README 0 bytes；3.11 未实跑；打包未完成（H-5） |
| **O** | 主办方 | endpoint/模型 ID/注册模板/限额/结果命名等未发布 |
| **R** | 临床 | 具名医生未签署 v1.2/v1.3 exact hash |

## 4. 提交前必须复核（项目完整性）

### 4.1 提示词与临床内容

- [ ] runtime 仍是 `v1-draft`，且 `prompts/system_v1.txt` 的 LF 哈希为 `5121dd88…`。
- [ ] 候选没有被 runtime 引用：`grep -rn "candidates" main.py src prompts/prompt_v1.py` 无运行时命中。
- [ ] v1.2 的 3,204 / 7,980 / `355c2daf…` 在 D25/D26/D30 一致。
- [ ] v1.3 的 A/B/C 已决定；若 A/B，spec 已按 Requirement Generation 更新，且不再超 ceiling。
- [ ] 五类否定/缺失（未提供/未查/明确阴性或正常/无记录/患者否认）没有互相替代。
- [ ] 明确正常（如“尿常规未见异常”）不会被 validator 误报（ST-2）。
- [ ] 患者否认不等于客观阴性（ST-9）；不得推荐具体药物启动/停用/调整/替换（ST-10）。
- [ ] 诊断/分期/因果有足够证据；单一异常值不确立疾病/分期/并发症/因果。
- [ ] 计划不写成已实施；不引入 `record_cutoff` 之后信息。
- [ ] 具名临床医生按 exact hash 签署；未签署时不得称“已批准/已冻结”。

### 4.2 真实运行与产物

- [ ] `.env` 只有 `MODEL_NAME`/`ENDPOINT`，无 key/token；无 `Authorization`。
- [ ] 真实 endpoint 先跑 `codes/check_endpoint.py`；401/403 询问主办方，不加 key。
- [ ] 一例真实 smoke：五字段、`prompt_version`、`case_id` 保序、失败记录保留。
- [ ] 根 `output.json`/`run_log.json` 由真实运行产生；不是 fixture。
- [ ] `output.json` 是 JSON array；模型层是 object；两层不混。
- [ ] `run_log.json` 每条有 `prompt_version`；attempt 数 = 实际发出请求数；无响应体/提示词/病例原文。
- [ ] 原子写：temp → replace；退出码 0/1/2 符合约定；单例失败不影响其余。
- [ ] `results.json` 是 `output.json` 的内容保持复制；记录集、顺序、字段、失败记录 equal；未执行前写 `blocked — H-4`。

### 4.3 环境、依赖与打包

- [ ] Python 3.11 clean env；`pip install -r requires.txt`；`python main.py` 无参数。
- [ ] 无网络、无运行时下载、无 GPU/NPU、无自建模型/Embedding 服务。
- [ ] `requires.txt` 只列实际使用包；无仅加速器可用包。
- [ ] 算法包含 `main.py`、`requires.txt`、`.env.example`（两个空键）、`README.md`、prompt 文本/版本；结果包含 `results.json`/`run_log.json`。
- [ ] README 覆盖方法、运行步骤、参数、seed 位置、改进/局限、教学用途/非临床、keyless、非确定性。
- [ ] OS/CPU/内存/存储/时限/包大小仍为 `TBD` + OI-49；没有臆造上限。

### 4.4 安全、数据与日志

- [ ] 无外部第三方 API；只联系主办方指定 Qwen/内部允许服务。
- [ ] 未把病例/资料上传第三方；未使用缓存答案；未获取答案。
- [ ] 未攻击/压测/未授权访问；未探测 GPU/NPU；未利用漏洞。
- [ ] 未伪造日志/结果；未逐例改写正文或挑选最好结果。
- [ ] 未使用未登记知识库/RAG/Embedding；D33“无”与实际一致。

### 4.5 文档与声明

- [ ] 没有任何文档把 2,000 字符写成主办方规则（内部 4,000 sanity ceiling）。
- [ ] 没有任何文档把 2026-11-17 当冻结节点（organizer 锚点 11-14/11-19/11-26；内部 11-24，fallback 11-23）。
- [ ] 没有任何文档称 `.env.example` 缺失（实际 22 bytes，OI-04/OI-50 已修正）。
- [ ] DP-1/DP-4 `closed-by-decision`、DP-2/DP-5 `narrowed`、DP-3 `open`、DP-6 `kept` 没有被写成“已回答”。
- [ ] H-1…H-5 仍是 `handoff`，没有写成 `resolved`。
- [ ] 单官方病例只作 anecdote；没有 mean/rate/variance/percentage。

## 5. 赛规逐条核对

| 赛规 | 当前证据 | 状态 | 缺口/所有者 |
|---|---|---|---|
| 外部第三方 API 禁止 | `hosts_no_third_party_or_accelerator` PASS；D33“无”；代码仅 localhost stub | 通过（静态） | 真实 endpoint 仍待 O |
| 内部 Embedding/本地 RAG 可登记使用 | 本项目不使用；D33 声明“无” | 通过 | 若启用需登记（OI-44/OI-07） |
| `seed` 支持但不保证一致 | D35 `seed=42` documented；实际 `none sent`（H-1）；不承诺确定性 | 部分 | A/T27 接线 + endpoint 观测 |
| `temperature`/`response_format` 失败可见 | D35 documented；未发送；拒绝必须报错 | 部分 | A/T27 + OI-47 |
| Thinking 默认开启，可关 | 不发送字段；必要时 `chat_template_kwargs.enable_thinking=false` | 通过（文档） | 字段名待确认 |
| 流式允许、默认非流式 | `stream=false`；schema 不变 | 通过 | 无 endpoint 证据 |
| prefix cache 自动，无手动标记 | 不发送 cachemark | 通过 | — |
| 恰好 1 个官方病例 | D36/D12 不做批量统计 | 通过 | 官方病例文件未到 |
| `output.json` vs `results.json` | OI-46 open；D37 内容保持映射；等值 `blocked — H-4` | 部分 | A/B/E |
| CPU-only / 无 GPU / 无网 / Py3.11 | D30 §4；本机 3.13.14；3.11 未跑 | 部分 | E/T30（H-5） |
| 不得伪造日志/结果 | mock/fixture 明确 `fixture, not a submission result`；根产物 absent | 通过（静态） | 真实运行后复核 |
| 不得上传/外泄病例 | 未使用外部服务；D33“无” | 通过（静态） | 真实运行后复核 |
| 不得攻击/压测/未授权 | 无相关代码/记录 | 通过（静态） | — |
| 结果 JSON array、UTF-8、无围栏 | D7 契约；fixture payload array | 通过 | 真实运行后复核 |
| 无主办方 prompt 长度上限 | 内部 4,000；v1.2 3,204；v1.3 4,176 | 通过（v1.2） | v1.3 决策 |
| 三正文 800–1600 汉字 | prompt 已写；资料不足允许更短 | 通过（文档） | 真实输出后复核 |
| 内部冻结 2026-11-24 / fallback 11-23 | D10/D26/D34 一致；无 11-17 | 通过 | 具名签署 |
| 临床签署为团队内部 gate | `signoff_state=null`；无批准/冻结声明 | 通过（诚实） | R |

## 6. 不能说的话（提交前硬边界）

- 不说“已获临床批准”或“clinically approved”。
- 不说“已冻结”或“v1 已定稿”。
- 不说“已在 Python 3.11 验证”（除非 E 完成 3.11 彩排）。
- 不说“VR-1…VR-15 已实现/已拦截”（C 未映射）。
- 不说“批量提升 x%”“平均错误下降”（只有一个官方病例）。
- 不说“结果文件已统一为 results.json”（OI-46 未决）。
- 不说“参数已发送/已接受/可复现”（H-1；`none sent`）。
- 不说“fixture 是提交结果”或“stub 是真实模型结果”。
- 不说“2,000 是主办方规则”。
- 不说“`.env.example` 缺失”。
- 不说“所有 DP 已回答”或“H-1…H-5 已解决”。

## 7. 复跑命令（reviewer 可直接执行）

```text
python codes/check_deliverables.py
python -m pytest -q
python codes/mock_run.py
python codes/mock_run.py --env
python codes/safety_suite.py --mode stub
```

预期：

- checker：**110/115**，红项仅 H-1/H-2/H-4/H-5。
- pytest：**69 passed**。
- mock：**21/21**，exit 0。
- safety：10 行，0 次模型调用，exit 0。
- `.env` absent；根 `output.json`/`run_log.json` absent。

哈希/行尾复核：

```text
python -c "import hashlib,pathlib; p=pathlib.Path('prompts/candidates/system_v1_3_candidate.txt'); b=p.read_bytes(); print(len(b.decode('utf-8').rstrip('\n')), len(b), hashlib.sha256(b).hexdigest(), b.count(b'\r\n'))"
```

## 8. 交接清单

| 所有者 | 下一步 | 阻塞 |
|---|---|---|
| **A** | T27 `run_config` 接线；真实 smoke；根产物 | OI-48/endpoint；H-1 |
| **B** | cutoff/提取/组装；单例运行完整性 | 真实 `.env` |
| **C** | T28 VR registry；69 测试映射；ST-2 零误报；ST-9/ST-10 | 无（可开始） |
| **D** | 审计完整性（T15/T23/T17.6/T26/T14/T25）；v1.3 A/B/C 执行（若选 A/B 先走 Requirement Generation） | v1.3 决策；D24 |
| **E** | README、3.11 彩排、声明、打包、`results.json` 等值 | H-4/H-5；OI-44/OI-46/OI-49 |
| **O** | endpoint/模型 ID/注册模板/限额/结果命名 | 主办方 |
| **R** | v1.2（或 v1.3）exact hash 签署 | 候选最终选择 |

## 9. 本文件边界

- 本文件是状态与核对清单，不是临床批准、不是冻结声明、不是提交结果。
- 所有 `TBD` 保持 `TBD`；所有未执行项保持 `not-executed`。
- 本文件不替代 D19 的执行记录；两者冲突时以实测命令和 D19 为准。