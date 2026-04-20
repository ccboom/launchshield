# LaunchShield Swarm

[![CI](https://github.com/Abdullahccgdq/launchshield/actions/workflows/ci.yml/badge.svg)](https://github.com/Abdullahccgdq/launchshield/actions/workflows/ci.yml)

AI security audits settled one tool call at a time — a FastAPI demo that fans out a
scan into dozens of atomic tool invocations and pays each one on-chain via
x402 / Arc Nanopayments.

This is the **hackathon submission MVP** described in `PLAN.md` in the parent folder.
The UI, SSE stream, scan engine and profitability matrix all ship in `mock-first`
mode so the full demo runs with zero external credentials. Swap environment flags to
call the real Arc / Circle / OpenAI / AIsa / GitHub providers.

## Documentation

- English quick overview: this `README.md`
- Change history: [`CHANGELOG.md`](CHANGELOG.md)
- Chinese step-by-step user manual: [`docs/user-manual.md`](docs/user-manual.md)
- Deployment guide: [`DEPLOY.md`](DEPLOY.md)
- Arc testnet payment wiring: [`docs/arc-testnet.md`](docs/arc-testnet.md)

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn launchshield.app:app --reload
```

Open http://127.0.0.1:8000 and press **Execute & Stress Test** — the preset run
fires 63 fully-priced tool calls back-to-back and renders the profitability matrix.

Custom runs accept a public GitHub URL and an `http(s)` target. They also support
`scan_scope=sample|full`: `sample` keeps the standard 34-call plan, while `full`
scans every eligible repo file plus every parsed dependency and updates the total
dynamically after `repo.fetch`.

## Environment switches

Copy `.env.example` to `.env` and flip the `USE_REAL_*` flags when credentials are
available:

| Switch | Effect |
| --- | --- |
| `USE_REAL_PAYMENTS` | Submit real USDC transfers on Arc testnet (`chain id 5042002`) via `ArcTestnetPaymentProvider`. Falls back to the x402 gateway skeleton only if `ARC_PRIVATE_KEY` is empty. See [`docs/arc-testnet.md`](docs/arc-testnet.md). |
| `USE_REAL_LLM` | Use an OpenAI-compatible LLM endpoint for `deep_analysis` and `fix_suggestion` |
| `USE_REAL_AISA` | POST high-severity findings to AIsa for intel correlation |
| `USE_REAL_GITHUB` | Pull trees + raw files from GitHub instead of the bundled fixture repo |
| `USE_REAL_BROWSER` | Attempt real CDP-backed page probes through `CHROME_DEBUG_URL`; fall back to HTTP probing when CDP is unavailable |

With the flags off (default) the orchestrator emits realistic-looking `tx_hash`
values, Explorer URLs and Console references so you can walk through the full
demo flow before the sandbox credentials land.

For LLM wiring, set `OPENAI_API_KEY`, `OPENAI_MODEL`, and optionally
`OPENAI_BASE_URL` when you are using an OpenAI-compatible gateway or proxy.
When `USE_REAL_LLM=false`, the analysis stages still run through the bundled
mock LLM provider so the demo stays complete end-to-end.

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
  browser_runtime.py Real CDP runtime with HTTP fallback
  site_probes.py    Header/path/DOM probes backed by the browser runtime
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

* The UI now shows effective provider sources for payments, GitHub, browser,
  LLM and AIsa so mock-vs-real fallback is explicit during a run.
* `USE_REAL_BROWSER=true` now attempts a real CDP session through
  `CHROME_DEBUG_URL`. If the browser is unavailable, the run falls back to HTTP
  probing and the browser source is marked as `mock`.
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
