import numpy as np

# Grid cache: (plot_key[, inv1], db_choice) -> {'x': ndarray, 'y': ndarray, 'z': 2D ndarray}
_cache = {}

# Figure cache: make_fig_key(...) -> go.Figure
# Keyed by grid key + rendering params so toggling log/smooth/colormap/lims hits cache
# instead of rerunning create_3D_figure. Evicted whenever the underlying grid is rebuilt.
_fig_cache = {}


def make_fig_key(grid_key, log_scale, smooth, colormap, x_lims, y_lims):
    """Build a hashable figure-cache key from grid identity + rendering params."""
    xl = tuple(x_lims) if x_lims else (None, None)
    yl = tuple(y_lims) if y_lims else (None, None)
    return grid_key + (bool(log_scale), bool(smooth), colormap or '', xl, yl)


def get_fig(key):
    return _fig_cache.get(key)


def put_fig(key, fig):
    _fig_cache[key] = fig


def _complete_axis(vals, inv_name):
    u = np.unique(vals)
    if u.size <= 1:
        return u.astype(float), np.zeros(vals.shape, dtype=int), np.ones(vals.shape, dtype=bool)
    step = np.min(np.diff(u))
    vmin = u.min()
    if inv_name in ('tau_NA', 'tau_AC', 'tau_CN'):
        n = int(round(360.0 / step))
        centers = vmin + step * np.arange(n)
        idx = np.rint((vals - vmin) / step).astype(int) % n
        valid = np.ones(vals.shape, dtype=bool)
    else:
        n = int(round((u.max() - vmin) / step)) + 1
        centers = vmin + step * np.arange(n)
        idx = np.rint((vals - vmin) / step).astype(int)
        valid = (idx >= 0) & (idx < n)
    return centers, idx, valid


def build_grid(points, inv1_name, inv2_name):
    """Convert a raw [[x, y, count], ...] points list into a pre-built grid dict."""
    if not points:
        return None
    xs, ys, zs = zip(*points)
    xs = np.array(xs, float)
    ys = np.array(ys, float)
    zs = np.array(zs, float)
    x_c, x_idx, x_ok = _complete_axis(xs, inv1_name)
    y_c, y_idx, y_ok = _complete_axis(ys, inv2_name)
    ok = x_ok & y_ok
    z_grid = np.zeros((len(y_c), len(x_c)), float)
    np.add.at(z_grid, (y_idx[ok], x_idx[ok]), zs[ok])
    return {'x': x_c, 'y': y_c, 'z': z_grid}


def get(key):
    return _cache.get(key)


def build_and_put(key, points, inv1_name, inv2_name):
    """Build the grid from points, store it under key, and return it."""
    grid = build_grid(points, inv1_name, inv2_name)
    if grid is not None:
        _cache[key] = grid
        # Evict all cached figures that were built from this grid so stale renders
        # are never served after a new query for the same plot_key+db arrives.
        stale = [k for k in _fig_cache if k[:len(key)] == key]
        for k in stale:
            del _fig_cache[k]
    return grid
