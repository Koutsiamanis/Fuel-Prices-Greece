# Greek Fuel Prices

A system that collects daily fuel price data from Greek government PDF bulletins, parses it, and will serve it through a public API with a chart-based frontend.

The Greek Ministry of Energy publishes a PDF every day with fuel prices per prefecture (51 regions). This project captures that data going back to 2017 and keeps it up to date automatically.

## Current Status

- **3,213 PDFs** collected and parsed (2017 – present)
- **3,213 JSON files** produced, one per day
- Daily pipeline running via cron — downloads, parses, inserts into MySQL, and logs each new bulletin
- MySQL schema applied; bulk-import script backfills all historical JSONs
- API and frontend are next

## How It Works

### Parsing pipeline

Older PDFs (pre-2023) have inconsistent formatting, so they are parsed by **Gemini 2.5 Flash** which reads the PDF and returns structured JSON. Newer PDFs follow a standardised table layout and are parsed locally with **pdfplumber** — faster and free. The daily pipeline tries pdfplumber first and falls back to Gemini automatically if validation fails.

### Daily automation

`daily_pipeline.py` is designed to run as a cron job. Each run it:
1. Fetches the government page and finds up to 30 recent bulletins
2. Downloads any PDFs not yet on disk
3. Parses each unprocessed one (pdfplumber → Gemini fallback)
4. Saves the result to `json_output/`
5. Logs the outcome to `logs/daily_pipeline.json`
6. Sends a weekly summary email on Sunday (and an immediate alert on failure)

## Project Structure

```
├── scripts/
│   ├── daily_pipeline.py   # Daily cron job: download → parse → DB → log → alert
│   ├── daily_parser.py     # pdfplumber parser for standardised (2023+) PDFs
│   ├── parceALLpdfs.py     # Bulk parser using Gemini AI (historical PDFs)
│   ├── downloadALL.py      # One-off: download all historical PDFs
│   ├── import_to_db.py     # One-off: bulk-import all JSONs into MySQL
│   └── db.py               # Shared MySQL connection + insert helpers
├── pdfs/                   # All downloaded PDFs (git-ignored)
├── json_output/            # Parsed output, one JSON per day (git-ignored)
├── logs/                   # Pipeline run logs (git-ignored)
├── database/
│   └── schema.sql          # MySQL schema
├── api/                    # PHP REST API — coming soon
└── frontend/               # Chart UI — coming soon
```

## Setup

1. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

2. Install Python dependencies:
   ```bash
   pip install google-genai pymysql python-dotenv tqdm pdfplumber requests beautifulsoup4
   ```

3. Apply the schema to your MySQL server:
   ```bash
   mysql -h <host> -u <user> -p <db_name> < database/schema.sql
   ```

4. Backfill all historical JSONs into the DB (idempotent — safe to re-run):
   ```bash
   python scripts/import_to_db.py
   ```

## Usage

### Daily cron job
```bash
python scripts/daily_pipeline.py
```
Add to crontab to run once a day (e.g. noon):
```
0 12 * * * /path/to/venv/bin/python /path/to/scripts/daily_pipeline.py
```

### Bulk historical import
```bash
python scripts/downloadALL.py          # download all PDFs
python scripts/parceALLpdfs.py ./pdfs  # parse them
```

### Test email configuration
```bash
python scripts/daily_pipeline.py --test-email
```

## Environment Variables

See `.env.example` for all required variables (Gemini API key, DB credentials, SMTP settings).
