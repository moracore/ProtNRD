import sqlite3
import time
import sys
import pandas as pd

def main(db_path):
    start_time = time.time()
    print(f"--- ProtNRD v0.9: 3-mer Population Mapping ---")
    
    # Strictly frequentist: No stats, just counting occurrences
    query = """
    SELECT 
        res_1, res_2, res_3,
        res_1 || res_2 || res_3 AS trimer,
        COUNT(*) AS population
    FROM v9_triplets
    GROUP BY res_1, res_2, res_3
    ORDER BY population DESC;
    """

    with sqlite3.connect(db_path) as conn:
        print("Executing aggregation on 10.8M rows...")
        df = pd.read_sql_query(query, conn)
        
        print("Storing results in 'v9_3mer_map' table...")
        df.to_sql('v9_3mer_map', conn, if_exists='replace', index=False)
        
        output_csv = "v9_3mer_frequencies.csv"
        df.to_csv(output_csv, index=False)

    runtime = time.time() - start_time
    print(f"\nSuccess: Identified {len(df)} unique 3-mer combinations.")
    print(f"Total Observations: {df['population'].sum():,}")
    print(f"Results saved to table 'v9_3mer_map' and file '{output_csv}'.")
    print(f"Total runtime: {runtime:.2f} seconds.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python v9_frequency_map.py <db_path>")
    main(sys.argv[1])