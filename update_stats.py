#!/usr/bin/env python3
"""
Fetches live GitHub stats for GH_USERNAME and re-renders assets/card.svg
(the animated panel at the top of README.md) via make_card.render().

Env vars required:
  GITHUB_TOKEN  - auto-provided by GitHub Actions
  GH_USERNAME   - profile owner's GitHub username
                  (workflow sets this to ${{ github.repository_owner }})

Metrics gathered:
  - owned, non-fork repo count + stargazer sum   (GraphQL)
  - repos contributed to                          (GraphQL)
  - total public commit contributions, all-time   (GraphQL, summed per year)
  - follower count                                (REST)
  - lines of code added/removed across public
    repos, attributed to this author              (shallow git clone + numstat)

Lines-of-code is the most expensive step (it clones every public, non-fork
repo). If your account has many/large repos this will slow the workflow
down significantly - see the SKIP_LOC env var below to disable it.
"""
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone

import requests

import make_card
import make_stats

GITHUB_USERNAME = os.environ["GH_USERNAME"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
SKIP_LOC = os.environ.get("SKIP_LOC", "false").lower() == "true"
CARD_PATH = "assets/card.svg"

HEADERS = {"Authorization": f"bearer {GITHUB_TOKEN}"}
GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"


def graphql(query, variables=None):
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables or {}},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def get_account_created_year():
    query = "query($login: String!) { user(login: $login) { createdAt } }"
    data = graphql(query, {"login": GITHUB_USERNAME})
    return int(data["user"]["createdAt"][:4])


def get_commit_total():
    """Sum public + restricted commit contributions, year by year since signup."""
    start_year = get_account_created_year()
    this_year = datetime.now(timezone.utc).year
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          restrictedContributionsCount
        }
      }
    }
    """
    total = 0
    for year in range(start_year, this_year + 1):
        variables = {
            "login": GITHUB_USERNAME,
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year}-12-31T23:59:59Z",
        }
        coll = graphql(query, variables)["user"]["contributionsCollection"]
        total += coll["totalCommitContributions"] + coll["restrictedContributionsCount"]
    return total


def get_repo_and_star_stats():
    query = """
    query($login: String!, $after: String) {
      user(login: $login) {
        repositoriesContributedTo(first: 1, contributionTypes: [COMMIT]) { totalCount }
        repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes {
            name url stargazerCount isPrivate
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name color } }
            }
          }
        }
      }
    }
    """
    repos, after, contributed_to = [], None, 0
    while True:
        data = graphql(query, {"login": GITHUB_USERNAME, "after": after})["user"]
        contributed_to = data["repositoriesContributedTo"]["totalCount"]
        page = data["repositories"]
        repos.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    total_stars = sum(r["stargazerCount"] for r in repos)
    return repos, len(repos), total_stars, contributed_to


def get_activity():
    """PR/issue totals plus the last year's contribution calendar.

    The calendar drives both the graph and the streak numbers, so they are
    guaranteed to agree - the old setup fetched them from two separate
    services that could disagree.
    """
    query = """
    query($login: String!) {
      user(login: $login) {
        pullRequests { totalCount }
        issues { totalCount }
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """
    u = graphql(query, {"login": GITHUB_USERNAME})["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [
        {"date": d["date"], "count": d["contributionCount"]}
        for week in cal["weeks"] for d in week["contributionDays"]
    ]
    days.sort(key=lambda d: d["date"])
    return {
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "total_contributions": cal["totalContributions"],
        "calendar": days,
    }


def aggregate_languages(repos, top=6):
    """Language split by bytes across public, non-fork repos."""
    totals, colors = {}, {}
    for repo in repos:
        for edge in (repo.get("languages") or {}).get("edges", []):
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = edge["node"].get("color")
    grand = sum(totals.values())
    if not grand:
        return []
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:top]
    return [{"name": name, "pct": size * 100.0 / grand, "color": colors.get(name)}
            for name, size in ranked]


def get_followers():
    resp = requests.get(f"{REST_URL}/users/{GITHUB_USERNAME}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()["followers"]


def get_lines_of_code(repos):
    """Shallow-clone each public repo and sum numstat additions/deletions by author."""
    additions = deletions = 0
    with tempfile.TemporaryDirectory() as tmp:
        for repo in repos:
            if repo["isPrivate"]:
                continue  # no credentials wired in for private clones
            dest = os.path.join(tmp, repo["name"])
            try:
                subprocess.run(
                    ["git", "clone", "--quiet", "--depth", "500", repo["url"], dest],
                    check=True, timeout=120,
                )
                log = subprocess.run(
                    ["git", "-C", dest, "log", f"--author={GITHUB_USERNAME}",
                     "--pretty=tformat:", "--numstat"],
                    check=True, capture_output=True, text=True, timeout=120,
                ).stdout
                for line in log.splitlines():
                    parts = line.split("\t")
                    if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                        additions += int(parts[0])
                        deletions += int(parts[1])
            except Exception as e:
                print(f"skipping {repo['name']}: {e}")
    return additions, deletions


def main():
    repos, total_repos, total_stars, contributed_to = get_repo_and_star_stats()
    commits = get_commit_total()
    followers = get_followers()

    if SKIP_LOC:
        additions = deletions = 0
    else:
        additions, deletions = get_lines_of_code(repos)

    stats = {
        "repos": total_repos,
        "contributed": contributed_to,
        "stars": total_stars,
        "commits": commits,
        "followers": followers,
        "additions": additions,
        "deletions": deletions,
        "loc_skipped": SKIP_LOC,
        "languages": aggregate_languages(repos),
        **get_activity(),
    }

    # Persist the numbers too, so the card can be re-rendered locally after a
    # design change without needing a token or scraping them back out of the SVG.
    os.makedirs(os.path.dirname(make_card.STATS_PATH) or ".", exist_ok=True)
    with open(make_card.STATS_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(stats, f, indent=2, sort_keys=True)

    make_card.render(stats, CARD_PATH)
    make_stats.render(stats, make_stats.OUT)

    print(f"wrote {CARD_PATH} + {make_stats.OUT} - Repos={total_repos} "
          f"Contributed={contributed_to} Stars={total_stars} Commits={commits} "
          f"Followers={followers} PRs={stats['prs']} Issues={stats['issues']} "
          f"Contributions={stats['total_contributions']} "
          f"Additions={additions} Deletions={deletions}")


if __name__ == "__main__":
    main()
