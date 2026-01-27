"""
Pipeline Step 1: Joined Table Generation (v6)

This script is the first stage of the v6 backend pipeline. It creates the
storage-efficient, non-redundant pre-joined database tables required for
efficient sliding-window pairwise analysis.

It reads from 'invariants_filtered' (the high-quality X-ray data) and generates:
- v6_offset_1: (i, i+1)
- v6_offset_2: (i, i+2)
- v6_offset_3: (i, i+3)
- v6_offset_4: (i, i+4)
"""
import sqlite3
import time
import sys
import pandas as pd
# Import from the new constants file
from tools.pipeline_constants import ALL_INVARIANTS

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
    print("--- Pipeline Step 1 (v6): Creating Non-Redundant Joined Tables ---")

    # Use the central constant list, but add 'residue' which is
    # needed for schema creation and filtering, but isn't an 'invariant'
    invariants = ['residue'] + ALL_INVARIANTS
    
    # Column lists for SELECT statements
    select_cols_t1 = ", ".join([f"t1.{inv} AS {inv}_1" for inv in invariants])
    
    # Schema definitions for CREATE TABLE
    schema_t1 = ", ".join([f"{inv}_1 {'TEXT' if inv == 'residue' else 'REAL'}" for inv in invariants])

    # Use a non-read-only connection for writing
    # Increased timeout for potentially long-running join operations
    with sqlite3.connect(db_path, timeout=3600) as conn:
        
        # Loop from offset +1 to +4
        for offset in range(1, 5):
            # Naming change: v6_pairwise -> v6_offset_1
            table_name = f'v6_offset_{offset}'
            
            select_cols_t_offset = ", ".join([f"t_offset.{inv} AS {inv}_{offset+1}" for inv in invariants])
            schema_t_offset = ", ".join([f"{inv}_{offset+1} {'TEXT' if inv == 'residue' else 'REAL'}" for inv in invariants])

            if check_table_populated(conn, table_name):
                print(f"Table '{table_name}' already exists and is populated. Skipping.")
                continue

            print(f"\nCreating and populating '{table_name}' for offset +{offset}...")
            
            create_sql = f"CREATE TABLE {table_name} (chain_id TEXT, position_1 INTEGER, {schema_t1}, {schema_t_offset});"
            
            insert_sql = f"""
                INSERT INTO {table_name}
                SELECT
                    t1.chain_id,
                    t1.position AS position_1,
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
            print(f"Table '{table_name}' created. Populating now (this may take a while)...")
            
            conn.execute(insert_sql)
            print(f"Data inserted. Creating indexes...")
            
            # Standard index for chain/position lookups
            conn.execute(f"CREATE INDEX idx_{table_name}_chain_pos ON {table_name}(chain_id, position_1);")
            
            # --- CRITICAL EFFICIENCY ADDITION ---
            # Add index for residue filtering, which pipeline_02 relies on
            res_col_offset = f"residue_{offset+1}"
            print(f"Creating residue filter index on (residue_1, {res_col_offset})...")
            conn.execute(f"CREATE INDEX idx_{table_name}_residues ON {table_name}(residue_1, {res_col_offset});")
            # --- END ---
            
            conn.commit()
            print(f"'{table_name}' is complete.")

    end_time = time.time()
    print(f"\n--- Pipeline Step 1 Complete ---")
    print(f"Total script runtime: {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Error: Please provide the database path as a command-line argument.")
    main(sys.argv[1])