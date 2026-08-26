# code-context-explainer

A CLI tool that shows *why* a specific line of code looks the way it does,
by connecting `git blame` with the linked PR/issue.

## Why

When you hit unfamiliar legacy code, figuring out "who wrote this and why"
usually means manually chasing `git blame` -> commit message -> PR -> issue.
This tool automates that chase.

## Usage

```bash
export GITHUB_TOKEN=your_token_here  # optional, raises the API rate limit
python explain.py path/to/file.py:42
```

## Use it as a GitHub Action

Add this to a workflow in your own repo to explain a specific line
(e.g. triggered by a `/explain path:line` comment on an issue or PR):

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0  # required: git blame needs full history

- uses: jakep-me/code-context-explainer@main
  id: explain
  with:
    target: src/app.py:42

- run: echo "${{ steps.explain.outputs.result }}"
```

## Current scope (v1)

- Finds the last commit that touched a given line via `git blame`
- Extracts PR/issue references like `#123` from the commit message
- Fetches the linked PR/issue title, state, and URL via the GitHub API
- If no reference is found, it says so explicitly instead of guessing

## Not yet supported

- Non-GitHub issue trackers (e.g. Jira)
- Squash-merged history where context is flattened
- LLM-based natural language summaries (planned for v2)
- Running inside a fork: PR/issue numbers resolve against the current
  repo, so a reference inherited from the upstream repo (e.g. `#7505`
  from `psf/requests`) won't be found in a fork. The number is still
  reported, just without title/state/URL.

## Contributing

This is an early-stage project. Issues and PRs are welcome, especially
around edge cases in commit message parsing.