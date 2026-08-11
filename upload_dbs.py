"""One-off helper: push local DBs from data/ up to the Hugging Face repo that
fetch_dbs.py pulls from. Run this locally, not on Railway.

    export HF_TOKEN=hf_...            # a *write* token
    export PROTNRD_HF_REPO=you/protnrd-dbs
    python upload_dbs.py                        # the two default DBs
    python upload_dbs.py proteins_v9.1deg.db    # or name files explicitly

Creates the dataset repo (private) if it does not exist. Uploads are resumable:
re-running skips files whose contents already match the Hub.
"""
import os
import sys

from huggingface_hub import HfApi

DEFAULT_FILES = ["proteins_v8.db", "proteins_v9_72bin.db"]

REPO_ID = os.environ.get("PROTNRD_HF_REPO", "").strip()
REPO_TYPE = os.environ.get("PROTNRD_HF_REPO_TYPE", "dataset").strip()
PRIVATE = os.environ.get("PROTNRD_HF_PRIVATE", "1") != "0"
DATA_DIR = os.environ.get("PROTNRD_DATA_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data"
)
TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")


def main(argv):
    if not REPO_ID:
        sys.exit("Set PROTNRD_HF_REPO, e.g. export PROTNRD_HF_REPO=you/protnrd-dbs")
    if not TOKEN:
        sys.exit("Set HF_TOKEN to a token with write access.")

    files = argv or DEFAULT_FILES
    paths = []
    for name in files:
        p = name if os.path.isabs(name) else os.path.join(DATA_DIR, name)
        if not os.path.isfile(p):
            sys.exit(f"missing: {p}")
        paths.append((os.path.basename(p), p))

    api = HfApi(token=TOKEN)
    api.create_repo(REPO_ID, repo_type=REPO_TYPE, private=PRIVATE, exist_ok=True)

    total = sum(os.path.getsize(p) for _, p in paths)
    print(f"uploading {len(paths)} file(s), {total / 1024 ** 3:.2f} GiB → {REPO_ID}")
    for name, path in paths:
        print(f"  {name} ({os.path.getsize(path) / 1024 ** 3:.2f} GiB)")
        api.upload_file(
            path_or_fileobj=path,
            path_in_repo=name,
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
        )
    print("done.")


if __name__ == "__main__":
    main(sys.argv[1:])
