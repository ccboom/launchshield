# Screenshot Capture Guide

All screenshots in this folder back the PPT and the video script. Capture them
from a fresh `preset-stress` run on a 1920×1200 viewport so the text stays
legible at 1080p playback. File names here are the ones referenced by
`../ppt-outline.md` and `../video-script.md`.

> Recommended tooling: Windows **Snipping Tool** (`Win+Shift+S`) for still
> crops, **OBS Studio** for video. Zoom the browser to 100% and hide
> bookmarks so the hero shot is clean.

## Shot list

| File name                        | When to capture                                                                | Must contain                                                                                     |
|----------------------------------|---------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| `01-hero.png`                    | Before clicking the CTA.                                                        | Hero headline, both CTAs, the preset-target footer, no panels revealed yet.                      |
| `02-execution-progress.png`      | ~5 seconds into the run (stage `repo.file_scan`).                               | Progress bar at ~20%, stage pill saying `repo.file_scan`, metric grid showing a few findings.    |
| `03-billing-waterfall.png`       | During `analysis.deep_review` with at least 40 confirmed rows.                  | Streaming Billing panel with mixed severities, at least one row highlighted on hover (tx link).  |
| `04-findings-top.png`            | Right after a critical finding appears.                                         | Findings panel showing at least 1 `critical` + 2 `high` cards.                                   |
| `05-profitability-matrix.png`    | After the run completes.                                                        | Three profit cards + red conclusion banner; `Traditional EVM Gas` card must be red.              |
| `06-circle-console.png`          | From the Circle sandbox console, *after* wiring real payments (Step 2).         | A list of Circle payment rows whose tx hashes match at least one billing row in `03-...png`.     |
| `07-arc-explorer.png`            | From the Arc sandbox explorer, *after* wiring real payments (Step 2).           | Block / tx view of the same hash highlighted in `06-circle-console.png`.                         |
| `08-pricing-matrix.png`          | Any time.                                                                        | Pricing matrix panel showing all six tool prices.                                                |
| `09-health-endpoint.png`         | Any time.                                                                        | `/api/health` JSON with all `use_real_*` flags visible.                                          |

## Replay instructions

```powershell
# 1) start the server
.\.venv\Scripts\Activate.ps1
uvicorn launchshield.app:app

# 2) slow the pace a bit so the waterfall reads on camera
$env:LAUNCHSHIELD_DEMO_PACE_SECONDS = "0.55"
uvicorn launchshield.app:app
```

For screenshots `06-` and `07-`, first finish Step 2 (real sandbox wiring) and
run `preset-stress` one more time so you have matching hashes on the chain.
