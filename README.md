# Telegram PDF Converter Bot

A Telegram bot that converts supported files to PDF using iLovePDF, designed for webhook/serverless deployment.

## Features

- Commands: `/start`, `/help`, `/formats`
- Supports common formats: `doc, docx, xls, xlsx, ppt, pptx, jpg, jpeg, png, tiff, odt, rtf, txt`
- Max upload size configurable (default 20 MB)
- Daily per-user conversion cap (default 20/day)
- Webhook mode for platforms like Vercel
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

## Environment Variables

- `TELEGRAM_BOT_TOKEN` (required)
- `ILOVEPDF_PUBLIC_KEY` (required)
- `ILOVEPDF_SECRET_KEY` (required)
- `TELEGRAM_WEBHOOK_URL` (required for `set-webhook` command)
- `TELEGRAM_WEBHOOK_SECRET` (optional, recommended)
- `MAX_FILE_MB` (default: `20`)
- `MAX_CONCURRENT_JOBS` (default: `2`)
- `CONVERSION_TIMEOUT_SECONDS` (default: `120`)
- `DAILY_CONVERSIONS_PER_USER` (default: `20`)

## Vercel Deploy (Webhook)

1. Push this repo to GitHub.
2. In Vercel, import this repository.
3. Ensure root directory is repo root.
4. Set environment variables in Vercel project settings.
5. Deploy.

Webhook endpoint in this repo:

- `POST /api/main`
- Health check: `GET /api/main`

After deployment, set Telegram webhook:

```bash
python main.py set-webhook
```

Check webhook status:

```bash
python main.py webhook-info
```

If you need to clear webhook:

```bash
python main.py delete-webhook
```

## Privacy

Uploaded and generated files are kept only in a per-request temporary directory and deleted immediately in `finally`, regardless of success or failure.

## Other Deploy Options

- Dockerfile included for container platforms.
- Linux service template: `deploy/systemd/pdf-converter-bot.service`
