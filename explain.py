#!/usr/bin/env python3
"""
code-context-explainer
Shows why a specific line of code looks the way it does, by connecting
git blame with the linked PR/issue.

Usage:
    python explain.py <file>:<line>
    python explain.py user.py:42
"""

import subprocess
import re
import sys
import os
import json
import urllib.request
import urllib.error


def run_git_blame(filepath, line):
    """Get blame info for the given line via git blame."""
    try:
        result = subprocess.run(
            ["git", "blame", "-L", f"{line},{line}", "--porcelain", filepath],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"git blame failed: {e.stderr}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("git is not installed or not in PATH.", file=sys.stderr)
        return None

    lines = result.stdout.splitlines()
    if not lines:
        return None

    commit_hash = lines[0].split()[0]

    info = {"commit": commit_hash}
    for l in lines[1:]:
        if l.startswith("author "):
            info["author"] = l[len("author "):]
        elif l.startswith("author-time "):
            info["author_time"] = l[len("author-time "):]
        elif l.startswith("summary "):
            info["summary"] = l[len("summary "):]
        if l.startswith("\t"):
            break

    return info


def get_full_commit_message(commit_hash):
    """Get the full commit message (including body) for a commit hash."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B", commit_hash],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def extract_references(text):
    """Extract PR/issue references from a commit message.

    Supported patterns:
        #123
        fixes #123, closes #123, resolves #123
    """
    all_refs = sorted(set(int(n) for n in re.findall(r"#(\d+)", text)))

    closes_pattern = re.compile(
        r"(?:fixes|closes|resolves)\s+#(\d+)", re.IGNORECASE
    )
    closes_refs = sorted(set(int(n) for n in closes_pattern.findall(text)))

    return {"all": all_refs, "closes": closes_refs}


def parse_github_slug(url):
    """Parse owner/repo out of a GitHub remote URL. Pure function, no I/O."""
    match = re.search(r"github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?$", url)
    if not match:
        return None
    return f"{match.group(1)}/{match.group(2)}"


def get_repo_slug():
    """Extract owner/repo from the current directory's git remote (GitHub only, v1)."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None

    return parse_github_slug(result.stdout.strip())


def fetch_github_issue_or_pr(repo_slug, number, token):
    """Fetch issue/PR info from the GitHub API.

    Issues and PRs share the same endpoint (/issues/{number}).
    For PRs, the response contains a 'pull_request' key.
    """
    url = f"https://api.github.com/repos/{repo_slug}/issues/{number}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(
                "Hit the GitHub API rate limit. Set a GITHUB_TOKEN "
                "environment variable to raise the limit.",
                file=sys.stderr,
            )
        elif e.code == 404:
            pass
        else:
            print(f"GitHub API error ({e.code}): {number}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        return None

    is_pr = "pull_request" in data
    return {
        "number": number,
        "type": "PR" if is_pr else "Issue",
        "title": data.get("title", ""),
        "state": data.get("state", ""),
        "url": data.get("html_url", ""),
        "body": (data.get("body") or "")[:300],
    }


def format_output(filepath, line, blame_info, refs, ref_details):
    out = []
    out.append(f"File: {filepath}:{line}")
    out.append(f"Commit: {blame_info['commit'][:8]}")
    out.append(f"Author: {blame_info.get('author', 'unknown')}")
    out.append(f"Summary: {blame_info.get('summary', '')}")
    out.append("")

    if not refs["all"]:
        out.append("-> No PR/issue linked in this commit (not in source).")
        return "\n".join(out)

    if not ref_details:
        out.append(f"-> Referenced numbers found ({refs['all']}) but could not fetch details.")
        return "\n".join(out)

    for ref in ref_details:
        marker = "closes" if ref["number"] in refs["closes"] else "related"
        out.append(f"-> [{marker}] {ref['type']} #{ref['number']} ({ref['state']}): {ref['title']}")
        out.append(f"   {ref['url']}")

    return "\n".join(out)


def main():
    if len(sys.argv) != 2 or ":" not in sys.argv[1]:
        print("Usage: python explain.py <file>:<line>", file=sys.stderr)
        print("Example: python explain.py user.py:42", file=sys.stderr)
        sys.exit(1)

    arg = sys.argv[1]
    filepath, _, line_str = arg.rpartition(":")
    try:
        line = int(line_str)
    except ValueError:
        print(f"Invalid line number: {line_str}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(filepath):
        print(f"File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    blame_info = run_git_blame(filepath, line)
    if blame_info is None:
        print("Could not get blame info.", file=sys.stderr)
        sys.exit(1)

    full_message = get_full_commit_message(blame_info["commit"])
    refs = extract_references(full_message)

    ref_details = []
    if refs["all"]:
        repo_slug = get_repo_slug()
        if repo_slug is None:
            print(
                "Could not determine GitHub repo (check origin remote). "
                "Showing PR/issue numbers only.",
                file=sys.stderr,
            )
        else:
            token = os.environ.get("GITHUB_TOKEN")
            for num in refs["all"]:
                info = fetch_github_issue_or_pr(repo_slug, num, token)
                if info:
                    ref_details.append(info)

    print(format_output(filepath, line, blame_info, refs, ref_details))


if __name__ == "__main__":
    main()