"""Shared MySQL helpers for the fuel-price pipeline.

Both the bulk importer (`import_to_db.py`) and the daily pipeline
(`daily_pipeline.py`) use these functions so the insert logic lives in one place.
"""

import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from parceALLpdfs import normalize_text

load_dotenv(_SCRIPT_DIR.parent / '.env')


def get_db_config() -> dict:
    return {
        'host': os.getenv('DB_HOST'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'database': os.getenv('DB_NAME'),
        'charset': 'utf8mb4',
    }


def connect():
    """Open a MySQL connection using env vars. Raises on missing config."""
    cfg = get_db_config()
    missing = [k for k in ('host', 'user', 'database') if not cfg.get(k)]
    if missing:
        raise RuntimeError(f"Missing DB config in .env: {missing}")
    return pymysql.connect(**cfg)


def load_id_maps(cursor) -> tuple[dict, dict]:
    """Return (prefecture name→id, fuel name→id). Prefecture names are normalized."""
    cursor.execute('SELECT id, name FROM prefectures')
    prefs = {normalize_text(name): pid for pid, name in cursor.fetchall()}
    cursor.execute('SELECT id, name FROM fuel_types')
    fuels = {name: fid for fid, name in cursor.fetchall()}
    return prefs, fuels


def find_prefecture_id(name: str, pref_ids: dict) -> int | None:
    """Map any prefecture name (already normalized in JSON) to its DB id."""
    norm = normalize_text(name)
    if norm in pref_ids:
        return pref_ids[norm]
    for db_norm, pid in pref_ids.items():
        if db_norm in norm or norm in db_norm:
            return pid
    return None


_INSERT_SQL = """
    INSERT INTO daily_fuel_prices (prefecture_id, fuel_type_id, date, price)
    VALUES (%s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE price = VALUES(price)
"""


def insert_entries(cursor, data: dict, pref_ids: dict, fuel_ids: dict) -> tuple[int, set]:
    """Upsert all price rows from one parsed-PDF dict.

    Returns (rows_upserted, unknown_prefecture_names_seen).
    """
    date = data.get('date')
    if not date:
        return 0, set()

    rows = []
    unknown = set()

    for entry in data.get('entries', []):
        pref_name = entry.get('prefecture', '')
        pref_id = find_prefecture_id(pref_name, pref_ids)
        if pref_id is None:
            unknown.add(pref_name)
            continue

        for fuel, price in entry.get('prices', {}).items():
            if price is None:
                continue
            fuel_id = fuel_ids.get(fuel)
            if fuel_id is None:
                continue
            rows.append((pref_id, fuel_id, date, float(price)))

    if rows:
        cursor.executemany(_INSERT_SQL, rows)

    return len(rows), unknown
