"""
Unit tests for the pure-logic parts of explain.py (no git/network required).

Run with:
    pip install pytest
    pytest tests/
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from explain import extract_references, parse_github_slug, build_summary_prompt


class TestExtractReferences:
    def test_no_references(self):
        refs = extract_references("just a normal commit message")
        assert refs["all"] == []
        assert refs["closes"] == []

    def test_single_reference(self):
        refs = extract_references("related to #123")
        assert refs["all"] == [123]
        assert refs["closes"] == []

    def test_closes_keyword(self):
        refs = extract_references("Fixes #42 and cleans up logging")
        assert refs["all"] == [42]
        assert refs["closes"] == [42]

    def test_closes_keyword_case_insensitive(self):
        refs = extract_references("CLOSES #7")
        assert refs["closes"] == [7]

    def test_resolves_keyword(self):
        refs = extract_references("resolves #99")
        assert refs["closes"] == [99]

    def test_multiple_references_deduplicated_and_sorted(self):
        refs = extract_references("see #10, also #3, and again #10")
        assert refs["all"] == [3, 10]

    def test_closes_is_subset_of_all(self):
        refs = extract_references("mentions #5, fixes #6")
        assert refs["all"] == [5, 6]
        assert refs["closes"] == [6]

    def test_empty_string(self):
        refs = extract_references("")
        assert refs["all"] == []
        assert refs["closes"] == []


class TestParseGithubSlug:
    def test_https_url(self):
        assert parse_github_slug("https://github.com/psf/requests") == "psf/requests"

    def test_https_url_with_git_suffix(self):
        assert parse_github_slug("https://github.com/psf/requests.git") == "psf/requests"

    def test_ssh_url(self):
        assert parse_github_slug("git@github.com:psf/requests.git") == "psf/requests"

    def test_non_github_url_returns_none(self):
        assert parse_github_slug("https://gitlab.com/psf/requests.git") is None

    def test_malformed_url_returns_none(self):
        assert parse_github_slug("not a url") is None


class TestBuildSummaryPrompt:
    def test_includes_commit_summary(self):
        blame_info = {"summary": "package refactor"}
        prompt = build_summary_prompt(blame_info, [])
        assert "package refactor" in prompt

    def test_includes_ref_title_and_body(self):
        blame_info = {"summary": "fix bug"}
        ref_details = [
            {"type": "PR", "number": 42, "title": "Fix the thing", "body": "details here"}
        ]
        prompt = build_summary_prompt(blame_info, ref_details)
        assert "PR #42 title: Fix the thing" in prompt
        assert "PR #42 body: details here" in prompt

    def test_skips_empty_body(self):
        blame_info = {"summary": "fix bug"}
        ref_details = [{"type": "Issue", "number": 5, "title": "Bug report", "body": ""}]
        prompt = build_summary_prompt(blame_info, ref_details)
        assert "Issue #5 title: Bug report" in prompt
        assert "body" not in prompt
