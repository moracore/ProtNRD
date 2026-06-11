# Pairwise Mode

Plot the backbone geometry of any amino acid, conditioned on a neighbouring residue in the chain. Each panel shows how two backbone properties co-occur across thousands of high-quality protein structures.

## Quick Start

1. Set **Residue 1** and **Residue 2** — or leave as **Any** to include all residues at that position.
2. Choose a **Residue Step**: how far apart the two residues are in the chain (0 = same position, 1–4 = neighbours).
3. When Step > 0, tick **Focus** to choose which residue's geometry is plotted.
4. Pick two **Components** for the axes, then hit **Load Data**.

## Controls

- **Residue 1 / 2** — Filter by amino acid type, or **Any** to include all residues at that position.
- **Residue Step** — Chain distance between the two residues (0–4). At Step 0 both positions describe the same residue, so Residue 2 has no additional effect.
- **Focus** — Which residue's geometry is plotted. Only relevant when Step > 0 — exactly one must be ticked.
- **Component 1 / 2** — The two backbone properties to plot on the X and Y axes.

## Visual Options

- **Scale** — Linear or Log frequency scale. Log is recommended for sharply peaked distributions.
- **Colormap** — Colour scheme for the 3D surface.
- **Axis Limits** — Zoom into a custom range on either axis. Applied to the active panel only.
- **Stat Formatting** — Toggle between fixed-point and scientific notation in the Stats view.

After changing any control, click **Load Data** to update all active panels.

## Sharing Layouts

The URL updates automatically as you add panels. Copy it from the share box at the bottom of the sidebar to save or send any layout — the layout lives in the part **after the `#`**.

The fragment is one segment per panel separated by `_`. Each segment is a fixed 6-character string `r1 r2 step c1 c2 view`:

- **Char 1** — Residue 1 (one-letter code; `X` for Any). **UPPERCASE = the focused residue.**
- **Char 2** — Residue 2 (one-letter code; `X` for Any). Lowercase when not the focus.
- **Char 3** — Step (0–4), the chain distance between the two residues. At Step 0 both describe the same residue.
- **Char 4** — Component 1 shortcode
- **Char 5** — Component 2 shortcode
- **Char 6** — View: `g` (graph) or `s` (stats)

Focus is carried by letter **case**: exactly one of the two residues is uppercase, and that is the one whose geometry is plotted.

Component shortcodes: `p` = φ, `y` = ψ, `w` = ω, `a` = Angle N, `b` = Angle A, `c` = Angle C, `l` = Length NA, `m` = Length AC, `n` = Length CN.

Colormap, frequency scale (linear/log) and axis limits are view-only — they are **not** encoded in the URL, so a shared link always opens with default visuals.

**Example — Alanine vs Proline across six separations (fills all 6 panels):**

[https://www.csc.liv.ac.uk/protNRD/v8/#Ap1pyg\_Ap2pyg\_Ap3pyg\_Pa1pyg\_Pa2pyg\_Pa3pyg](https://www.csc.liv.ac.uk/protNRD/v8/#Ap1pyg_Ap2pyg_Ap3pyg_Pa1pyg_Pa2pyg_Pa3pyg)

- `Ap1pyg` — Focus **A**, Proline at +1, φ vs ψ, graph
- `Ap2pyg` — Focus **A**, Proline at +2, φ vs ψ, graph
- `Ap3pyg` — Focus **A**, Proline at +3, φ vs ψ, graph
- `Pa1pyg` — Focus **P**, Alanine at +1, φ vs ψ, graph
- `Pa2pyg` — Focus **P**, Alanine at +2, φ vs ψ, graph
- `Pa3pyg` — Focus **P**, Alanine at +3, φ vs ψ, graph

The first three panels show how A's geometry shifts depending on how far ahead P appears. The last three show the same from P's perspective — together they capture the full pairwise relationship in both chain directions.
