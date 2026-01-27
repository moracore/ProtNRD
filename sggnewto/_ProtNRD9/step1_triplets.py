import sqlite3
import time
import sys
import os

def main(db_path):
    start_time = time.time()
    print("--- Step 1: Creating '3mers' Table ---")
    
    if not os.path.exists(db_path):
        sys.exit(f"Error: Database file '{db_path}' not found.")

    # Mapping: DB_Column -> Output_Alias
    torsions = [('tau_NA', 'tau_NA'), ('tau_AC', 'tau_AC'), ('tau_CN', 'tau_CN')]
    lengths  = [('length_N', 'length_NA'), ('length_A', 'length_AC'), ('length_C', 'length_CN')]
    angles   = [('angle_N', 'angle_N'), ('angle_A', 'angle_A'), ('angle_C', 'angle_C')]
    
    all_metrics = torsions + lengths + angles
    cols = ["t1.chain_id"]
    
    # Loop through positions 1, 2, and 3
    for i in range(1, 4):
        t_name = f"t{i}"
        cols.append(f"{t_name}.residue AS res_{i}")
        for db_col, alias in all_metrics:
            cols.append(f"{t_name}.{db_col} AS {alias}_{i}")

    select_clause = ", ".join(cols)

    # LOGIC: Join t1->t2->t3 using ROWID + 1 to find neighbors
    create_sql = f"""
    CREATE TABLE '3mers' AS
    SELECT {select_clause}
    FROM invariants t1
    JOIN invariants t2 ON t1.chain_id = t2.chain_id AND t1.rowid + 1 = t2.rowid
    JOIN invariants t3 ON t2.chain_id = t3.chain_id AND t2.rowid + 1 = t3.rowid;
    """

    with sqlite3.connect(db_path, timeout=3600) as conn:
        # Performance tuning for large inserts
        conn.execute("PRAGMA journal_mode = WAL;") 
        conn.execute("PRAGMA synchronous = NORMAL;")
        
        print("Dropping old '3mers' table...")
        conn.execute("DROP TABLE IF EXISTS '3mers';")
        
        print("Executing Sliding Window Join...")
        conn.execute(create_sql)
        
        print("Indexing '3mers' for fast lookups...")
        conn.execute("CREATE INDEX idx_3mers_res_triplet ON '3mers'(res_1, res_2, res_3);")
        
    print(f"Step 1 Complete: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit("Usage: python3 step1_triplets.py <db_path>")
    main(sys.argv[1])