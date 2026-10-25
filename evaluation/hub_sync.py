"""Share benchmark outputs through a (free) Hugging Face dataset repo.

    python -m evaluation.hub_sync pull --repo ORG/vlm-results
    python -m evaluation.hub_sync push --repo ORG/vlm-results --patterns "results/gen/pope*" ...

Each process pushes only its own files; pushes retry because two processes
committing at the same moment can conflict.  Requires HF_TOKEN.
"""
from __future__ import annotations

import argparse
import time


def pull(repo: str) -> None:
    from huggingface_hub import snapshot_download
    try:
        snapshot_download(repo, repo_type="dataset", local_dir=".", allow_patterns=["results/**"])
        print(f"pulled results from {repo}")
    except Exception as exc:  # first run: empty repo is fine
        print(f"nothing pulled from {repo}: {type(exc).__name__}: {str(exc)[:200]}")


def push(repo: str, patterns: list[str], tries: int = 4) -> bool:
    from huggingface_hub import HfApi
    for attempt in range(tries):
        try:
            HfApi().upload_folder(repo_id=repo, repo_type="dataset", folder_path=".", allow_patterns=patterns,
                                  commit_message=f"results: {', '.join(patterns)[:120]}")
            return True
        except Exception as exc:
            if attempt == tries - 1:
                print(f"push failed (results remain on local disk): {type(exc).__name__}: {str(exc)[:200]}")
                return False
            time.sleep(10 * (attempt + 1))
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["pull", "push"])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--patterns", nargs="*", default=["results/**"])
    args = parser.parse_args()
    pull(args.repo) if args.action == "pull" else push(args.repo, args.patterns)
