# Trimer Mode

Plot the backbone geometry of one position in a three-residue sequence context. Each panel shows how the immediate neighbours shape the geometry of your chosen position, drawn from thousands of high-quality protein structures.

## Quick Start

1. Type a **Triplet** — three one-letter amino acid codes (e.g. **GAS**, **AAA**). The field auto-uppercases.
2. Set **Pos** to the position (1, 2, or 3) whose geometry you want to see.
3. Pick two **Components** for the axes, then hit **Load Data**.

## Controls

- **Triplet** — Three one-letter amino acid codes (case-insensitive). The field auto-uppercases as you type.
- **Pos** — Which position in the triplet to analyse: 1 (N-terminal), 2 (central), or 3 (C-terminal).
- **Component 1 / 2** — The two backbone properties to plot on the X and Y axes.

## Visual Options

- **Scale** — Linear or Log frequency scale. Log is recommended for sharply peaked distributions.
- **Colormap** — Colour scheme for the 3D surface.
- **Axis Limits** — Zoom into a custom range on either axis. Applied to the active panel only.
- **Stat Formatting** — Toggle between fixed-point and scientific notation in the Stats view.

After changing any control, click **Load Data** to update all active panels.

## Sharing Layouts

The URL updates automatically as you add panels. Copy it from the share box at the bottom of the sidebar to save or send any layout.

**Shortcut encoding** — If the query string is exactly three letters (e.g. `?GAP`), the app loads all 6 panels instantly without any further configuration:

- Panels 1–3: φ vs ψ surface plots, focusing on positions 1, 2, and 3 respectively
- Panels 4–6: the corresponding stats views for the same three positions

**Example — [`?GAP`](https://www.csc.liv.ac.uk/protNRD/v9/?GAP) fills all 6 panels:**

- Panel 1 (graph) — φ vs ψ, triplet GAP, focus **G** (pos 1)
- Panel 2 (graph) — φ vs ψ, triplet GAP, focus **A** (pos 2)
- Panel 3 (graph) — φ vs ψ, triplet GAP, focus **P** (pos 3)
- Panel 4 (stats) — φ vs ψ, triplet GAP, focus **G** (pos 1)
- Panel 5 (stats) — φ vs ψ, triplet GAP, focus **A** (pos 2)
- Panel 6 (stats) — φ vs ψ, triplet GAP, focus **P** (pos 3)

**Full encoding** — For precise control over each panel, the query parameter is `?q=`, followed by one segment per panel separated by `_`. Each segment is a compact 7-character string:

- **Position 1–3** — Triplet letters (e.g. `G`, `A`, `P`)
- **Position 4** — Focus position (1, 2, or 3)
- **Position 5** — Component 1 shortcode
- **Position 6** — Component 2 shortcode
- **Position 7** — View: `g` (graph) or `s` (stats)

Component shortcodes: `p` = φ, `y` = ψ, `w` = ω, `a` = Angle N, `b` = Angle A, `c` = Angle C, `l` = Length NA, `m` = Length AC, `n` = Length CN.

An optional visual suffix can be appended with `~` in the format `~{colormap}{scale},{xmin},{xmax},{ymin},{ymax}`. Colormap is a digit 0–9, scale is `1` for log or `0` for linear, followed by four comma-separated axis limit values (`N` for default). Omit the `~` block entirely when all visuals are default.

The `?GAP` shortcut above is equivalent to:

[https://www.csc.liv.ac.uk/protNRD/v9/?q=GAP1pyg\_GAP2pyg\_GAP3pyg\_GAP1pys\_GAP2pys\_GAP3pys](https://www.csc.liv.ac.uk/protNRD/v9/?q=GAP1pyg_GAP2pyg_GAP3pyg_GAP1pys_GAP2pys_GAP3pys)
