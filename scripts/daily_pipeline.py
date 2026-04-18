#!/usr/bin/env python3
"""
Daily fuel price pipeline.

Downloads the latest PDF bulletin from fuelprices.gr, parses it with pdfplumber,
validates results, falls back to Gemini LLM if needed, saves JSON output,
logs results, and sends a weekly email summary on Sunday.

Usage:
    python daily_pipeline.py              # normal daily run
    python daily_pipeline.py --test-email # test email configuration
"""

import json
import os
import re
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Ensure sibling imports work regardless of cwd
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from daily_parser import parse_pdf, parse_greek_date, CANONICAL_PREFECTURES

load_dotenv(_PROJECT_DIR / '.env')

# --- Configuration ---
BASE_URL = "https://www.fuelprices.gr/"
TARGET_PAGE = "https://www.fuelprices.gr/deltia_dn.view"
PDF_DIR = _PROJECT_DIR / "pdfs"
JSON_DIR = _PROJECT_DIR / "json_output"
LOG_DIR = _PROJECT_DIR / "logs"
LOG_FILE = LOG_DIR / "daily_pipeline.json"
DEBUG_DIR = LOG_DIR / "debug"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}

PRICE_MIN, PRICE_MAX = 0.3, 4.0
MIN_ENTRIES = 50  # expect 51-52 (50 prefectures + national average)
NATIONAL_AVG = "ΠΑΝΕΛΛΗΝΙΟΣ ΣΤΑΘΜΙΣΜΕΝΟΣ Μ.Ο."
AVG_DEVIATION_PCT = 10  # max allowed % deviation between simple avg and national avg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg):
    """Print with timestamp."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ---------------------------------------------------------------------------
# 1. Download
# ---------------------------------------------------------------------------

def get_pending_pdfs(limit=30):
    """Fetch the page, find the most recent `limit` PDFs, download any missing,
    and return those that haven't been processed yet (no JSON in json_output/).

    Returns (pending: list[(pdf_path, date_str)], error_msg).
    List is sorted oldest-first so we process in chronological order.
    On failure returns (None, error_msg).
    """
    resp = requests.get(TARGET_PAGE, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, 'html.parser')
    date_re = re.compile(r'\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}')
    links = soup.find_all('a', string=date_re)

    if not links:
        return None, "No date links found on page"

    # Parse all date links
    dated_links = []
    for link in links:
        text = link.get_text(strip=True)
        parts = re.split(r'[/.\-]', text)
        if len(parts) != 3:
            continue
        try:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            dt = datetime(y, m, d)
            date_str = f"{y}-{m:02d}-{d:02d}"
            dated_links.append((dt, date_str, link))
        except (ValueError, IndexError):
            continue

    if not dated_links:
        return None, "Could not parse any dates from links"

    # Keep only the most recent `limit` dates
    dated_links.sort(key=lambda x: x[0], reverse=True)
    dated_links = dated_links[:limit]

    # Download missing PDFs, collect those without a JSON yet
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pending = []

    for dt, date_str, link in dated_links:
        if (JSON_DIR / f"{date_str}.json").exists():
            continue  # already processed

        pdf_path = PDF_DIR / f"{date_str}.pdf"
        if not pdf_path.exists():
            href = link.get('href')
            if not href:
                log(f"No href for {date_str} — skipping")
                continue
            try:
                file_resp = requests.get(urljoin(BASE_URL, href), headers=HEADERS, timeout=60)
                file_resp.raise_for_status()
                with open(pdf_path, 'wb') as f:
                    f.write(file_resp.content)
                log(f"Downloaded: {pdf_path.name}")
            except Exception as e:
                log(f"Failed to download {date_str}: {e}")
                continue

        pending.append((pdf_path, date_str))

    # Process oldest first (chronological order)
    pending.sort(key=lambda x: x[1])
    return pending, None


# ---------------------------------------------------------------------------
# 2. Date fallback (LLM)
# ---------------------------------------------------------------------------

def extract_date_with_llm(pdf_path, link_text=None):
    """LLM fallback to extract the bulletin date from the PDF header.

    Returns YYYY-MM-DD string or None.
    """
    from google import genai
    from google.genai import types

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None

    client = genai.Client(api_key=api_key)
    pdf_bytes = pdf_path.read_bytes()

    prompt = "Extract the date from this Greek fuel price bulletin PDF header. "
    if link_text:
        prompt += f'The website listed this date as "{link_text}". Cross-reference with the date in the PDF. '
    prompt += "Return ONLY the date in YYYY-MM-DD format, nothing else."

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf'),
                prompt,
            ],
            config=types.GenerateContentConfig(temperature=0, max_output_tokens=20),
        )
        text = response.text.strip()
        if re.match(r'\d{4}-\d{2}-\d{2}$', text):
            return text
    except Exception as e:
        log(f"LLM date extraction failed: {e}")

    return None


# ---------------------------------------------------------------------------
# 3. Validation
# ---------------------------------------------------------------------------

def validate_parse(data):
    """Check if pdfplumber output is good enough or needs LLM fallback.

    Returns (acceptable: bool, warnings: list[str]).
    """
    warnings = []
    entries = data.get('entries', [])

    if not data.get('date'):
        warnings.append("no date extracted")

    if len(entries) < MIN_ENTRIES:
        warnings.append(f"only {len(entries)} entries (expected 51-52)")

    unmatched = []
    out_of_range = 0
    low_price_entries = 0

    for entry in entries:
        pref = entry.get('prefecture', '')
        if pref not in CANONICAL_PREFECTURES:
            unmatched.append(pref)

        prices = entry.get('prices', {})
        non_null = [v for v in prices.values() if isinstance(v, (int, float))]
        if len(non_null) < 3:
            low_price_entries += 1

        for fuel, val in prices.items():
            if isinstance(val, (int, float)) and not (PRICE_MIN <= val <= PRICE_MAX):
                out_of_range += 1

    if unmatched:
        warnings.append(f"{len(unmatched)} unmatched prefectures: {unmatched}")
    if out_of_range:
        warnings.append(f"{out_of_range} prices out of range")
    if low_price_entries:
        warnings.append(f"{low_price_entries} entries with <3 prices")

    # Compare simple average vs national weighted average
    national = None
    prefectures_only = []
    for entry in entries:
        if entry.get('prefecture') == NATIONAL_AVG:
            national = entry.get('prices', {})
        else:
            prefectures_only.append(entry)

    avg_deviation_fail = False
    if national:
        for fuel, national_val in national.items():
            if not isinstance(national_val, (int, float)) or national_val == 0:
                continue
            values = [
                e['prices'][fuel] for e in prefectures_only
                if isinstance(e.get('prices', {}).get(fuel), (int, float))
            ]
            if not values:
                continue
            simple_avg = sum(values) / len(values)
            deviation = abs(simple_avg - national_val) / national_val * 100
            if deviation > AVG_DEVIATION_PCT:
                warnings.append(
                    f"avg deviation {fuel}: avg={simple_avg:.3f} vs national={national_val:.3f} ({deviation:.1f}%)"
                )
                avg_deviation_fail = True
    else:
        warnings.append("missing ΠΑΝΕΛΛΗΝΙΟΣ Μ.Ο.")

    acceptable = (
        len(entries) >= MIN_ENTRIES
        and len(unmatched) == 0
        and out_of_range <= 5
        and low_price_entries <= 3
        and not avg_deviation_fail
    )

    return acceptable, warnings


# ---------------------------------------------------------------------------
# 4. LLM parse fallback
# ---------------------------------------------------------------------------

def llm_parse(pdf_path):
    """Parse PDF with Gemini LLM as fallback.  Returns (data, error_msg)."""
    from parceALLpdfs import extract_data_from_pdf
    from google import genai

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None, "GEMINI_API_KEY not set"

    client = genai.Client(api_key=api_key)
    data = extract_data_from_pdf(client, pdf_path)

    if data is None:
        return None, "LLM extraction returned None after retries"

    # Date from filename (authoritative)
    data['date'] = pdf_path.stem
    return data, None


# ---------------------------------------------------------------------------
# 5. Logging
# ---------------------------------------------------------------------------

def load_log():
    if LOG_FILE.exists():
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_log(entries):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def append_log(date_str, status, method, entries_count, warnings=None, error=None):
    """Append a run record to the daily log.

    status: 'success' | 'fallback_llm' | 'failed'
    method: 'pdfplumber' | 'llm' | 'none'
    """
    entries = load_log()
    entries.append({
        'date': date_str,
        'run_at': datetime.now().isoformat(timespec='seconds'),
        'status': status,
        'method': method,
        'entries_count': entries_count,
        'warnings': warnings or [],
        'error': error,
    })
    save_log(entries)


def save_debug(date_str, data, suffix='pdfplumber'):
    """Save partial/failed parse output for manual inspection."""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DIR / f"{date_str}_{suffix}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"Debug output saved: {path}")


# ---------------------------------------------------------------------------
# 6. Email
# ---------------------------------------------------------------------------

def send_email(subject, body):
    """Send an email via SMTP.  Returns True on success."""
    host = os.getenv('SMTP_HOST')
    port = int(os.getenv('SMTP_PORT', '587'))
    user = os.getenv('SMTP_USER')
    password = os.getenv('SMTP_PASSWORD')
    to_addr = os.getenv('ALERT_EMAIL')

    if not all([host, user, password, to_addr]):
        log("Email not configured (set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL)")
        return False

    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = user
    msg['To'] = to_addr

    try:
        with smtplib.SMTP(host, port) as srv:
            srv.starttls()
            srv.login(user, password)
            srv.send_message(msg)
        log("Email sent successfully")
        return True
    except Exception as e:
        log(f"Email failed: {e}")
        return False


def send_critical_alert(date_str, error):
    """Immediate alert for critical failures (don't wait until Sunday)."""
    send_email(
        f"ALERT: Fuel price pipeline FAILED - {date_str}",
        f"The daily fuel price pipeline failed.\n\n"
        f"Date: {date_str}\n"
        f"Error: {error}\n\n"
        f"Check manually: {TARGET_PAGE}\n"
        f"Log: {LOG_FILE.resolve()}"
    )


def send_weekly_summary():
    """Compile and send a summary of the past 7 days."""
    entries = load_log()
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    week = [e for e in entries if e.get('run_at', '') >= cutoff]

    if not week:
        send_email(
            "ALERT: Weekly Fuel Prices - No runs this week",
            "No pipeline runs recorded in the past 7 days.\n"
            "This likely means the cron job is not running."
        )
        return

    ok = [e for e in week if e['status'] == 'success']
    fb = [e for e in week if e['status'] == 'fallback_llm']
    fail = [e for e in week if e['status'] == 'failed']

    lines = [
        "Weekly Fuel Price Pipeline Summary",
        f"Period: {week[0]['date']} to {week[-1]['date']}",
        "",
        f"Total runs: {len(week)}",
        f"  Successful (pdfplumber): {len(ok)}",
        f"  Fallback (LLM):         {len(fb)}",
        f"  Failed:                  {len(fail)}",
    ]

    if fb:
        lines += ["", "LLM Fallbacks:"]
        for e in fb:
            lines.append(f"  {e['date']}: {'; '.join(e.get('warnings', []))}")

    if fail:
        lines += ["", "Failures:"]
        for e in fail:
            lines.append(f"  {e['date']}: {e.get('error', 'unknown')}")

    all_warnings = []
    for e in week:
        for w in e.get('warnings', []):
            all_warnings.append(f"  {e['date']}: {w}")
    if all_warnings:
        lines += ["", "All warnings:"]
        lines.extend(all_warnings)

    if not fail and not fb:
        lines += ["", "Everything ran smoothly this week."]

    prefix = "OK" if not fail else "ALERT"
    subject = f"[{prefix}] Weekly Fuel Prices - {len(ok) + len(fb)}/{len(week)} processed"
    send_email(subject, "\n".join(lines))


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_pdf(pdf_path, date_str):
    """Parse, validate, and save one PDF.  Returns True on success, False on failure."""
    log(f"Processing: {pdf_path.name}")
    json_path = JSON_DIR / f"{date_str}.json"
    data = None
    method = None
    status = None
    all_warnings = []

    # ---- Try pdfplumber (fast, free) ----
    try:
        log("  Parsing with pdfplumber...")
        pdfplumber_data = parse_pdf(pdf_path)

        if not pdfplumber_data.get('date'):
            pdfplumber_data['date'] = date_str

        acceptable, warnings = validate_parse(pdfplumber_data)
        all_warnings.extend(warnings)

        if acceptable:
            data = pdfplumber_data
            method = 'pdfplumber'
            status = 'success'
            log(f"  pdfplumber OK - {len(data['entries'])} entries")
            if warnings:
                log(f"  Warnings: {'; '.join(warnings)}")
        else:
            log(f"  pdfplumber insufficient: {'; '.join(warnings)}")
            save_debug(date_str, pdfplumber_data)

    except Exception as e:
        log(f"  pdfplumber error: {e}")
        all_warnings.append(f"pdfplumber exception: {e}")

    # ---- LLM fallback ----
    if data is None:
        log("  Falling back to Gemini LLM...")
        data, llm_err = llm_parse(pdf_path)

        if data is None:
            err = f"Both parsers failed. LLM: {llm_err}. Warnings: {'; '.join(all_warnings)}"
            log(f"  CRITICAL: {err}")
            append_log(date_str, 'failed', 'both', 0, warnings=all_warnings, error=err)
            send_critical_alert(date_str, err)
            return False

        method = 'llm'
        status = 'fallback_llm'
        log(f"  LLM OK - {len(data.get('entries', []))} entries")

    # ---- Save JSON ----
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"  Saved: {json_path}")

    # ---- Log ----
    entries_count = len(data.get('entries', []))
    append_log(date_str, status, method, entries_count,
               warnings=all_warnings if all_warnings else None)

    # ---- DB insert (uncomment when ready) ----
    # from parceALLpdfs import get_db_ids, insert_data, DB_CONFIG
    # import psycopg2
    # conn = psycopg2.connect(**DB_CONFIG)
    # cur = conn.cursor()
    # ids = get_db_ids(cur)
    # rows = insert_data(cur, data, ids)
    # conn.commit(); cur.close(); conn.close()
    # log(f"  DB: {rows} rows inserted")

    return True


def main():
    # --test-email flag
    if '--test-email' in sys.argv:
        log("Sending test email...")
        ok = send_email("Test - Fuel Price Pipeline", "This is a test email from daily_pipeline.py.")
        log("Sent!" if ok else "Failed - check SMTP env vars in .env")
        return

    log("Daily fuel price pipeline starting")

    # ---- 1. Find unprocessed PDFs (up to last 30) ----
    try:
        pending, err = get_pending_pdfs(limit=30)
    except Exception as e:
        err = f"Page fetch exception: {e}"
        log(f"CRITICAL: {err}")
        today = datetime.now().strftime('%Y-%m-%d')
        append_log(today, 'failed', 'none', 0, error=err)
        send_critical_alert(today, err)
        sys.exit(1)

    if pending is None:
        log(f"CRITICAL: {err}")
        today = datetime.now().strftime('%Y-%m-%d')
        append_log(today, 'failed', 'none', 0, error=err)
        send_critical_alert(today, err)
        sys.exit(1)

    if not pending:
        log("Nothing new to process — all up to date")
        if datetime.now().weekday() == 6:
            send_weekly_summary()
        return

    log(f"Found {len(pending)} unprocessed PDF(s)")

    # ---- 2. Process each one (oldest first) ----
    for pdf_path, date_str in pending:
        process_pdf(pdf_path, date_str)

    # ---- 3. Weekly email on Sunday ----
    if datetime.now().weekday() == 6:
        log("Sunday - sending weekly summary")
        send_weekly_summary()

    log("Pipeline finished")


if __name__ == '__main__':
    main()
