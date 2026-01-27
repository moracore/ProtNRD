import sqlite3
import shutil
import sys
import os

# --- Table Definitions ---
# Tables containing generated plot data and statistics (to keep in main DB).
# (Removed 'v6_stats_cache' as it was consolidated into v6_stats)
CACHE_TABLES = ['v6_3D_cache', 'v6_histo_cache', 'v6_stats']

# Tables containing joined/interim data (to drop from both).
OFFSET_TABLES = ['v6_offset_1', 'v6_offset_2', 'v6_offset_3', 'v6_offset_4']

# The single primary raw input table.
INVARIANT_TABLE = 'invariants_filtered'

# --- Main Logic ---
def cleanup(db_path: str):
    """
    Separates the analysis cache from the raw data, creating two specialized DBs.
    - The original DB path will be modified to contain ONLY raw data.
    - A new '<name>_app.db' file will be created to contain ONLY cache/app data.
    """
    if not os.path.exists(db_path):
        sys.exit(f"Error: Database file not found at '{db_path}'.")

    # Determine the new app database path
    app_db_path = f"proteins_app.db"

    print(f"--- Pipeline Step 3: Database Cleanup and Separation ---")
    print(f"Source (will become RAW data DB): {db_path}")
    print(f"Target (will become APP cache DB): {app_db_path}\n")

    # 1. Create a full file system copy for the app database
    try:
        shutil.copy2(db_path, app_db_path)
        print(f"App DB copy created successfully: {app_db_path}")
    except Exception as e:
        sys.exit(f"Error creating app DB copy: {e}")

    # 2. Cleanup Original DB (db_path)
    # Goal: KEEP ONLY invariants_filtered (raw data)
    print(f"\nCleaning original DB '{db_path}' (Removing cache and offsets)...")
    tables_to_drop_from_original = CACHE_TABLES + OFFSET_TABLES
    
    with sqlite3.connect(db_path) as conn:
        for table in tables_to_drop_from_original:
            conn.execute(f"DROP TABLE IF EXISTS {table};")
            print(f"  Dropped {table} from original.")
        conn.commit()

        # --- VACUUM for Original DB ---
        print("  Vacuuming original DB to reclaim space...")
        conn.execute("VACUUM;")
        # --- END VACUUM ---

    print(f"'{db_path}' now contains only the raw '{INVARIANT_TABLE}' data.")


    # 3. Cleanup App DB (app_db_path)
    # Goal: KEEP ONLY cache and stats (for front-end serving)
    print(f"\nCleaning app DB '{app_db_path}' (Removing raw data and offsets)...")
    tables_to_drop_from_app = [INVARIANT_TABLE] + OFFSET_TABLES
    
    with sqlite3.connect(app_db_path) as conn:
        for table in tables_to_drop_from_app:
            conn.execute(f"DROP TABLE IF EXISTS {table};")
            print(f"  Dropped {table} from app.")
        conn.commit()

        # --- VACUUM for App DB ---
        print("  Vacuuming app DB to reclaim space...")
        conn.execute("VACUUM;")
        # --- END VACUUM ---

    print(f"'{app_db_path}' now contains only cache and stats tables.")
    print("\n--- Cleanup Complete ---")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Error: Please provide the database path as a command-line argument (e.g., python cleanup.py /path/to/proteins.db).")
    cleanup(sys.argv[1])