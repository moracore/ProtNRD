import sqlite3
import time
import sys
# Import the missing constants
from tools.pipeline_constants import TORSION_INVARIANTS, LENGTH_INVARIANTS, ANGLE_INVARIANTS

def main(db_path):
    start_time = time.time()
    print("--- ProtNRD v0.9: Creating Unified 3-mer (Triplets) Table ---")

    # Define all geometric invariants to pull
    torsions = TORSION_INVARIANTS 
    lengths = LENGTH_INVARIANTS
    angles = ANGLE_INVARIANTS
    
    cols = ["t1.chain_id", "t1.position AS pos_1"]
    
    # Loop through positions 1, 2, and 3
    for i in range(1, 4):
        t_name = f"t{i}"
        cols.append(f"{t_name}.residue AS res_{i}")
        
        # Add Torsions (phi, psi, omega)
        for tor in torsions:
            cols.append(f"{t_name}.{tor} AS {tor}_{i}")
            
        # Add Lengths (N-CA, CA-C, C-N)
        for l in lengths:
            cols.append(f"{t_name}.{l} AS {l}_{i}")
            
        # Add Bond Angles (N-CA-C, etc.)
        for a in angles:
            cols.append(f"{t_name}.{a} AS {a}_{i}")

    select_clause = ", ".join(cols)

    # Note: Table renamed to '3mers' to match your cache script's expectation
    create_sql = f"""
    CREATE TABLE '3mers' AS
    SELECT {select_clause}
    FROM invariants_filtered t1
    JOIN invariants_filtered t2 ON t1.chain_id = t2.chain_id AND t1.position + 1 = t2.position
    JOIN invariants_filtered t3 ON t2.chain_id = t3.chain_id AND t2.position + 1 = t3.position;
    """

    with sqlite3.connect(db_path, timeout=3600) as conn:
        print("Dropping old '3mers' if exists...")
        conn.execute("DROP TABLE IF EXISTS '3mers';")
        
        print("Populating '3mers' with Torsions, Lengths, and Angles...")
        conn.execute(create_sql)
        
        print("Creating index on residue triplet for frequency analysis...")
        conn.execute("CREATE INDEX idx_3mers_res_triplet ON '3mers'(res_1, res_2, res_3);")
        
        conn.commit()

    print(f"--- Complete in {time.time() - start_time:.2f} seconds ---")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python pipeline_v9_triplets.py <db_path>")
    main(sys.argv[1])