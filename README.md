# Greek Fuel Prices

A system for collecting, storing, and serving daily fuel price data from Greek government PDF bulletins.

## Project Structure

```
├── scripts/
│   ├── parceALLpdfs.py     # One-time bulk import of 3000+ historical PDFs using Gemini AI
│   ├── daily_parser.py     # Daily cron job: parses the latest PDF and inserts into DB
│   └── downloadALL.py      # Downloads all historical PDFs from the government website
├── database/
│   └── schema.sql          # PostgreSQL schema (prefectures, fuel_types, daily_fuel_prices)
├── api/                    # PHP REST API with token-based auth (coming soon)
├── frontend/               # HTML/CSS/JS chart UI (coming soon)
└── .env.example            # Environment variable template
```

## Setup

1. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

2. Install Python dependencies:
   ```bash
   pip install google-genai psycopg2-binary python-dotenv tqdm pdfplumber
   ```

3. Set up the database using `database/schema.sql`.

## Usage

### Bulk historical import
```bash
python scripts/parceALLpdfs.py ./allPDFS
```
Processes all PDFs in the given directory, saves results to `json_output/`, and writes `flagged.json` for entries needing manual review.

### Daily cron job
```bash
python scripts/daily_parser.py
```

## Environment Variables

See `.env.example` for all required variables.
