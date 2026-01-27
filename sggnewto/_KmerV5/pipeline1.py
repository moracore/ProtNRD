"""
Pipeline Step 1: Joined Table Generation (v5.1 - Optimized)

This script is the first stage of the v5 backend pipeline. Its purpose is to
create the pre-joined database tables required for efficient sliding-window
pairwise analysis.

This optimized version replaces the inefficient per-chain loop with a single,
fast, set-based INSERT-SELECT operation for each required table.

It reads from the 'invariants_filtered' table and generates:
- v5_pairwise: Contains data for residues at (i) and (i+1)
- v5_triplets: Contains data for residues at (i) and (i+2)
- v5_quads:    Contains data for residues at (i) and (i+3)
- v5_quints:   Contains data for residues at (i) and (i+4)
"""
import sqlite3
import time
import sys
import pandas as pd

def check_table_populated(conn, table_name):
    """Checks if a table exists and has at least one row."""
    try:
        query = f"SELECT 1 FROM {table_name} LIMIT 1;"
        result = pd.read_sql_query(query, conn)
        return not result.empty
    except pd.io.sql.DatabaseError:
        return False # Table doesn't exist

def main(db_path):
    """Main function to create all joined tables needed for pairwise analysis."""
    start_time = time.time()
    print("--- Pipeline Step 1 (Optimized): Creating Joined Tables ---")

    invariants = ["residue", "length_N", "length_A", "length_C", "angle_N", "angle_A", "angle_C", "tau_NA", "tau_AC", "tau_CN"]

    with sqlite3.connect(db_path, timeout=3600) as conn:
        for offset in range(1, 5):
            table_name = {1: 'v5_pairwise', 2: 'v5_triplets', 3: 'v5_quads', 4: 'v5_quints'}[offset]
            
            if check_table_populated(conn, table_name):
                print(f"Table '{table_name}' already exists and is populated. Skipping.")
                continue

            print(f"\nCreating and populating '{table_name}' for offset +{offset}...")
            
            # --- Schema Definition ---
            cols_t1 = ", ".join([f"{inv}_1 {'TEXT' if inv == 'residue' else 'REAL'}" for inv in invariants])
            cols_t_offset = ", ".join([f"{inv}_{offset+1} {'TEXT' if inv == 'residue' else 'REAL'}" for inv in invariants])
            create_sql = f"CREATE TABLE {table_name} (chain_id TEXT, position INTEGER, {cols_t1}, {cols_t_offset});"

            # --- Optimized Bulk Insert-Select Statement ---
            select_cols_t1 = ", ".join([f"t1.{inv}" for inv in invariants])
            select_cols_t_offset = ", ".join([f"t_offset.{inv}" for inv in invariants])
            aliases_t1 = ", ".join([f"t1.{inv} AS {inv}_1" for inv in invariants])
            aliases_t_offset = ", ".join([f"t_offset.{inv} AS {inv}_{offset+1}" for inv in invariants])
            
            insert_sql = f"""
            INSERT INTO {table_name}
            SELECT
                t1.chain_id,
                t1.position,
                {select_cols_t1},
                {select_cols_t_offset}
            FROM
                invariants_filtered AS t1
            JOIN
                invariants_filtered AS t_offset
            ON
                t1.chain_id = t_offset.chain_id AND t1.position + {offset} = t_offset.position;
            """

            conn.execute(f"DROP TABLE IF EXISTS {table_name};")
            conn.execute(create_sql)
            print(f"Table '{table_name}' created. Populating now (this may take a moment)...")
            
            conn.execute(insert_sql)
            print(f"Data inserted. Creating index...")
            conn.execute(f"CREATE INDEX idx_{table_name}_chain_pos ON {table_name}(chain_id, position);")
            conn.commit()
            print(f"'{table_name}' is complete.")

    end_time = time.time()
    print(f"\n--- Pipeline Step 1 Complete ---")
    print(f"Total script runtime: {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Error: Please provide the database path as a command-line argument.")
    main(sys.argv[1])
