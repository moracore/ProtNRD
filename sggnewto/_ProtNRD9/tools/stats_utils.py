import numpy as np

def calculate_2d_torsion_stats(phi_deg, psi_deg):
    """
    Calculates Joint 2D Mean, Correlation, R2D, Mode, and specific Densities.
    Returns 8 metrics.
    """
    N = len(phi_deg)
    if N == 0: return [None]*8
    
    phi_rad, psi_rad = np.deg2rad(phi_deg), np.deg2rad(psi_deg)
    
    # 1. 2D Joint Circular Mean
    mean_phi = np.degrees(np.arctan2(np.sum(np.sin(phi_rad)), np.sum(np.cos(phi_rad))))
    mean_psi = np.degrees(np.arctan2(np.sum(np.sin(psi_rad)), np.sum(np.cos(psi_rad))))
    
    # 2. Joint Resultant Length (R2D)
    # Average of the resultant lengths of the individual components
    r_phi = np.sqrt(np.sum(np.cos(phi_rad))**2 + np.sum(np.sin(phi_rad))**2) / N
    r_psi = np.sqrt(np.sum(np.cos(psi_rad))**2 + np.sum(np.sin(psi_rad))**2) / N
    R2D = (r_phi + r_psi) / 2
    
    # 3. Circular Correlation (Fisher and Lee)
    sin_phi_diff = np.sin(phi_rad - np.deg2rad(mean_phi))
    sin_psi_diff = np.sin(psi_rad - np.deg2rad(mean_psi))
    corr = np.sum(sin_phi_diff * sin_psi_diff) / np.sqrt(np.sum(sin_phi_diff**2) * np.sum(sin_psi_diff**2))

    # 4. Mode and Frequencies via 2D Histogram (1-degree bins)
    hist, xedges, yedges = np.histogram2d(phi_deg, psi_deg, bins=[np.arange(-180, 182), np.arange(-180, 182)])
    
    peak_idx = np.unravel_index(np.argmax(hist), hist.shape)
    peak_phi, peak_psi = xedges[peak_idx[0]], yedges[peak_idx[1]]
    peak_freq = int(np.max(hist))
    
    # Frequency at calculated 2D Mean (integer bin lookup)
    try:
        mean_f = int(hist[int(mean_phi) + 180, int(mean_psi) + 180])
    except IndexError:
        mean_f = 0

    return mean_phi, mean_psi, corr, R2D, peak_phi, peak_psi, peak_freq, mean_f

def calculate_circular_stats(angles_deg):
    """Circular Stats: Returns 7 metrics."""
    N = len(angles_deg)
    if N == 0: return [None, None, None, None, 0, 0, 0]
    
    rads = np.deg2rad(angles_deg)
    sin_sum, cos_sum = np.sum(np.sin(rads)), np.sum(np.cos(rads))
    
    mean_deg = np.degrees(np.arctan2(sin_sum, cos_sum))
    R = np.sqrt(sin_sum**2 + cos_sum**2) / N
    circ_std = np.degrees(np.sqrt(-2 * np.log(R))) if R > 1e-9 else 180.0
    
    counts = np.bincount((angles_deg.astype(int) + 180), minlength=361)
    peak_angle = np.argmax(counts) - 180
    peak_freq = int(np.max(counts))
    
    mean_f_bin = int(counts[int(mean_deg) + 180])
    
    l, u = mean_deg - 5, mean_deg + 5
    if l < -180:
        at_mean_win = np.sum((angles_deg >= l + 360) | (angles_deg <= u))
    elif u > 180:
        at_mean_win = np.sum((angles_deg >= l) | (angles_deg <= u - 360))
    else:
        at_mean_win = np.sum((angles_deg >= l) & (angles_deg <= u))

    return mean_deg, R, circ_std, peak_angle, peak_freq, mean_f_bin, int(at_mean_win)

def calculate_linear_stats(values, window=0.02):
    """Linear Stats: Returns 8 metrics."""
    N = len(values)
    if N == 0: return [None, None, None, None, None, 0, 0, 0]
    
    mean_val = np.mean(values)
    std_val = np.std(values)
    
    counts = {}
    for v in values:
        rounded = round(v, 2)
        counts[rounded] = counts.get(rounded, 0) + 1
    
    peak_val = max(counts, key=counts.get)
    peak_freq = counts[peak_val]
    mean_f_bin = counts.get(round(mean_val, 2), 0)
    at_mean_win = np.sum((values >= mean_val - window) & (values <= mean_val + window))
    
    return mean_val, std_val, np.min(values), np.max(values), peak_val, peak_freq, int(mean_f_bin), int(at_mean_win)