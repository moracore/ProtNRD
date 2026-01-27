import pandas as pd
import json

def generate_sparse_heatmap(data_df, x_col, y_col):
    """
    Generates the v0.8/v0.9 style points-system JSON for 3D heatmaps.
    Aggregates coordinates into 1.0 degree integer bins.
    """
    if data_df.empty:
        return json.dumps({'points': []})

    # Group by integer degrees (1.0 degree bins)
    # We cast to int to truncate decimals, effectively binning the data
    binned = data_df.groupby([
        data_df[x_col].astype(int), 
        data_df[y_col].astype(int)
    ]).size().reset_index(name='z')
    
    # Rename for consistency in the frontend
    binned.columns = ['x', 'y', 'z']
    
    # Convert to sparse list format [[x, y, z], ...] for storage efficiency
    # This format is significantly smaller than a dense 360x360 matrix
    return json.dumps({'points': binned.values.tolist()})