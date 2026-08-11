"""Fetch the SQLite DBs from a Hugging Face dataset repo into PROTNRD_DATA_DIR.

Runs before gunicorn on every boot (see Procfile). The DBs live on a Railway
volume, so after the first successful deploy this is a no-op: each file is
skipped when a local copy already matches the size recorded on the Hub.

Configuration (all via environment):
  PROTNRD_HF_REPO   dataset repo id, e.g. "gtnbr/protnrd-dbs"   (required)
  PROTNRD_HF_FILES  comma-separated filenames to pull; defaults to the two
                    DBs the apps open by default
  PROTNRD_DATA_DIR  destination directory; must match the volume mount path
  HF_TOKEN          read token — required for a private repo, ignored otherwise
  PROTNRD_FETCH_STRICT
                    "0" boots the app even if a download fails (DB pickers come
                    up blank). Default is strict: fail the boot loudly.

Run it by hand for a dry run:  PROTNRD_HF_REPO=... python fetch_dbs.py
"""
import os
import shutil
import sys

DEFAULT_FILES = "proteins_v8.db,proteins_v9_72bin.db"

REPO_ID = os.environ.get("PROTNRD_HF_REPO", "").strip()
REPO_TYPE = os.environ.get("PROTNRD_HF_REPO_TYPE", "dataset").strip()
REVISION = os.environ.get("PROTNRD_HF_REVISION", "").strip() or None
DATA_DIR = os.environ.get("PROTNRD_DATA_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data"
)
FILES = [f.strip() for f in
         os.environ.get("PROTNRD_HF_FILES", DEFAULT_FILES).split(",") if f.strip()]
STRICT = os.environ.get("PROTNRD_FETCH_STRICT", "1") != "0"
TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")


def log(msg):
    print(f"[fetch_dbs] {msg}", flush=True)


def gib(n):
    return f"{n / 1024 ** 3:.2f} GiB"


def main():
    if not REPO_ID:
        log("PROTNRD_HF_REPO is not set — skipping download.")
        log("Set it to your dataset repo (e.g. gtnbr/protnrd-dbs) to pull the DBs.")
        return 0

    # hf_transfer is a large speed-up on Railway's network but is optional; only
    # switch it on if the wheel actually made it into the image.
    try:
        import hf_transfer  # noqa: F401
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
    except ImportError:
        pass

    from huggingface_hub import HfApi, hf_hub_download
    try:  # huggingface_hub >= 0.29 (and all of 1.x)
        from huggingface_hub.errors import EntryNotFoundError, RepositoryNotFoundError
    except ImportError:  # older releases only expose these under .utils
        from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError

    os.makedirs(DATA_DIR, exist_ok=True)
    api = HfApi(token=TOKEN)

    try:
        info = api.repo_info(REPO_ID, repo_type=REPO_TYPE, revision=REVISION, files_metadata=True)
    except RepositoryNotFoundError:
        log(f"ERROR: repo '{REPO_ID}' ({REPO_TYPE}) not found, or the token cannot read it.")
        return 1 if STRICT else 0

    # Remote sizes come from the LFS pointer when present, else the blob size.
    remote_sizes = {}
    for s in info.siblings or []:
        size = getattr(getattr(s, "lfs", None), "size", None) or s.size
        remote_sizes[s.rfilename] = size

    wanted, missing = [], []
    for name in FILES:
        (wanted if name in remote_sizes else missing).append(name)
    for name in missing:
        log(f"WARNING: '{name}' is not in {REPO_ID} — skipping.")

    todo = []
    for name in wanted:
        dest = os.path.join(DATA_DIR, name)
        remote = remote_sizes[name]
        if os.path.isfile(dest):
            local = os.path.getsize(dest)
            if remote is None or local == remote:
                log(f"have  {name} ({gib(local)}) — skipping")
                continue
            log(f"stale {name}: local {gib(local)} != remote {gib(remote)} — re-downloading")
        todo.append((name, remote))

    if not todo:
        log("all DBs present.")
        return 0

    needed = sum(size or 0 for _, size in todo)
    free = shutil.disk_usage(DATA_DIR).free
    log(f"need {gib(needed)}, free on {DATA_DIR}: {gib(free)}")
    if needed and free < needed * 1.05:
        log("ERROR: not enough free space on the volume. Grow it and redeploy.")
        return 1 if STRICT else 0

    failed = False
    for name, size in todo:
        log(f"downloading {name} ({gib(size or 0)}) from {REPO_ID} …")
        try:
            hf_hub_download(
                repo_id=REPO_ID,
                repo_type=REPO_TYPE,
                revision=REVISION,
                filename=name,
                local_dir=DATA_DIR,   # writes straight into the volume, no symlink
                token=TOKEN,
            )
            log(f"done {name}")
        except EntryNotFoundError:
            log(f"ERROR: '{name}' vanished from the repo mid-run.")
            failed = True
        except Exception as exc:  # network, auth, disk — all fatal to this file
            log(f"ERROR downloading {name}: {type(exc).__name__}: {exc}")
            failed = True

    if failed:
        log("one or more downloads failed.")
        return 1 if STRICT else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
