# ProtNRD — Next Release Checklist

Ordered. Data source first, GitHub release page last.

- [ ] **1. Explain the data source**
      Where the structural data comes from, how it's pulled/filtered into the DBs.
      Scripts now live in `pipelines/00_data_source/` (RCSB scrape → resolution
      flags → 2A/3A `invariants_filtered` DBs); see that stage in
      `pipelines/README.md`. Write the user-facing explanation from there.

- [ ] **2. Explain polar stats calculation**
      How the circular/torsion stats are computed (`calculate_circular_stats` /
      `calculate_2d_torsion_stats`) for the polar plots.

- [ ] **3. Revisit installation** _(feeds into #4)_
      Review how it's installed; rework the install flow.

- [ ] **4. GitHub release page** for this version
      Write it up last, and fold the finalized install instructions from #3 into it.

> Note: #3 and #4 are coupled — install method gets reworked in #3, then
> documented in the release notes in #4.

> claude --resume fddd0b75-2481-4205-b6a7-2a70dffbf4dc
