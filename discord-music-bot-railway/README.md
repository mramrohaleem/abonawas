# Discord Music Bot

A production-ready Discord music bot built with Discord.js v14 and @discord-player v6.

## Features

- `/play <query|URL>` — Play tracks from YouTube
- `/queue` — Display the current queue
- `/skip`, `/previous`, `/stop`, `/loop` — Playback controls
- Embedded now-playing message with interactive buttons
- In-memory per-guild queue, no database needed
- Graceful error handling

---

## 📦 Local Setup

1. Clone & install  
   ```bash
   git clone <your-repo-url>
   cd discord-music-bot
   npm install
   ```

2. Environment  
   ```bash
   cp .env.example .env
   ```  
   Edit `.env`:
   ```
   DISCORD_TOKEN=your-bot-token
   CLIENT_ID=your-client-id
   GUILD_ID=your-test-guild-id   # only for local/dev
   ```

3. Run locally  
   ```bash
   npm start
   ```

   - `NODE_ENV` defaults to `"development"`, so slash commands register to `GUILD_ID` instantly.

4. Production (Railway)  
   - In Railway **Variables**, set:
     ```
     DISCORD_TOKEN
     CLIENT_ID
     NODE_ENV=production
     ```
   - Deploy — Railway will build the Docker image and start your bot.

---

## 🚀 Slash Command Registration

- **Development**  
  Registers to your test guild (`GUILD_ID`) on each start — commands appear within seconds.
- **Production**  
  Registers globally when `NODE_ENV=production`. Changes can take up to an hour to propagate.

---

## 🛠️ Troubleshooting

- **Missing Permissions**  
  Ensure the bot’s role has: `CONNECT`, `SPEAK`, `SEND_MESSAGES`, `EMBED_LINKS`, `MANAGE_MESSAGES`.
- **Slash commands not appearing**  
  - Check `GUILD_ID` in `.env` for dev  
  - Ensure `NODE_ENV=production` for global
- **Audio errors**  
  Make sure voice channel permissions are correct, and YouTube links/queries are valid.

---

Enjoy your new music bot!