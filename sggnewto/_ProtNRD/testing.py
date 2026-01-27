import sqlite3
import time
import os

# --- CONFIGURATION ---
DB_RAW_PATH = '/users/sggnewto/fastscratch/proteins_v8.db'
OUTPUT_FILE = "benchmark_results.txt"

COL_X = "tau_NA" 
COL_Y = "tau_AC" 

ITERATIONS = 3

def get_db_connection(db_path):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    return conn

def run_test(cursor, sql):
    """Runs a single query and returns the execution time in seconds."""
    start = time.perf_counter()
    cursor.execute(sql)
    _ = cursor.fetchall() # Retrieve and discard
    end = time.perf_counter()
    return float(end - start)

def benchmark_scenario(name, conn, sql):
    times = []
    cursor = conn.cursor()

    print(f"  Running ({name})...")
    for _ in range(ITERATIONS):
        t = run_test(cursor, sql)
        times.append(t)
        
    return times

def main():
    print("Initializing Raw benchmarks only...")
    
    try:
        conn = get_db_connection(DB_RAW_PATH)
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to database. {e}")
        return

    # --- DEFINITIONS ---
    
    # 1. Full Rama
    s1_sql = f"SELECT {COL_X}, {COL_Y} FROM invariants_filtered"
    
    # 2. G -> P (Step 3)
    s2_sql = f"""
        SELECT t1.{COL_X}, t1.{COL_Y}
        FROM invariants_filtered t1
        JOIN invariants_filtered t2 
          ON t1.chain_id = t2.chain_id AND t1.position = t2.position - 3
        WHERE t1.residue = 'G' AND t2.residue = 'P'
    """

    # 3. Any -> P (Step 1)
    s3_sql = f"""
        SELECT t1.{COL_X}, t1.{COL_Y}
        FROM invariants_filtered t1
        JOIN invariants_filtered t2 
          ON t1.chain_id = t2.chain_id AND t1.position = t2.position - 1
        WHERE t2.residue = 'P'
    """
    
    # --- EXECUTION ---
    results = {}
    
    print("Starting Scenario 1 (Full Rama)...")
    results["Scenario 1"] = benchmark_scenario("S1", conn, s1_sql)
    
    print("Starting Scenario 2 (G->P Step 3)...")
    results["Scenario 2"] = benchmark_scenario("S2", conn, s2_sql)
    
    print("Starting Scenario 3 (Any->P Step 1)...")
    results["Scenario 3"] = benchmark_scenario("S3", conn, s3_sql)

    conn.close()

    # --- OUTPUT TO FILE ---
    print(f"Writing results to {OUTPUT_FILE}...")
    
    with open(OUTPUT_FILE, "w") as f:
        f.write("BENCHMARK RESULTS (Seconds) [RAW ONLY]\n")
        f.write("======================================\n")
        
        for name, times in results.items():
            f.write(f"\n[{name}]\n")
            for t in times:
                f.write(f"{t:.6f}\n")
                
    print("Done.")

if __name__ == "__main__":
    main()