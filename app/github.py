"""Clone a public GitHub repo into a temporary folder."""

import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager

GITHUB_RE = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


def parse(url):
    m = GITHUB_RE.match(url.strip())
    if not m:
        raise ValueError("Only public URLs like https://github.com/<owner>/<repo> are supported.")
    return m.group(1), m.group(2)


@contextmanager
def clone(url, timeout=120):
    """Shallow-clone the repo; yield (local_path, permalink_base); delete afterwards."""
    owner, repo = parse(url)
    tmp = tempfile.mkdtemp(prefix="atr_")
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        dest = os.path.join(tmp, repo)
        subprocess.run(
            ["git", "clone", "--depth", "1", f"https://github.com/{owner}/{repo}.git", dest],
            check=True, capture_output=True, timeout=timeout, env=env,
        )
        sha = subprocess.run(
            ["git", "-C", dest, "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        yield dest, f"https://github.com/{owner}/{repo}/blob/{sha}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)