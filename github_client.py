import requests
import pprint
import os 
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

HEADERS = {
    'Authorization': f'Bearer {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.+json'    
}

# This function fetches pull requests from a specified GitHub repository, handling pagination to retrieve multiple pages of results
def fetch_pull_requests(owner, repo, max_pages=3):
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls'
    
    all_prs = []
    for page in range(1, max_pages + 1):
        params = {
            'state': 'closed', 
            'per_page': 30, 
            'page': page
            }
        response = requests.get(url, headers=HEADERS, params=params)
        
        response.raise_for_status()  # Raise an error for bad responses
        
        prs = response.json()
        if not prs:
            break
        
        all_prs.extend(prs)
    return all_prs


# This function takes a list of pull requests and summarizes key information about each one
def summarize_pr(pr):
    return {
        "number": pr["number"],
        "title": pr["title"],
        "author": pr["user"]["login"],
        "created_at": pr["created_at"],
        "merged_at": pr.get("merged_at") or pr.get("closed_at"),
        "reviewers": [r["login"] for r in pr.get("requested_reviewers", [])],
        "reviewer_count": len(pr.get("requested_reviewers", [])),
        "draft": pr["draft"],
        "labels": [l["name"] for l in pr.get("labels", [])],
    }

def fetch_commits(owner, repo, max_pages=3):
    """
    Fetches recent commits from a repo.
    We'll use this to detect after-hours work patterns and contributor activity.
    """
    all_commits = []

    for page in range(1, max_pages + 1):

        url = f"https://api.github.com/repos/{owner}/{repo}/commits"

        params = {
            "per_page": 30,
            "page": page
        }

        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()

        commits = response.json()

        if not commits:
            break

        all_commits.extend(commits)
        print(f"  Page {page} fetched — {len(all_commits)} commits so far")

    return all_commits


def summarize_commit(commit):
    """
    Extracts the fields we care about from a raw commit object.
    Note: GitHub has two author fields:
      - commit.author = the git author (name + timestamp)
      - author = the GitHub user account (may be None for external contributors)
    """
    github_user = commit.get("author")  # GitHub account — can be None

    return {
        "sha": commit["sha"][:7],  # short hash — like git log --oneline
        "message": commit["commit"]["message"].split("\n")[0],  # first line only
        "author_name": commit["commit"]["author"]["name"],
        "author_login": github_user["login"] if github_user else "unknown",
        "committed_at": commit["commit"]["author"]["date"],
        "hour_of_day": int(commit["commit"]["author"]["date"][11:13]),  # extract hour from ISO timestamp
    }


def fetch_contributors(owner, repo):
    """
    Fetches contributor stats — total commits per person.
    GitHub pre-aggregates this for us, so no pagination needed.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contributors"

    params = { "per_page": 30 }

    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()

    contributors = response.json()

    # List comprehension to extract just what we need
    return [
        {
            "login": c["login"],
            "total_commits": c["contributions"],
            "avatar_url": c["avatar_url"]
        }
        for c in contributors
    ]


def compute_pr_cycle_time(pr):
    """
    Calculates how many days a PR took from open to merge.
    This is your first real engineering metric — delivery speed signal.

    In Java you'd use ChronoUnit.DAYS.between(LocalDateTime, LocalDateTime)
    Python's datetime module works similarly.
    """
    from datetime import datetime

    if not pr.get("merged_at"):
        return None # unmerged PRs don't have a cycle time

    # Python datetime parsing — %Y-%m-%dT%H:%M:%SZ matches "2024-03-01T14:22:00Z"
    created = datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ")
    merged = datetime.strptime(pr["merged_at"], "%Y-%m-%dT%H:%M:%SZ") if pr["merged_at"] else None

    # datetime subtraction gives a timedelta object — .days extracts the integer
    cycle_time = (merged - created).days

    return cycle_time

#this is python main function, it will run when you execute this file directly
if __name__ == "__main__":

    owner = "microsoft"
    repo = "vscode"

    # ── Pull Requests ──────────────────────────────────────
    print("Fetching PRs...")
    raw_prs = fetch_pull_requests(owner, repo, max_pages=2)
    prs = [summarize_pr(pr) for pr in raw_prs]

    # Compute cycle time for each PR
    for pr in prs:
        pr["cycle_time_days"] = compute_pr_cycle_time(pr)

    # Filter to only merged PRs (cycle time is None for unmerged)
    merged_prs = [pr for pr in prs if pr["cycle_time_days"] is not None]

    avg_cycle_time = sum(pr["cycle_time_days"] for pr in merged_prs) / len(merged_prs)

    print(f"\n── PR Summary ──────────────────────────")
    print(f"  Total PRs fetched:   {len(prs)}")
    print(f"  Merged PRs:          {len(merged_prs)}")
    print(f"  Avg cycle time:      {avg_cycle_time:.1f} days")
    print(f"\n  Slowest PRs:")
    # sorted() with key= is like Java's Comparator.comparing()
    slowest = sorted(merged_prs, key=lambda pr: pr["cycle_time_days"], reverse=True)[:3]
    for pr in slowest:
        print(f"    #{pr['pr_number']} by {pr['user']} — {pr['cycle_time_days']} days — {pr['title'][:60]}")

    # ── Commits ───────────────────────────────────────────
    print(f"\nFetching commits...")
    raw_commits = fetch_commits(owner, repo, max_pages=2)
    commits = [summarize_commit(c) for c in raw_commits]

    # After-hours commits = committed between 8pm and 6am
    after_hours = [c for c in commits if c["hour_of_day"] >= 20 or c["hour_of_day"] < 6]
    after_hours_pct = len(after_hours) / len(commits) * 100

    print(f"\n── Commit Summary ──────────────────────")
    print(f"  Total commits:       {len(commits)}")
    print(f"  After-hours commits: {len(after_hours)} ({after_hours_pct:.1f}%)")

    # ── Contributors ──────────────────────────────────────
    print(f"\nFetching contributors...")
    contributors = fetch_contributors(owner, repo)

    print(f"\n── Top Contributors ────────────────────")
    for c in contributors[:5]:
        print(f"  {c['login']:<20} {c['total_commits']} commits")