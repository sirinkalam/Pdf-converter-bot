# Telegram PDF Converter Bot

A public Telegram bot that converts supported files to PDF using iLovePDF.

## Features

- Commands: `/start`, `/help`, `/formats`
- Supports common formats: `doc, docx, xls, xlsx, ppt, pptx, jpg, jpeg, png, tiff, odt, rtf, txt`
- Max upload size configurable (default 20 MB)
- Daily per-user conversion cap (default 20/day)
- Long polling runtime
- Immediate file deletion after each request (success or failure)

## Local Setup

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
```

2. Copy environment template and set values:

```bash
copy .env.example .env
```

3. Run the bot:

```bash
python main.py
```

## Environment Variables

- `TELEGRAM_BOT_TOKEN` (required)
- `ILOVEPDF_PUBLIC_KEY` (required)
- `ILOVEPDF_SECRET_KEY` (required)
- `MAX_FILE_MB` (default: `20`)
- `MAX_CONCURRENT_JOBS` (default: `2`)
- `CONVERSION_TIMEOUT_SECONDS` (default: `120`)
- `DAILY_CONVERSIONS_PER_USER` (default: `20`)

## Deploy on Render (24/7)

This repo includes `render.yaml` for a Render Background Worker.

1. Push this project to GitHub.
2. In Render, choose **New +** -> **Blueprint**.
3. Select your repo; Render detects `render.yaml`.
4. Set secret env vars in Render:
   - `TELEGRAM_BOT_TOKEN`
   - `ILOVEPDF_PUBLIC_KEY`
   - `ILOVEPDF_SECRET_KEY`
5. Deploy.

Notes:
- Use a paid worker plan for always-on behavior.
- Keep only one active bot instance (stop local bot after cloud deploy) to avoid duplicate replies.

## Privacy

Uploaded and generated files are kept only in a per-request temporary directory and deleted immediately in `finally`, regardless of success or failure.

## Other Deploy Options

- Dockerfile included for container platforms.
- Linux service template: `deploy/systemd/pdf-converter-bot.service`
