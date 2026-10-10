"""Tools the agent can call. Kept small, side-effect free and easy to test."""
from __future__ import annotations

import httpx


def github_repos(user: str, limit: int = 4) -> list[dict]:
    """Most recently updated public repositories, via GitHub's free public API (no key needed)."""
    r = httpx.get(f"https://api.github.com/users/{user}/repos", params={"sort": "updated", "per_page": 10},
                  headers={"Accept": "application/vnd.github+json"}, timeout=6)
    r.raise_for_status()
    repos = [x for x in r.json() if not x.get("fork")][:limit]
    return [{"name": x["name"], "url": x["html_url"], "description": x.get("description") or "",
             "language": x.get("language") or "", "updated": x.get("pushed_at", "")} for x in repos]


def speakable_repo_list(repos: list[dict]) -> str:
    names = [r["name"].replace("-", " ").replace("_", " ").strip() for r in repos]
    if not names:
        return "I couldn't find any public repositories."
    joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return f"Fresh from GitHub: Kavya's most recently updated public repositories are {joined}."
