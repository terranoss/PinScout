from __future__ import annotations

import subprocess
from pathlib import Path


def get_git_short_sha() -> str:
    """
    Return the current git commit short SHA (like GitHub's commit list).

    If git metadata isn't available (e.g. running from a zip), return "unknown".
    """

    repo_root = Path(__file__).resolve().parents[1]
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return "unknown"

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        sha = (result.stdout or "").strip()
        return sha or "unknown"
    except Exception:
        return "unknown"

