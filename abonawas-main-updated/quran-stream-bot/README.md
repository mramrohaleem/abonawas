# Quran Stream Bot

A production-ready Discord bot (Python) for streaming Quran recitations or any MP3 URL with a download-then-play queue, interactive button controls, detailed embeds, and robust logging.

## Features

- **Queue management**: Add multiple MP3 URLs; auto-download next track while playing.
- **Interactive controls**: ▶️ Play/Resume, ⏸️ Pause, ⏭️ Next, ⏹️ Stop via Discord buttons.
- **Dynamic embeds**: Shows title, duration, elapsed time (refreshes every 10s), and queue length.
- **Logging**: INFO for commands, DEBUG for downloads & tasks, ERROR for exceptions; logs to console + rotating file.
- **Modular**: Separated into Downloader, Player Cog, UI View, Logger setup, and main bot runner.
- **Deployment**: Connected to Railway via GitHub; auto-deploy on push to `main`.

## Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) installed & in PATH
- A Discord bot token

## Installation

```bash
git clone https://github.com/yourusername/quran-stream-bot.git
cd quran-stream-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running Locally

```bash
python bot.py
```

Use command:

```
!stream https://example.com/some-recitation.mp3
```

That's it! 🎧
