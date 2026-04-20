# LaunchShield Swarm 使用手册

## 1. 项目是做什么的

LaunchShield Swarm 是一个 FastAPI 演示应用。它把一次 AI 安全审计拆成很多个细粒度工具调用，并给每次调用单独计价、单独结算。

一次完整扫描会覆盖两类目标：

- 仓库级静态扫描：扫描公开 GitHub 仓库里的源码和依赖清单
- 站点级探测：对目标站点做 HTTP 和页面层面的安全探测

页面会实时展示：

- 当前跑到哪个阶段
- 每一笔工具调用对应的支付状态
- 扫描出的高危问题
- 微支付模式和传统 gas 模式的成本对比

这个项目默认采用 `mock-first` 模式，开箱即跑，不需要外部密钥。等你准备好凭证后，再按开关逐步切到真实 GitHub、真实 OpenAI、真实 AIsa、真实 Arc 支付。

## 2. 你会用到哪些能力

### `preset-stress`

用于演示、录屏、比赛展示。

- 固定目标
- 固定 63 次调用
- 一键执行
- 最适合验证整条链路和利润矩阵

### `custom-standard`

用于给别人看“这不是写死的回放”。

- 你自己输入 GitHub 仓库 URL
- 你自己输入目标站点 URL
- 固定 34 次调用
- 更适合日常演示和低成本验证

## 3. 运行前准备

建议环境：

- Python `3.11` 或 `3.12`
- PowerShell
- 能访问目标站点和 GitHub 的网络环境

如果你要跑 `custom-standard`，还需要准备：

- 一个公开 GitHub 仓库 URL，格式必须是 `https://github.com/<owner>/<repo>`
- 一个可访问的 `http://` 或 `https://` 站点 URL

## 4. 本地快速启动

### 第一步：创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 第二步：复制环境变量模板

```powershell
Copy-Item .env.example .env
```

默认情况下，`.env.example` 里的所有 `USE_REAL_*` 都是 `false`。这套默认值已经可以完整跑通页面和演示流程。

### 第三步：启动服务

```powershell
uvicorn launchshield.app:app --host 127.0.0.1 --port 8000 --reload
```

浏览器打开：

```text
http://127.0.0.1:8000
```

### 第四步：确认服务正常

先看页面能否正常打开，再访问健康检查：

```text
http://127.0.0.1:8000/api/health
```

如果返回 `status: ok`，说明服务已经起来了。这里也会显示当前是否启用了真实支付、真实 LLM、真实 AIsa、真实 GitHub、真实浏览器模式。

## 5. 页面怎么用

首页只有两个入口，使用路径很直接。

### 5.1 `Execute & Stress Test`

点击首页左侧主按钮后，系统会直接使用预设目标启动一次 `preset-stress`。

预设目标来自环境变量：

- `PRESET_REPO_URL`
- `PRESET_TARGET_URL`

默认值已经在 `.env.example` 里给好。你也可以自己改成别的演示目标。

这个模式会触发以下固定配额：

| 工具 | 次数 |
| --- | ---: |
| `file_scan` | 25 |
| `dep_lookup` | 15 |
| `site_probe` | 12 |
| `deep_analysis` | 6 |
| `aisa_verify` | 3 |
| `fix_suggestion` | 2 |
| 总计 | 63 |

### 5.2 `Run Standard Scan`

在右侧表单里填入：

- `GitHub Repo URL`
- `Target Site URL`

然后点击按钮，系统会启动一次 `custom-standard`。

这个模式的固定配额更轻：

| 工具 | 次数 |
| --- | ---: |
| `file_scan` | 12 |
| `dep_lookup` | 6 |
| `site_probe` | 8 |
| `deep_analysis` | 4 |
| `aisa_verify` | 2 |
| `fix_suggestion` | 2 |
| 总计 | 34 |

### 5.3 页面上的每个区域怎么看

#### `Execution`

这里看整体进度。

- `run-mode`：当前是 `preset-stress` 还是 `custom-standard`
- `run-id`：本次运行的唯一 ID
- 进度条：已完成调用数 / 计划调用数
- `progress-stage`：当前阶段名
- `Completed`：已结束的调用数，包含成功和失败
- `Confirmed txns`：支付已确认的调用数
- `Critical / High / Medium / Low`：当前累计问题级别统计

阶段顺序固定如下：

1. `repo.fetch`
2. `repo.file_scan`
3. `repo.dep_lookup`
4. `site.browser_probes`
5. `analysis.deep_review`
6. `analysis.aisa_verify`
7. `analysis.fix_suggestions`
8. `summary.profitability`
9. `summary.finalize`

#### `Streaming Billing`

这里看每次工具调用的支付流水。

每一行对应一次 invocation，包含：

- 时间
- 工具名
- 目标
- 金额
- 交易状态或交易链接

常见状态：

- `invoked`：调用已创建
- `submitted`：支付已提交
- `confirmed`：支付已确认
- `failed`：本次调用失败

当支付完成后，这里会展示短交易哈希。带链接时，点击可以跳到区块浏览器。

#### `Top Findings`

这里显示当前最重要的问题摘要。页面会保留最近的 10 条卡片。

完整结果要看：

- `/api/runs/<run_id>`
- `data/runs/<run_id>.json`
- `data/runs/<run_id>-artifacts/findings.json`

#### `Profitability Matrix`

这里看这套商业模型是否成立。

- `Total AI Service Cost`：工具调用理论成本总和
- `Arc / Circle Settled Cost`：微支付实际结算金额
- `Traditional EVM Gas Estimate`：如果每次都走传统链上 gas，大概会花多少

这个区域是整套演示里最重要的产品叙事之一。

#### `Pricing Matrix`

这里是每个工具的单价。所有工具都保持在 `$0.01` 以下。

当前定价如下：

| 工具 | 单价（USD） |
| --- | ---: |
| `file_scan` | 0.001 |
| `dep_lookup` | 0.002 |
| `site_probe` | 0.003 |
| `deep_analysis` | 0.005 |
| `aisa_verify` | 0.005 |
| `fix_suggestion` | 0.008 |

## 6. `.env` 应该怎么配

### 6.1 最常用的基础变量

| 变量 | 作用 |
| --- | --- |
| `APP_ENV` | 运行环境标识，默认 `development` |
| `HOST` | 监听地址 |
| `PORT` | 监听端口 |
| `LAUNCHSHIELD_DATA_DIR` | 运行产物目录，默认 `data` |
| `LAUNCHSHIELD_DEMO_PACE_SECONDS` | mock 模式下的演示节奏，数值越大越慢 |
| `PRESET_REPO_URL` | 预设仓库 URL |
| `PRESET_TARGET_URL` | 预设站点 URL |

### 6.2 五个 `USE_REAL_*` 开关

| 开关 | 打开后的行为 | 必要条件 |
| --- | --- | --- |
| `USE_REAL_GITHUB` | 真实拉取 GitHub 仓库树和源文件 | 公开 GitHub 仓库；`GITHUB_TOKEN` 可选 |
| `USE_REAL_LLM` | 用 OpenAI 兼容接口生成深度分析和修复建议 | `OPENAI_API_KEY` |
| `USE_REAL_AISA` | 调用真实 AIsa 验证高危问题 | `AISA_API_KEY` 和 `AISA_BASE_URL` |
| `USE_REAL_PAYMENTS` | 每次调用都走真实 Arc testnet 支付 | `ARC_PRIVATE_KEY`，或 `X402_GATEWAY_*` |
| `USE_REAL_BROWSER` | 预留浏览器真机路径 | 当前版本主要仍由 HTTP 探测完成 |

### 6.3 默认模式和真实模式的边界

这部分很重要，建议直接按下面理解：

- `USE_REAL_GITHUB=false`
  - 仓库扫描使用仓库内置的 fixture 数据
  - 你在页面里填的 GitHub URL 仍然会做格式校验
- `USE_REAL_GITHUB=true`
  - 仓库扫描真正请求 GitHub API 和 raw 文件内容
- `USE_REAL_LLM=true` 且设置了 `OPENAI_API_KEY`
  - `deep_analysis` 和 `fix_suggestion` 会走真实 OpenAI
- `OPENAI_BASE_URL` 有值
  - 真实 LLM 会改走你指定的 OpenAI 兼容接口地址
- `USE_REAL_LLM=true` 但没配 `OPENAI_API_KEY`
  - 仍然会回落到 mock LLM
- `USE_REAL_LLM=false`
  - 分析阶段仍会继续执行
  - `deep_analysis` 和 `fix_suggestion` 会使用内置 mock LLM，方便把整条演示链路跑完
- `USE_REAL_AISA=true` 且同时设置了 `AISA_API_KEY` 与 `AISA_BASE_URL`
  - AIsa 验证走真实服务
- `USE_REAL_AISA=true` 但凭证不完整
  - 仍然会回落到 mock AIsa
- `USE_REAL_PAYMENTS=false`
  - 支付用 mock receipt，页面会展示看起来真实的交易哈希和浏览器链接
- `USE_REAL_PAYMENTS=true`
  - 每次调用先支付，再执行工具逻辑
  - 凭证缺失时会直接导致 run 失败
- `USE_REAL_BROWSER=true`
  - 当前版本保留了开关和配置项
  - 现有 probe 主要依赖 HTTP 抓取和轻量页面分析，CI 也按这个路径跑

### 6.4 推荐的切换顺序

建议按这个顺序推进：

1. 所有 `USE_REAL_*` 保持 `false`，先确认页面、SSE、产物目录都正常
2. 打开 `USE_REAL_GITHUB=true`，先验证真实仓库扫描
3. 打开 `USE_REAL_LLM=true`，验证深度分析和修复建议
4. 打开 `USE_REAL_AISA=true`，验证情报相关能力
5. 最后打开 `USE_REAL_PAYMENTS=true`，先跑一次 `custom-standard`
6. 全链路确认后，再跑 `preset-stress`

## 7. 如何切到真实 Arc 支付

### 7.1 必要变量

最常用的一组是：

```dotenv
USE_REAL_PAYMENTS=true
ARC_PRIVATE_KEY=0x...
```

常见补充项：

| 变量 | 作用 |
| --- | --- |
| `ARC_RPC_URL` | Arc testnet RPC |
| `ARC_CHAIN_ID` | 默认 `5042002` |
| `ARC_USDC_ADDRESS` | Arc testnet USDC 系统合约 |
| `ARC_EXPLORER_BASE_URL` | 区块浏览器地址 |
| `ARC_MERCHANT_ADDRESS` | 收款方地址，默认可用自转账演示 |
| `ARC_PAYMENT_AMOUNT_OVERRIDE_USDC` | 固定每笔实际支付额度，方便节省 faucet 余额 |
| `ARC_TX_TIMEOUT_SECONDS` | 单笔确认超时时间 |

### 7.2 推荐操作步骤

```powershell
Copy-Item .env.example .env
```

把 `.env` 改成自己的真实值后，先做预检：

```powershell
.\.venv\Scripts\python.exe scripts\check_arc_testnet.py
```

这一步会检查：

- RPC 是否可访问
- 钱包地址是否可导出
- USDC 余额是否足够

接着做一笔真实小额转账：

```powershell
.\.venv\Scripts\python.exe scripts\check_arc_testnet.py --send
```

这一步成功后，再重启应用并跑一次 `custom-standard`。

### 7.3 预算建议

真实支付模式下，建议先用 `custom-standard` 做首轮验证，再跑 `preset-stress`。

如果你只是想验证支付链路，不想消耗太多 faucet 余额，可以设置：

```dotenv
ARC_PAYMENT_AMOUNT_OVERRIDE_USDC=0.001
```

更完整的链上接线说明见：

- [Arc Testnet Wiring](./arc-testnet.md)

## 8. 运行结果存在哪里

### 8.1 主运行文件

每次运行都会写入：

```text
data/runs/<run_id>.json
```

这个文件会在运行过程中持续更新，适合做状态追踪和故障排查。

### 8.2 完成后的归档目录

运行成功结束后，还会写入：

```text
data/runs/<run_id>-artifacts/
```

目录内固定包含：

- `summary.json`
- `invocations.json`
- `findings.json`
- `profitability.json`

### 8.3 每个文件怎么看

| 文件 | 用途 |
| --- | --- |
| `summary.json` | 本次 run 的完整汇总 |
| `invocations.json` | 每次工具调用的详细记录、支付信息和结果摘要 |
| `findings.json` | 所有发现的问题 |
| `profitability.json` | 成本与利润矩阵快照 |

补充说明：

- 失败的 run 一定会留下 `data/runs/<run_id>.json`
- `*-artifacts/` 在成功完成的 run 上最稳定
- 页面里的 `Top Findings` 只展示一部分，完整数据以 JSON 为准

## 9. 不走页面，直接调 API

### 9.1 健康检查

```powershell
Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8000/api/health'
```

### 9.2 创建一次预设运行

```powershell
$body = @{
  mode = 'preset-stress'
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/api/runs' `
  -ContentType 'application/json' `
  -Body $body
```

### 9.3 创建一次自定义运行

```powershell
$body = @{
  mode = 'custom-standard'
  repo_url = 'https://github.com/owner/repo'
  target_url = 'https://example.com'
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/api/runs' `
  -ContentType 'application/json' `
  -Body $body
```

### 9.4 查看运行摘要

```powershell
Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8000/api/runs/<run_id>'
```

### 9.5 查看 SSE 事件流

```powershell
curl.exe -N http://127.0.0.1:8000/api/runs/<run_id>/events
```

事件类型固定如下：

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

## 10. 常见问题与排错

### 10.1 `repo_url and target_url are required`

你启动的是 `custom-standard`，但表单或请求体里没有同时提供仓库 URL 和站点 URL。

### 10.2 `repo_url must be a public GitHub URL`

只接受这种格式：

```text
https://github.com/<owner>/<repo>
```

当前版本只支持公开 GitHub 仓库。

### 10.3 `target_url must be http:// or https://`

站点 URL 必须带协议头，例如：

- `https://example.com`
- `http://127.0.0.1:3000`

### 10.4 页面里看到了你的站点结果，但仓库扫描看起来像演示数据

这通常意味着：

- 你填写了真实 `target_url`
- 站点探测确实在打真实目标
- `USE_REAL_GITHUB` 仍然是 `false`

此时仓库扫描部分仍然来自内置 fixture。

### 10.5 打开了 `USE_REAL_LLM=true`，结果还是像 mock

检查：

- `OPENAI_API_KEY` 是否已设置
- 服务是否重启

当前实现里，`USE_REAL_LLM=true` 且 `OPENAI_API_KEY` 有值时才会切到真实 OpenAI。

### 10.6 打开了 `USE_REAL_AISA=true`，结果还是像 mock

检查：

- `AISA_API_KEY`
- `AISA_BASE_URL`

两个值都齐全时，AIsa 才会走真实服务。

### 10.7 一开启 `USE_REAL_PAYMENTS=true` 就直接失败

优先检查：

- `ARC_PRIVATE_KEY` 是否存在
- 或者 `X402_GATEWAY_BASE_URL` 和 `X402_GATEWAY_API_KEY` 是否同时存在

支付是整条链路的前置步骤。支付失败时，这次 run 会直接失败。

### 10.8 真实 Arc 支付确认慢

可以检查：

- RPC 连通性
- 钱包余额
- `ARC_TX_TIMEOUT_SECONDS` 是否过小

先跑：

```powershell
.\.venv\Scripts\python.exe scripts\check_arc_testnet.py
```

### 10.9 SSE 显示 `disconnected`

这代表浏览器和事件流连接中断。处理顺序建议如下：

1. 先查 `/api/runs/<run_id>` 看任务是否还在继续
2. 再看 `data/runs/<run_id>.json` 是否还在更新
3. 页面刷新后重新进入本次 run 的摘要数据

### 10.10 Windows 环境下 `pytest` 临时目录权限报错

这类问题通常和本机 ACL 或临时目录权限有关。先用下面两步做基础验证更稳：

```powershell
python -m compileall launchshield tests
uvicorn launchshield.app:app --host 127.0.0.1 --port 8000 --reload
```

先确认页面能完整跑通，再单独处理 `pytest` 环境权限。

## 11. 部署和比赛资料入口

部署和录屏资料已经拆到单独文档：

- [部署指南](../DEPLOY.md)
- [Arc Testnet 接线说明](./arc-testnet.md)
- [Hackathon 资料目录](./hackathon/)

如果你的目标是稳定演示，推荐顺序是：本地 mock 跑通，真实 GitHub 和 LLM 跑通，Arc 预检通过，最后再开真实支付录屏。

## 12. 2026-04-19 新增能力

### 12.1 全量仓库扫描

自定义扫描现在支持 `scan_scope`：

- `sample`
  - 继续使用标准 34 次调用档位
- `full`
  - 在 `repo.fetch` 完成后，按真实仓库内容动态展开
  - `file_scan` 会扫描全部允许类型的文件
  - `dep_lookup` 会检查全部解析出的依赖
  - 页面里的总调用数会在仓库元数据拉取完成后更新

页面表单里新增了 `Scan Scope` 下拉框。

### 12.2 真正的浏览器探针

`USE_REAL_BROWSER=true` 时：

- 系统会优先尝试通过 `CHROME_DEBUG_URL` 建立 CDP 会话
- `site_probe` 的主页探针会走真实浏览器导航和 JS 求值
- 如果本机没有可用的 CDP 浏览器端口，会自动回落到 HTTP fallback

### 12.3 mock / real 来源展示

首页现在新增 `Provider Sources` 面板，运行时会明确显示：

- `payments`
- `github`
- `browser`
- `llm`
- `aisa`

每个来源都会展示：

- 请求模式：用户要求的是 `mock` 还是 `real`
- 实际模式：当前真正跑的是 `mock`、`real` 或错误状态
- provider 名称和补充说明

`Streaming Billing` 每一行也会附带来源标签，尤其能直接看出 `deep_analysis` / `fix_suggestion` 用的是哪种 LLM，`aisa_verify` 用的是 mock 还是真实 AIsa。
