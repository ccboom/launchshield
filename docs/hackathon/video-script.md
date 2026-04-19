# Video Script — LaunchShield Swarm (target 90 seconds)

> **Recording setup:** 1920×1200 window at 100% zoom, browser bookmarks hidden,
> dark desktop wallpaper. Before recording start uvicorn with
> `LAUNCHSHIELD_DEMO_PACE_SECONDS=0.55` so the billing waterfall is readable at 1×.
> All screenshot references point at `docs/hackathon/screenshots/` (see that
> folder's README for capture instructions).

## 1. Problem (0:00 – 0:12)
On-camera: Title card "Every AI security agent call should be billed."
B-roll underlay: `screenshots/01-hero.png` fading in at 0:06.
VO: "AI security audits are already a dozen tools wide. The hard part isn't the
scan — it's settling every tool call without eating the margin."

## 2. Product one-liner (0:12 – 0:22)
On-camera: `screenshots/01-hero.png` — full home page, focus on the headline and
the two CTAs.
VO: "LaunchShield Swarm breaks every audit into sub-cent tool calls and settles
them on Arc in real time."
On-screen lower-third: `preset-stress = 63 paid tool calls · < $0.01 each`.

## 3. Click `Execute & Stress Test` (0:22 – 0:30)
Live-capture the click on the green CTA. Cursor should linger on the sub-label
`63 paid tool calls · preset target` for ~1 second before clicking.
Immediately after the click, cross-fade to `screenshots/02-execution-progress.png`
showing the progress bar at ~20% and the `repo.file_scan` stage pill.
VO: "One click — 63 paid tool invocations, back to back, on a preset target."

## 4. Transaction waterfall (0:30 – 0:55)
Live capture: the `Streaming Billing` panel. Let it run for ~20 seconds so the
viewer sees the feed climb from 5 rows to 40+.
Zoom-in at 0:42 on a single confirmed row so the viewer can read the
`tool · target · 0.00x USDC · 0x…` columns. Hover the short hash so the
Explorer link tooltip appears.
Cutaway at 0:50 to `screenshots/03-billing-waterfall.png` for the tight crop.
VO: "Every row is a real settlement. The feed IS the audit — stage, tool,
target, price, on-chain hash."

## 5. Risk results (0:55 – 1:05)
Pan down to the `Top Findings` panel. Use `screenshots/04-findings-top.png` as
b-roll. Highlight exactly one `critical` card (hardcoded secret) and one `high`
card (dangerous eval).
VO: "As the swarm runs, the scanner produces findings with evidence and
remediation, attached to the exact paid tool calls that discovered them."

## 6. Circle Console proof (1:05 – 1:15)
Cut to `screenshots/06-circle-console.png`. On-screen annotation: a thin yellow
box around one Circle row plus a matching box around the same `0x…` hash in the
`03-billing-waterfall.png` frame (picture-in-picture).
VO: "Each receipt is backed by a real Circle sandbox console entry — same hash,
same amount, same memo."

## 7. Arc Explorer proof (1:15 – 1:22)
Cut to `screenshots/07-arc-explorer.png`. Optional: browser tab lift where the
viewer sees the URL bar reading `sandbox.explorer.arc.network/tx/…`.
VO: "Arc Explorer confirms the transaction landed on the testnet."

## 8. Profitability matrix (1:22 – 1:32)
Cut to `screenshots/05-profitability-matrix.png`. Animate a highlight across the
three cards in order: AI service cost → Arc/Circle settled cost → Traditional EVM
gas. End with a red flash on the conclusion banner.
On-screen callout: “$0.15 settled vs $3.15 on EVM — ~20×.”
VO: "Traditional gas destroys this business model. Only Arc and Circle
micropayments make high-frequency AI security profitable."

## 9. Outro (1:32 – 1:35)
On-camera: LaunchShield Swarm wordmark + GitHub URL + public demo URL.
VO: "LaunchShield Swarm. AI security, priced by the call."
