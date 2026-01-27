## Pipeline Utility Functions

import sqlite3
import pandas as pd
import numpy as np

from tools.pipeline_constants import INVARIANT_LIMITS, INVARIANT_TYPES, RESOLUTION_BINS

def get_db_connection(db_path, read_only=True, timeout=120):
    """Establishes a connection to the SQLite database."""

    if read_only:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=timeout)
    else:
        return sqlite3.connect(db_path, timeout=timeout)

def get_invariant_limits():
    """Returns the hard-coded invariant limits from the constants file."""
    return INVARIANT_LIMITS

def get_source_table(offset):
    """Returns the correct source table name for a given offset."""
    if offset == 0:
        return 'invariants_filtered' ##### Future: have this be in argument
    elif offset == 1:
        return 'v8_offset_1' # v0.8
    elif offset == 2:
        return 'v8_offset_2' # v0.8
    elif offset == 3:
        return 'v8_offset_3' # v0.8
    elif offset == 4:
        return 'v8_offset_4' # v0.8
    else:
        raise ValueError(f"Invalid offset: {offset}")

def build_where_clause(inv1, inv2, offset, res1, res2, pos):
    """
    Builds the SQL WHERE clause and parameters for a query.
    v0.8: Handles 'pos' and 'Any' context.
    """
    params = []
    where_clauses = []

    if offset == 0:
        # Offset 0: pos is always 0. Filter on residue.
        col1 = f"{inv1}"
        col2 = f"{inv2}"
        res1_col = "residue"
        
        where_clauses.append(f"{col1} IS NOT NULL")
        where_clauses.append(f"{col2} IS NOT NULL")
        
        # v0.8: Handle "Any" context
        if res1 != 'Any':
            where_clauses.append(f"{res1_col} = ?")
            params.append(res1)
        
        res2_col = None # No second residue at offset 0
        
    else:
        # Offset > 0: Filter on residue_1 AND residue_{offset+1}.
        res1_col = "residue_1"
        res2_col = f"residue_{offset+1}"
        
        # v0.8: Handle "Any" context
        if res1 != 'Any':
            where_clauses.append(f"{res1_col} = ?")
            params.append(res1)
        if res2 != 'Any':
            where_clauses.append(f"{res2_col} = ?")
            params.append(res2)

        if pos == 0:
            # Focus on position 0 (i)
            col1 = f"{inv1}_1"
            col2 = f"{inv2}_1"
        elif pos == 1:
            # Focus on position 1 (i+n)
            col1 = f"{inv1}_{offset+1}"
            col2 = f"{inv2}_{offset+1}"
        else:
            raise ValueError(f"Invalid position '{pos}' for offset > 0")
            
        where_clauses.append(f"{col1} IS NOT NULL")
        where_clauses.append(f"{col2} IS NOT NULL")

    # Only add WHERE if there are clauses
    where_sql = ""
    if where_clauses:
        where_sql = f"WHERE { ' AND '.join(where_clauses) }"

    return where_sql, params, col1, col2

def query_data_for_comparison(db_path, inv1, inv2, offset, res1, res2, pos):
    """
    A generic, high-performance function to query the raw (x, y) data 
    for any given comparison, regardless of type.
    v0.8: Added 'pos' argument.
    """
    table_name = get_source_table(offset)
    # Note: 'pos' is new
    where_sql, params, col1, col2 = build_where_clause(inv1, inv2, offset, res1, res2, pos)
    
    sql_query = f"SELECT {col1} AS x, {col2} AS y FROM {table_name} {where_sql};"
    
    with get_db_connection(db_path, read_only=True) as conn:
        df = pd.read_sql_query(sql_query, conn, params=params)
    return df

def get_resolution_bins(invariant_name, resolution_level):
    """
    Calculates the *number* of bins for a given invariant and resolution level,
    based on the invariant's range and the physical bin size defined in constants.
    """
    inv_type = INVARIANT_TYPES.get(invariant_name)
    if not inv_type:
        raise ValueError(f"Unknown invariant type for: {invariant_name}")

    bin_size = RESOLUTION_BINS.get(resolution_level, {}).get(inv_type)
    if not bin_size:
        raise ValueError(f"No bin size defined for level '{resolution_level}' and type '{inv_type}'")
        
    limits = INVARIANT_LIMITS.get(invariant_name)
    if not limits:
        raise ValueError(f"No limits defined for invariant: {invariant_name}")

    limit_min = limits['limit_min']
    limit_max = limits['limit_max']
    data_range = limit_max - limit_min
    
    num_bins = int(np.ceil(data_range / bin_size))
    
    return num_bins