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

The URL updates automatically as you add panels. Copy it from the share box at the bottom of the sidebar to save or send any layout.

The query parameter is `?q=`, followed by one segment per panel separated by `_`. Each segment is a 7-character string:

- **Position 1** — Residue 1 (one-letter code, or `Z` for Any)
- **Position 2** — Residue 2 (one-letter code, or `Z` for Any)
- **Position 3** — Step (0–4)
- **Position 4** — Focus: `1` = focus Residue 1, `2` = focus Residue 2, `0` when Step is 0 (ignored)
- **Position 5** — Component 1 shortcode
- **Position 6** — Component 2 shortcode
- **Position 7** — View: `g` (graph) or `s` (stats)

Component shortcodes: `p` = φ, `y` = ψ, `w` = ω, `a` = Angle N, `b` = Angle A, `c` = Angle C, `l` = Length NA, `m` = Length AC, `n` = Length CN.

An optional visual suffix can be appended with `~` in the format `~{colormap}{scale},{xmin},{xmax},{ymin},{ymax}`. Colormap is a digit 0–9, scale is `1` for log or `0` for linear, followed by four comma-separated axis limit values (`N` for default). Omit the `~` block entirely when all visuals are default.

**Example — Alanine vs Proline across six separations (fills all 6 panels):**

[https://www.csc.liv.ac.uk/protNRD/v8/?q=AP11pyg\_AP21pyg\_AP31pyg\_PA11pyg\_PA21pyg\_PA31pyg](https://www.csc.liv.ac.uk/protNRD/v8/?q=AP11pyg_AP21pyg_AP31pyg_PA11pyg_PA21pyg_PA31pyg)

- `AP11pyg` — Focus **A** (pos 1), Proline at +1, φ vs ψ, graph
- `AP21pyg` — Focus **A** (pos 1), Proline at +2, φ vs ψ, graph
- `AP31pyg` — Focus **A** (pos 1), Proline at +3, φ vs ψ, graph
- `PA11pyg` — Focus **P** (pos 1), Alanine at +1 (= P precedes A by 1), φ vs ψ, graph
- `PA21pyg` — Focus **P** (pos 1), Alanine at +2, φ vs ψ, graph
- `PA31pyg` — Focus **P** (pos 1), Alanine at +3, φ vs ψ, graph

The first three panels show how A's geometry shifts depending on how far ahead P appears. The last three show the same from P's perspective — together they capture the full pairwise relationship in both chain directions.
