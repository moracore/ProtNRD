"""
Pipeline Utility Functions (v6)

This file contains shared helper functions used by all other
pipeline scripts to ensure consistency and avoid code duplication.
It is not intended to be run directly.
"""
import sqlite3
import pandas as pd
import numpy as np
# Import from the new constants file
from tools.pipeline_constants import INVARIANT_LIMITS, INVARIANT_TYPES, RESOLUTION_BINS

def get_db_connection(db_path, read_only=True, timeout=120):
    """Establishes a connection to the SQLite database."""
    # Use read-only mode for all worker-based data querying
    if read_only:
        # Connect using URI for read-only mode
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=timeout)
    else:
        return sqlite3.connect(db_path, timeout=timeout)

def get_invariant_limits():
    """
    Returns the hard-coded invariant limits from the constants file.
    (This replaces the database-driven v5_invariant_limits table).
    """
    return INVARIANT_LIMITS

def get_source_table(offset):
    """Returns the correct source table name for a given offset."""
    if offset == 0:
        return 'invariants_filtered'
    elif offset == 1:
        return 'v6_offset_1' # Corrected from v6_pairwise
    elif offset == 2:
        return 'v6_offset_2'
    elif offset == 3:
        return 'v6_offset_3'
    elif offset == 4:
        return 'v6_offset_4'
    else:
        raise ValueError(f"Invalid offset: {offset}")

def build_where_clause(inv1, inv2, offset, res1, res2):
    """Builds the SQL WHERE clause and parameters for a query."""
    params = []
    where_clauses = []

    # Get column names
    col1 = f"{inv1}" if offset == 0 else f"{inv1}_1"
    col2 = f"{inv2}" if offset == 0 else f"{inv2}_{offset+1}"
    where_clauses.append(f"{col1} IS NOT NULL")
    where_clauses.append(f"{col2} IS NOT NULL")
    
    # Get residue column names
    res1_col = "residue" if offset == 0 else "residue_1"
    res2_col = "residue" if offset == 0 else f"residue_{offset+1}"
    
    if res1 != 'Any':
        where_clauses.append(f"{res1_col} = ?")
        params.append(res1)
    if res2 != 'Any':
        where_clauses.append(f"{res2_col} = ?")
        params.append(res2)
        
    return f"WHERE { ' AND '.join(where_clauses) }", params, col1, col2

def query_data_for_comparison(db_path, inv1, inv2, offset, res1, res2):
    """
    A generic, high-performance function to query the raw (x, y) data 
    for any given comparison, regardless of type.
    """
    table_name = get_source_table(offset)
    where_sql, params, col1, col2 = build_where_clause(inv1, inv2, offset, res1, res2)
    
    sql_query = f"SELECT {col1} AS x, {col2} AS y FROM {table_name} {where_sql};"
    
    # All queries from workers should be read-only
    with get_db_connection(db_path, read_only=True) as conn:
        df = pd.read_sql_query(sql_query, conn, params=params)
    return df

def get_resolution_bins(invariant_name, resolution_level):
    """
    Calculates the *number* of bins for a given invariant and resolution level,
    based on the invariant's range and the physical bin size defined in constants.
    """
    # 1. Get invariant type (e.g., 'torsion', 'length')
    inv_type = INVARIANT_TYPES.get(invariant_name)
    if not inv_type:
        raise ValueError(f"Unknown invariant type for: {invariant_name}")

    # 2. Get physical bin size (e.g., 1.0 degrees)
    bin_size = RESOLUTION_BINS.get(resolution_level, {}).get(inv_type)
    if not bin_size:
        raise ValueError(f"No bin size defined for level '{resolution_level}' and type '{inv_type}'")
        
    # 3. Get invariant limits (e.g., -180 to 180)
    limits = INVARIANT_LIMITS.get(invariant_name)
    if not limits:
        raise ValueError(f"No limits defined for invariant: {invariant_name}")

    # 4. Calculate number of bins
    limit_min = limits['limit_min']
    limit_max = limits['limit_max']
    data_range = limit_max - limit_min
    
    # Use ceil to ensure the full range is covered
    num_bins = int(np.ceil(data_range / bin_size))
    
    return num_bins