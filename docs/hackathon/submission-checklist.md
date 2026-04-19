# Submission Checklist — LaunchShield Swarm

- [ ] GitHub repository public and clean (`launchshield/`, `templates/`, `static/`, `docs/`, `tests/`, `README.md`, `PLAN.md`).
- [ ] Public demo URL reachable (record the URL here).
- [ ] Demo video uploaded and accessible (link recorded here).
- [ ] PPT uploaded and accessible (link recorded here).
- [ ] `python scripts/check_arc_testnet.py` reports `[OK] read-only checks passed.`
- [ ] `python scripts/check_arc_testnet.py --send` lands one real tx on Arc testnet (hash recorded).
- [ ] Arc Explorer screenshot captured (`docs/hackathon/screenshots/07-arc-explorer.png`) for at least one landed transaction.
- [ ] Circle Console / Circle sandbox screenshot captured (`docs/hackathon/screenshots/06-circle-console.png`) if operating through the Circle product surface.
- [ ] 50+ real sandbox settlements visible in the billing feed screenshot set (`03-billing-waterfall.png`).
- [ ] Every tool price verified `< $0.01` (run `pytest -k pricing`).
- [ ] `preset-stress` total verified as `63` invocations (run `pytest -k preset`).
- [ ] Profitability matrix in the app matches the numbers stated in the PPT and video.
- [ ] `.env.example` committed; `.env` never committed.
- [ ] `requirements.txt` installs cleanly in a fresh venv.
- [ ] Health endpoint `/api/health` returns `200` in the deployed environment.
