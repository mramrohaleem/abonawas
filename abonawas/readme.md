# Discord Music Bot (Railway Deploy)

This is a production-ready Discord music bot written in Python 3.12.

## 🚀 Features
- Play audio from YouTube URLs
- Per-guild music queues
- One persistent control panel per guild with buttons
- Auto-disconnect after 60s idle
- Slash commands for control

## 📦 Deploy to Railway

1. Create a new Railway project.
2. Add the following environment variable:
   - `DISCORD_TOKEN` = your bot token
3. Deploy the project.
   - Railway auto-installs from `requirements.txt` and runs `Procfile`.

You're done! Invite your bot and use `/play` in any server with voice channels.
