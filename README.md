# Greek Fuel Prices

A system that collects daily fuel price data from Greek government PDF bulletins, stores it in a relational database, exposes it through a public REST API, and visualises it in an interactive web app.

The Greek Ministry of Development publishes a PDF every day with fuel prices for the 51 Greek prefectures. This project captures that data going back to 2017 and keeps it up to date automatically.

**Live application:** https://nireas.iee.ihu.gr/fuel/

## How It Works

### Parsing pipeline

Older PDFs (pre-2023) have inconsistent formatting, so they are parsed by **Gemini 2.5 Flash** which reads the PDF and returns structured JSON. Newer PDFs follow a standardised table layout and are parsed locally with **pdfplumber** — faster and free. The daily pipeline tries pdfplumber first and falls back to Gemini automatically if validation fails.

### Daily automation

`daily_pipeline.py` is designed to run as a cron job. Each run it:
1. Fetches the government page and finds up to 30 recent bulletins
2. Downloads any PDFs not yet on disk
3. Parses each unprocessed one (pdfplumber → Gemini fallback)
4. Saves the result to `json_output/` and inserts into MySQL
5. Logs the outcome to `logs/daily_pipeline.json`
6. Sends a weekly summary email on Sunday (and an immediate alert on failure)

## Project Structure

```
├── scripts/
│   ├── daily_pipeline.py   # Daily cron job: download → parse → DB → log → alert
│   ├── daily_parser.py     # pdfplumber parser for standardised (2023+) PDFs
│   ├── parceALLpdfs.py     # Bulk parser using Gemini (historical PDFs)
│   ├── downloadALL.py      # One-off: download all historical PDFs
│   ├── import_to_db.py     # One-off: bulk-import all JSONs into MySQL
│   └── db.py               # Shared MySQL connection + insert helpers
├── pdfs/                   # Downloaded PDFs (git-ignored, deleted after parsing)
├── json_output/            # Parsed output, one JSON per day (git-ignored)
├── logs/                   # Pipeline run logs (git-ignored)
├── database/
│   └── schema.sql          # MySQL schema
├── api/                    # PHP REST API (see below)
│   ├── index.php           # Front controller: routing + CORS
│   ├── config.php          # DB connection + .env loader
│   ├── helpers.php         # Response + input-validation helpers
│   └── endpoints/          # One file per endpoint
├── frontend/               # Web app assets
│   ├── app.js              # Chart.js logic + multi-select dropdowns
│   └── style.css           # Responsive styling
├── index.html              # Home page (charts + latest prices)
├── docs.html               # API documentation page
└── about.html              # Project info page
```

## Setup

1. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
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
python scripts/parceALLpdfs.py ./pdfs  # parse them with Gemini
```

### Test email configuration
```bash
python scripts/daily_pipeline.py --test-email
```

## Environment Variables

See `.env.example` for all required variables (Gemini API key, DB credentials, SMTP settings).

## Public API

Read-only JSON API, versioned at `/api/v1/`. **Public — no authentication required.** All responses share the envelope `{ "data": ..., "meta": ... }` on success or `{ "error": {...}, "meta": ... }` on failure.

### Endpoints

| Method | Path                     | Description                                           |
|--------|--------------------------|-------------------------------------------------------|
| GET    | `/api/v1/`               | API metadata + dataset coverage + endpoint list       |
| GET    | `/api/v1/prefectures`    | All prefectures (51 + national weighted average)      |
| GET    | `/api/v1/fuel-types`     | All tracked fuel types                                |
| GET    | `/api/v1/prices`         | Time series for one prefecture + fuel + date range    |
| GET    | `/api/v1/prices/latest`  | Latest bulletin snapshot, every prefecture            |

### `/prices` query parameters (all required)

- `prefecture_id` — integer, from `/prefectures`
- `fuel_type_id` — integer, from `/fuel-types`
- `from` — `YYYY-MM-DD`
- `to` — `YYYY-MM-DD`

### Example

```
curl 'https://nireas.iee.ihu.gr/fuel/api/v1/prices?prefecture_id=1&fuel_type_id=1&from=2026-01-01&to=2026-05-01'
```
