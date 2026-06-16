# 3D Surface Rendering — Sparse Bins Fix

Changes to how the v8 / v9 3D histogram surfaces render sparse (low-count) bins, and
the addition of a global toggle for it.

## The problem

The 3D plots use `go.Surface` over a grid of histogram **bin counts**. An earlier change
set empty bins to `NaN` (a transparent floor). But `go.Surface` only draws a face when
**all four corners of a cell are finite**. Consequences once empties were `NaN`:

- An isolated populated bin (a count surrounded by empty bins) had no finite neighbours,
  so it couldn't form a face and **disappeared**.
- A one-bin-wide ridge of data (empties on both sides) formed no complete quads and
  vanished too.

A first patch added `size=1` "orphan" marker dots to recover those cells, but at 1px they
read as weird specks — and data still effectively looked hidden.

## Key fact about the data

Every count in the histogram is an **exact integer** — bin populations. Verified directly
in `cache_3d` (values 1–1428, type `int`). There are **no fractional counts** in the raw
data. This matters: any rendering fix must not invent fractional "counts."

## Approaches considered

1. **Gaussian smoothing** (tried, then rejected). Blurring the count grid gave each bin a
   skirt of neighbours so isolated bins rendered as bumps. But the blur **fabricated
   fractional values** that don't exist in the data and **shaved the real peaks**. Even
   restricting it to `count < 5` cells still meant the displayed surface contained invented
   numbers under a "Count" axis. Rejected for data integrity.

2. **Near-zero edge scaffold** (adopted). Drop a tiny `1e-6` value onto only the empty
   cells that *touch* a populated bin. This gives isolated bins finite neighbours to span a
   face, **without changing any real count**. The eps cells sit flat at the floor (height
   ≈ 0, lowest colour); far-from-data empties stay `0 → NaN → transparent`.

## Final implementation

A helper `_scaffold_edges(z, inv_row, inv_col, eps=1e-6)` in each app's
`callbacks/rendering.py`:

- `mask = z > 0` (populated bins).
- 8-neighbour `binary_dilation` of the mask, padded **wrap** on periodic τ torsion axes
  (`tau_NA`, `tau_AC`, `tau_CN`) and **constant** otherwise.
- Empty cells in the dilated rim get `eps`; real counts are left exact.

Called once where the count grid is built, gated by the toggle:

```python
if smooth:
    original_z_data = _scaffold_edges(original_z_data, inv2_name, inv1_name)
```

Grid orientation in both apps: `z` axis0 → inv2 (rows), axis1 → inv1 (cols).

### Colour scale

- **v9** pins `cmin` to `log10(1)`, so the `1e-6` rim doesn't affect colours — no change
  needed.
- **v8** derived `cmin/cmax` from the data via `nanmin/nanmax`, which the `1e-6` rim would
  skew. Fixed to compute the scale from real counts only (`z_proc >= 1`); the rim is
  clamped to the floor colour.

### Hover / height of the rim

The raw `1e-6` would otherwise leak into the hover readout (Plotly renders it as `1µ`) and
as a tiny height. The **displayed** z for rim cells (`0 < count < 1`) is forced to `0`, so
the rim sits flat on the floor and hovering it shows `z: 0`. Real integer counts (`>= 1`)
and NaN empties are untouched.

### Hover: no NaN tags, count readout preserved

`go.Surface` has no per-cell hover control (its `hoverinfo` is all-or-nothing, unlike
Scatter), so Plotly tags `z: NaN` over the transparent empty cells (and `z: 0`/`1µ` over the
rim). Fix:

- The **surface** trace is set to `hoverinfo='skip'`.
- Hover lives on a second **invisible** `Scatter3d` placed only at the real bins
  (`z >= 1`), with `marker=dict(color='rgba(0,0,0,0)')` so nothing is drawn but the points
  are still hoverable. Its `hovertemplate` shows the two axis invariant values and the
  integer `Count` (`customdata`).

Result: hovering data gives a clean count readout; hovering empty space gives nothing — no
NaN, no eps tags. (Markers are invisible by design; bump the marker opacity if hover ever
fails to register in a given renderer.)

### Rim colour (so isolated spikes aren't blue)

`go.Surface` colours a face by interpolating the `surfacecolor` of its corner vertices. An
isolated bin renders as a thin spike: its apex vertex has the true count colour, but its
base is the rim. If the rim is coloured by its own ~0 value it lands at the floor colour
(blue), so a thin spike interpolates almost entirely blue — only the tip shows the real
colour. Dense regions are unaffected because they're broad.

Fix: each rim cell is coloured by the **max real count in its 3×3 neighbourhood**
(`maximum_filter`), not by its own `1e-6`. So an isolated spike is one solid colour over its
whole height. This affects only `surfacecolor` (an eps cell's *height* is still `0` and its
*count* is still nonexistent); the colour scale (`cmin/cmax`) is still computed from real
counts only.

## The toggle

A global switch was added (parallel to the existing Linear/Log scale switch), default
**on**:

- Layout (`layouts.py`): `dbc.Switch(id='smooth-switch', ...)` under a **"Sparse data"**
  heading, labelled **"Show isolated bins"**.
- Wired through every figure-building path as a `smooth` flag on `create_3D_figure(...)`:
  - **v9**: main render callback (`update_all_panels` → `build_graph_content`), focus modal
    (`open_focus_modal`), HTML download (`download_graph_html`).
  - **v8**: main render (`render_all_panels`), focus modal (`open_focus_modal`), download
    (`download`).

Off = original behaviour (isolated bins vanish). On = scaffold so they render.

## Files changed (v8 and v9)

- `layouts.py` — added the switch.
- `callbacks/rendering.py` — `_scaffold_edges`, `import binary_dilation`, the `smooth`
  param on `create_3D_figure`, the gated call, and (v8) the colour-scale fix.
- `callbacks/interactions.py` — threaded `smooth-switch` into the render / focus / download
  callbacks. (v9's main render lives in `rendering.py`.)

## Dependency note

Uses `scipy.ndimage.binary_dilation` (scipy already installed, 1.17.1). Ensure `scipy` is
in the deploy requirements.

## Verification

- All raw counts preserved exactly (e.g. 1, 4, 100 render at their true heights).
- Only added value anywhere is `1e-6` (the rim).
- Isolated bins now render (44 renderable cells on vs 12 off on a 3-bin test).
- Both apps register all callbacks cleanly.
