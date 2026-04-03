# Telegram PDF Converter Bot

A Telegram bot that processes files with iLovePDF in webhook mode (Vercel/serverless friendly).

## Features

- Commands: `/start`, `/help`, `/formats`
- Interactive actions after upload (button-based)
- For non-PDF files: convert to PDF
- For PDF files: merge, split, compress
- Max upload size configurable (default 20 MB)
- Daily per-user operation cap (default 20/day)
- Immediate temporary-file cleanup after each job

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
2. Import repo in Vercel.
3. Root directory must be repo root.
4. Add environment variables in Vercel.
5. Deploy.

Webhook endpoint in this repo:

- `POST /`
- Health check: `GET /`

After deployment, set Telegram webhook:

```bash
python main.py set-webhook
```

Check webhook status:

```bash
python main.py webhook-info
```

If needed, clear webhook:

```bash
python main.py delete-webhook
```

## Privacy

Uploaded and generated files are stored only in per-job temporary directories and deleted after processing.

## Other Deploy Options

- Dockerfile included for container platforms.
- Linux service template: `deploy/systemd/pdf-converter-bot.service`
