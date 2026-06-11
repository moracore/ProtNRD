# ProtNRD DB pipelines (integer-angle binning)

Clean, runnable pipelines that regenerate the two app databases with **bin
centres rounded to integer degrees** (no more `179.5` / `177.1875` / `180.5`).

```
pipelines/
  00_data_source/ -> scrapes/filters PDB into the source + 2A/3A invariant DBs
  v8_pairwise/    -> builds proteins_v8.db   (Pairwise app, served at /v8/)
  v9_trimer/      -> builds proteins_v9.db   (Trimer app,   served at /v9/)
```

> ⚠️ **Not executed here** — this machine's venv has a broken numpy, so these
> were written/patched but **not run**. Validate on a working env before
> regenerating production DBs. A verification checklist is at the bottom.

---

## What "integer-angle binning" means

Every torsion (phi/psi/omega, range −180..180) is **rounded to the nearest whole
degree** and folded `+180 → −180`, so bin centres are the integers **−180..179**
(360 clean bins, no duplicated seam at ±180). Non-torsion axes (bond lengths,
bond angles) keep their existing finer resolution — integer degrees only make
sense for the angular plots.

| | Before | After |
|---|---|---|
| Pairwise 1D histo | `bins=360` → centres `…, 179.5` | integers `…, 179` |
| Pairwise 3D heatmap | `histogram2d` → `.5` centres | integer centres (torsion axes) |
| Trimer 3D heatmap | `bins=64` → `5.625°` → `177.1875` | integer centres |

---

## 00_data_source/  (→ source + 2A/3A invariant DBs)

Upstream of v8/v9: this is where the structural data is pulled from the RCSB PDB
and filtered into the `invariants_filtered` DBs the binning pipelines consume.
Extracted from `data_pipeline_scripts.zip`. These ran on the HPC cluster (SLURM),
so the `.sh` wrappers carry hard-coded `fastscratch` paths — adjust before reuse.

- `original_scraper.py` / `resumable_scraper.py` — fetch each unique PDB ID's CIF
  from `files.rcsb.org`, read method + resolution, and flag X-ray ≤ 2.0 Å (`2AXR`
  column on the source DB). The resumable variant checkpoints in batches of 500.
- `add_resolution_flags.py` — builds a `pdb_resolution` lookup table (one row per
  PDB ID: `resolution`, `is_xray`); resumable, skips IDs already present.
- `filter_db.py` — creates the two filtered DBs: **2A** (X-ray ≤ 2.0 Å via `2AXR`)
  and **3A** (X-ray < 3.0 Å via `pdb_resolution`), each a single
  `invariants_filtered` table (terminal `0.0` bond artifacts → NULL, sequential
  per-chain `position`).
- `fix_resolution.sh` / `apply_resolution_fix.sh` — re-fetch resolutions from CIF
  and re-derive the valid-PDB sets (preview, then apply).
- `run_scraper_rebuild.sh` — SLURM driver: resumable scrape → rebuild 2A/3A DBs.

---

## v8_pairwise/  (→ proteins_v8.db)

Copy of the coherent `oldProtNRD/PipelineNRD-v0.8` pipeline. **Only the binning
was changed**, in `tools/generate_visualizations.py`:
- `_calculate_1d_histo` → integer-degree centres via round+fold + `bincount`.
- the 3D-heatmap block → new `_bin_axis()` (torsion = integer degrees, else =
  configured resolution grid) + a pandas `groupby`, so stored centres are exactly
  the bin labels.

Run: `cd v8_pairwise && python3 pipeline_02_cache.py <db_path> --recalculate`
(see `pipeline.sh`; `pipeline_01_joins.py` / `pipeline_03_cleanup.py` unchanged).

## v9_trimer/  (→ proteins_v9.db)

Based on the canonical `~/Documents/ProtNRD/_ProtNRD9` 3-mer pipeline, with three
fixes so it actually reproduces the **deployed** DB *and* uses integer bins:

1. **Integer binning** — `tools/heatmap_utils.py` rewritten: round-to-nearest +
   fold (was `bins=64`, then a truncating `astype(int)`).
2. **Position-aware** — `3_3M_cache.py` now loops focus positions 1/2/3:
   - stats stored per position (`pos1_`/`pos2_`/`pos3_`, 233 columns) — matches the
     live `stats` schema; built programmatically in `tools/database_utils.py`.
   - heatmaps keyed `{trimer}_p{pos}_{suffix}` from that position's torsions —
     matches the app's `cache_3d` lookups (was middle-residue-only, position-less).
3. **Reconciled table chain** — `1_3M_flat.py` → `'3mers'`, `2_3M_freq.py` reads
   `'3mers'` → `v9_3mer_map(res_1,res_2,res_3,trimer,population)`, `3_3M_cache.py`
   reads `v9_3mer_map` + `'3mers'`. (The originals referenced mismatched
   `v9_triplets` / `freq` tables and never chained.)

Run: `cd v9_trimer && ./run_pipeline.sh <db_path>` (DB must already have
`invariants_filtered`).

Unchanged from `_ProtNRD9`: `tools/stats_utils.py`, `tools/pipeline_constants.py`.

---

## Verification checklist (run on a working env)

1. `python3 -c "import ast,glob; [ast.parse(open(f).read()) for f in glob.glob('**/*.py',recursive=True)]"`
2. Build against a **small copy** of each DB, then:
   - `SELECT data FROM cache_3d LIMIT 1` → every point x/y is an integer in [−180,179].
   - v8: `SELECT data FROM v8_histo_cache LIMIT 1` → bins are integers.
   - v9: `PRAGMA table_info(stats)` → 233 columns (`pos1_…`/`pos2_…`/`pos3_…`);
     `cache_3d` keys look like `AAA_p1_phi_psi`; p1/p2/p3 differ.
3. Open each mode in the app and confirm axes read whole degrees.
