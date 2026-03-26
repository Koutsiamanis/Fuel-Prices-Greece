import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import pdfplumber
# import psycopg2
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT', '5432'),
    'sslmode': 'require',
}

# Η ΠΛΗΡΗΣ λίστα καυσίμων με τη σειρά που εμφανίζονται στον πίνακα
# Αν το αρχείο έχει λιγότερες στήλες (καλοκαίρι), το script θα σταματήσει αυτόματα στο Autogas.
ALL_FUELS_ORDER = [
    'Αμόλυβδη 95 οκτ.',
    'Αμόλυβδη 100 οκτ.',
    'Diesel Κίνησης',
    'Υγραέριο κίνησης (Autogas)',
    'Diesel Θέρμανσης Κατ΄ οίκον',
]

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

GREEK_MONTHS = {
    'ΙΑΝΟΥΑΡΙΟΥ': '01', 'ΦΕΒΡΟΥΑΡΙΟΥ': '02', 'ΜΑΡΤΙΟΥ': '03', 'ΑΠΡΙΛΙΟΥ': '04',
    'ΜΑΙΟΥ': '05', 'ΜΑΪΟΥ': '05', 'ΙΟΥΝΙΟΥ': '06', 'ΙΟΥΛΙΟΥ': '07',
    'ΑΥΓΟΥΣΤΟΥ': '08', 'ΣΕΠΤΕΜΒΡΙΟΥ': '09', 'ΟΚΤΩΒΡΙΟΥ': '10',
    'ΝΟΕΜΒΡΙΟΥ': '11', 'ΔΕΚΕΜΒΡΙΟΥ': '12',
}


def normalize_text(text):
    if not text:
        return ""
    text = text.upper()
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    replacements = {
        'A': 'Α', 'B': 'Β', 'E': 'Ε', 'H': 'Η', 'I': 'Ι',
        'K': 'Κ', 'M': 'Μ', 'N': 'Ν', 'O': 'Ο', 'P': 'Ρ',
        'T': 'Τ', 'X': 'Χ', 'Y': 'Υ', 'Z': 'Ζ',
    }
    for latin, greek in replacements.items():
        text = text.replace(latin, greek)
    return " ".join(text.split())


# Pre-compute normalized canonical names for matching without DB
_NORM_PREFECTURES = {normalize_text(n): n for n in CANONICAL_PREFECTURES}


def match_prefecture(line_norm):
    """Match a normalized line against canonical prefecture names."""
    for norm_name, canonical in _NORM_PREFECTURES.items():
        if line_norm.startswith(norm_name):
            return canonical, norm_name
    return None, None


def parse_greek_date(text):
    match = re.search(r'(\d{1,2})\s+([Α-Ωα-ωά-ώ]+)\s+(\d{4})', text)
    if match:
        day = match.group(1).zfill(2)
        month_clean = ''.join(c for c in unicodedata.normalize('NFD', match.group(2).upper()) if unicodedata.category(c) != 'Mn')
        year = match.group(3)
        if month_clean in GREEK_MONTHS:
            return f"{year}-{GREEK_MONTHS[month_clean]}-{day}"
    return None


def clean_price(price_str):
    if not price_str or price_str.strip() in ['-', '', 'NULL']:
        return None
    try:
        clean = price_str.replace(',', '.')
        clean = re.sub(r'[^\d.]', '', clean)
        val = float(clean)
        if val == 0.0:
            return None
        return val
    except ValueError:
        return None


def main():
    if len(sys.argv) < 2:
        print(f'Usage: python {sys.argv[0]} <pdf_file>')
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f'ERROR: file not found: {pdf_path}')
        sys.exit(1)

    # Date from filename if it looks like YYYY-MM-DD, otherwise from PDF header
    if re.match(r'\d{4}-\d{2}-\d{2}', pdf_path.stem):
        report_date = pdf_path.stem
    else:
        report_date = None

    data = {'date': None, 'entries': []}

    with pdfplumber.open(pdf_path) as pdf:
        if report_date is None:
            first_page_text = pdf.pages[0].extract_text()
            report_date = parse_greek_date(first_page_text)
            if not report_date:
                print("ERROR: Could not determine date from filename or PDF header.")
                sys.exit(1)

        data['date'] = report_date

        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')

            for line in lines:
                line_norm = normalize_text(line)

                # 1. Εντοπισμός Νομού
                canonical, norm_name = match_prefecture(line_norm)
                if not canonical:
                    continue

                # 2. Απομόνωση των τιμών
                rest_of_line = line_norm.replace(norm_name, "", 1).strip()
                parts = rest_of_line.split()
                price_parts = [p for p in parts if re.match(r'^[\d,\.-]+$', p)]

                if len(price_parts) < 3:
                    continue

                # 3. Δυναμική Αντιστοίχιση (ZIP)
                # Η εντολή zip θα σταματήσει αυτόματα στο μήκος της μικρότερης λίστας.
                # - Αν το price_parts έχει 4 τιμές -> θα πάρει τα πρώτα 4 καύσιμα.
                # - Αν το price_parts έχει 5 τιμές -> θα πάρει και τα 5 καύσιμα.
                prices = {}
                for fuel_label, raw_price in zip(ALL_FUELS_ORDER, price_parts):
                    prices[fuel_label] = clean_price(raw_price)

                # Fill any missing fuels with null
                for fuel in ALL_FUELS_ORDER:
                    if fuel not in prices:
                        prices[fuel] = None

                data['entries'].append({
                    'prefecture': canonical,
                    'prices': prices,
                })

    # Save JSON
    output_dir = Path('json_output')
    output_dir.mkdir(exist_ok=True)
    out_file = output_dir / (pdf_path.stem + '.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'Date: {data["date"]}')
    print(f'Entries: {len(data["entries"])}')
    print(f'Saved: {out_file}')

    # --- DB insert (uncomment when DB is available) ---
    # conn = None
    # cur = None
    # try:
    #     conn = psycopg2.connect(**DB_CONFIG)
    #     cur = conn.cursor()
    #     ids_cache = get_db_ids(cur)
    #     rows = 0
    #     for entry in data['entries']:
    #         pref_norm = normalize_text(entry['prefecture'])
    #         pref_id = ids_cache['prefectures'].get(pref_norm)
    #         if pref_id is None:
    #             continue
    #         for fuel_name, price in entry['prices'].items():
    #             if price is None:
    #                 continue
    #             fuel_id = ids_cache['fuels'].get(fuel_name)
    #             if fuel_id is None:
    #                 continue
    #             cur.execute("""
    #                 INSERT INTO daily_fuel_prices (prefecture_id, fuel_type_id, date, price)
    #                 VALUES (%s, %s, %s, %s)
    #                 ON CONFLICT (prefecture_id, fuel_type_id, date)
    #                 DO UPDATE SET price = EXCLUDED.price
    #             """, (pref_id, fuel_id, data['date'], price))
    #             rows += 1
    #     conn.commit()
    #     print(f'DB: inserted {rows} rows')
    # except Exception as e:
    #     print(f'DB ERROR: {e}')
    #     if conn:
    #         conn.rollback()
    # finally:
    #     if cur:
    #         cur.close()
    #     if conn:
    #         conn.close()


def get_db_ids(cursor):
    ids_cache = {'prefectures': {}, 'fuels': {}}
    cursor.execute("SELECT name, id FROM prefectures")
    for name, p_id in cursor.fetchall():
        ids_cache['prefectures'][normalize_text(name)] = p_id
    cursor.execute("SELECT name, id FROM fuel_types")
    for name, f_id in cursor.fetchall():
        ids_cache['fuels'][name] = f_id
    return ids_cache


if __name__ == "__main__":
    main()
