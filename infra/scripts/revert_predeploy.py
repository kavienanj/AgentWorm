#!/usr/bin/env python3
"""Reset the webapp repo to the known-clean commit via GitHub API force-push."""
import sys
import json
import urllib.request
import urllib.error

CLEAN_SHA = "5577a6f044a9aa109cb314e0721168083f78321b"


def reset_repo(token: str, repo: str) -> None:
    url = f"https://api.github.com/repos/{repo}/git/refs/heads/main"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "agentworm-reset",
    }

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        ref = json.loads(resp.read())

    current_sha = ref["object"]["sha"]
    if current_sha == CLEAN_SHA:
        print(f"Repo already at clean commit {CLEAN_SHA[:7]} — nothing to do.")
        return

    print(f"Current HEAD: {current_sha[:7]} — force-resetting to {CLEAN_SHA[:7]}...")

    payload = json.dumps({"sha": CLEAN_SHA, "force": True}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={**headers, "Content-Type": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    print(f"Reset to {result['object']['sha'][:7]}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: revert_predeploy.py <github_token> <owner/repo>")
        sys.exit(1)
    reset_repo(sys.argv[1], sys.argv[2])
