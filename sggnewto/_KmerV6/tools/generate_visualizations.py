## Standalone Tool & Pipeline Data Generator
# This is the primary calculation engine for pipeline_02_cache.2.py.
# Generates 3D heatmap data, unified 1D/2D statistics, and
# 1D context-dependent histograms for a pair of invariants.
# Example (standalone):
# python tools/generate_visualizations.py /path/to/db.db --inv1 tau_NA --inv2 tau_AC --offset 1 --res1 A --res2 C --level level_1

import pandas as pd
import numpy as np
import argparse
import json
from tools.pipeline_utils import query_data_for_comparison, get_invariant_limits, get_resolution_bins
from tools.pipeline_constants import (
    ALL_INVARIANTS, RESIDUE_CONTEXTS, RESOLUTION_LEVELS,
    TORSION_INVARIANTS, INVARIANT_TYPES, RESOLUTION_BINS
)

def round_to_sig_figs(x, sig=4):
    """
    Rounds a number to a specified number of significant figures.
    Returns a float.
    """
    if x is None:
        return None
    # Handle non-finite numbers and zero
    if np.isnan(x) or np.isinf(x) or x == 0:
        return float(x)
    
    # Calculate the number of decimal places needed
    magnitude = np.floor(np.log10(np.abs(x)))
    # n is the number of decimal places
    n = sig - 1 - int(magnitude) 
    return round(x, n)

def _calculate_1d_histo(data_series, invariant_name):
    """Calculates 1D histogram for a pandas Series."""
    if data_series.empty or data_series.isnull().all():
        return None

    limits = get_invariant_limits()
    limit_def = limits.get(invariant_name, {'limit_min': -180, 'limit_max': 180})
    bin_min, bin_max = limit_def['limit_min'], limit_def['limit_max']

    counts, bin_edges = np.histogram(data_series, bins=360, range=(bin_min, bin_max))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    return {
        'bins': [round(b, 2) for b in bin_centers],
        'counts': [int(c) for c in counts]
    }

def _get_bin_width(invariant_name):
    """Helper to get the physical bin size for freq_at_mean calc."""
    try:
        inv_type = INVARIANT_TYPES[invariant_name]
        res_level_1 = RESOLUTION_LEVELS[0]
        bin_width = RESOLUTION_BINS[res_level_1][inv_type]
        return bin_width
    except KeyError:
        return 1.0

def _calculate_raw_stats(data_x, data_y, inv1, inv2, is_circular_x=False, is_circular_y=False):
    """
    Calculates all statistics derived from the raw (unbinned)
    data_x and data_y pandas Series.
    Uses circular statistics for mean, variance, and freq_at_mean
    if is_circular_x or is_circular_y is True.
    Rounds all float stats to 4 significant figures.
    """
    stats = {}
    stats['population'] = int(data_x.count())

    if stats['population'] == 0:
        return stats

    # --- X-Axis Statistics ---
    if is_circular_x:
        # Use circular statistics (angles in degrees)
        data_rad_x = np.deg2rad(data_x)
        x_comp_mean = np.mean(np.cos(data_rad_x))
        y_comp_mean = np.mean(np.sin(data_rad_x))
        
        mean_rad_x = np.arctan2(y_comp_mean, x_comp_mean)
        stats['mean_x'] = round_to_sig_figs(np.rad2deg(mean_rad_x))
        
        R_x = np.sqrt(x_comp_mean**2 + y_comp_mean**2)
        stats['variance_x'] = round_to_sig_figs(1 - R_x) # Circular variance, bounded 0-1
        
        # Linear stats are meaningless for circular data
        stats['median_x'] = None
        stats['min_x'] = None
        stats['max_x'] = None
    else:
        # Use linear statistics
        stats['mean_x'] = round_to_sig_figs(data_x.mean())
        stats['variance_x'] = round_to_sig_figs(data_x.var())
        stats['median_x'] = round_to_sig_figs(data_x.median())
        stats['min_x'] = round_to_sig_figs(data_x.min())
        stats['max_x'] = round_to_sig_figs(data_x.max())

    # --- Y-Axis Statistics ---
    if is_circular_y:
        # Use circular statistics (angles in degrees)
        data_rad_y = np.deg2rad(data_y)
        x_comp_mean_y = np.mean(np.cos(data_rad_y))
        y_comp_mean_y = np.mean(np.sin(data_rad_y))
        
        mean_rad_y = np.arctan2(y_comp_mean_y, x_comp_mean_y)
        stats['mean_y'] = round_to_sig_figs(np.rad2deg(mean_rad_y))
        
        R_y = np.sqrt(x_comp_mean_y**2 + y_comp_mean_y**2)
        stats['variance_y'] = round_to_sig_figs(1 - R_y) # Circular variance, bounded 0-1
        
        # Linear stats are meaningless for circular data
        stats['median_y'] = None
        stats['min_y'] = None
        stats['max_y'] = None
    else:
        # Use linear statistics
        stats['mean_y'] = round_to_sig_figs(data_y.mean())
        stats['variance_y'] = round_to_sig_figs(data_y.var())
        stats['median_y'] = round_to_sig_figs(data_y.median())
        stats['min_y'] = round_to_sig_figs(data_y.min())
        stats['max_y'] = round_to_sig_figs(data_y.max())

    # --- Joint Statistics ---
    if is_circular_x or is_circular_y:
        # Linear covariance is meaningless if either variable is circular
        stats['covariance'] = None
    else:
        stats['covariance'] = round_to_sig_figs(data_x.cov(data_y))

    # --- Frequency at Mean (X) ---
    bin_width_x = _get_bin_width(inv1)
    window_x = bin_width_x / 2.0
    
    if stats['mean_x'] is None:
         stats['freq_at_mean_x'] = 0
    else:
        mean_x_val = stats['mean_x']
        if is_circular_x:
            lower = mean_x_val - window_x
            upper = mean_x_val + window_x
            if lower < -180: # Wraps around -180
                freq_x = data_x[(data_x >= (lower + 360)) | (data_x < upper)].count()
            elif upper > 180: # Wraps around +180
                freq_x = data_x[(data_x >= lower) | (data_x < (upper - 360))].count()
            else: # No wrap
                freq_x = data_x[(data_x >= lower) & (data_x < upper)].count()
        else:
            freq_x = data_x[(data_x >= mean_x_val - window_x) & (data_x < mean_x_val + window_x)].count()
        stats['freq_at_mean_x'] = int(freq_x)

    # --- Frequency at Mean (Y) ---
    bin_width_y = _get_bin_width(inv2)
    window_y = bin_width_y / 2.0

    if stats['mean_y'] is None:
        stats['freq_at_mean_y'] = 0
    else:
        mean_y_val = stats['mean_y']
        if is_circular_y:
            lower = mean_y_val - window_y
            upper = mean_y_val + window_y
            if lower < -180: # Wraps around -180
                freq_y = data_y[(data_y >= (lower + 360)) | (data_y < upper)].count()
            elif upper > 180: # Wraps around +180
                freq_y = data_y[(data_y >= lower) | (data_y < (upper - 360))].count()
            else: # No wrap
                freq_y = data_y[(data_y >= lower) & (data_y < upper)].count()
        else:
            freq_y = data_y[(data_y >= mean_y_val - window_y) & (data_y < mean_y_val + window_y)].count()
        stats['freq_at_mean_y'] = int(freq_y)

    return stats


def generate_visualization_data(db_path, inv1, inv2, offset, res1, res2, res_level, TORSION_INVARIANTS_LIST):
    """
    Generates all data for a given invariant pair context:
    1. 3D Heatmap (as list of points)
    2. Unified 1D and 3D Stats (Raw + Binned)
    3. 1D Histograms (for Torsions)

    Returns:
    (heatmap_data_dict, stats_data_dict, histo_data_x, histo_data_y)
    """

    df = query_data_for_comparison(db_path, inv1, inv2, offset, res1, res2)

    heatmap_data = {'points': []}
    histo_data_x = None
    histo_data_y = None

    df.dropna(subset=['x', 'y'], inplace=True)
    data_x = df['x']
    data_y = df['y']

    # Check if invariants are circular (torsions)
    is_circ_x = inv1 in TORSION_INVARIANTS_LIST
    is_circ_y = inv2 in TORSION_INVARIANTS_LIST
    
    stats_data = _calculate_raw_stats(data_x, data_y, inv1, inv2, is_circ_x, is_circ_y)
    population = stats_data.get('population', 0)

    if population == 0:
        return heatmap_data, stats_data, histo_data_x, histo_data_y

    if inv1 in TORSION_INVARIANTS_LIST:
        histo_data_x = _calculate_1d_histo(data_x, inv1)
    if inv2 in TORSION_INVARIANTS_LIST:
        histo_data_y = _calculate_1d_histo(data_y, inv2)

    limits = get_invariant_limits()
    x_bins = get_resolution_bins(inv1, res_level)
    y_bins = get_resolution_bins(inv2, res_level)
    x_lim = (limits[inv1]['limit_min'], limits[inv1]['limit_max'])
    y_lim = (limits[inv2]['limit_min'], limits[inv2]['limit_max'])

    H, xedges, yedges = np.histogram2d(
        data_x,
        data_y,
        bins=[x_bins, y_bins],
        range=[x_lim, y_lim]
    )

    if H.size > 0:
        peak_freq_raw = H.max()
        peak_indices = np.unravel_index(H.argmax(), H.shape)
        peak_x_center = (xedges[peak_indices[0]] + xedges[peak_indices[0] + 1]) / 2
        peak_y_center = (yedges[peak_indices[1]] + yedges[peak_indices[1] + 1]) / 2
        # Apply significant figure rounding to peak stats
        stats_data['peak_x'] = round_to_sig_figs(peak_x_center)
        stats_data['peak_y'] = round_to_sig_figs(peak_y_center)
        stats_data['peak_freq'] = int(peak_freq_raw)
    else:
        stats_data['peak_x'] = None
        stats_data['peak_y'] = None
        stats_data['peak_freq'] = 0

    points_list = [] # Major storage saving method for sparser data
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            count = H[i, j]
            if count > 0:
                x_center = (xedges[i] + xedges[i+1]) / 2
                y_center = (yedges[j] + yedges[j+1]) / 2
                points_list.append((round(x_center, 2), round(y_center, 2), int(count)))

    heatmap_data = {'points': points_list}

    return heatmap_data, stats_data, histo_data_x, histo_data_y


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate 3D heatmap (points), 1D stats, and 1D histo data.")
    parser.add_argument("db_path", type=str, help="Path to the SQLite database file.")
    parser.add_argument("--inv1", type=str, required=True, choices=ALL_INVARIANTS, help="Invariant 1 (x-axis).")
    parser.add_argument("--inv2", type=str, required=True, choices=ALL_INVARIANTS, help="Invariant 2 (y-axis).")
    parser.add_argument("--offset", type=int, default=0, choices=range(5), help="Residue offset (0-4).")
    parser.add_argument("--res1", type=str, default="Any", choices=RESIDUE_CONTEXTS, help="Residue context for invariant 1.")
    parser.add_argument("--res2", type=str, default="Any", choices=RESIDUE_CONTEXTS, help="Residue context for invariant 2.")
    parser.add_argument("--level", type=str, default="level_1", choices=RESOLUTION_LEVELS, help="Resolution level for heatmap.")
    args = parser.parse_args()

    print(f"Generating data for {args.inv1} vs {args.inv2} (Offset +{args.offset}, {args.res1}-{args.res2}, {args.level} res)")

    heatmap, stats, histo_x, histo_y = generate_visualization_data(
        args.db_path, args.inv1, args.inv2, args.offset,
        args.res1, args.res2, args.level, TORSION_INVARIANTS
    )

    print("\n--- Unified Stats ---")
    print(json.dumps(stats, indent=4))

    if histo_x:
        print(f"\n--- Histo X ({args.inv1}) ---")
        if histo_x: print(f"Bins: {len(histo_x.get('bins', []))}, Total Count: {sum(histo_x.get('counts', []))}")

    if histo_y:
        print(f"\n--- Histo Y ({args.inv2}) ---")
        if histo_y: print(f"Bins: {len(histo_y.get('bins', []))}, Total Count: {sum(histo_s.get('counts', []))}")

    output_file = f"vizdata_{args.inv1}_vs_{args.inv2}+{args.offset}_{args.res1}_{args.res2}_{args.level}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "heatmap": heatmap,
            "statistics": stats,
            "histogram_x": histo_x,
            "histogram_y": histo_TORSION_INVARIANTS
        }, f, indent=4)

    print(f"\nFull data saved to {output_file}")