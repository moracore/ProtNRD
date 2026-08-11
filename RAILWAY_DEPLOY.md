# Deploying ProtNRD to Railway

The app is two Dash apps (`v8/` = Pairwise, `v9/` = Trimer) mounted under one
WSGI dispatcher in `run.py`. Gunicorn serves `run:application`; there is no
single root `app.py`.

## Files that make this deployable

| file | purpose |
|---|---|
| `Procfile` | start command — `python fetch_dbs.py && gunicorn run:application` |
| `.python-version` | pins Python 3.13 so numpy/scipy install from wheels |
| `requirements.txt` | adds `gunicorn` + `huggingface_hub`, pins `werkzeug`, retargets numpy/scipy/pandas to PyPI wheels |
| `run.py` | exposes `server = application` alongside `application` |
| `fetch_dbs.py` | boot-time download of the DBs from Hugging Face onto the volume |
| `upload_dbs.py` | local helper to push the DBs up to Hugging Face (run once) |

## Environment variables

| var | value on Railway | notes |
|---|---|---|
| `PROTNRD_BASE` | `""` (empty) | app is served at the domain root, not a sub-path |
| `PROTNRD_DATA_DIR` | `/data` | must match the volume mount path below |
| `PROTNRD_HF_REPO` | `<you>/protnrd-dbs` | dataset repo holding the DBs |
| `HF_TOKEN` | `hf_…` (read scope) | only needed if that repo is private |
| `PROTNRD_HF_FILES` | *(optional)* | comma-separated; defaults to the two default DBs |
| `PROTNRD_FETCH_STRICT` | *(optional)* | `0` boots the app even if a download fails |

`PORT` is injected by Railway; do not set it.

## The databases: Hugging Face → volume

The DBs are gitignored and far too large for the build image:

- `proteins_v8.db` — 3.2 GB (Pairwise default)
- `proteins_v9_72bin.db` — 1.7 GB (Trimer default)

They are hosted in a Hugging Face **dataset** repo and pulled onto a Railway
volume on boot. Both apps read `PROTNRD_DATA_DIR` (default `<repo>/data` for
local dev), so nothing else needs to change.

### 1. Push the DBs to Hugging Face (once, from this machine)

Create a token at huggingface.co/settings/tokens with **write** access, then:

```bash
pip install huggingface_hub          # not in the local .venv by default
export HF_TOKEN=hf_...
export PROTNRD_HF_REPO=<you>/protnrd-dbs
python upload_dbs.py                 # creates the repo (private) and uploads
```

That uploads `proteins_v8.db` and `proteins_v9_72bin.db`. Pass filenames to
send others (`python upload_dbs.py proteins_v9.1deg.db`). Set
`PROTNRD_HF_PRIVATE=0` for a public repo — then Railway needs no `HF_TOKEN`.
5 GB over LFS takes a while; the upload resumes if it drops.

### 2. Attach the volume on Railway

Attach a volume to the service with mount path `/data` and set
`PROTNRD_DATA_DIR=/data`. Size it for the DBs plus headroom — ~10 GB for the
two defaults. Storage is billed separately from the service.

### 3. Set `PROTNRD_HF_REPO` (and `HF_TOKEN` if private) and deploy

On first boot `fetch_dbs.py` downloads each file straight into `/data`; watch
the `[fetch_dbs]` lines in the deploy logs. Expect several minutes before
gunicorn starts. Because the volume persists, later deploys log
`have <file> — skipping` and boot immediately.

A file is re-downloaded only when its local size differs from the Hub's, so
replacing a DB is: upload the new one to the same filename, then redeploy.
Any extra `proteins_v8*.db` / `proteins_v9*.db` files that land in the volume
show up automatically in each app's DB picker — `list_db_options()` scans the
directory at request time.

If a download fails the boot fails (Railway will retry). Set
`PROTNRD_FETCH_STRICT=0` to boot anyway with empty DB pickers.

## Notes

- `fetch_dbs.py` is a no-op when `PROTNRD_HF_REPO` is unset, so local runs and
  any non-Railway environment are unaffected.
- `hf_transfer` (Rust fast-path downloader) is in `requirements.txt` and is
  enabled automatically when importable; `fetch_dbs.py` falls back to the plain
  HTTP downloader if it is absent.
- `--workers 1` in the Procfile is deliberate. `figure_cache.py` is an
  in-process dict, so extra workers duplicate cache memory and cold-start each
  one independently. `--threads 4` handles concurrency instead. Scale workers
  only if you also raise the memory allocation.
- `--timeout 120` covers the first uncached query against a multi-GB DB.
- `run.py` unlocks Dash's read-only `requests_pathname_prefix` to mount both
  apps. That touches Dash internals, which is why `dash==3.3.0` is pinned exactly.

## Dependency pins differ from the local venv — deliberately

The local `.venv` runs Python 3.14 with conda/MKL builds of numpy 2.0.2 and
scipy 1.17.1. Neither is installable from PyPI: scipy 1.17.1 does not exist
there at all (1.16.3 is the newest), and numpy 2.0.2 has no wheel above
cp312. Left as-is, the Railway build would fall back to compiling from source
and fail.

`requirements.txt` therefore targets numpy 2.2.6 / scipy 1.16.3 / pandas 2.3.2
on Python 3.13, which resolves entirely to prebuilt wheels. The only scipy API
the app uses is `binary_dilation` / `maximum_filter` from `scipy.ndimage`
(`v8/callbacks/rendering.py`, `v9/callbacks/rendering.py`), which is unchanged
across these versions. **This combination has not been run end-to-end** — it
cannot be, locally, without a 3.13 interpreter. Check the sparse-bin rim
rendering on the first deploy.

## Local development is unchanged

`python run.py` still serves both apps on http://localhost:8050 using the local
`data/` directory.
