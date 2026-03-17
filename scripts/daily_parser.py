import os
import pdfplumber
import re
import psycopg2
import unicodedata
from dotenv import load_dotenv

load_dotenv()

# --- ΡΥΘΜΙΣΕΙΣ ---
PDF_FILE = './fuel_pdfs/2023-08-22.pdf'

DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT', '5432'),
}

# Η ΠΛΗΡΗΣ λίστα καυσίμων με τη σειρά που εμφανίζονται στον πίνακα 
# Αν το αρχείο έχει λιγότερες στήλες (καλοκαίρι), το script θα σταματήσει αυτόματα στο Autogas.
ALL_FUELS_ORDER = [
    'Αμόλυβδη 95 οκτ.',            # 1η Τιμή
    'Αμόλυβδη 100 οκτ.',           # 2η Τιμή
    'Diesel Κίνησης',              # 3η Τιμή
    'Υγραέριο κίνησης (Autogas)',  # 4η Τιμή
    'Diesel Θέρμανσης Κατ΄ οίκον'  # 5η Τιμή (Μόνο τον χειμώνα) 
]

GREEK_MONTHS = {
    'ΙΑΝΟΥΑΡΙΟΥ': '01', 'ΦΕΒΡΟΥΑΡΙΟΥ': '02', 'ΜΑΡΤΙΟΥ': '03', 'ΑΠΡΙΛΙΟΥ': '04',
    'ΜΑΙΟΥ': '05', 'ΜΑΪΟΥ': '05', 'ΙΟΥΝΙΟΥ': '06', 'ΙΟΥΛΙΟΥ': '07',
    'ΑΥΓΟΥΣΤΟΥ': '08', 'ΣΕΠΤΕΜΒΡΙΟΥ': '09', 'ΟΚΤΩΒΡΙΟΥ': '10',
    'ΝΟΕΜΒΡΙΟΥ': '11', 'ΔΕΚΕΜΒΡΙΟΥ': '12'
}

def normalize_text(text):
    if not text: return ""
    text = text.upper()
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    replacements = {'A': 'Α', 'B': 'Β', 'E': 'Ε', 'H': 'Η', 'I': 'Ι', 'K': 'Κ', 'M': 'Μ', 'N': 'Ν', 'O': 'Ο', 'P': 'Ρ', 'T': 'Τ', 'X': 'Χ', 'Y': 'Υ', 'Z': 'Ζ'}
    for latin, greek in replacements.items():
        text = text.replace(latin, greek)
    return " ".join(text.split())

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
    # Αν βρει παύλα ή κενό, επιστρέφει None
    if not price_str or price_str.strip() in ['-', '', 'NULL']:
        return None
    try:
        clean = price_str.replace(',', '.')
        # Κρατάμε μόνο αριθμούς και τελεία
        clean = re.sub(r'[^\d.]', '', clean)
        return float(clean)
    except ValueError:
        return None

def get_db_ids(cursor):
    ids_cache = {'prefectures': {}, 'fuels': {}}
    cursor.execute("SELECT name, id FROM prefectures")
    for name, p_id in cursor.fetchall():
        ids_cache['prefectures'][normalize_text(name)] = p_id
    cursor.execute("SELECT name, id FROM fuel_types")
    for name, f_id in cursor.fetchall():
        ids_cache['fuels'][name] = f_id
    return ids_cache

def main():
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        ids_cache = get_db_ids(cur)
        print(f"DEBUG: Φορτώθηκαν {len(ids_cache['prefectures'])} νομοί.")

        with pdfplumber.open(PDF_FILE) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            report_date = parse_greek_date(first_page_text)
            
            if not report_date:
                print("ΣΦΑΛΜΑ: Δεν βρέθηκε ημερομηνία.")
                return
            
            print(f"DEBUG: Ημερομηνία: {report_date}")
            rows_inserted = 0

            for page in pdf.pages:
                text = page.extract_text()
                lines = text.split('\n')
                
                for line in lines:
                    line_norm = normalize_text(line)
                    
                    # 1. Εντοπισμός Νομού
                    matched_pref_name = None
                    matched_pref_id = None
                    
                    for db_name, db_id in ids_cache['prefectures'].items():
                        if line_norm.startswith(db_name):
                            matched_pref_name = db_name
                            matched_pref_id = db_id
                            break
                    
                    if not matched_pref_id:
                        continue 

                    # 2. Απομόνωση των τιμών
                    # Αφαιρούμε το όνομα του νομού και κρατάμε τα υπόλοιπα κομμάτια
                    rest_of_line = line_norm.replace(matched_pref_name, "").strip()
                    
                    # Σπάμε τη γραμμή στα κενά
                    parts = rest_of_line.split()
                    
                    # Φιλτράρισμα: Κρατάμε μόνο ότι μοιάζει με αριθμό ή παύλα (αγνοούμε τυχόν σκουπίδια)
                    price_parts = [p for p in parts if re.match(r'^[\d,\.-]+$', p)]

                    # Έλεγχος ασφαλείας: Πρέπει να έχουμε τουλάχιστον 3 τιμές για να είναι έγκυρη γραμμή
                    if len(price_parts) < 3:
                        continue

                    # 3. Δυναμική Αντιστοίχιση (ZIP)
                    # Η εντολή zip θα σταματήσει αυτόματα στο μήκος της μικρότερης λίστας.
                    # - Αν το price_parts έχει 4 τιμές -> θα πάρει τα πρώτα 4 καύσιμα.
                    # - Αν το price_parts έχει 5 τιμές -> θα πάρει και τα 5 καύσιμα.
                    
                    for fuel_label, raw_price in zip(ALL_FUELS_ORDER, price_parts):
                        price = clean_price(raw_price)
                        fuel_id = ids_cache['fuels'][fuel_label]
                        
                        if price is not None:
                            query = """
                                INSERT INTO daily_fuel_prices (prefecture_id, fuel_type_id, date, price)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (prefecture_id, fuel_type_id, date)
                                DO UPDATE SET price = EXCLUDED.price;
                            """
                            cur.execute(query, (matched_pref_id, fuel_id, report_date, price))
                            rows_inserted += 1

        conn.commit()
        print(f"ΤΕΛΟΣ! Καταχωρήθηκαν {rows_inserted} τιμές συνολικά.")

    except Exception as e:
        print(f"ΣΦΑΛΜΑ: {e}")
        if conn: conn.rollback()
    finally:
        if conn: 
            cur.close()
            conn.close()

if __name__ == "__main__":
    main()