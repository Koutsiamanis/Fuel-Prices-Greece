import json
import os
import sys
import time
import unicodedata
from pathlib import Path

# import psycopg2
from dotenv import load_dotenv
from google import genai
from google.genai import types
from tqdm import tqdm

load_dotenv()

# --- Configuration ---
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'postgres'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT', '5432'),
    'sslmode': 'require',  # Required for Supabase
}

PROGRESS_FILE = Path('processed_log.json')

MODEL = 'gemini-2.5-flash'

# Canonical prefecture names exactly as stored in the database
CANONICAL_PREFECTURES = [
    'ΝΟΜΟΣ ΑΤΤΙΚΗΣ',
    'ΝΟΜΟΣ ΑΙΤΩΛΙΑΣ ΚΑΙ ΑΚΑΡΝΑΝΙΑΣ',
    'ΝΟΜΟΣ ΑΡΓΟΛΙΔΟΣ',
    'ΝΟΜΟΣ ΑΡΚΑΔΙΑΣ',
    'ΝΟΜΟΣ ΑΡΤΗΣ',
    'ΝΟΜΟΣ ΑΧΑΪΑΣ',
    'ΝΟΜΟΣ ΒΟΙΩΤΙΑΣ',
    'ΝΟΜΟΣ ΓΡΕΒΕΝΩΝ',
    'ΝΟΜΟΣ ΔΡΑΜΑΣ',
    'ΝΟΜΟΣ ΔΩΔΕΚΑΝΗΣΟΥ',
    'ΝΟΜΟΣ ΕΒΡΟΥ',
    'ΝΟΜΟΣ ΕΥΒΟΙΑΣ',
    'ΝΟΜΟΣ ΕΥΡΥΤΑΝΙΑΣ',
    'ΝΟΜΟΣ ΖΑΚΥΝΘΟΥ',
    'ΝΟΜΟΣ ΗΛΕΙΑΣ',
    'ΝΟΜΟΣ ΗΜΑΘΙΑΣ',
    'ΝΟΜΟΣ ΗΡΑΚΛΕΙΟΥ',
    'ΝΟΜΟΣ ΘΕΣΠΡΩΤΙΑΣ',
    'ΝΟΜΟΣ ΘΕΣΣΑΛΟΝΙΚΗΣ',
    'ΝΟΜΟΣ ΙΩΑΝΝΙΝΩΝ',
    'ΝΟΜΟΣ ΚΑΒΑΛΑΣ',
    'ΝΟΜΟΣ ΚΑΡΔΙΤΣΗΣ',
    'ΝΟΜΟΣ ΚΑΣΤΟΡΙΑΣ',
    'ΝΟΜΟΣ ΚΕΡΚΥΡΑΣ',
    'ΝΟΜΟΣ ΚΕΦΑΛΛΗΝΙΑΣ',
    'ΝΟΜΟΣ ΚΙΛΚΙΣ',
    'ΝΟΜΟΣ ΚΟΖΑΝΗΣ',
    'ΝΟΜΟΣ ΚΟΡΙΝΘΙΑΣ',
    'ΝΟΜΟΣ ΚΥΚΛΑΔΩΝ',
    'ΝΟΜΟΣ ΛΑΚΩΝΙΑΣ',
    'ΝΟΜΟΣ ΛΑΡΙΣΗΣ',
    'ΝΟΜΟΣ ΛΑΣΙΘΙΟΥ',
    'ΝΟΜΟΣ ΛΕΣΒΟΥ',
    'ΝΟΜΟΣ ΛΕΥΚΑΔΟΣ',
    'ΝΟΜΟΣ ΜΑΓΝΗΣΙΑΣ',
    'ΝΟΜΟΣ ΜΕΣΣΗΝΙΑΣ',
    'ΝΟΜΟΣ ΞΑΝΘΗΣ',
    'ΝΟΜΟΣ ΠΕΛΛΗΣ',
    'ΝΟΜΟΣ ΠΙΕΡΙΑΣ',
    'ΝΟΜΟΣ ΠΡΕΒΕΖΗΣ',
    'ΝΟΜΟΣ ΡΕΘΥΜΝΗΣ',
    'ΝΟΜΟΣ ΡΟΔΟΠΗΣ',
    'ΝΟΜΟΣ ΣΑΜΟΥ',
    'ΝΟΜΟΣ ΣΕΡΡΩΝ',
    'ΝΟΜΟΣ ΤΡΙΚΑΛΩΝ',
    'ΝΟΜΟΣ ΦΘΙΩΤΙΔΟΣ',
    'ΝΟΜΟΣ ΦΛΩΡΙΝΗΣ',
    'ΝΟΜΟΣ ΦΩΚΙΔΟΣ',
    'ΝΟΜΟΣ ΧΑΛΚΙΔΙΚΗΣ',
    'ΝΟΜΟΣ ΧΑΝΙΩΝ',
    'ΝΟΜΟΣ ΧΙΟΥ',
    'ΠΑΝΕΛΛΗΝΙΟΣ ΣΤΑΘΜΙΣΜΕΝΟΣ Μ.Ο.',
]

SYSTEM_PROMPT = """\
You are a precise data extraction assistant. You will receive a PDF of a Greek \
government daily fuel price bulletin (Καθημερινό Δελτίο Επισκόπησης Τιμών Υγρών Καυσίμων).

Extract ALL data from the fuel price table(s) and return ONLY a valid JSON object \
with this exact structure:
{
  "date": "YYYY-MM-DD",
  "entries": [
    {
      "prefecture": "<prefecture name in Greek as it appears in the table>",
      "prices": {
        "Αμόλυβδη 95 οκτ.": <float or null>,
        "Αμόλυβδη 100 οκτ.": <float or null>,
        "Diesel Κίνησης": <float or null>,
        "Υγραέριο κίνησης (Autogas)": <float or null>,
        "Diesel Θέρμανσης Κατ΄ οίκον": <float or null>
      }
    }
  ]
}

CRITICAL RULES — read carefully:

1. COLUMN HEADERS: The column order in the table changes between years. You MUST \
identify each column by reading its actual header text, then map each price value \
to the correct fuel key. Do NOT assume a fixed column position.

2. HEATING DIESEL — SEASONAL COLUMN: "Diesel Θέρμανσης Κατ΄ οίκον" is a seasonal \
fuel sold only in winter months. Many PDFs — especially from spring and summer — do \
NOT have this column at all. If you cannot find a column with this exact header (or \
a clear abbreviation of it) in the table, set every entry's value to null. Never \
invent or borrow values from another column to fill it.

3. NULL VALUES: Use null for "-", "0,000", "0.000", or any blank/missing cell.

4. DECIMAL SEPARATOR: Prices use a comma in the source; convert to float ("1,743" → 1.743).

5. Include every row, including "ΠΑΝΕΛΛΗΝΙΟΣ ΣΤΑΘΜΙΣΜΕΝΟΣ Μ.Ο." if present.

6. Return ONLY the JSON object — no markdown, no explanation.\
"""


def normalize_text(text: str) -> str:
    """Uppercase, strip accents, replace visually identical Latin→Greek chars."""
    if not text:
        return ""
    text = text.upper()
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    replacements = {
        'A': 'Α', 'B': 'Β', 'E': 'Ε', 'H': 'Η', 'I': 'Ι',
        'K': 'Κ', 'M': 'Μ', 'N': 'Ν', 'O': 'Ο', 'P': 'Ρ',
        'T': 'Τ', 'X': 'Χ', 'Y': 'Υ', 'Z': 'Ζ',
    }
    for latin, greek in replacements.items():
        text = text.replace(latin, greek)
    return ' '.join(text.split())


# Pre-compute normalized canonical names for fast lookup
_NORM_TO_CANONICAL = {normalize_text(n): n for n in CANONICAL_PREFECTURES}

# Aliases for alternate spellings found in older PDFs
_ALIASES = {
    normalize_text('ΝΟΜΟΣ ΑΙΤΩΛΟΑΚΑΡΝΑΝΙΑΣ'): 'ΝΟΜΟΣ ΑΙΤΩΛΙΑΣ ΚΑΙ ΑΚΑΡΝΑΝΙΑΣ',
}
_NORM_TO_CANONICAL.update(_ALIASES)


def _levenshtein(a: str, b: str) -> int:
    dp = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        dp2 = [i + 1]
        for j, cb in enumerate(b):
            dp2.append(min(dp[j + 1] + 1, dp2[-1] + 1, dp[j] + (ca != cb)))
        dp = dp2
    return dp[-1]


def normalize_prefecture(llm_name: str) -> str:
    """Map any LLM-returned prefecture name to the canonical DB name."""
    norm = normalize_text(llm_name)

    # 1. Exact match
    if norm in _NORM_TO_CANONICAL:
        return _NORM_TO_CANONICAL[norm]

    # 2. Substring containment (handles partial names)
    for canon_norm, canon in _NORM_TO_CANONICAL.items():
        if canon_norm in norm or norm in canon_norm:
            return canon

    # 3. Best Levenshtein match (handles genitive/nominative variants like ΠΕΛΛΑΣ→ΠΕΛΛΗΣ)
    best_dist = float('inf')
    best_canon = llm_name  # fall back to original if nothing close
    for canon_norm, canon in _NORM_TO_CANONICAL.items():
        d = _levenshtein(norm, canon_norm)
        if d < best_dist:
            best_dist = d
            best_canon = canon

    # Only accept if reasonably close (allow up to 4 character edits)
    if best_dist <= 4:
        return best_canon

    return llm_name  # unknown — return as-is so we can spot it


def normalize_entries(data: dict) -> dict:
    """Post-process LLM output: normalize prefecture names and drop unwanted keys."""
    for entry in data.get('entries', []):
        entry['prefecture'] = normalize_prefecture(entry.get('prefecture', ''))
        # Super is not tracked — remove it regardless of what the LLM returned
        entry.get('prices', {}).pop('Super', None)
        # 0.0 means no data (no station reported), convert to null
        prices = entry.get('prices', {})
        for fuel, val in prices.items():
            if val == 0.0:
                prices[fuel] = None
    return data


FLAGGED_FILE = Path('flagged.json')
PRICE_MIN, PRICE_MAX = 0.3, 4.0  # plausible €/L range for Greek fuel prices


def validate(data: dict, pdf_name: str) -> list[str]:
    """Return a list of warning strings; empty means the extraction looks clean."""
    warnings = []
    entries = data.get('entries', [])

    if len(entries) < 40:
        warnings.append(f'only {len(entries)} entries (expected 51-52)')

    for entry in entries:
        pref = entry.get('prefecture', '')
        if pref not in CANONICAL_PREFECTURES:
            warnings.append(f'unmatched prefecture: "{pref}"')

        prices = entry.get('prices', {})
        numeric = [v for v in prices.values() if isinstance(v, (int, float))]

        if numeric and all(v is None or not isinstance(v, (int, float)) for v in prices.values()):
            warnings.append(f'all prices null for {pref}')

        for fuel, val in prices.items():
            if isinstance(val, (int, float)) and not (PRICE_MIN <= val <= PRICE_MAX):
                warnings.append(f'price out of range for {pref} / {fuel}: {val}')

    return warnings


def load_flagged() -> dict:
    if FLAGGED_FILE.exists():
        with open(FLAGGED_FILE) as f:
            return json.load(f)
    return {}


def save_flagged(flagged: dict) -> None:
    with open(FLAGGED_FILE, 'w', encoding='utf-8') as f:
        json.dump(flagged, f, ensure_ascii=False, indent=2)


def extract_data_from_pdf(client: genai.Client, pdf_path: Path) -> dict | None:
    """Send the PDF directly to Gemini and return normalized JSON, or None."""
    pdf_bytes = pdf_path.read_bytes()

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf'),
                    'Extract all fuel price data from this PDF and return as JSON.',
                ],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0,
                    response_mime_type='application/json',
                    max_output_tokens=65536,
                ),
            )
            data = json.loads(response.text)
            return normalize_entries(data)
        except Exception as e:
            if attempt < 2:
                wait = 5 * (2 ** attempt)
                tqdm.write(f'  API error ({e}), retrying in {wait}s...')
                time.sleep(wait)
            else:
                tqdm.write(f'  FAILED after 3 attempts for {pdf_path.name}: {e}')
                return None


def get_db_ids(cursor) -> dict:
    """Load prefecture and fuel type name→id maps from the database."""
    ids = {'prefectures': {}, 'fuels': {}}
    cursor.execute('SELECT name, id FROM prefectures')
    for name, pid in cursor.fetchall():
        ids['prefectures'][normalize_text(name)] = pid
    cursor.execute('SELECT name, id FROM fuel_types')
    for name, fid in cursor.fetchall():
        ids['fuels'][name] = fid
    return ids


def find_prefecture_id(llm_name: str, ids_cache: dict) -> int | None:
    """Fuzzy-match an LLM-returned prefecture name to a DB id."""
    normalized = normalize_text(llm_name)
    if normalized in ids_cache['prefectures']:
        return ids_cache['prefectures'][normalized]
    for db_name, db_id in ids_cache['prefectures'].items():
        if db_name in normalized or normalized in db_name:
            return db_id
    return None


def insert_data(cursor, data: dict, ids_cache: dict) -> int:
    """Insert extracted price entries. Returns the number of rows upserted."""
    date = data.get('date')
    if not date:
        return 0

    rows = 0
    for entry in data.get('entries', []):
        pref_id = find_prefecture_id(entry.get('prefecture', ''), ids_cache)
        if pref_id is None:
            continue

        for fuel_name, price in entry.get('prices', {}).items():
            if price is None:
                continue
            fuel_id = ids_cache['fuels'].get(fuel_name)
            if fuel_id is None:
                continue

            cursor.execute(
                """
                INSERT INTO daily_fuel_prices (prefecture_id, fuel_type_id, date, price)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (prefecture_id, fuel_type_id, date)
                DO UPDATE SET price = EXCLUDED.price
                """,
                (pref_id, fuel_id, date, float(price)),
            )
            rows += 1
    return rows


def load_progress() -> set:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return set(json.load(f))
    return set()


def save_progress(processed: set) -> None:
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(sorted(processed), f, indent=2)


def main() -> None:
    pdf_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('./test_pdfs')

    if not pdf_dir.is_dir():
        print(f'ERROR: directory not found: {pdf_dir}')
        sys.exit(1)

    pdf_files = sorted(pdf_dir.glob('*.pdf'))
    if not pdf_files:
        print(f'No PDF files found in {pdf_dir}')
        sys.exit(0)

    processed = load_progress()
    remaining = [f for f in pdf_files if f.name not in processed]

    print(f'PDF directory : {pdf_dir}')
    print(f'Total PDFs    : {len(pdf_files)}')
    print(f'Already done  : {len(processed)}')
    print(f'To process    : {len(remaining)}')
    print(f'Model         : {MODEL}')

    if not remaining:
        print('Nothing to do.')
        return

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print('ERROR: GEMINI_API_KEY not set in .env file')
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # --- DB disabled for testing ---
    # conn = psycopg2.connect(**DB_CONFIG)
    # cur = conn.cursor()
    # ids_cache = get_db_ids(cur)
    # print(f'DB prefectures: {len(ids_cache["prefectures"])}  fuel types: {len(ids_cache["fuels"])}')

    output_dir = Path('json_output')
    output_dir.mkdir(exist_ok=True)

    flagged = load_flagged()
    errors = []

    for pdf_path in tqdm(remaining, desc='Processing', unit='pdf'):
        data = extract_data_from_pdf(client, pdf_path)

        if data is None:
            errors.append(pdf_path.name)
            flagged[pdf_path.name] = ['FAILED: extraction returned None after 3 attempts']
            save_flagged(flagged)
            continue

        data['date'] = pdf_path.stem  # filename is always the correct survey date

        # Validate and flag suspicious extractions for manual review
        warnings = validate(data, pdf_path.name)
        if warnings:
            flagged[pdf_path.name] = warnings
            save_flagged(flagged)
            tqdm.write(f'  ⚠ {pdf_path.name}  flagged: {"; ".join(warnings)}')

        # Save extracted data as JSON for inspection
        out_file = output_dir / (pdf_path.stem + '.json')
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # --- DB insert disabled for testing ---
        # rows = insert_data(cur, data, ids_cache)
        # conn.commit()
        # total_rows += rows

        processed.add(pdf_path.name)
        save_progress(processed)
        tqdm.write(f'  {pdf_path.name}  →  {len(data.get("entries", []))} entries  (date: {data.get("date")})')

    # cur.close()
    # conn.close()

    print(f'\nFinished. JSON files saved to {output_dir}/')
    if flagged:
        print(f'Flagged for review ({len(flagged)}): see {FLAGGED_FILE}')
    if errors:
        print(f'Failed ({len(errors)}): {", ".join(errors)}')


if __name__ == '__main__':
    main()
