# 临床智录 Mock 测试运行指南

> 版本：v1-draft  
> 日期：2026-11-15  
> 适用对象：B / C / D / 队内  
> 目的：在没有 API key、没有真实 endpoint 的情况下，验证 D 的提示词 → 请求 → 解析 → 输出链路  
> 注意：Mock 结果是**夹具**，不是提交结果；不要上传 `fixtures/`

## 0. 先确认

- 使用当前代码：`main.py`、`prompts/prompt_v1.py`、`prompts/system_v1.txt`、`src/api_client.py`、`codes/mock_run.py`。
- B 的分支如果较旧，先 rebase；**不要恢复 `PROMPT_STEP1/2`**。
- Mock **不需要** `.env`、API key、`Authorization` 或真实 endpoint。
- Mock 使用 `mock-model` 和本地 `127.0.0.1` HTTP stub，**不会调用 Qwen**。
- 真实模型 `qwen3.8 27b`（精确拼写待主办方确认）只在拿到真实 `.env` 后使用。

## 0.1 Python 3.11 运行环境（重要）

- 赛方统一运行环境：**Python 3.11**（精确补丁见赛前技术附件）。
- 本机可能是 3.12 / 3.13；Mock 可在开发机跑，但**提交前必须在 3.11 跑一次**。
- 安装与运行：

```text
winget install Python.Python.3.11
py -3.11 -m venv .venv311
.venv311\Scripts\activate
python -m pip install -r requires.txt
python -m compileall -q main.py src prompts codes
python codes/mock_run.py
python codes/mock_run.py --env
```

- 若脚本打印 `WARNING: competition runtime is Python 3.11`，说明当前不是 3.11；这次结果不能当作 3.11 验证。
- 不要提交 `.venv311/`、`__pycache__/`、`.env`、`fixtures/`。

## 1. 安装依赖

在仓库根目录执行：

```text
pip install -r requires.txt
```

只需要 `requests` 和 `python-dotenv`。

## 2. 运行方式 A：注入配置（最简单）

```text
python codes/mock_run.py
```

- 不需要 `.env`。
- 脚本启动本地 HTTP stub，并把 `MODEL_NAME=mock-model` 注入到 `api._CONFIG`。
- 输出只写 `fixtures/`。
- 预期：全部 `PASS`，`config_mode= injected`。

## 3. 运行方式 B：测试 `.env` 加载路径

```text
python codes/mock_run.py --env
```

- 临时写入本地 `.env`：
  ```text
  MODEL_NAME=mock-model
  ENDPOINT=http://127.0.0.1:<随机端口>
  ```
- 走真实的 `dotenv_values` → `get_config()` 路径。
- 运行结束后恢复或删除 `.env`。
- 预期：全部 `PASS`，`config_mode= env`，`env_clean=PASS`。

## 4. 预期输出

```text
python_version= 3.13.14
python_is_3_11= False
WARNING: competition runtime is Python 3.11; current is 3.13.14
处理完成！成功: 1 例，失败: 0 例。
exit_zero=PASS
status_success=PASS
five_fields=PASS
evidence_at_least_one=PASS
run_log_present=PASS
prompt_version=PASS
model_in_log=PASS
no_authorization=PASS
content_type=PASS
payload_keys=PASS
root_untouched=PASS
env_clean=PASS
config_mode= injected
fixture_output= fixtures/output.json
fixture_log= fixtures/run_log.json
FIXTURE: not a submission result
```

`config_mode` 在 `--env` 模式下显示 `env`。

在 3.11 环境下应为 `python_is_3_11=True` 且不出现 warning；上面的 3.13 输出只是开发机示例。

## 5. 检查项含义与失败处理

| 检查项 | 含义 | 失败时先看 |
|---|---|---|
| `exit_zero` | `main.py` 正常结束 | 上方打印、`config_mode`、输入文件 |
| `status_success` | DEMO001 成功生成 | `parse_json_response`、模型返回内容 |
| `five_fields` | 五个字段齐全 | `prompts/system_v1.txt`、`build_messages` |
| `evidence_at_least_one` | evidence ≥ 1 | 模拟响应、`validate_record` |
| `run_log_present` | 运行日志有记录 | `call_llm`、`RUN_LOGS` |
| `prompt_version` | 每条日志有 `v1-draft` | `main.py` 的版本注入 |
| `model_in_log` | 日志模型为 `mock-model` | `api._CONFIG` 或临时 `.env` |
| `no_authorization` | 请求没有 `Authorization` | `src/api_client.py`；不要加 key |
| `content_type` | 请求头为 JSON | `call_llm` headers |
| `payload_keys` | 只有 `messages/model/stream` | `call_llm` payload |
| `root_untouched` | 根 `output.json` / `run_log.json` 未被覆盖 | 输出路径是否指向 `fixtures/` |
| `env_clean` | 临时 `.env` 已恢复/删除 | `--env` 模式、仓库根 `.env` |

> `python_version` / `python_is_3_11` 是环境提示，不是 PASS/FAIL 检查；3.11 下应为 `True`。

## 6. 常见问题

- **`ModuleNotFoundError`**：在仓库根目录执行 `pip install -r requires.txt`。
- **`FileNotFoundError: input.json`**：必须在仓库根目录运行；`input.json` 要存在。
- **`exit_zero=FAIL`**：先看是否 rebase 了当前 `main.py` 和 `prompt_v1.py`；B 的旧分支仍用 `PROMPT_STEP1/2`，会失败。
- **`no_authorization=FAIL`**：不要添加 API key 或 `Authorization`；检查 `src/api_client.py` 的 headers。
- **`--env` 后仓库根仍有 `.env`**：说明脚本异常中断；手动删除，不要提交。
- **端口/权限错误**：脚本使用随机本地端口；重试即可；不需要外部网络。
- **`CASE_CONTENT_ERROR`**：检查 `input.json` 的 `case_id`、`record_cutoff`、`sources`、`source_id`。

## 7. 这个 Mock 证明什么、不证明什么

**证明：**

- 提示词资产能加载，`build_messages` 能组装 system/user 消息。
- `call_llm` 请求体、请求头、无 `Authorization`。
- 响应解析、五字段、输出写入、`run_log` 与 `prompt_version`。
- 根结果不被覆盖。

**不证明：**

- 主办方真实 endpoint 可访问、模型名被接受、免密钥规则成立。
- 真实响应结构与 stub 完全一致。
- 真实超时、4xx/5xx/429、重试/限流行为。
- 真实模型质量、医学正确性、C 的 7 条红线校验。
- 可以冻结 v1 或作为提交结果。
- 在 3.13 / 3.12 上跑通不证明 3.11 运行时一致；提交前必须在 3.11 重跑。

## 8. 清理

- 如果仓库根出现 `.env`，删除；它可能包含真实配置，不能提交。
- `fixtures/` 是 git-ignored；不要上传。
- `__pycache__/` 不要上传。
- `.venv311/` 是本地虚拟环境，不要上传。
- 不要执行 `git add` / `commit` / `push`；由协调人统一上传。

## 9. 真实 `.env` 来了以后

1. 先运行：
   ```text
   python codes/check_endpoint.py
   ```
   确认 HTTP 200 且存在 `choices[0].message.content`。
2. 如果 `401/403`：说明 endpoint 不是免密钥端点；问主办方，**不要加 key**。
3. 再跑一例真实数据：
   ```text
   python main.py
   ```
   检查 exit 0、五字段、无 `Authorization`。
4. 全量批量测试要等临床审核冻结 v1 后再跑，用于 D11/D12/D13。

## 10. 一句话总结

```text
python codes/mock_run.py
```

或测试 `.env` 加载：

```text
python codes/mock_run.py --env
```

看到 `FIXTURE: not a submission result` 且全部 `PASS`，就说明 D 的 Mock 链路正常。