import json
import numpy as np
import pandas as pd


def generate_sparse_heatmap(data_df, x_col, y_col):
    """Sparse points-system JSON for a torsion-torsion 3D heatmap.

    INTEGER-angle binning: each angle is rounded to the nearest whole degree and
    folded (+180 -> -180) so the bin centres are the integers in [-180, 179] with
    no duplicated seam at +/-180. Output: {'points': [[x, y, count], ...]}.

    This replaces the old `bins=64` histogram2d (5.625-degree bins -> ugly
    177.1875-style centres) and the earlier truncating `astype(int)`.
    """
    if data_df.empty:
        return json.dumps({'points': []})

    sub = data_df[[x_col, y_col]].dropna()
    if sub.empty:
        return json.dumps({'points': []})

    def _wrap_int(series):
        v = np.round(series.to_numpy(dtype=float))
        return (((v + 180.0) % 360.0) - 180.0).astype(int)

    binned = pd.DataFrame({'x': _wrap_int(sub[x_col]), 'y': _wrap_int(sub[y_col])})
    grouped = binned.groupby(['x', 'y']).size().reset_index(name='z')

    # Native python ints/list for clean JSON.
    points = [[int(x), int(y), int(z)] for x, y, z in grouped.itertuples(index=False)]
    return json.dumps({'points': points})
