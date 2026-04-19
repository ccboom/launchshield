# PPT Outline — LaunchShield Swarm (10 slides)

## Slide 1 — Problem
"AI security is already a swarm — billing it is the unsolved problem."
Bullet: 1 audit ≈ 40+ tool calls, traditional rails bankrupt the margin.

## Slide 2 — Why micropayments matter
Graphic: one audit broken into sub-cent boxes.
Bullet: Every individual call is too cheap for card / rail / EVM gas models.

## Slide 3 — Product overview
Screenshot: `screenshots/01-hero.png`.
Three bullets: atomic tool calls, per-call settlement, per-call provenance.
Footer: "63 paid tool calls per preset run · all < $0.01."

## Slide 4 — System architecture
Diagram: FastAPI + SSE + orchestrator + provider adapters + Arc/Circle sandbox.
Callouts: repo_scan, site_probes, deep_analysis, aisa_verify, fix_suggestion.

## Slide 5 — Live run breakdown
Screenshot pair: `screenshots/02-execution-progress.png` (left) +
`screenshots/03-billing-waterfall.png` (right).
Numbers: 63 invocations · $0.001–$0.008 each · every row a real settlement.

## Slide 6 — Circle payment proof
Screenshot: `screenshots/06-circle-console.png`.
Callout: "Every row in our billing feed has a matching Circle sandbox entry."

## Slide 7 — Arc Explorer proof
Screenshot: `screenshots/07-arc-explorer.png`.
Callout: "Same hash, same amount, landed in an Arc sandbox block."

## Slide 8 — Business model
Screenshot: `screenshots/05-profitability-matrix.png`.
Three columns: AI service cost ($0.152), Arc/Circle settled cost (0.152 USDC),
traditional EVM gas ($3.15 — ~20×).
Highlight the red conclusion banner from the app.

## Slide 9 — Market and users
Bullet: AppSec teams, security consultancies, AI agent marketplaces.
Quote: "I can't ship an agent that costs more to settle than it charges."

## Slide 10 — Roadmap
Bullet chain: multi-tenant · richer scanner · AIsa deep integration · Arc mainnet launch.
Footer: GitHub URL + public demo URL + team handle.
