#!/usr/bin/env python3
"""MCP server for the GitHub public API — hand-crafted example for MCPForge."""

import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("GitHub API")
BASE_URL = "https://api.github.com"

# Set GITHUB_TOKEN env var to increase rate limits (public endpoints work without it)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


@mcp.tool()
def list_repos(owner: str, per_page: int = 30, sort: str = "updated") -> dict:
    """List public repositories for a GitHub user or organisation.

    Args:
        owner: GitHub username or organisation name.
        per_page: Number of repos to return (max 100).
        sort: Sort by 'created', 'updated', 'pushed', or 'full_name'.

    Returns:
        List of repository objects with name, description, stars, and URL.
    """
    params = {"per_page": per_page, "sort": sort}
    resp = httpx.get(f"{BASE_URL}/users/{owner}/repos", params=params, headers=_headers(), timeout=30)
    resp.raise_for_status()
    repos = resp.json()
    return {
        "owner": owner,
        "count": len(repos),
        "repos": [
            {
                "name": r["name"],
                "full_name": r["full_name"],
                "description": r.get("description", ""),
                "stars": r["stargazers_count"],
                "forks": r["forks_count"],
                "language": r.get("language", ""),
                "url": r["html_url"],
                "updated_at": r["updated_at"],
            }
            for r in repos
        ],
    }


@mcp.tool()
def get_repo(owner: str, repo: str) -> dict:
    """Get detailed information about a specific GitHub repository.

    Args:
        owner: GitHub username or organisation name.
        repo: Repository name.

    Returns:
        Repository details including description, stats, topics, and license.
    """
    resp = httpx.get(f"{BASE_URL}/repos/{owner}/{repo}", headers=_headers(), timeout=30)
    resp.raise_for_status()
    r = resp.json()
    return {
        "name": r["name"],
        "full_name": r["full_name"],
        "description": r.get("description", ""),
        "homepage": r.get("homepage", ""),
        "stars": r["stargazers_count"],
        "watchers": r["watchers_count"],
        "forks": r["forks_count"],
        "open_issues": r["open_issues_count"],
        "language": r.get("language", ""),
        "topics": r.get("topics", []),
        "license": r.get("license", {}).get("name", "") if r.get("license") else "",
        "default_branch": r["default_branch"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
        "url": r["html_url"],
        "clone_url": r["clone_url"],
    }


@mcp.tool()
def search_repos(query: str, sort: str = "stars", per_page: int = 10) -> dict:
    """Search GitHub repositories by keyword, language, or other qualifiers.

    Args:
        query: Search query (e.g. 'mcp python', 'language:rust stars:>100').
        sort: Sort by 'stars', 'forks', 'help-wanted-issues', or 'updated'.
        per_page: Number of results (max 100).

    Returns:
        List of matching repositories with key stats.
    """
    params = {"q": query, "sort": sort, "per_page": per_page}
    resp = httpx.get(f"{BASE_URL}/search/repositories", params=params, headers=_headers(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return {
        "total_count": data.get("total_count", 0),
        "results": [
            {
                "full_name": r["full_name"],
                "description": r.get("description", ""),
                "stars": r["stargazers_count"],
                "language": r.get("language", ""),
                "url": r["html_url"],
            }
            for r in data.get("items", [])
        ],
    }


@mcp.tool()
def list_issues(owner: str, repo: str, state: str = "open", per_page: int = 20) -> dict:
    """List issues for a GitHub repository.

    Args:
        owner: GitHub username or organisation name.
        repo: Repository name.
        state: Filter by issue state — 'open', 'closed', or 'all'.
        per_page: Number of issues to return (max 100).

    Returns:
        List of issues with title, number, author, labels, and URL.
    """
    params = {"state": state, "per_page": per_page}
    resp = httpx.get(
        f"{BASE_URL}/repos/{owner}/{repo}/issues",
        params=params,
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    issues = resp.json()
    # Filter out pull requests (GitHub returns PRs in issues endpoint)
    issues = [i for i in issues if "pull_request" not in i]
    return {
        "owner": owner,
        "repo": repo,
        "state": state,
        "count": len(issues),
        "issues": [
            {
                "number": i["number"],
                "title": i["title"],
                "state": i["state"],
                "author": i["user"]["login"],
                "labels": [lbl["name"] for lbl in i.get("labels", [])],
                "comments": i["comments"],
                "created_at": i["created_at"],
                "url": i["html_url"],
            }
            for i in issues
        ],
    }


if __name__ == "__main__":
    mcp.run()
