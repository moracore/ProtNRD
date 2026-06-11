import sqlite3
import sys
import time
import pandas as pd


def main(db_path):
    """Aggregates triplet populations into 'v9_3mer_map'.

    Reads the flat '3mers' table built by 1_3M_flat.py and writes
    v9_3mer_map(res_1, res_2, res_3, trimer, population) -- the exact schema the
    Trimer app queries (`SELECT population FROM v9_3mer_map WHERE trimer = ?`).
    """
    start = time.time()
    print("--- ProtNRD v0.9: 3-mer Population Mapping ---")

    query = """
    SELECT
        res_1, res_2, res_3,
        res_1 || res_2 || res_3 AS trimer,
        COUNT(*) AS population
    FROM '3mers'
    GROUP BY res_1, res_2, res_3
    ORDER BY population DESC;
    """

    with sqlite3.connect(db_path, timeout=3600) as conn:
        print("Aggregating triplet populations from '3mers'...")
        df = pd.read_sql_query(query, conn)
        if df.empty:
            sys.exit("Error: '3mers' is empty. Did 1_3M_flat.py run?")
        df.to_sql('v9_3mer_map', conn, if_exists='replace', index=False)
        df.to_csv("v9_3mer_frequencies.csv", index=False)

    print(f"Success: {len(df)} unique 3-mers, {df['population'].sum():,} observations.")
    print(f"Saved table 'v9_3mer_map' (+ CSV). Runtime: {time.time() - start:.2f}s")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 2_3M_freq.py <db_path>")
    main(sys.argv[1])
