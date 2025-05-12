# Discord Quran Bot

## Setup

```bash
git clone <repo_url>
cd discord-quran-bot
npm install
cp .env.example .env
# fill in DISCORD_TOKEN & CLIENT_ID
npm run deploy
npm start
```

## Slash Commands

- `/play input` (URL or `surah:ayah`)
- `/queue`
- `/skip`
- `/pause`
- `/resume`
- `/stop`

## Railway

- Connect GitHub repo in Railway dashboard.
- Set env vars: `DISCORD_TOKEN`, `CLIENT_ID`, `CACHE_DIR`, `LOG_LEVEL`.
- Build command: `npm install && npm run build`
- Start command: `npm start`
- Procfile: `worker: npm start`
