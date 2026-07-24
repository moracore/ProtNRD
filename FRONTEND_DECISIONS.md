# ProtNRD Front-End: Design Decisions

This document explains every non-obvious design choice made in the Dash front end. It covers both decisions recorded in inline comments and architectural choices made during the performance/stability refactor (2026-07-21).

---

## 1. Server-Side Caching (`figure_cache.py`)

Both v8 (Pairwise) and v9 (Trimer) run in a single Python process under Werkzeug `DispatcherMiddleware`. The shared module `figure_cache.py` exploits this to keep two in-process caches that survive for the lifetime of the server.

### 1.1 Grid cache (`_cache`)

**What it stores:** Raw count data gridded into `{'x': ndarray, 'y': ndarray, 'z': 2D ndarray}`.

**Why:** The raw data for a given query comes back from SQLite as a flat list of `[x, y, count]` triples. Converting that into a regular 2-D grid (`_complete_axis` + `np.add.at`) is the most CPU-intensive step in the render path. Without a cache, this work repeats on every panel re-render (scale toggle, smooth toggle, colormap change, switching the active panel, opening the focus modal, downloading) for the same underlying query.

**Cache keys:**
- v8: `(plot_key, db_choice)` — uniquely identifies a query in the pairwise database.
- v9: `(plot_key, inv1, db_choice)` — `inv1` is included because `fetch_v9_data` applies an axis swap that depends on which invariant occupies position 1; the same `plot_key` with a different `inv1` produces a transposed grid.

**Eviction:** The cache is unbounded and lives for the process lifetime. Entries are only replaced when `build_and_put` is called again with the same key (new query, same parameters), which also evicts all figure-cache entries built from that grid (see §1.2).

### 1.2 Figure cache (`_fig_cache`)

**What it stores:** Fully-built `go.Figure` objects, keyed by `make_fig_key(grid_key, log_scale, smooth, colormap, x_lims, y_lims)`.

**Why:** Even with the grid cached, calling `create_3D_figure` on every re-render still runs the full NumPy pipeline (NaN masking, log transform, scaffold, tiling, colour-scale computation) and serialises the figure into Plotly's JSON-heavy internal format. All of this is deterministic given the grid and the rendering parameters. Caching the finished figure object means that toggling log scale, smooth, or colormap on a panel that has already been rendered is a dictionary lookup rather than CPU work.

**Key design:** `make_fig_key` appends `(log_scale, smooth, colormap, x_lims_tuple, y_lims_tuple)` to the grid key, producing a single hashable tuple. Lims are converted to tuples because lists are not hashable.

**Eviction on new data:** When `build_and_put` stores a new grid for a given key, it scans `_fig_cache` and deletes every entry whose key prefix matches the grid key. This ensures that if a user clears a panel and re-queries the same invariant pair, they get a freshly built figure rather than a stale cached one.

---

## 2. `dcc.Store` Storage Type: `'memory'`

All panel-state, sci-notation, and active-panel stores are set to `storage_type='memory'` (v8: `v8-panel-states-store`, `v8-sci-notation-store`, `active-panel-store`; v9: equivalents).

**Why not `'session'`:** The default `'session'` maps to `sessionStorage`, which is capped at ~5 MB in most browsers. A single loaded 3D panel previously stored the full raw point list inside the store (thousands of `[x, y, count]` triples), pushing multi-panel layouts over the limit and causing silent data loss. Switching to `'memory'` keeps all state in the Dash virtual DOM with no browser storage cap.

**Trade-off:** `'memory'` does not survive a page refresh; users lose their layout on reload. The share-URL feature (`#`-encoded layout in the address bar) is the intended persistence mechanism.

---

## 3. Two-Trace Hover Architecture

The 3D view uses exactly two Plotly traces:

1. **`go.Surface`** — renders the colour surface; `hoverinfo='skip'`.
2. **`go.Scatter3d`** — invisible markers (`color='rgba(0,0,0,0)'`) at the real data bins only; carries the hover tooltip via `hovertemplate`.

**Why the split:** `go.Surface` has no per-cell hover control. When the surface spans empty (NaN) cells, hovering over them would display `z: NaN` — misleading to the user. Disabling surface hover entirely and placing a separate invisible point layer at every real bin gives a clean `Count: N` readout with exact coordinates, with no NaN entries ever appearing in the tooltip.

**Hover data:** The Scatter3d layer stores raw integer counts in `customdata` (not the log-transformed display height). The `hovertemplate` reads `%{customdata}` so the user always sees the true count regardless of whether log scale is active.

---

## 4. WebGL Vertex Cap (`_MAX_HOVER = 5000`)

**Problem:** Firefox (and Chrome) impose a hard limit of ~30 million WebGL vertices per draw call. Each `go.Scatter3d` marker costs approximately 700 vertices. A fully-populated torsion grid can have up to ~83,836 real bins; 83,836 × 700 ≈ 58.8 M vertices, which exceeds the limit and crashes the browser tab with the error:

```
WebGL warning: drawArraysInstanced: Context's max vertCount is 30000000, but 58852872 requested
```

**Fix:** Before building the Scatter3d trace, the rendering code checks whether the number of real bins exceeds 5,000. If so, it uses `np.argpartition` (O(n), avoids a full sort) to select the 5,000 highest-count bins and discards the rest. 5,000 markers × 700 vertices = 3.5 M vertices, well under the 30 M limit.

**Why keep the highest-count bins:** Sparse, low-count bins are visually indistinguishable on a dense surface and are the least likely hover targets. Preserving the peaks ensures the most scientifically relevant hover tooltips remain accessible.

---

## 5. Edge Scaffolding (`_scaffold_edges`, `EDGE_EPS = 1e-6`)

**Problem:** `go.Surface` renders a quad between adjacent grid cells. A lone bin with count = 1 and all-zero neighbours has no adjacent finite cell to form a face with, so it disappears from the rendered surface entirely.

**Fix:** When the "smooth" option is enabled, `_scaffold_edges` sets every empty cell that is an 8-neighbour of a populated cell to `EDGE_EPS = 1e-6`. This gives the Surface renderer a finite neighbouring value to connect to, so isolated spikes appear.

**Constraints the implementation respects:**
- **Real counts are never modified.** Only cells with value `0` (empty) are touched.
- **Far-from-data empties remain 0**, which is later converted to NaN (fully transparent). The eps rim does not spread across the whole grid.
- **Periodic axes wrap correctly.** τ torsion angles (tau_NA, tau_AC, tau_CN) are periodic over 360°; `np.pad` with `mode='wrap'` is used for these axes so a bin at −180° recognises a bin at +180° as a neighbour.
- **The eps rim is displayed at height 0.** After scaffolding, cells where `0 < count < 1` are clamped to `z_disp = 0.0` so the near-zero value never appears as a visible spike. The rim sits flush at the floor.
- **Rim colour is borrowed from its nearest real neighbour** (`scipy.ndimage.maximum_filter`, 3×3 kernel). Without this, the base of an isolated spike would be assigned the colour-scale minimum (typically blue) even though the surrounding "ground" is the eps rim, making the spike appear to fade into the floor. Borrowing the neighbour's count keeps the spike a single solid colour from base to peak.

**The eps value is excluded from the colour scale:** `cmin_v`/`cmax_v` are computed only over cells with `z_proc >= 1`, so the scaffold rim never compresses the colour range.

---

## 6. Empty Bins as NaN (Transparent Floor)

After edge scaffolding, all remaining zero-count cells are converted to `np.nan`:

```python
z_proc[z_proc == 0] = np.nan
```

**Why NaN and not 0:** `go.Surface` treats NaN as "no face here" and renders nothing, giving a fully transparent hole in the surface. A value of 0 would instead render as a visible flat floor at the minimum colour, visually polluting the plot with a false baseline.

**No alpha/blending:** NaN avoids any depth-sorting ambiguity that semi-transparent surfaces introduce in WebGL. The surface only exists where real data (or the eps scaffold rim) is present.

---

## 7. Log Colour Scale and Colour Separation

The colour channel (`surfacecolor`) and the height channel (`z`) are handled independently:

- **Height (`z_disp`):** `log10(count + 1)` in log mode, raw count in linear mode.
- **Colour (`color_v`):** Always `log10(count + 1e-9)`, regardless of the log/linear toggle.

**Why always log colour:** Raw counts in the pairwise database span several orders of magnitude (single digits to ~10⁶). On a linear colour scale, the 99th-percentile bins would dominate the palette and every other bin would appear as the same minimum colour, hiding the structure of the distribution. Logarithmic colour is a scientific convention for frequency data of this kind.

**Why the +1e-9 offset:** To avoid `log10(0)` = −∞ on the eps scaffold rim cells. The 1e-9 keeps colour computation finite; these cells are excluded from `cmin_v`/`cmax_v` so the microscopic offset does not affect the colour scale.

---

## 8. Fixed Cube Aspect Ratio (`aspectmode: 'cube'`)

Plotly's default `aspectmode: 'auto'` scales each axis proportionally to its data range. When count values reach 10⁵–10⁷ (as in the aggregated "all proteins" database), the Z axis becomes thousands of times taller than the ±180° angular axes, and the surface collapses into a thin vertical sliver.

`aspectmode: 'cube'` forces all three axes to occupy equal visual lengths regardless of their value ranges, preserving the legibility of the XY distribution while still showing Z variation through colour.

---

## 9. Angular Tiling for Periodic Axes

Torsion angles are periodic over 360°. If the user sets an axis range that spans more than one period (e.g. X from −270° to +270°), the single copy of the data in [−180°, +180°) must be repeated ("tiled") at ±360° offsets to fill the visible window.

**Implementation:** For each angular axis, the code computes the minimum number of 360° copies needed to cover `[min_lim, max_lim]`, concatenates the offset copies, sorts the result, and tiles the Z matrix accordingly. Tick labels are generated at human-friendly intervals (5°, 10°, 15°, 30°, 45°, 90°, or 180°) chosen to produce at most 6 ticks in the visible range.

**Special case for tau_CN:** The database stores tau_CN in [−90°, 270°] rather than [−180°, 180°]. `_get_axis_range` returns `[-90, 270]` for this invariant so the default view is centred on the native data range.

---

## 10. Grid Axis Convention (v8 vs v9)

The grid stored in `_cache` follows the convention `z[row, col]` where `row` indexes `inv2` (the Y axis) and `col` indexes `inv1` (the X axis). This matches NumPy's row-major layout and allows standard 2-D indexing without transposing for v8.

**v9 is transposed:** `fetch_v9_data` returns data with inv1 and inv2 swapped relative to v8. v9's `create_3D_figure` transposes the Z matrix (`original_z_data.T`) to compensate, and its `build_graph_content` maps screen X to inv2 and screen Y to inv1 (the reverse of v8). The v9 cache key therefore includes `inv1` — `(plot_key, inv1, db_choice)` — because the same plot_key with a different inv1 produces a different transposition.

---

## 11. `uirevision` for Zoom Persistence

Plotly preserves the camera position and zoom state between figure updates as long as `uirevision` does not change.

**3D figures:** `uirevision_key` is set at panel-creation time (`str(time.time())`) and stored in the panel state. It stays constant for the lifetime of a panel, so camera position is preserved across scale/smooth/colormap changes. It changes only when the panel is re-generated from a new query.

**1D histograms:** `uirevision` is set to `title`. The title encodes the invariant, residue, and offset, so it changes with any new query and resets zoom appropriately, but it stays constant when only log scale or other cosmetic options change, preserving the axis zoom.

**Why not `str(time.time())`:** This was the original implementation for 1D histograms. Because `time.time()` changes on every Python call, every re-render (including toggling log scale or switching the active panel) reset the histogram zoom, making it impossible to inspect a region of interest without the view snapping back.

---

## 12. Panel State Structure in `dcc.Store`

Each panel slot in the store contains only the metadata needed to reconstruct or re-render the panel:

```
{
  'job_type':    '3D_HEATMAP' | '1D_HISTO_VS_STATS' | ...,
  'plot_key':    <str>,      # grid cache lookup key
  'db_choice':   <str>,      # database identifier
  'inv1', 'inv2', ...        # invariant names
  'x_lims', 'y_lims',        # axis limits
  'colormap':    <str>,
  'full_v8_stats': {...},    # statistics dict (small JSON)
  'uirevision_key': <str>,   # stable per-panel camera key
  'view':        'graph' | 'stats'
}
```

**What is NOT stored:** The raw point list and the gridded arrays. These previously lived in the store as `figure_data_3d`, growing to 2–3 MB per 3D panel. Multi-panel layouts exceeded the 5 MB `sessionStorage` cap and caused silent data loss. The raw data now lives only in the server-side grid cache, addressed by `(plot_key[, inv1], db_choice)`. The store entry for a 3D panel is under 1 KB.
