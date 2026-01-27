import sqlite3
import shutil
import sys
import os

CACHE_TABLES = ['v8_3D_cache', 'v8_histo_cache', 'v8_stats']
OFFSET_TABLES = ['v8_offset_1', 'v8_offset_2', 'v8_offset_3', 'v8_offset_4']
INVARIANT_TABLE = 'invariants_filtered'

def cleanup(db_path: str):
    """
    Separates the analysis cache from the raw data, creating two specialized DBs.
    - The original DB path will be modified to contain ONLY raw data.
    - A new '<name>_app.db' file will be created to contain ONLY cache/app data.
    """
    if not os.path.exists(db_path):
        sys.exit(f"Error: Database file not found at '{db_path}'.")

    # FIX 1: Ensure the output directory exists
    os.makedirs("app", exist_ok=True)
    app_db_path = f"app/proteins_app.db"

    print(f"--- Pipeline Step 3: Database Cleanup and Separation ---")
    
    # FIX 2: Safety Check (Idempotency)
    # Check if the source DB actually has the cache tables. 
    # If not, it was likely already cleaned, and proceeding would create a blank App DB.
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        # Check for the existence of the main stats table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='v8_stats';")
        if not cursor.fetchone():
            print(f"CRITICAL ERROR: Cache table 'v8_stats' not found in source '{db_path}'.")
            print("The source database appears to be already cleaned (raw-only).")
            print("Aborting operation to prevent creating an empty App database.")
            sys.exit(1)

    print(f"Source (will become RAW data DB): {db_path}")
    print(f"Target (will become APP cache DB): {app_db_path}\n")

    try:
        shutil.copy2(db_path, app_db_path)
        print(f"App DB copy created successfully: {app_db_path}")
    except Exception as e:
        sys.exit(f"Error creating app DB copy: {e}")

    print(f"\nCleaning original DB '{db_path}' (Removing cache and offsets)...")
    tables_to_drop_from_original = CACHE_TABLES + OFFSET_TABLES
    
    with sqlite3.connect(db_path) as conn:
        for table in tables_to_drop_from_original:
            conn.execute(f"DROP TABLE IF EXISTS {table};")
            print(f"  Dropped {table} from original.")
        conn.commit()

        print("  Vacuuming original DB to reclaim space...")
        conn.execute("VACUUM;")

    print(f"'{db_path}' now contains only the raw '{INVARIANT_TABLE}' data.")

    print(f"\nCleaning app DB '{app_db_path}' (Removing raw data and offsets)...")
    tables_to_drop_from_app = [INVARIANT_TABLE] + OFFSET_TABLES
    
    with sqlite3.connect(app_db_path) as conn:
        for table in tables_to_drop_from_app:
            conn.execute(f"DROP TABLE IF EXISTS {table};")
            print(f"  Dropped {table} from app.")
        conn.commit()

        print("  Vacuuming app DB to reclaim space...")
        conn.execute("VACUUM;")

    print(f"'{app_db_path}' now contains only cache and stats tables.")
    print("\n--- Cleanup Complete ---")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Error: Please provide the database path as a command-line argument (e.g., python cleanup.py /path/to/proteins.db).")
    cleanup(sys.argv[1])