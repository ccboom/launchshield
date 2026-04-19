# LaunchShield Swarm

[![CI](https://github.com/Abdullahccgdq/launchshield/actions/workflows/ci.yml/badge.svg)](https://github.com/Abdullahccgdq/launchshield/actions/workflows/ci.yml)

AI security audits settled one tool call at a time — a FastAPI demo that fans out a
scan into dozens of atomic tool invocations and pays each one on-chain via
x402 / Arc Nanopayments.

This is the **hackathon submission MVP** described in `PLAN.md` in the parent folder.
The UI, SSE stream, scan engine and profitability matrix all ship in `mock-first`
mode so the full demo runs with zero external credentials. Swap environment flags to
call the real Arc / Circle / OpenAI / AIsa / GitHub providers.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn launchshield.app:app --reload
```

Open http://127.0.0.1:8000 and press **Execute & Stress Test** — the preset run
fires 63 fully-priced tool calls back-to-back and renders the profitability matrix.

Custom runs accept a public GitHub URL and an `http(s)` target; every UI element,
SSE event and JSON artefact is produced by the same code path used in preset mode.

## Environment switches

Copy `.env.example` to `.env` and flip the `USE_REAL_*` flags when credentials are
available:

| Switch | Effect |
| --- | --- |
| `USE_REAL_PAYMENTS` | Submit real USDC transfers on Arc testnet (`chain id 5042002`) via `ArcTestnetPaymentProvider`. Falls back to the x402 gateway skeleton only if `ARC_PRIVATE_KEY` is empty. See [`docs/arc-testnet.md`](docs/arc-testnet.md). |
| `USE_REAL_LLM` | Use OpenAI for `deep_analysis` and `fix_suggestion` |
| `USE_REAL_AISA` | POST high-severity findings to AIsa for intel correlation |
| `USE_REAL_GITHUB` | Pull trees + raw files from GitHub instead of the bundled fixture repo |
| `USE_REAL_BROWSER` | Reserved — engage the CDP path via `CHROME_DEBUG_URL` |

With the flags off (default) the orchestrator emits realistic-looking `tx_hash`
values, Explorer URLs and Console references so you can walk through the full
demo flow before the sandbox credentials land.

## Project layout

```
launchshield/
  app.py            FastAPI app, routes, SSE
  orchestrator.py   Phase runner, event bus, per-run background task
  models.py         Pydantic models for run / invocation / finding
  pricing.py        Fixed price matrix (< $0.01 per tool)
  presets.py        63-call stress tier + 34-call standard tier
  events.py         SSE event shaping
  storage.py        Thread-safe JSON registry under data/runs/
  payments.py       Mock + x402/Gateway adapters
  llm.py            Mock + OpenAI adapters
  aisa.py           Mock + real AIsa adapters
  repo_source.py    Mock + GitHub Tree/raw-content adapters
  repo_scan.py      File-level regex rules
  dep_check.py      Manifest parsers + static advisory DB
  browser_runtime.py Minimal HTTP+CDP-friendly runtime (replacement for the
                     originally-planned arc_house_helper.cdp module)
  site_probes.py    HTTP + browser-layer probes
  profitability.py  Traditional-gas vs micropayment cost model
templates/index.html     Single-page submission UI
static/app.js            EventSource wiring + live render
static/styles.css        Submission-ready dark theme
tests/                   Unit + API + integration tests
docs/hackathon/          Video script, PPT outline, submission checklist
```

## Tests

```powershell
pytest
```

The test suite covers pricing / tier invariants, the run state machine, API
validation, SSE ordering and end-to-end preset completion under the mock
providers.

## Mock vs real notes

* `browser_runtime.BrowserRuntime` deliberately falls back to HTTP-only fetch
  so the full suite runs on CI. Flip `USE_REAL_BROWSER=true` when you have a
  Chromium bound to `CHROME_DEBUG_URL` and want to extend the probe set.
* `payments.X402GatewayProvider` is a minimal skeleton — slot in the official
  Arc sandbox client when credentials are issued.
* `llm.OpenAIProvider` assumes the Chat Completions JSON mode. Swap to the
  Responses API if preferred.
* Mock settlement uses a deterministic SHA-256 hash of the memo + nonce so the
  UI always renders believable `0x…` transaction hashes.

## Hackathon deliverables

See `docs/hackathon/`:

* `video-script.md` — 90-second capture cue sheet
* `ppt-outline.md` — 10-slide deck
* `submission-checklist.md` — final go/no-go list

## Not in scope for this MVP

* Multi-tenant auth or persistent user sessions
* A production-grade vulnerability database
* GitHub Enterprise or private repositories
* Background queues, workers or external storage
