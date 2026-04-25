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

## 2026-04-25

### 修复真实支付失败后仍继续排队后续扫描

- 背景：真实支付模式下，Arc 返回 `insufficient funds for gas * price + value` 后，run 已经进入 `failed`，前端仍继续出现后续 `file_scan / dep_lookup / site_probe` 失败行，视觉上像“最后又 failed 了一次”。
- 修改内容：
  - 调整 `launchshield/orchestrator.py`，支付异常时先把当前 invocation 落为 `tool.failed`，再把 run 置为 `failed`。
  - 为各 stage 增加失败态短路；run 进入 `failed` 后，当前 stage 立即停止，后续 stage 不再继续排队。
  - 修复支付失败路径下 `completed_invocations` 和 `tool.failed` 事件不一致的问题。
- 影响文件：
  - `launchshield/orchestrator.py`
- 验证方式：
  - 对照 `data/runs/run_20260425_4xm05m.json` 和前端状态流，确认根因来自真实 Arc 支付失败。
  - 代码检查确认支付失败后不再继续进入后续 stage 循环。
- 遗留问题：
  - 当前钱包余额不足时，UI 仍然只显示通用 `failed` 状态，后续适合补一条更直接的“余额不足 / 需要 faucet”提示。

### 修复真实 LLM 返回数组字段导致 orchestrator 崩溃

- 背景：最新真实运行在 `analysis.fix_suggestions` 阶段失败，`run_20260425_cla5hd.json` 显示 `Finding.recommendation` 收到的是 list，触发 Pydantic 校验错误，整次 run 被标记为 `orchestrator crashed`。
- 修改内容：
  - 为 `launchshield/llm.py` 新增 LLM 文本字段归一化逻辑。
  - 当 OpenAI 兼容网关返回 list / tuple / dict 类型字段时，统一收敛成字符串后再组装 `DeepAnalysisResult` 和 `FixSuggestionResult`。
  - 新增回归测试，覆盖 `validation_steps` 返回数组时的兼容处理。
- 影响文件：
  - `launchshield/llm.py`
  - `tests/test_llm_provider.py`
- 验证方式：
  - `pytest tests/test_llm_provider.py -k coerces_list_validation_steps_to_string`
- 遗留问题：
  - 当前仍未对真实上游返回体做更严格 schema 校验，后续适合补一层字段级结构告警。

### 将中文视频脚本改为中英对照版

- 背景：用户需要把 `docs/hackathon/video-script.zh-CN.md` 里的中文话术翻译成英文，并按中英对照形式写回文件，方便直接用于录制和提交材料。
- 修改内容：
  - 重写 `docs/hackathon/video-script.zh-CN.md`，保留原有章节结构。
  - 为定位、录制建议、分镜脚本、精简口播、X 发帖文案和录制重点补齐英文翻译。
  - 把整份文档整理成中英对照版，便于直接照读、配字幕和做国际化提交。
- 影响文件：
  - `docs/hackathon/video-script.zh-CN.md`
- 验证方式：
  - 手工检查章节结构、时间轴和文案段落是否完整保留。
  - 手工检查每一段中文后都附有对应英文译文。
- 遗留问题：
  - 当前文案是偏演示和评审语境的英文版本，后续如需更口语化配音稿，还可以再收一轮语气。

### 新增详细英文版 Slide Presentation 文案稿

- 背景：用户需要一份更详细的英文版 Slide Presentation，用于 LabLab 提交页中的 `Slide Presentation` 材料。
- 修改内容：
  - 新增 `docs/hackathon/slide-presentation.en.md`。
  - 按逐页方式写出详细 deck 文案，覆盖标题、核心信息、页内文案、视觉建议和 speaker notes。
  - 内容对齐现有项目定位、`ppt-outline.md`、LabLab Step 1 材料和截图命名约定，方便直接转成 PPT 或 PDF。
- 影响文件：
  - `docs/hackathon/slide-presentation.en.md`
- 验证方式：
  - 手工检查页数、结构、叙事顺序和项目事实是否与现有材料一致。
  - 手工检查每一页都具备可直接转制为 PPT 的英文文案。
- 遗留问题：
  - 当前是文案稿，不是最终 `.pptx` 或设计成品；后续可继续产出正式 PPT/PDF。

### 生成可提交的英文版 Slide Presentation `.pptx`

- 背景：现有 `docs/hackathon/slide-presentation.en.md` 已经具备完整英文文案，需要进一步落成可直接提交的真实演示文件。
- 修改内容：
  - 新增 `scripts/generate_hackathon_pptx.py`，基于本机 Office 宽屏模板生成 `16:9` 的英文版 deck。
  - 输出 `docs/hackathon/LaunchShield-Swarm-Slide-Presentation.pptx`，包含 `12` 页内容页与收尾页。
  - 统一把模板产物从 `.potx` 主文档类型转换为标准 `.pptx`，并重写 slide、presentation 关系、文档元数据和标题清单。
  - 由于当前环境缺少稳定的本地 PDF 转换链路，这一轮先交付 `.pptx` 成品。
- 影响文件：
  - `scripts/generate_hackathon_pptx.py`
  - `docs/hackathon/LaunchShield-Swarm-Slide-Presentation.pptx`
  - `CHANGELOG.md`
- 验证方式：
  - 运行 `python scripts/generate_hackathon_pptx.py`
  - 检查产物 zip 结构，确认 `slide_count=12`
  - 检查 `[Content_Types].xml` 已切换到 `presentation.main+xml`
  - 抽查 `slide1.xml`、`slide6.xml`、`slide12.xml` 关键文案存在
- 遗留问题：
  - 当前 deck 使用程序化绘制的文本与占位视觉块，未嵌入真实产品截图。
  - 本轮未导出 `.pdf`，后续可在本机 PowerPoint 或 LibreOffice 环境补导出。

### 导出英文版 Slide Presentation `.pdf`

- 背景：在真实 `.pptx` 成品已经生成后，需要补一个可直接上传的 `.pdf` 版本。
- 修改内容：
  - 使用本机 PowerPoint 把 `docs/hackathon/LaunchShield-Swarm-Slide-Presentation.pptx` 导出为 `docs/hackathon/LaunchShield-Swarm-Slide-Presentation.pdf`。
- 影响文件：
  - `docs/hackathon/LaunchShield-Swarm-Slide-Presentation.pdf`
  - `CHANGELOG.md`
- 验证方式：
  - 检查 PDF 文件已生成并成功落盘
  - 抽查 PDF 包内页对象数量，确认页数为 `12`
- 遗留问题：
  - 当前 PDF 内容与 `.pptx` 保持一致，视觉素材仍以程序化卡片和占位块为主，未嵌入真实产品截图。
