import sqlite3
import time
import sys

# --- Configuration ---
# DB_PATH is now passed as a command-line argument

def main(db_path):
    """
    Creates a new table ('invariants_filtered') containing only the rows
    from the 'invariants' table that have the '2AXR' flag set to 1.
    This is a one-time, potentially long-running data copy operation.
    """
    start_time = time.time()
    print("--- Creating 'invariants_filtered' table from existing 2AXR flag ---")
    
    with sqlite3.connect(db_path, timeout=7200) as conn:
        cursor = conn.cursor()
        
        # Check if the 2AXR column exists and has data
        print("Verifying '2AXR' column...")
        try:
            count_query = cursor.execute('SELECT SUM("2AXR") FROM invariants;')
            high_quality_rows = count_query.fetchone()[0]
            if high_quality_rows is None or high_quality_rows == 0:
                print("Error: The '2AXR' column contains no TRUE (1) values. No data to filter.")
                sys.exit(1)
            print(f"Found {high_quality_rows:,.0f} high-quality rows to process.")
        except sqlite3.OperationalError:
            print("Error: The 'invariants' table does not have a '2AXR' column. Please run the scraper script first.")
            sys.exit(1)

        print("\nDropping old filtered table if it exists...")
        cursor.execute("DROP TABLE IF EXISTS invariants_filtered;")
        
        print("Creating and populating new 'invariants_filtered' table... (This may take a very long time)")
        # This single command creates the new table with only the high-quality data.
        cursor.execute("""
            CREATE TABLE invariants_filtered AS 
            SELECT * FROM invariants WHERE "2AXR" = 1;
        """)
        conn.commit()
        print("'invariants_filtered' table created successfully.")

        print("Creating indexes on the new filtered table for performance...")
        cursor.execute("CREATE INDEX idx_filtered_chain_id ON invariants_filtered(chain_id);")
        cursor.execute("CREATE INDEX idx_filtered_chain_pos ON invariants_filtered(chain_id, position);")
        conn.commit()
        print("Indexes created.")
        
    end_time = time.time()
    print(f"\nTotal runtime: {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Error: Please provide the database path as a command-line argument.", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])

