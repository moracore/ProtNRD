import sqlite3
import time
import sys
import os

def main(db_path):
    start_time = time.time()
    print("--- Step 1: Creating '3mers' Table (Target: invariants_filtered) ---")
    
    if not os.path.exists(db_path):
        sys.exit(f"Error: Database file '{db_path}' not found.")

    # Explicitly use the v9 table name
    src_table = "invariants_filtered"

    # Columns present in v9
    torsions = [('tau_NA', 'tau_NA'), ('tau_AC', 'tau_AC'), ('tau_CN', 'tau_CN')]
    lengths  = [('length_NA', 'length_NA'), ('length_AC', 'length_AC'), ('length_CN', 'length_CN')]
    angles   = [('angle_N', 'angle_N'), ('angle_A', 'angle_A'), ('angle_C', 'angle_C')]
    
    all_metrics = torsions + lengths + angles
    cols = ["t1.chain_id"]
    
    for i in range(1, 4):
        t_name = f"t{i}"
        cols.append(f"{t_name}.residue AS res_{i}")
        for db_col, alias in all_metrics:
            cols.append(f"{t_name}.{db_col} AS {alias}_{i}")

    select_clause = ", ".join(cols)

    # v9 has 'position' column
    create_sql = f"""
    CREATE TABLE '3mers' AS
    SELECT {select_clause}
    FROM {src_table} t1
    JOIN {src_table} t2 ON t1.chain_id = t2.chain_id AND t1.position + 1 = t2.position
    JOIN {src_table} t3 ON t2.chain_id = t3.chain_id AND t2.position + 1 = t3.position;
    """

    with sqlite3.connect(db_path, timeout=3600) as conn:
        conn.execute("PRAGMA journal_mode = WAL;") 
        conn.execute("PRAGMA synchronous = NORMAL;")
        
        print(f"Dropping old '3mers' table...")
        conn.execute("DROP TABLE IF EXISTS '3mers';")
        
        print(f"Executing Sliding Window Join on '{src_table}'...")
        try:
            conn.execute(create_sql)
        except sqlite3.OperationalError as e:
            print(f"\nCRITICAL ERROR: {e}")
            print(f"Ensure table '{src_table}' exists in {db_path}")
            sys.exit(1)
            
        print("Indexing '3mers'...")
        conn.execute("CREATE INDEX idx_3mers_res_triplet ON '3mers'(res_1, res_2, res_3);")
        
    print(f"Step 1 Complete: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit("Usage: python3 step1_triplets.py <db_path>")
    main(sys.argv[1])