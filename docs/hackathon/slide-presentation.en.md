# LaunchShield Swarm - Detailed Slide Presentation (English)

This file is a detailed English deck draft for the LabLab submission.

Recommended length:
- `10 slides`
- `3-5 minutes` for a live pitch
- `6-10 minutes` for a fuller walkthrough with Q&A

Recommended structure:
- Use the slide titles below as your final slide titles.
- Keep each slide visually simple.
- Put the boldest claim in large text.
- Use screenshots from `docs/hackathon/screenshots/` where noted.

---

## Slide 1 - Title / Core Thesis

### Slide Title

`LaunchShield Swarm`

### Main Message

`AI security is already a swarm of tiny actions. Billing and proving each action is the missing layer.`

### On-Slide Copy

`One audit becomes dozens of atomic security tool calls.`

`LaunchShield Swarm turns those calls into a live execution feed, a live billing feed, and a verifiable evidence trail.`

### Supporting Bullets

- Repo scans
- Dependency checks
- Browser probes
- Deep LLM analysis
- Verification and fix suggestions

### Visual Suggestion

- Use the product hero screenshot: `01-hero.png`
- Dark background
- Large product name
- One strong subtitle

### Speaker Notes

LaunchShield Swarm is an AI security audit demo built around one idea: agent work should be billed and settled one tool call at a time. A modern audit is not one monolithic action. It is a swarm of small, repeated, high-frequency operations. We built the missing layer that makes those operations traceable, priced, and provable.

---

## Slide 2 - Problem

### Slide Title

`The execution model already changed. The payment model did not.`

### Main Message

`AI security work creates many high-signal actions with very low value per call. Traditional payment rails kill the economics.`

### On-Slide Copy

`1 audit != 1 action`

`1 audit = 40+ to 60+ tool calls`

`Each call matters. Each call is too cheap for legacy settlement.`

### Supporting Bullets

- AI security pipelines fan out into many specialized sub-tasks
- Each sub-task may cost less than one cent
- Card rails and high-gas settlement models are too expensive per action
- Flat pricing hides execution quality, cost, and provenance

### Visual Suggestion

- Show one audit branching into many boxes
- Each box labeled with a micro-price such as `$0.001`, `$0.003`, `$0.005`

### Speaker Notes

The core problem is economic, not just technical. AI systems increasingly do valuable work through many tiny operations. In security, one user request can trigger repository inspection, dependency parsing, browser checks, LLM review, verification, and remediation guidance. Every action is individually meaningful, and every action is individually too cheap for legacy settlement assumptions.

---

## Slide 3 - Why Micropayments Matter

### Slide Title

`Micropayments turn AI work from a black box into a priced workflow.`

### Main Message

`When each tool call has a price, a result, and a receipt, the workflow becomes commercially legible.`

### On-Slide Copy

`Per-call settlement creates:`

- Fair usage-based billing
- Tool-level provenance
- Auditable receipts
- Better margins for high-frequency AI workflows

### Supporting Bullets

- Buyers see what happened
- Builders see where value is created
- Platforms can price workflows without hiding cost in subscriptions
- Security teams get proof, not just summaries

### Visual Suggestion

- A row of cards showing:
  - `Invocation`
  - `Price`
  - `Result`
  - `Receipt`

### Speaker Notes

We are not just saying micropayments are cheaper. We are saying they unlock a better product model. Once each invocation has a price and a receipt, the workflow becomes measurable. You can audit execution quality, reconcile spending, prove service delivery, and support agentic systems whose value is created through many tiny actions rather than one giant transaction.

---

## Slide 4 - Product Overview

### Slide Title

`What LaunchShield Swarm does`

### Main Message

`LaunchShield Swarm breaks one AI security audit into priced micro-tasks and renders the whole run live.`

### On-Slide Copy

`A single run includes:`

- Repository file scanning
- Dependency vulnerability lookups
- Live site probing
- Deep LLM review of high-risk findings
- Verification and fix suggestions

`Every invocation has a target, price, output, and settlement record.`

### Supporting Bullets

- FastAPI web app
- Server-Sent Events for live updates
- Pricing matrix under `$0.01` per tool call
- Mock-first demo flow
- Real-provider mode for Arc, Circle, GitHub, browser, and LLM integrations

### Visual Suggestion

- Use `01-hero.png`
- Add 3 callouts:
  - `Atomic tool calls`
  - `Live billing waterfall`
  - `Per-call evidence`

### Speaker Notes

The product experience is designed to make the economics visible. You start a run once. The system then fans out into many atomic invocations. The interface shows progress, billing, findings, and profitability together, so the user sees one coherent story: what ran, what it found, what it cost, and why the workflow is economically viable on Arc.

---

## Slide 5 - Architecture

### Slide Title

`System architecture`

### Main Message

`A provider-based orchestration layer turns AI security work into billable, observable execution.`

### On-Slide Copy

`Frontend`

- FastAPI + templated UI
- SSE for real-time run streaming

`Core runtime`

- Orchestrator
- Pricing engine
- Run storage
- Profitability model

`Provider adapters`

- GitHub / repo source
- Browser runtime
- LLM analysis
- AIsa verification
- Arc / Circle settlement

### Supporting Bullets

- Mock-first by default
- Real providers can be enabled one by one
- Full repository scan mode supported
- Mock-vs-real source labels are shown in the UI

### Visual Suggestion

- Diagram with three layers:
  - UI
  - Orchestrator core
  - Provider adapters

### Speaker Notes

The architecture is intentionally modular. The orchestrator owns the run. It emits events, charges per invocation, and collects evidence. Each subsystem is behind a provider adapter, so the same product can run in fully mocked mode for demos or in real mode for live settlement and live analysis. That makes the system easy to demonstrate and easy to extend.

---

## Slide 6 - Live Execution and Billing

### Slide Title

`One run becomes a live waterfall of paid actions`

### Main Message

`The billing feed is not decoration. It is the product proof.`

### On-Slide Copy

`Preset stress run`

- `63` paid tool invocations
- `$0.001 - $0.008` per call
- Every row tied to a target and a tool type
- Every row can carry a settlement reference

### Supporting Bullets

- The user sees execution and settlement together
- The feed creates a native audit trail
- Cost and provenance are visible at tool-call granularity

### Visual Suggestion

- Use `02-execution-progress.png` and `03-billing-waterfall.png`
- Left side: progress and run status
- Right side: scrolling billing feed

### Speaker Notes

This slide shows the heart of the product. A run is not summarized at the end after everything disappears. Instead, the system exposes a live waterfall of atomic work. Every row tells a story: what ran, what it targeted, how much it cost, and whether settlement is confirmed. This is the point where AI workflow economics become visible and credible.

---

## Slide 7 - Real Security Findings

### Slide Title

`This is not just billing. The system produces security value.`

### Main Message

`LaunchShield Swarm turns execution into findings, evidence, and remediation guidance.`

### On-Slide Copy

`Example findings`

- Hardcoded secrets
- Dangerous `eval()` usage
- Missing security headers
- Dependency risk signals

`Each finding is tied back to the invocation that produced it.`

### Supporting Bullets

- Evidence is attached to each finding
- LLM deep review expands high-risk findings
- Verification layers help prioritize remediation
- Fix suggestions make the workflow actionable

### Visual Suggestion

- Use `04-findings-top.png`
- Highlight one critical finding and one high finding

### Speaker Notes

The system has to earn the right to bill. It does that by producing actual security value. As the run progresses, it identifies concrete problems and ties them back to the specific invocation that found them. That means the user is not just paying for activity. The user is paying for traceable, inspectable outcomes.

---

## Slide 8 - Proof of Settlement on Circle and Arc

### Slide Title

`Live billing rows can be matched to real settlement proof`

### Main Message

`The same billing feed can be traced into external payment and chain evidence.`

### On-Slide Copy

`Proof chain`

`Billing row -> payment reference -> Circle console -> Arc Explorer`

### Supporting Bullets

- Every settlement can be cross-checked
- External proof strengthens trust for usage-based AI services
- Tool-level receipts are more transparent than aggregate invoices

### Visual Suggestion

- Use `06-circle-console.png`
- Use `07-arc-explorer.png`
- If space is tight, put Circle on the main slide and Arc as an inset

### Speaker Notes

This slide closes the trust loop. The live billing feed inside the app is not a simulated ledger UI. In real mode, those rows can be matched against external settlement evidence. That is important for agentic systems, where trust comes from verifiable execution and verifiable payment, not from a single final invoice.

---

## Slide 9 - Business Model and Economic Case

### Slide Title

`Why Arc + stablecoin settlement matters economically`

### Main Message

`Traditional gas-heavy settlement destroys the margin of high-frequency AI security workflows.`

### On-Slide Copy

`Example economics from the product model`

- AI service cost: `$0.152`
- Arc / Circle settled cost: `0.152 USDC`
- Traditional EVM gas estimate: `$3.15`

`Same workflow. Very different business outcome.`

### Supporting Bullets

- High frequency
- Low ticket size
- Many repeated actions
- Margin-sensitive workflow

### Visual Suggestion

- Use `05-profitability-matrix.png`
- Make the traditional gas column red
- Make the Arc / Circle column the “viable path”

### Speaker Notes

This is the hackathon argument in one slide. Our thesis is that the next generation of AI workflows will create value through many tiny operations. If the settlement layer is too heavy, the business model breaks. Arc and stablecoin micropayments make it possible to charge fairly, preserve margin, and keep the workflow transparent.

---

## Slide 10 - Users, Wedge, and Why Now

### Slide Title

`Who needs this first`

### Main Message

`The first wedge is security teams and platforms that already understand the pain of opaque AI cost and provenance.`

### On-Slide Copy

`Initial users`

- AppSec teams
- Security consultancies
- AI agent platforms
- Developer tool marketplaces

`Core buyer pain`

`"I cannot ship an agent that costs more to settle than it charges."`

### Supporting Bullets

- Security has clear outputs and high trust requirements
- Buyers care about proof, traceability, and unit economics
- Agent marketplaces need usage-based monetization primitives

### Visual Suggestion

- 2x2 grid of user groups
- Quote callout in a contrasting accent block

### Speaker Notes

We chose AI security because it is a strong wedge. The workflow is easy to understand, the trust requirements are high, and the unit economics are immediately visible. If you can make per-call settlement work here, the same model extends to other agentic workflows such as monitoring, optimization, QA, and autonomous operations.

---

## Slide 11 - Roadmap

### Slide Title

`Roadmap`

### Main Message

`This MVP proves the workflow. The roadmap expands precision, integrations, and deployment depth.`

### On-Slide Copy

`Near term`

- Multi-tenant runs and team workspaces
- Richer scanners and better finding quality
- Deeper AIsa integration
- More real-provider hardening

`Mid term`

- Agent marketplace integrations
- Repeatable production billing flows
- Better dashboards for many tiny settlements

`Long term`

- Arc mainnet launch
- Production-grade usage-based security workflows

### Visual Suggestion

- Timeline or three-column roadmap
- Use a strong accent only on the Arc mainnet milestone

### Speaker Notes

This project is intentionally an MVP. It proves the product logic and the economic logic. The next stage is depth: better detection, stronger provider integrations, more production-ready settlement flows, and deployment into real team environments. The long-term goal is a category where agent work is priced, settled, and audited natively.

---

## Slide 12 - Closing / Ask

### Slide Title

`LaunchShield Swarm`

### Main Message

`Billable. Traceable. Verifiable AI security workflows.`

### On-Slide Copy

`We built a product that makes AI security audits visible at the tool-call level.`

`Arc and Circle make the workflow economically viable.`

`That is why this belongs in the agentic economy on Arc.`

### Footer

- GitHub repo
- Demo URL
- Team name: `Red Snail`

### Visual Suggestion

- Return to the hero screen
- Keep this slide visually clean
- One strong closing sentence

### Speaker Notes

LaunchShield Swarm is our argument for a new AI product primitive: the paid, provable micro-task. AI security is the first use case. The broader opportunity is any workflow where one request becomes many tiny, valuable, high-frequency actions. Arc and stablecoin micropayments make that model viable.

---

## Optional Appendix Slides

Use these only if you want a longer deck.

### Appendix A - Pricing Matrix

- Show all six tool prices
- Emphasize that every call stays below `$0.01`

### Appendix B - Provider Modes

- Mock-first mode
- Real-provider mode
- Explicit source labeling in the UI

### Appendix C - Full Repository Scan

- Explain `sample` vs `full`
- Position it as a realism upgrade for users who want deeper coverage

### Appendix D - Demo Evidence Checklist

- Hero screenshot
- Execution progress
- Billing waterfall
- Findings
- Profitability matrix
- Circle console
- Arc Explorer

---

## Build Notes

If you turn this into a real deck:

- Keep Slide 1 and Slide 12 dark
- Keep content slides light for readability
- Use one strong accent color
- Prefer screenshots over dense diagrams when possible
- Keep slide text shorter than this draft when moving into final design

