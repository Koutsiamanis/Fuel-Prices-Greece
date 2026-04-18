#!/usr/bin/env python3
"""Bulk-import every JSON file in `json_output/` into the MySQL database.

Idempotent — uses INSERT ... ON DUPLICATE KEY UPDATE, so re-runs are safe.
Run once after applying `database/schema.sql` to backfill the historical data.

Usage:
    python scripts/import_to_db.py              # import everything
    python scripts/import_to_db.py --limit 10   # only the first 10 files (smoke test)
    python scripts/import_to_db.py --dry-run    # parse + count rows, no DB writes
"""

import argparse
import json
import sys
from pathlib import Path

from tqdm import tqdm

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from db import connect, load_id_maps, insert_entries

JSON_DIR = _PROJECT_DIR / 'json_output'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, help='Only import the first N files (for testing)')
    ap.add_argument('--dry-run', action='store_true', help='Parse files but do not write to DB')
    args = ap.parse_args()

    files = sorted(JSON_DIR.glob('*.json'))
    if args.limit:
        files = files[:args.limit]

    if not files:
        sys.exit(f'No JSON files in {JSON_DIR}')

    print(f'Found {len(files)} JSON files in {JSON_DIR}')

    if args.dry_run:
        print('DRY RUN — no DB writes')
        total = 0
        for fpath in tqdm(files, desc='Scanning', unit='file'):
            with open(fpath, encoding='utf-8') as f:
                data = json.load(f)
            for entry in data.get('entries', []):
                total += sum(1 for v in entry.get('prices', {}).values() if v is not None)
        print(f'Would upsert ~{total} rows total')
        return

    conn = connect()
    cur = conn.cursor()

    pref_ids, fuel_ids = load_id_maps(cur)
    if not pref_ids or not fuel_ids:
        sys.exit('ERROR: prefectures/fuel_types tables empty — apply schema.sql first')
    print(f'DB has {len(pref_ids)} prefectures and {len(fuel_ids)} fuel types')

    total_rows = 0
    skipped_files = 0
    all_unknown = set()

    for fpath in tqdm(files, desc='Importing', unit='file'):
        with open(fpath, encoding='utf-8') as f:
            data = json.load(f)

        if not data.get('date'):
            tqdm.write(f'  Skipping {fpath.name}: no date')
            skipped_files += 1
            continue

        rows, unknown = insert_entries(cur, data, pref_ids, fuel_ids)
        conn.commit()
        total_rows += rows
        all_unknown |= unknown

    cur.close()
    conn.close()

    print(f'\nDone. {total_rows} rows upserted across {len(files) - skipped_files} files')
    if skipped_files:
        print(f'Skipped {skipped_files} files (no date)')
    if all_unknown:
        print(f'Unknown prefectures (not inserted): {sorted(all_unknown)}')


if __name__ == '__main__':
    main()
