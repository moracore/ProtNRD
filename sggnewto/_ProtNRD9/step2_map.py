import sqlite3
import time
import sys
import pandas as pd
import os

def main(db_path):
    start_time = time.time()
    print(f"--- Step 2: 3-mer Population Mapping ---")
    
    if not os.path.exists(db_path):
        sys.exit(f"Error: Database file '{db_path}' not found.")
    
    # Aggregates counts for every unique triplet (e.g. AAA, ALA, etc.)
    query = """
    SELECT 
        res_1, res_2, res_3,
        res_1 || res_2 || res_3 AS trimer,
        COUNT(*) AS population
    FROM "3mers"
    GROUP BY res_1, res_2, res_3
    ORDER BY population DESC;
    """

    with sqlite3.connect(db_path) as conn:
        print("Aggregating populations...")
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            sys.exit("Error: No data found in '3mers' table. Did Step 1 run correctly?")

        print(f"Found {len(df)} unique triplets. Saving to 'v9_3mer_map'...")
        df.to_sql('v9_3mer_map', conn, if_exists='replace', index=False)
        
    print(f"Step 2 Complete: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit("Usage: python3 step2_map.py <db_path>")
    main(sys.argv[1])