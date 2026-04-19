# Deployment Guide — LaunchShield Swarm

Three supported paths, in order of simplicity.

## 1. Local Docker (sanity check)

```powershell
docker build -t launchshield-swarm:local .
docker run --rm -p 8000:8000 -e LAUNCHSHIELD_DEMO_PACE_SECONDS=0.35 launchshield-swarm:local
```

Open http://127.0.0.1:8000. `docker logs` will stream uvicorn output;
`/api/health` must return HTTP 200 within ~15 s.

## 2. Fly.io (recommended for the hackathon demo)

Requires [flyctl](https://fly.io/docs/flyctl/). Run these once from the repo root.

```powershell
# First-time setup
flyctl auth login
flyctl launch --copy-config --no-deploy --name launchshield-swarm --region sin

# Set any real credentials you already have as secrets (skip the lines you don't have)
flyctl secrets set `
  USE_REAL_PAYMENTS=true `
  X402_GATEWAY_BASE_URL=... `
  X402_GATEWAY_API_KEY=... `
  CIRCLE_API_KEY=... `
  ARC_RPC_URL=... `
  ARC_WALLET_ADDRESS=... `
  ARC_PRIVATE_KEY=... `
  OPENAI_API_KEY=... `
  GITHUB_TOKEN=...

# Deploy
flyctl deploy --remote-only
flyctl status
```

The app is then reachable at
`https://<app-name>.fly.dev`. The persistent volume (`launchshield_data` mounted at `/data`) keeps every past run's JSON summary and artefacts so you can cite them from the
submission.

### Automated redeploys

`.github/workflows/deploy-fly.yml` will redeploy on any push to `main` that touches
the app, **provided you add a `FLY_API_TOKEN` repository secret**:

```powershell
flyctl tokens create deploy --name github-actions-ci > fly_token.txt
# Then copy the contents of fly_token.txt into GitHub → Settings → Secrets → Actions
# as FLY_API_TOKEN. Delete the local file afterwards.
```

## 3. Render (one-click alternative)

`render.yaml` defines a Blueprint that Render picks up automatically.

1. Push the repo to GitHub.
2. In the Render dashboard: **New → Blueprint → connect the repo**.
3. Render will provision the web service + 1 GB disk from `render.yaml`.
4. Open the service settings and add these secrets through the UI (none are in YAML):
   - `CIRCLE_API_KEY`, `X402_GATEWAY_BASE_URL`, `X402_GATEWAY_API_KEY`
   - `ARC_RPC_URL`, `ARC_WALLET_ADDRESS`, `ARC_PRIVATE_KEY`
   - `OPENAI_API_KEY`, `AISA_API_KEY`, `AISA_BASE_URL`, `GITHUB_TOKEN`
5. Flip the relevant `USE_REAL_*` env vars to `true`.

The public URL will be
`https://launchshield-swarm.onrender.com` (or whatever slug Render picks).

## Flip to real payments safely

See [`docs/arc-testnet.md`](docs/arc-testnet.md) for the full wallet/faucet walkthrough.

1. Confirm `/api/health` still returns 200 after setting secrets.
2. On production, start with `USE_REAL_LLM=true` and `USE_REAL_GITHUB=true` first
   — they do not move USDC, so you can verify plumbing without risk.
3. Run the pre-flight: `python scripts/check_arc_testnet.py`. It must report
   `[OK] read-only checks passed.`
4. Run `python scripts/check_arc_testnet.py --send` to land **one** real tx.
   Open the printed explorer URL to confirm.
5. Then flip `USE_REAL_PAYMENTS=true`. Run **one** `custom-standard` scan
   (34 invocations) against a cheap target before doing a `preset-stress` (63).
6. Watch the Arc Explorer live at `https://testnet.arcscan.app/address/<wallet>`
   during the first 5 confirmations — hashes should match the Streaming Billing
   panel exactly.

## Rollback

```powershell
# Fly
flyctl releases list
flyctl releases rollback <version>

# Render
# Use the "Rollback" button on the service page.
```

## Teardown

```powershell
# Fly
flyctl apps destroy launchshield-swarm

# Render
# Delete the Blueprint from the dashboard.
```
