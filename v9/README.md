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

The URL updates automatically as you add panels. Copy it from the share box at the bottom of the sidebar to save or send any layout — the layout lives in the part **after the `#`**.

**Shortcut encoding** — If the fragment is exactly three letters (e.g. `#GAP`), the app loads all 6 panels instantly without any further configuration:

- Panels 1–3: φ vs ψ surface plots, focusing on positions 1, 2, and 3 respectively
- Panels 4–6: the corresponding stats views for the same three positions

**Example — [`#GAP`](https://www.csc.liv.ac.uk/protNRD/v9/#GAP) fills all 6 panels:**

- Panel 1 (graph) — φ vs ψ, triplet GAP, focus **G** (pos 1)
- Panel 2 (graph) — φ vs ψ, triplet GAP, focus **A** (pos 2)
- Panel 3 (graph) — φ vs ψ, triplet GAP, focus **P** (pos 3)
- Panel 4 (stats) — φ vs ψ, triplet GAP, focus **G** (pos 1)
- Panel 5 (stats) — φ vs ψ, triplet GAP, focus **A** (pos 2)
- Panel 6 (stats) — φ vs ψ, triplet GAP, focus **P** (pos 3)

**Full encoding** — For precise control over each panel, the fragment is one segment per panel separated by `_`. Each segment is a fixed 6-character string `r1 r2 r3 c1 c2 view`:

- **Char 1–3** — The three triplet residues (one-letter codes; `X` for Any). **The UPPERCASE one is the focused position.**
- **Char 4** — Component 1 shortcode
- **Char 5** — Component 2 shortcode
- **Char 6** — View: `g` (graph) or `s` (stats)

Focus is carried by letter **case**: exactly one of the three residues is uppercase, marking the position whose geometry is plotted.

Component shortcodes: `p` = φ, `y` = ψ, `w` = ω, `a` = Angle N, `b` = Angle A, `c` = Angle C, `l` = Length NA, `m` = Length AC, `n` = Length CN.

Colormap, frequency scale (linear/log) and axis limits are view-only — they are **not** encoded in the URL, so a shared link always opens with default visuals.

The `#GAP` shortcut above is equivalent to:

[https://www.csc.liv.ac.uk/protNRD/v9/#Gappyg\_gAppyg\_gaPpyg\_Gappys\_gAppys\_gaPpys](https://www.csc.liv.ac.uk/protNRD/v9/#Gappyg_gAppyg_gaPpyg_Gappys_gAppys_gaPpys)
