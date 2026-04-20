# LaunchShield 代码审查报告

**范围**：合入 PR #1 之后的全仓库静态分析 + 人工核心逻辑审查  
**提交**：`d927e0a` → `8c1ced3` (main)  
**时间**：2026-04-20  
**工具**：`ruff 0.14.x`、`pyflakes`、人工阅读 orchestrator / payments / llm / browser_runtime / arc_chain  
**测试基线**：53 / 53 pytest pass（修复前后均通过）

---

## 0. TL;DR

一共命中 **17 处问题 / 改进点**，按严重度分桶：

| 等级 | 数量 | 是否修复 | 说明 |
|------|-----:|----------|------|
| 🔴 Bug / 正确性 | 1 | ✅ 已修 | 异常链丢失 |
| 🟡 潜在 Bug / 死代码 | 5 | ✅ 已修 | lambda late-binding × 4 + gas_used 死代码 × 1 |
| ⚪ 代码质量 | 11 | ✅ 已修 | 未用 import / 变量、可读性 |
| ⚫ 风格噪音（不修） | 164 | ❌ 故意保留 | E501 行长、I001 import 排序等，纯品味 |

**全部 11 个需要改的点都已修掉并推到 `main`。53 / 53 测试仍然通过。**

---

## 1. 高危：异常链丢失（1 处，已修）

### 1.1 `app.py:95`  B904 — raise-without-from-inside-except

**修前**：

```python
except ValueError as exc:
    logger.warning("run config invalid", error=str(exc))
    raise HTTPException(status_code=400, detail=str(exc))
```

**问题**：在 `except` 块里再 `raise` 一个新异常却没写 `from`，原 `ValueError` 的 traceback 会被吞掉，线上排错要靠猜。

**修后**：

```python
except ValueError as exc:
    logger.warning("run config invalid", error=str(exc))
    raise HTTPException(status_code=400, detail=str(exc)) from exc
```

**提交**：`8c1ced3`

---

## 2. 潜在 Bug / 死代码（5 处，已修）

### 2.1 `orchestrator.py` × 4 处  B023 — function-uses-loop-variable（lambda 晚绑定）

在 `_retry_once` 重试包装器的 4 个调用点，内联 lambda 捕获了循环 / 闭包里的可变变量：

| 行号 | 捕获的变量 | 风险 |
|---:|---|---|
| 502 | `snippet` | llm_review stage |
| 561 | `rule` | rules stage |
| 617 | `language` | dep_check stage |
| 847 | `target_finding` | profitability stage |

**原理**：Python 的 lambda 抓的是**名字引用**，不是当前值。如果未来有人把 `_retry_once` 改成并发 / 异步调度（例如换成 `asyncio.gather` 或 ThreadPool），lambda 实际执行时循环变量可能已经走到下一个值 → 静默算错。

**修法**（统一套路）：把循环变量用默认参数绑定死：

```python
# 修前
result = self._retry_once(lambda: self.llm.review_snippet(snippet, ...), ...)

# 修后
result = self._retry_once(
    lambda snippet=snippet: self.llm.review_snippet(snippet, ...),
    ...,
)
```

当前同步执行路径下 4 处**没有实际触发 bug**，属于**防御性修复**，杜绝"未来自己挖的坑"。

### 2.2 `arc_chain.py:157` — `gas_used` 死代码

**修前**：

```python
gas_used = receipt.get("gasUsed") or 0  # 读了但从不使用
return PaymentReceipt(
    ...,
    console_reference={"blockNumber": receipt.get("blockNumber")},
)
```

**问题**：本地算了 `gas_used` 又丢掉，导致 PaymentReceipt artifacts 里看不到链上 gas 消耗，hackathon 评审想验真都没法看。

**修后**：

```python
gas_used = receipt.get("gasUsed") or 0
return PaymentReceipt(
    ...,
    console_reference={
        "blockNumber": receipt.get("blockNumber"),
        "gasUsed": gas_used,
    },
)
```

顺便把 `tx_hash` 的 hex 格式化固定带 `0x` 前缀，避免后续 explorer 链接拼接混乱。

---

## 3. 代码质量（11 处，已修）

### 3.1 未用 import / 变量（F401 / F841）

| 文件 | 改动 |
|------|------|
| `launchshield/orchestrator.py` | 移除 `ProfitabilitySnapshot`、`FileMatch`、`RepoFile` 三个没被用到的 import（合并 PR 后遗症）|
| `launchshield/payments.py` | 移除单独的 `json` import（已在别处 import）|
| `launchshield/events.py` | 移除未用的 `uuid4` 别名 |
| `launchshield/repo_source.py` | 移除未用的 `urlparse` import |
| `tests/conftest.py` | 移除未用的 `os` |
| `tests/test_arc_provider.py` | 移除未用的 `ArcPaymentProvider`、未用局部变量 `receipt` |
| `tests/test_repo_scan_and_deps.py` | 移除未用的 `RepoFile` |

### 3.2 可读性（SIM103 / B007）

**`launchshield/repo_source.py:85-86`** — SIM103：

```python
# 修前
if path.startswith(("docs/", ".github/")):
    return False
return True

# 修后
return not path.startswith(("docs/", ".github/"))
```

**`launchshield/site_probes.py:140`** — B007 循环体变量没用：

```python
# 修前
for idx, body in enumerate(scripts):
    findings.append(... idx ...)

# 修后
for idx in range(len(scripts)):
    findings.append(... idx ...)
```

---

## 4. 核心逻辑人工审查（无改动，结论：OK）

对以下核心模块做了逐行阅读，结论**无需改**：

| 模块 | 审查点 | 结论 |
|------|--------|------|
| `orchestrator.py` | event bus、SSE backpressure、stage 串联、retry 策略 | 逻辑自洽。`_retry_once` 只重试一次符合 MVP 目标；SSE 用 asyncio.Queue 背压 OK |
| `llm.py` | OpenAI provider 超时 / fallback / mock | 超时有 `timeout=cfg.llm_timeout_seconds`；提供 mock fallback 合理 |
| `payments.py` | mock / x402 gateway / Arc testnet 三种路径 | `build_provider` 分支清晰；Arc provider 仅在显式开启 + 有私钥时启用 |
| `arc_chain.py` | web3.py 交互、EIP-1559 fee 估算、USDC ERC-20 `transfer` | 先查余额再发交易；`wait_for_transaction_receipt` 带超时；金额 decimals 单位处理正确（6 位）|
| `browser_runtime.py` | Playwright 子进程、超时控制 | 有 hard timeout；subprocess 标准输出/错误都捕获 |
| `repo_source.py` | GitHub tarball 抓取、路径白名单、大小限制 | `max_repo_size_bytes`、`max_file_size_bytes` 双层限制；tar 解压前校验路径防 zip-slip |
| `site_probes.py` | 外链 fetch、超时、robots | 5s timeout；user-agent 显式标注 |

---

## 5. 安全审查（无改动，结论：OK）

| 威胁面 | 现状 | 评级 |
|--------|------|------|
| SSRF（scan 目标是 URL） | `site_probes.safe_fetch` 走 `urllib` + 超时，未做 IP 黑名单但 MVP 可接受 | 🟡 低 |
| 路径遍历（tar 解压） | `repo_source._safe_extract` 校验相对路径未出 tmp 根 | ✅ 已挡 |
| CORS | `app.py` 默认 `allow_origins=["*"]` 仅 MVP；生产要收敛 | 🟡 文档化 |
| 密钥泄漏 | `.env.example` 全是占位；真 private key 靠 `ARC_PRIVATE_KEY` env 注入；demo fixture 里的 Stripe 秘钥已按 push protection 拆字符串 | ✅ |
| 日志脱敏 | `structlog` 输出不带私钥；`PaymentReceipt` 只存 `tx_hash` 和 `console_reference`，不存私钥 | ✅ |
| 依赖 CVE | 未跑 `pip-audit`（hackathon 前建议跑一次） | 🟡 TODO 可选 |

---

## 6. 刻意不修的（164 条，纯噪音）

运行 `ruff check launchshield tests scripts` 会看到的剩余提示，**全部是风格问题，不是 bug**：

| 规则 | 数量 | 含义 | 为什么不修 |
|------|----:|------|------------|
| E501 | 145 | 行长 > 88 列 | 黑线上挂条 URL / 一串 JSON literal 就会超，追着改会把 diff 搞得乱七八糟 |
| I001 | 11 | import 排序不规范 | 留给后续一次性 `ruff format --fix` 统一处理 |
| SIM105 | 4 | `try/except: pass` → `contextlib.suppress` | 品味问题，当前写法更显眼 |
| RUF100 | 2 | 冗余 `# noqa` | 无害 |
| RUF046 | 1 | `int(round(...))` 冗余（`arc_chain.py:139`）| round() 返回 int 是 Py3 行为，显式 int() 意图更清楚，保留 |
| B009 | 1 | `getattr(obj, "literal")` → `obj.literal`（`arc_chain.py:71`）| 为兼容 web3.py 新旧版本的属性差异，**必须**用 `getattr` |

想一键统一格式可以跑：

```bash
ruff check --fix launchshield tests scripts
ruff format launchshield tests scripts
```

但会造成一次 ~200 行纯风格 diff，**不建议**在评审期这样做。

---

## 7. 验证结果

```text
$ python -m pytest -q
.......................................................        [100%]
53 passed in 6.80s

$ ruff check --select F401,F841,B023,B904,B007,SIM103 launchshield tests scripts
All checks passed!

$ pyflakes launchshield tests scripts
(无输出)
```

---

## 8. 涉及提交

| Commit | 内容 |
|--------|------|
| `8c1ced3` | fix: address ruff/pyflakes findings from post-merge code review |
| `d927e0a` | Merge pull request #1（外部贡献者）|
| 之前提交 | MVP 实现、Arc testnet 接入、CI/CD、文档 |

远端：<https://github.com/Abdullahccgdq/launchshield>
