# LaunchShield Swarm 提交版 MVP 详细实施计划

## 摘要
- 这次实现一个可公开访问的黑客松提交应用：`LaunchShield Swarm`。
- 用户输入 GitHub 仓库 URL 和目标站点 URL，系统执行两类扫描：
  1. 仓库级静态安全扫描
  2. 站点级浏览器探针扫描
- 每一次工具调用都走真实 Arc/Circle sandbox 微支付，单次价格固定小于 `$0.01`，预置压力档固定打出 `63` 笔上链交易。
- 产品主叙事固定为：`AI 安全审计任务被拆解成几十个原子工具调用，只有 Circle Nanopayments + Arc 这种微支付结算方式，才能让这个商业模型成立。`
- 现有仓库里直接复用的核心能力是 [cdp.py](D:/1goose/arc_house_helper/arc_helper/cdp.py)；现有 CLI 工作流和自动化逻辑保留不动，这版新增独立 Web 应用层。

## 实现边界
- 这版按“比赛提交可用”来设计，包含：
  - 公网 Web 应用
  - 真实 sandbox 微支付
  - 真实 Arc Explorer 交易链接
  - 预置压力测试目标
  - 自定义输入能力
  - 视频脚本
  - PPT 大纲
  - 提交核对清单
- 这版产品定位是 `提交版 MVP`，功能优先级固定如下：
  1. 预置目标完整跑通并稳定展示 `63` 笔交易
  2. 自定义输入能跑通标准档
  3. 利润矩阵、Explorer 链接、Console 证明完整可展示
  4. 结果解释足够像 AI 产品
- 这版不做：
  - 多用户并发
  - 登录鉴权
  - 数据库
  - 后台任务队列
  - 真正的安全准确率承诺
  - 全量 GitHub 仓库支持
  - 私有仓库支持

## 系统结构
### 整体运行方式
- 单仓 Python 全栈。
- Web 层用 FastAPI。
- 页面层用 Jinja2 模板 + Vanilla JS。
- 实时进度通过 SSE 推送。
- 后台任务采用进程内 worker 线程。
- 运行记录落盘到 `data/runs/`。
- 浏览器探针通过本机或容器内 Chromium `--remote-debugging-port=9222` 驱动。
- 真实支付通过 x402/Gateway 风格适配层提交到 Arc/Circle sandbox。

### 模块划分
| 模块 | 责任 |
|---|---|
| `arc_helper/cdp.py` | 复用现有 CDP 基础能力，负责连接 9222、页面导航、JS evaluate、页面身份读取 |
| `launchshield/app.py` | FastAPI 入口，挂载 HTML、静态资源、API、SSE |
| `launchshield/config.py` | 读取环境变量，统一配置默认值 |
| `launchshield/models.py` | Run、ToolInvocation、PaymentReceipt、Finding、ProfitabilitySnapshot、RunSummary 数据模型 |
| `launchshield/storage.py` | JSON 持久化与 run 恢复 |
| `launchshield/pricing.py` | 工具定价、档位、交易数目标 |
| `launchshield/presets.py` | 预置仓库、预置站点、压力档配置 |
| `launchshield/repo_source.py` | GitHub 公共仓库树获取、源码文件拉取、依赖清单提取 |
| `launchshield/repo_scan.py` | 文件扫描规则、依赖检查、可疑片段收敛 |
| `launchshield/site_probes.py` | 浏览器探针集合与站点 finding 生成 |
| `launchshield/payments.py` | x402/Gateway 风格支付适配、交易确认、Explorer 链接生成 |
| `launchshield/llm.py` | 高危片段深度分析、修复建议生成 |
| `launchshield/profitability.py` | AI 工具成本、链上成本、传统 Gas 对比计算 |
| `launchshield/orchestrator.py` | 把所有阶段串起来，产生统一事件流 |
| `launchshield/events.py` | SSE 事件格式化 |
| `templates/index.html` | 首页与运行页合并的单页模板 |
| `static/app.js` | 发起 run、监听 SSE、更新进度条和流水面板 |
| `static/styles.css` | 提交版视觉样式 |
| `tests/` | 单测、API 测试、集成测试、回归测试 |
| `docs/hackathon/` | 视频脚本、PPT 大纲、提交 checklist |

### 现有代码复用策略
- [main.py](D:/1goose/arc_house_helper/main.py) 保持原状。
- [workflow.py](D:/1goose/arc_house_helper/arc_helper/workflow.py)、[automation.py](D:/1goose/arc_house_helper/arc_helper/automation.py)、[scan.py](D:/1goose/arc_house_helper/arc_helper/scan.py)、[state.py](D:/1goose/arc_house_helper/arc_helper/state.py) 这版不并入产品逻辑。
- [cdp.py](D:/1goose/arc_house_helper/arc_helper/cdp.py) 直接作为浏览器探针底层依赖。
- 如果后续发现站点探针需要截图或 console/network 证据，再补充 `launchshield/browser_runtime.py`，这版计划先按现有 `cdp.py` 能力闭环。

## 对外接口与数据契约
### HTTP API
#### `POST /api/runs`
用途：创建一次扫描任务。

请求体固定为：
```json
{
  "mode": "preset-stress",
  "repo_url": "https://github.com/example/demo-repo",
  "target_url": "https://demo-target.example.com"
}
```

约束固定为：
- `mode` 只允许：
  - `preset-stress`
  - `custom-standard`
- `preset-stress` 忽略外部 `repo_url` 和 `target_url`，直接使用预置目标。
- `custom-standard` 必须提供：
  - 公共 GitHub 仓库 URL
  - `http` 或 `https` 的目标站点 URL

返回体固定为：
```json
{
  "run_id": "run_20260418_abc123",
  "status": "queued",
  "mode": "preset-stress",
  "stream_url": "/api/runs/run_20260418_abc123/events",
  "summary_url": "/api/runs/run_20260418_abc123"
}
```

#### `GET /api/runs/{run_id}`
用途：获取任务当前摘要或最终结果。

返回体核心字段固定为：
```json
{
  "run_id": "run_20260418_abc123",
  "status": "running",
  "mode": "preset-stress",
  "repo_url": "https://github.com/example/demo-repo",
  "target_url": "https://demo-target.example.com",
  "started_at": "2026-04-18T20:00:00+08:00",
  "completed_at": null,
  "counts": {
    "planned_invocations": 63,
    "completed_invocations": 21,
    "confirmed_payments": 21,
    "critical_findings": 2,
    "high_findings": 3,
    "medium_findings": 5
  },
  "totals": {
    "tool_cost_usd": 0.071,
    "settled_usdc": 0.071,
    "traditional_gas_estimate_usd": 1.05
  },
  "profitability": {
    "micro_model_margin_signal": "profitable",
    "traditional_model_signal": "bankrupt"
  },
  "findings": [],
  "tool_invocations": []
}
```

#### `GET /api/runs/{run_id}/events`
用途：SSE 推送运行过程。

事件类型固定为：
- `run.started`
- `stage.started`
- `tool.invoked`
- `payment.submitted`
- `payment.confirmed`
- `tool.completed`
- `tool.failed`
- `finding.created`
- `stage.completed`
- `run.completed`
- `run.failed`

### 内部核心类型
#### `ScanRun`
字段固定为：
- `run_id`
- `mode`
- `status`
- `repo_url`
- `target_url`
- `created_at`
- `started_at`
- `completed_at`
- `planned_invocations`
- `completed_invocations`
- `tool_invocations`
- `findings`
- `profitability`
- `error_message`

状态固定为：
- `queued`
- `running`
- `completed`
- `failed`

#### `ToolInvocation`
字段固定为：
- `invocation_id`
- `stage`
- `tool_name`
- `target`
- `price_usd`
- `status`
- `payment`
- `result_summary`
- `finding_ids`
- `started_at`
- `completed_at`
- `error_message`

状态固定为：
- `pending`
- `payment_submitted`
- `payment_confirmed`
- `completed`
- `failed`

#### `PaymentReceipt`
字段固定为：
- `provider`
- `amount_usdc`
- `tx_hash`
- `network`
- `explorer_url`
- `submitted_at`
- `confirmed_at`
- `console_reference`

#### `Finding`
字段固定为：
- `finding_id`
- `source`
- `severity`
- `title`
- `summary`
- `evidence`
- `recommendation`
- `related_invocation_ids`

`severity` 固定为：
- `critical`
- `high`
- `medium`
- `low`

### 数据落盘格式
每个 run 固定写一个 JSON 文件：
- `data/runs/<run_id>.json`

预置演示附加产物固定写到：
- `data/runs/<run_id>-artifacts/`

产物包括：
- `summary.json`
- `invocations.json`
- `findings.json`
- `profitability.json`

## 核心执行流程
### 运行档位
#### 1. `preset-stress`
用途：视频录制、现场演示、评分主流程。

调用数固定为：
- 文件扫描 `25`
- 依赖检查 `15`
- 站点探针 `12`
- 深度分析 `6`
- AIsa 验证 `3`
- 修复建议 `2`

总计固定 `63` 笔。

#### 2. `custom-standard`
用途：给评委和用户看“这不是纯回放”。

调用数固定为：
- 文件扫描 `12`
- 依赖检查 `6`
- 站点探针 `8`
- 深度分析 `4`
- AIsa 验证 `2`
- 修复建议 `2`

总计固定 `34` 笔。

### 单次工具调用执行顺序
每个工具调用严格按以下顺序执行：
1. 创建 invocation 记录，状态 `pending`
2. 发出 `tool.invoked`
3. 通过 x402/Gateway 适配层提交本次微支付
4. 发出 `payment.submitted`
5. 等待链上确认
6. 写入 `tx_hash`、Explorer URL、Console reference
7. 发出 `payment.confirmed`
8. 执行工具逻辑
9. 产出 result summary 或 finding
10. 发出 `tool.completed` 或 `tool.failed`

### 阶段顺序
固定阶段顺序如下：
1. `repo.fetch`
2. `repo.file_scan`
3. `repo.dep_lookup`
4. `site.browser_probes`
5. `analysis.deep_review`
6. `analysis.aisa_verify`
7. `analysis.fix_suggestions`
8. `summary.profitability`
9. `summary.finalize`

### 失败处理规则
- 支付失败：整次 run 立即失败，状态写为 `failed`，页面显式显示支付失败原因，不回退到 mock。
- GitHub 拉取失败：整次 run 失败。
- 单个源码文件读取失败：该 invocation 标记失败，run 继续。
- 单个站点探针失败：该 invocation 标记失败，run 继续。
- LLM 调用失败：自动重试一次；第二次仍失败则 invocation 标记失败，run 继续。
- AIsa 验证失败：自动重试一次；第二次仍失败则该步标记失败，run 继续。
- 运行中任意非支付失败都进入最终摘要，保持透明展示。

## 扫描与分析规则
### 仓库源码获取
- 只支持公共 GitHub 仓库。
- 仓库树通过 GitHub Tree API 拉取。
- 文件选择按路径和扩展名过滤。
- 允许的扩展名固定为：
  - `.py`
  - `.js`
  - `.ts`
  - `.tsx`
  - `.jsx`
  - `.json`
  - `.yaml`
  - `.yml`
  - `.toml`
  - `.html`
  - `.env.example`
- 优先扫描的目录固定为：
  - `src/`
  - `app/`
  - `server/`
  - `api/`
  - `lib/`
  - `config/`
  - `.github/workflows/`

### 文件扫描规则
文件扫描产生的基础 finding 类型固定为：
- `hardcoded_secret`
- `dangerous_eval`
- `unsafe_shell_call`
- `debug_mode_exposed`
- `weak_cors_config`
- `open_redirect_pattern`
- `insecure_deserialization`
- `unsafe_innerhtml`
- `suspicious_env_exposure`

### 依赖检查
依赖提取来源固定为：
- `requirements.txt`
- `pyproject.toml`
- `package.json`
- `package-lock.json`

依赖漏洞查询固定走公开漏洞数据库接口，再把高风险结果收敛成 finding。

依赖 finding 标题格式固定为：
- `Vulnerable dependency: <name>`

### 浏览器探针
站点探针分两类：
- HTTP 层探针
- 浏览器层探针

HTTP 层探针固定检查：
- `Content-Security-Policy`
- `X-Frame-Options`
- `Strict-Transport-Security`
- `Access-Control-Allow-Origin`
- `Server` 头暴露
- 常见敏感路径返回状态码

浏览器层探针固定检查：
- 登录页或后台路径暴露
- 表单密码字段配置
- `window.__NEXT_DATA__` 或类似元数据泄露
- 内联脚本与危险 sink
- 可疑重定向逻辑
- Mixed Content 信号
- 调试页或文档页暴露

### 深度分析与修复建议
- 真实 LLM 只处理“高危候选”。
- 深度分析输入固定为：片段上下文、规则命中原因、依赖/站点证据、目标语言。
- 深度分析输出固定包含：
  - 风险摘要
  - 可利用路径
  - 影响范围
  - 修复方向
- 修复建议输出固定包含：
  - `why`
  - `patch_summary`
  - `suggested_code_change`
  - `validation_steps`

### AIsa 验证
- AIsa 作为额外威胁情报验证步骤。
- 输入固定为高危片段或高危依赖摘要。
- 输出固定为：
  - `match_level`
  - `intel_summary`
  - `recommended_priority`
- AIsa 验证失败不阻塞最终报告。

## 微支付与利润模型
### 定价矩阵
| 工具 | 单价 |
|---|---|
| `file_scan` | `$0.001` |
| `dep_lookup` | `$0.002` |
| `site_probe` | `$0.003` |
| `deep_analysis` | `$0.005` |
| `aisa_verify` | `$0.005` |
| `fix_suggestion` | `$0.008` |

### 计费原则
- 每个工具调用单独支付一次。
- 所有单价都严格低于 `$0.01`。
- 页面所有交易都显示真实结算金额和真实 tx hash。
- 页面总成本直接累加所有 `confirmed` receipt。
- 页面底部利润矩阵固定展示三列：
  - `Total AI Service Cost`
  - `Arc/Circle Settled Cost`
  - `Traditional EVM Gas Estimate`

### 传统 Gas 对比公式
- 传统 Gas 单笔估值固定用 `$0.05`
- 公式固定为：
  - `traditional_gas_estimate_usd = confirmed_payments * 0.05`
- 预置压力档 `63` 笔时，页面默认出现“传统模式成本远高于微支付模型”的红色结论。
- 结论文案固定为：
  - `Traditional gas destroys the margin of high-frequency AI security workflows. Arc + Circle micropayments keep the model profitable.`

## 页面与 Demo 体验
### 首页结构
首页固定有 6 个区域：
1. `Hero`
2. `Preset Demo CTA`
3. `Custom Input Form`
4. `Execution Panel`
5. `Streaming Billing`
6. `Profitability Matrix`

### Hero 文案
固定表达三件事：
- 这是一个 AI 安全扫描 swarm
- 每一次工具调用都会独立结算
- 传统 Gas 无法支持这样的高频安全工作流

### 预置 CTA
- 页面默认高亮 `Execute & Stress Test`
- 点击后直接跑 `preset-stress`
- 这是首页最醒目的主按钮

### 自定义输入
表单字段固定为：
- `GitHub Repo URL`
- `Target Site URL`

按钮固定为：
- `Run Standard Scan`

### Execution Panel
固定显示：
- 总进度条
- 当前阶段
- 完成交易数
- 严重 finding 数量
- 风险等级汇总

### Streaming Billing
每条流水固定显示：
- 时间
- 工具名
- 金额
- 目标对象
- 支付状态
- Arc Explorer 链接

示例样式固定类似：
- `[0.003 USDC] site_probe -> /login -> confirmed -> 0xabc...`

### 最终结果面板
固定显示：
- `Critical / High / Medium / Low` finding 数量
- Top 5 风险卡片
- 每个风险的证据摘要
- 对应的工具调用链接
- 修复建议摘要

## 依赖、配置与部署
### 依赖新增
在 [requirements.txt](D:/1goose/arc_house_helper/requirements.txt) 中新增：
- `fastapi`
- `uvicorn[standard]`
- `jinja2`
- `httpx`
- `pydantic`
- `openai`
- 任何 x402/Gateway 客户端依赖
- 如需 TOML 解析，增加对应解析库

### 环境变量
固定使用以下环境变量：
- `APP_ENV`
- `HOST`
- `PORT`
- `CHROME_DEBUG_URL`
- `GITHUB_TOKEN`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `CIRCLE_API_KEY`
- `ARC_RPC_URL`
- `ARC_CHAIN_ID`
- `ARC_WALLET_ADDRESS`
- `ARC_PRIVATE_KEY`
- `ARC_EXPLORER_BASE_URL`
- `X402_GATEWAY_BASE_URL`
- `X402_GATEWAY_API_KEY`
- `AISA_API_KEY`
- `AISA_BASE_URL`
- `PRESET_REPO_URL`
- `PRESET_TARGET_URL`

默认值固定为：
- `OPENAI_MODEL=gpt-4.1-mini`
- `CHROME_DEBUG_URL=http://127.0.0.1:9222`

### 部署形态
- 采用 Linux 容器或 VM 部署。
- 启动时先启动 Chromium。
- 再启动 FastAPI。
- 健康检查固定检查：
  - `/`
  - `/api/health`
  - `CHROME_DEBUG_URL/json/version`

### 启动流程
部署入口固定为两步：
1. Chromium 以 headless 模式启动并打开 `9222`
2. `uvicorn launchshield.app:app --host 0.0.0.0 --port 8000`

## 具体实施顺序
### 阶段 1：Web 骨架与运行模型
- 新增 `launchshield/` 包和 FastAPI 入口。
- 挂载 `templates/` 和 `static/`。
- 加入 `POST /api/runs`、`GET /api/runs/{id}`、`GET /api/runs/{id}/events`。
- 建立 `ScanRun` 和 JSON 存储。
- 跑通“创建 run -> 页面收到 fake 事件 -> 页面展示进度”的最小闭环。

### 阶段 2：预置档与价格系统
- 固定 `preset-stress` 和 `custom-standard` 档位。
- 固定调用配额和单价。
- 页面显示预计交易数和总成本。
- 页面上先把利润矩阵跑通。

### 阶段 3：GitHub 仓库读取与文件扫描
- 拉公共仓库树。
- 选中配额内文件。
- 执行文件扫描规则。
- 落 finding。
- 写入工具调用记录。

### 阶段 4：依赖检查
- 解析依赖清单。
- 执行漏洞查询。
- 产出高危依赖 finding。
- 加入计费流水。

### 阶段 5：浏览器探针
- 复用 `arc_helper.cdp.CdpClient` 连接 `9222`
- 对目标站点执行固定探针
- 产出站点级 finding
- 让交易流水开始具有“安全扫描爆发感”

### 阶段 6：支付接入
- 接入 x402/Gateway 风格支付层
- 每次工具调用真实提交 sandbox 交易
- 写入 tx hash、Explorer URL、Console reference
- 页面中所有流水切换为真实 receipt

### 阶段 7：LLM 深度分析与修复建议
- 按高危 finding 数量收敛需要分析的片段
- 调真实 LLM 输出分析与修复建议
- 生成最终结果卡片

### 阶段 8：AIsa 验证
- 对高危 finding 或高危依赖走 AIsa
- 把情报结果挂到 finding 明细里
- 页面展示 “Verified with AIsa” 标签

### 阶段 9：结果页打磨与视觉优化
- 完成交易瀑布流
- 完成风险摘要卡
- 完成利润矩阵
- 完成红色结论区块
- 调整为录屏友好的布局和节奏

### 阶段 10：部署与提交资产
- 部署到公网 URL
- 验证预置压力档可跑完
- 录视频脚本
- 生成 PPT 大纲
- 整理提交 checklist

## 测试计划
### 单元测试
新增测试覆盖以下点：
- 定价全都 `< $0.01`
- `preset-stress` 总调用数固定 `63`
- `custom-standard` 总调用数固定 `34`
- 传统 Gas 公式正确
- run 状态机正确
- finding 严重级别汇总正确
- 文件过滤与配额选择正确
- 依赖提取逻辑正确

### API 测试
覆盖以下场景：
- `preset-stress` 创建成功
- `custom-standard` 输入合法时创建成功
- 非 GitHub URL 被拒绝
- 非 `http/https` 目标站点被拒绝
- 非法 `mode` 被拒绝
- run 完成后摘要接口返回完整 totals
- SSE 事件顺序正确

### 集成测试
覆盖以下场景：
- fake 支付网关下完整跑通预置档
- fake GitHub provider 下完整产出 finding
- fake CDP target 下完整产出站点 finding
- fake LLM 下完整产出修复建议
- JSON 持久化后页面刷新能恢复 run

### 真实环境 smoke test
固定执行：
- 使用真实 sandbox 凭证
- 连接真实 Arc Explorer
- 跑一次预置压力档
- 核验：
  - 交易数 `>= 50`
  - 所有 payment 都有 `tx_hash`
  - 至少一条流水能从页面跳转到 Arc Explorer
  - 至少一条 Circle Console 证明可在录屏中展示

### 手工验收清单
验收通过的标准固定为：
- 首页 3 秒内可见主按钮
- 预置按钮点击后 1 秒内出现第一条流水
- 预置 run 全流程能在可录屏时间内完成
- 最终页出现 finding、tx、利润矩阵
- 红色利润结论区块清晰可读
- 自定义输入至少能成功跑一个标准档

## 提交资产计划
### 视频脚本
新增：
- `docs/hackathon/video-script.md`

脚本结构固定为：
1. 问题陈述
2. 产品一句话
3. 点击 `Execute & Stress Test`
4. 展示交易瀑布
5. 展示风险结果
6. 展示 Circle Console
7. 展示 Arc Explorer
8. 展示利润矩阵
9. 收尾总结

### PPT 大纲
新增：
- `docs/hackathon/ppt-outline.md`

PPT 页序固定为：
1. Problem
2. Why micropayments matter
3. Product overview
4. System architecture
5. Live run breakdown
6. Circle payment proof
7. Arc Explorer proof
8. Business model
9. Market and users
10. Roadmap

### 提交核对清单
新增：
- `docs/hackathon/submission-checklist.md`

清单固定核对：
- GitHub 仓库公开
- 公网 URL 可访问
- 视频链接可访问
- PPT 可访问
- Circle Console 证明已截图
- Arc Explorer 证明已截图
- `50+` 笔交易有证据
- 单次价格 `< $0.01`
- 利润对比页面和 PPT 一致

## 假设与默认值
- Arc/Circle sandbox 凭证已经就绪。
- AIsa 接口可用。
- 预置仓库和预置站点由你们自己控制，能稳定复现。
- 部署环境支持 Chromium 和 9222。
- 这版以演示稳定性和评分表现为第一优先级。
- [main.py](D:/1goose/arc_house_helper/main.py) 和现有 CLI 逻辑不纳入这次产品改造范围。
