# ProtNRD

Interactive visualisation of protein backbone geometry, built on **LAI
invariants**. ProtNRD plots how backbone properties co-occur across thousands of
high-quality PDB structures, conditioned on local sequence context.

## Live application

| | |
|---|---|
| **Launch ProtNRD** | https://web-production-ce7bf.up.railway.app/ |
| Example — Pairwise layout | https://web-production-ce7bf.up.railway.app/#Xx0pyg_Xp1pyg_Gg0pyg_Xx0pys_Xp2pyg_Gg0pys |
| Example — Trimer layout | https://web-production-ce7bf.up.railway.app/v9/#Gapypg_gApypg_gaPypg_Gappys_gAppys_gaPpys |

The example links open a preconfigured six-panel layout. Any layout you build in
the app is encoded in the URL fragment, so the address bar is always a shareable
link to exactly what you are looking at.

ProtNRD runs in two modes:

- **Pairwise** — the geometry of one amino acid conditioned on a neighbouring
  residue, at a chain separation of 0 to 4.
- **Trimer** — the geometry of one position within a three-residue sequence
  context.

## Related tools

| Tool | | |
|---|---|---|
| **Torsion** | Interactive 3D visualiser for dihedral angles along a polypeptide backbone. | https://moracore.github.io/torsion |
| **RamaCube** | Three-dimensional Ramachandran explorer for backbone dihedral space. | https://moracore.github.io/ramacube |

## Invariants

The geometry plotted here is expressed in **LAI invariants**, calculated by the
BRI extension:

https://github.com/AAAAAkki/Backbone_invariant-public_release

## Running locally

Requires Python 3.13.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

Pairwise is served at `/v8/` and Trimer at `/v9/` on <http://localhost:8050/>.

### Databases

The application reads precomputed SQLite databases from a `data/` directory at
the repository root (create it if absent). They are too large to ship in the
repository:

- **Pairwise** — [`proteins_v8.db`](https://huggingface.co/datasets/moracore/ProtNRD/resolve/main/proteins_v8.db) (3.2 GB)
- **Trimer** — [`proteins_v9.db`](https://huggingface.co/datasets/moracore/ProtNRD/resolve/main/proteins_v9.db) (2.1 GB)

Place them as `data/proteins_v8.db` and `data/proteins_v9.db`. Set
`PROTNRD_DATA_DIR` to read them from elsewhere.

Alternative bin sizes and resolution filters are available in the same dataset
repository:

https://huggingface.co/datasets/moracore/ProtNRD/tree/main

Any `proteins_v8*.db` or `proteins_v9*.db` file placed in the data directory
appears automatically in the in-app database picker, so several can be kept
side by side and switched between without restarting.

## Repository layout

```text
.
├── run.py            # WSGI entry point; mounts both modes
├── v8/               # Pairwise mode  (served at /v8/)
├── v9/               # Trimer mode    (served at /v9/)
├── pipelines/        # offline pipelines that build the databases
└── data/             # databases (not tracked)
```
