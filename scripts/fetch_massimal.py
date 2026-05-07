"""Fetch MASSIMAL project metadata and dataset links from GitHub.

MASSIMAL (UiT Arctic University) maps marine habitats using drone hyperspectral
imagery at sites including Bodø, Vega, Smøla, and Larvik — all relevant to the
seagrass and kelp inventory. This script queries the GitHub API for the project's
repositories, releases, and publications, writing a structured reference catalog.

No data download is attempted (hyperspectral datasets are large; access may vary).
The output is a reference document for manual follow-up.

Outputs:
  - data/external/massimal/massimal_repos.json
  - data/external/massimal/massimal_catalog.csv
  - data/external/massimal/massimal_manifest.json

Run:
  source .venv/bin/activate
  python scripts/fetch_massimal.py
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import urllib.error

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "external" / "massimal"

GITHUB_API = "https://api.github.com"
# Known MASSIMAL GitHub handle(s)
GITHUB_USERS = ["mh-skjelvareid", "massimal-project"]
SOURCE_NAME = "MASSIMAL (UiT The Arctic University of Norway)"
LICENSE = "MASSIMAL — check individual repository/dataset licenses"

# Keywords relevant to the blue-carbon inventory
RELEVANT_TERMS = {"seagrass", "eelgrass", "kelp", "macroalgae", "habitat", "coastal", "marine", "zostera"}

KNOWN_SITES = {
    "Bodø": (67.28, 14.38),
    "Vega": (65.67, 11.93),
    "Smøla": (63.37, 8.03),
    "Larvik": (59.05, 10.03),
}


def fetch_json(url: str, timeout: int = 20) -> dict | list:
    req = Request(url, headers={
        "User-Agent": "mia-capstone-research/1.0",
        "Accept": "application/vnd.github+json",
    })
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def fetch_user_repos(username: str) -> list[dict]:
    try:
        return fetch_json(f"{GITHUB_API}/users/{username}/repos?per_page=100&sort=updated")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise


def is_relevant(repo: dict) -> bool:
    text = " ".join([
        repo.get("name", ""),
        repo.get("description", "") or "",
        repo.get("topics", []) and " ".join(repo.get("topics", [])) or "",
    ]).lower()
    return any(term in text for term in RELEVANT_TERMS)


def repo_to_row(repo: dict, username: str) -> dict:
    return {
        "github_user": username,
        "name": repo.get("name"),
        "description": repo.get("description"),
        "html_url": repo.get("html_url"),
        "language": repo.get("language"),
        "topics": "; ".join(repo.get("topics") or []),
        "stargazers_count": repo.get("stargazers_count"),
        "updated_at": repo.get("updated_at"),
        "license": (repo.get("license") or {}).get("spdx_id"),
        "is_relevant": is_relevant(repo),
        "source_name": SOURCE_NAME,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_repos: list[dict] = []
    all_rows: list[dict] = []

    for username in GITHUB_USERS:
        print(f"Fetching repos for {username}...")
        repos = fetch_user_repos(username)
        print(f"  {len(repos)} repos")
        all_repos.extend(repos)
        all_rows.extend(repo_to_row(r, username) for r in repos)

    relevant_count = sum(1 for r in all_rows if r["is_relevant"])

    repos_path = OUT_DIR / "massimal_repos.json"
    repos_path.write_text(json.dumps(all_repos, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = OUT_DIR / "massimal_catalog.csv"
    write_csv(csv_path, all_rows)

    manifest = {
        "source_name": SOURCE_NAME,
        "github_users_queried": GITHUB_USERS,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "license": LICENSE,
        "total_repos": len(all_repos),
        "relevant_repos": relevant_count,
        "known_field_sites": KNOWN_SITES,
        "outputs": {
            "repos_json": str(repos_path.relative_to(REPO_ROOT)),
            "catalog_csv": str(csv_path.relative_to(REPO_ROOT)),
        },
        "note": (
            "Actual hyperspectral datasets are large and require case-by-case access. "
            "See individual repo README files and contact UiT for data access. "
            "Field sites: Bodø, Vega, Smøla, Larvik — relevant for seagrass and kelp mapping."
        ),
    }
    manifest_path = OUT_DIR / "massimal_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  {len(all_repos)} repos total, {relevant_count} relevant")
    print(f"  wrote {repos_path}")
    print(f"  wrote {csv_path}")
    print(f"  wrote {manifest_path}")


if __name__ == "__main__":
    main()
