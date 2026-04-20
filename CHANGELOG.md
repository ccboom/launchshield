# 修改记录

这个文档用于持续记录项目修改历史。

后续每次改动，按下面格式追加：

## YYYY-MM-DD

### 变更标题

- 背景：
- 修改内容：
- 影响文件：
- 验证方式：
- 遗留问题：

---

## 2026-04-20

### 修复真实 LLM 缺包导致 live 运行直接 failed

- 背景：前端实测点击 `Execute & Stress Test` 后，`Execution` 和 `Streaming Billing` 会立即显示 `failed`，run 详情里的根因是 `RuntimeError('openai package not installed')`。
- 修改内容：
  - 调整 `launchshield/llm.py` 的真实 provider 选择逻辑，只有在 `USE_REAL_LLM=true`、`OPENAI_API_KEY` 已配置且 `openai` SDK 可导入时才启用真实 LLM。
  - 当用户请求真实 LLM 但本地环境缺少 SDK 时，自动回落到 `MockLLMProvider`，避免整次 run 在启动阶段直接崩溃。
  - 同步修正 provider 来源展示；这类场景现在会显示 `requested real / effective mock`，并明确写出 `openai package not installed; using bundled mock analysis`。
  - 补充 LLM provider 回归测试，覆盖“缺少 openai SDK 时自动回落”和“provider 来源正确展示”。
- 影响文件：
  - `launchshield/llm.py`
  - `tests/test_llm_provider.py`
- 验证方式：
  - 前端手工复现 `run_20260420_du2ufu`，确认旧问题根因为 `orchestrator crashed: RuntimeError('openai package not installed')`
  - 运行 `pytest tests/test_llm_provider.py`
  - 再次从前端触发运行，确认不会因为缺少 `openai` SDK 在 run 启动阶段直接 failed
- 遗留问题：
  - 当前 `.env` 仍启用了真实 payments / GitHub / LLM；如果真实 Arc RPC、GitHub API 配额或外部 LLM 服务不可达，运行仍可能在对应 provider 阶段失败

### 规范化 OpenAI Base URL 并显式暴露网关响应问题

- 背景：实测当前 `OPENAI_BASE_URL=http://141.98.198.98:1025/` 时，OpenAI SDK 会命中根路径下的 `/chat/completions`，上游返回的是网关 HTML 页面；即使手工切到 `/v1/chat/completions`，当前上游响应也没有 `message.content`。
- 修改内容：
  - `launchshield/llm.py` 现在会把根地址自动规范化为 `.../v1`，降低 OpenAI 兼容网关常见配置错误带来的接入失败。
  - 真实 LLM 响应解析现在会显式校验返回结构；遇到 HTML 页面、空 `choices`、空 `message.content` 时直接抛出清晰错误，不再悄悄产出空字符串结果。
  - 补充 LLM provider 测试，覆盖 base URL 规范化、空内容报错、HTML 网关误配报错。
- 影响文件：
  - `launchshield/llm.py`
  - `tests/test_llm_provider.py`
- 验证方式：
  - `pytest tests\\test_llm_provider.py`
  - 真实网关手工验证 `http://141.98.198.98:1025/chat/completions` 返回 HTML，`http://141.98.198.98:1025/v1/chat/completions` 返回 200 但无 `message.content`
- 遗留问题：
  - 非流式响应仍然没有 `message.content`，需要代码侧做流式回退才能拿到正文

### 兼容仅在 stream 模式返回正文的 LLM 网关

- 背景：重新检查返回体后确认，当前网关的 `/v1/chat/completions` 非流式响应里 `choices[0].message.content` 为空，但 `stream=true` 的 SSE chunk 里会按 `delta.content` 返回正文。
- 修改内容：
  - `launchshield/llm.py` 的真实 LLM 调用现在会先尝试普通 chat completion。
  - 如果上游返回空 `message.content`，自动回退到 `stream=true`，把所有 `delta.content` 拼接后再做 JSON 解析。
  - 保留 HTML 网关误配和真正空流响应的清晰报错。
- 影响文件：
  - `launchshield/llm.py`
  - `tests/test_llm_provider.py`
- 验证方式：
  - `pytest tests\\test_llm_provider.py`
  - 真实网关验证 `deep_analysis` 已返回完整内容，包含 `risk_summary`、`exploit_path`、`impact_scope`、`remediation_direction`
- 遗留问题：
  - 当前上游网关的非流式实现仍然不标准，代码依赖流式回退获取正文

## 2026-04-19

### 审计与核心链路修复

- 背景：对照 `PLAN.md` 审计代码时，发现依赖匹配、站点探针执行顺序、失败计数和重试链路存在偏差。
- 修改内容：
  - 收紧依赖漏洞匹配逻辑，只有精确命中已知脆弱版本才返回 advisory。
  - 扩展 `debug_mode_exposed` 规则，支持大小写形式的 `debug = true`。
  - 将 `site_probe` 执行改成“每次 invocation 先支付，再执行单个 probe”。
  - 修复 invocation 失败时 `completed_invocations` 计数不递增的问题。
  - 为 `deep_analysis`、`fix_suggestion`、`aisa_verify` 增加一次自动重试。
- 影响文件：
  - `launchshield/dep_check.py`
  - `launchshield/repo_scan.py`
  - `launchshield/site_probes.py`
  - `launchshield/orchestrator.py`
  - `tests/test_repo_scan_and_deps.py`
  - `tests/test_orchestrator_end_to_end.py`
- 验证方式：
  - `python -m compileall launchshield tests`
  - 手工回归验证 `site_probe` 首事件为支付
  - 手工回归验证 LLM / AIsa 瞬时失败后第二次成功
  - 手工回归验证 `preset-stress` 可完成并产出对应支付数量
- 遗留问题：
  - `launchshield/orchestrator.py` 里仍有一段 `if False:` 死代码待清理
  - 完整 `pytest` 受当前 Windows ACL 异常影响，无法稳定跑通

### 新增中文使用手册

- 背景：仓库原始文档偏英文，缺少面向实际操作的中文说明。
- 修改内容：
  - 新增完整中文使用手册，覆盖本地启动、页面操作、运行模式、环境变量、真实支付接线、结果目录和常见排错。
  - 在 README 里增加文档入口。
- 影响文件：
  - `docs/user-manual.md`
  - `README.md`
- 验证方式：
  - 检查文档链接是否可达
  - 检查关键段落和路径引用是否存在
- 遗留问题：
  - README 仍然以英文为主，中文手册承担主要操作说明

### 修复 `.env` 未加载导致的 Arc 配置失效

- 背景：`scripts/check_arc_testnet.py` 无法读取 `.env` 中的 `ARC_PRIVATE_KEY`。
- 修改内容：
  - 在配置层增加 `.env` 自动加载逻辑。
  - 保持系统环境变量优先，`.env` 只补默认值。
  - 补充配置层回归测试。
- 影响文件：
  - `launchshield/config.py`
  - `tests/test_config_env.py`
- 验证方式：
  - 手工验证 `AppConfig().arc_private_key` 能读取 `.env`
  - 手工验证 `check_arc_testnet.py` 不再停在“私钥未设置”
- 遗留问题：
  - 当前环境访问 Arc RPC 仍可能受网络限制

### 修复自定义扫描输入与依赖解析问题

- 背景：一次真实运行中，`target_url` 被填成 GitHub 仓库地址，导致 `site_probe` 实际在扫 GitHub 页面；同时 `requirements.txt` 中大量 `>=` 依赖被漏掉，`dep_lookup` 全显示 `empty-manifest`。
- 修改内容：
  - 拒绝把 GitHub 仓库 URL 作为 `target_url` 提交。
  - 扩展依赖解析，支持 `==`、`>=`、`<=`、`~=`、`>`、`<`。
  - 为依赖条目增加 `specifier` 和 `pinned` 元数据。
  - 保持只有精确锁定版本才命中静态漏洞库。
  - 改进 `dep_lookup` 在账单流中的目标显示，优先展示版本约束。
- 影响文件：
  - `launchshield/app.py`
  - `launchshield/dep_check.py`
  - `launchshield/orchestrator.py`
  - `tests/test_api_validation.py`
  - `tests/test_repo_scan_and_deps.py`
- 验证方式：
  - 手工验证 API 会拒绝 GitHub 仓库地址作为 `target_url`
  - 手工验证 `requirements.txt` 中 `fastapi>=...` 这类依赖可被解析
  - `python -m compileall launchshield tests`
- 遗留问题：
  - `file_scan` 仍然是配额扫描，不是全量仓库扫描

### 支持 OpenAI 兼容接口的 `base_url`

- 背景：真实 LLM 接入只支持官方默认地址，无法配置兼容 OpenAI 协议的代理或聚合服务。
- 修改内容：
  - 增加 `OPENAI_BASE_URL` 配置项。
  - 在 `OpenAIProvider` 初始化时透传 `base_url` 给 `AsyncOpenAI(...)`。
  - 更新 `.env.example`、README 和中文使用手册。
  - 新增 LLM provider 配置测试。
- 影响文件：
  - `launchshield/config.py`
  - `launchshield/llm.py`
  - `.env.example`
  - `README.md`
  - `docs/user-manual.md`
  - `tests/test_llm_provider.py`
- 验证方式：
  - 手工验证 `AppConfig` 能读取 `OPENAI_BASE_URL`
  - 手工验证 `OpenAIProvider` 会把 `base_url` 传给 SDK
  - `python -m compileall launchshield tests`
- 遗留问题：
  - `USE_REAL_LLM=false` 时，分析阶段仍会走内置 mock LLM，这是当前设计

### 当前仍未完成的计划项

- 真正的浏览器级探针仍未完成，当前 `site_probe` 主要是 HTTP / HTML 级探针。
- 全量仓库扫描模式仍未完成，当前 `file_scan` 依然按档位配额执行。
- AIsa 前端专用标签仍未实现，当前只作为通用 finding 渲染。
- 真实环境 smoke test 还未形成完整证据闭环。

### 全量扫描、真实浏览器探针、来源展示

- 背景：用户要求把仓库扫描从配额模式扩成全量模式，让 `USE_REAL_BROWSER` 真正驱动 CDP 探针，并在 UI 上明确展示 mock / real 来源。
- 修改内容：
  - 为 run 请求新增 `scan_scope`，支持 `sample` 和 `full`。
  - `full` 模式下在 `repo.fetch` 完成后动态计算 `planned_invocations` 和 `planned_breakdown`。
  - `site_probe` 改为优先走真实 CDP 浏览器会话，失败时自动回落到 HTTP fallback。
  - `/api/health`、`run.started` 和 `RunSummary` 现在都会返回 `provider_sources`。
  - 前端新增 Provider Sources 面板，并在 billing 行内展示 browser / LLM / AIsa / GitHub 的实际来源标签。
  - 修复 Windows 高频保存 run JSON 时偶发 `PermissionError` 的问题，为原子替换增加重试。
  - 调整测试隔离方式，移除对 `pytest-asyncio` 和系统临时目录权限的依赖。
- 影响文件：
  - `launchshield/models.py`
  - `launchshield/orchestrator.py`
  - `launchshield/browser_runtime.py`
  - `launchshield/site_probes.py`
  - `launchshield/app.py`
  - `launchshield/llm.py`
  - `launchshield/aisa.py`
  - `launchshield/payments.py`
  - `launchshield/repo_source.py`
  - `launchshield/storage.py`
  - `templates/index.html`
  - `static/app.js`
  - `static/styles.css`
  - `tests/conftest.py`
  - `tests/test_api_validation.py`
  - `tests/test_orchestrator_end_to_end.py`
  - `README.md`
- 验证方式：
  - `python -m compileall launchshield tests`
  - `python -m pytest tests\\test_api_validation.py tests\\test_orchestrator_end_to_end.py -q --cache-clear`
- 遗留问题：
  - 真实环境 smoke test 这轮按用户要求暂缓，尚未产出新的现场证据。
  - 如果本机没有开启 `CHROME_DEBUG_URL` 对应的浏览器端口，`USE_REAL_BROWSER=true` 会显示为 HTTP fallback。
