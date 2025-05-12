# Discord Quran Bot

## Setup

1. Clone repo
2. Create env file with `DISCORD_TOKEN`

## Local Run

```bash
pip install -r requirements.txt
python bot.py
```

## CI/CD

Workflow in `.github/workflows/deploy.yml` installs deps, lints, tests, then deploys via Railway CLI.

## Deployment

- Connect GitHub to Railway
- Set `DISCORD_TOKEN` in Railway env
- Railway auto-builds on push
- Health check: GET `/healthz` returns 200
