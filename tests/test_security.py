# PFA-ALLOW-SECRET-FIXTURES: contains synthetic credential-shaped strings by design.
"""Security tests.

This repository is meant to be public. These tests are the automated half of
that promise: they fail the build if the tree drifts toward leaking anything.

They assert on the repository as committed, not on runtime behaviour.
"""

from __future__ import annotations

import re
import subprocess

import pytest

# Credential SHAPES. Matching on the word "token" produces noise; matching on
# `ghp_` followed by 30+ characters does not.
CREDENTIAL_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\d{8,10}:AA[A-Za-z0-9_-]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"postgres(?:ql)?://[^:\s]+:[^@\s]{6,}@"),
]

# A file that legitimately contains credential-shaped text declares itself with
# this marker. Self-declaration beats a central exclude list, which silently
# drifts out of date the moment someone adds a test.
FIXTURE_MARKER = "PFA-ALLOW-SECRET-FIXTURES"


def tracked_files(repo_root) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


class TestNoCredentialsInTree:
    def test_no_tracked_file_contains_a_credential(self, repo_root):
        offenders = []
        for relative in tracked_files(repo_root):
            path = repo_root / relative
            if not path.is_file():
                continue
            try:
                body = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if FIXTURE_MARKER in body:
                continue
            for pattern in CREDENTIAL_PATTERNS:
                if pattern.search(body):
                    offenders.append(f"{relative}: matched {pattern.pattern}")
        assert not offenders, "credential-shaped content in tracked files: " + "; ".join(offenders)

    def test_dotenv_is_not_tracked(self, repo_root):
        assert ".env" not in tracked_files(repo_root), ".env must never be committed"

    def test_no_sqlite_database_is_tracked(self, repo_root):
        offenders = [
            f for f in tracked_files(repo_root) if f.endswith((".db", ".sqlite", ".sqlite3"))
        ]
        assert not offenders, f"agent state databases must not be committed: {offenders}"


class TestGitignoreCoverage:
    REQUIRED = [
        ".env",
        "*.db",
        "private/",
        "var/",
        "*.pem",
        "*.key",
        "node_modules/",
        "__pycache__/",
        ".hermes/",
    ]

    @pytest.mark.parametrize("pattern", REQUIRED)
    def test_pattern_is_ignored(self, repo_root, pattern):
        body = (repo_root / ".gitignore").read_text(encoding="utf-8")
        assert pattern in body, f".gitignore must cover {pattern}"

    def test_env_example_is_explicitly_re_included(self, repo_root):
        body = (repo_root / ".gitignore").read_text(encoding="utf-8")
        assert "!.env.example" in body, "the template must stay committed"


class TestEnvExample:
    def test_exists(self, repo_root):
        assert (repo_root / ".env.example").is_file()

    def test_contains_only_placeholders(self, repo_root):
        body = (repo_root / ".env.example").read_text(encoding="utf-8")
        for pattern in CREDENTIAL_PATTERNS:
            assert not pattern.search(body), f".env.example matched {pattern.pattern}"

    def test_marks_secrets_for_replacement(self, repo_root):
        body = (repo_root / ".env.example").read_text(encoding="utf-8")
        assert "REPLACE_ME" in body

    def test_documents_every_variable_the_policy_references(self, repo_root):
        from pfa.config import load_config

        config = load_config(repo_root / "config" / "routing.yaml")
        body = (repo_root / ".env.example").read_text(encoding="utf-8")
        for provider in config.providers.values():
            assert provider.api_key_env in body, (
                f"{provider.api_key_env} is referenced by the policy but "
                f"undocumented in .env.example"
            )


class TestNoPrivateDataInSkills:
    """Skills are procedures. Personal or client data belongs nowhere near them."""

    def test_skills_contain_no_credentials(self, repo_root):
        skills_dir = repo_root / "skills"
        if not skills_dir.is_dir():
            pytest.skip("no skills directory yet")
        for path in skills_dir.rglob("*.md"):
            body = path.read_text(encoding="utf-8")
            for pattern in CREDENTIAL_PATTERNS:
                assert not pattern.search(body), f"{path} matched {pattern.pattern}"

    def test_no_skill_names_a_client_specific_host_or_path(self, repo_root):
        """Skills are committed to a public repository; they must stay generic.

        Shape-based, like the credential scan: an absolute home directory or a
        non-example hostname in a procedure means a real engagement leaked in.
        """

        suspicious = [
            re.compile(r"/(?:home|Users)/(?!user\b)[a-z][a-z0-9_-]{2,}/"),
            re.compile(
                r"https?://(?!(?:[a-z0-9.-]*\.)?(?:example\.(?:com|org|invalid)|"
                r"localhost|agentskills\.io|hermes-agent\.nousresearch\.com|"
                r"github\.com|nousresearch\.com))[a-z0-9.-]+\.[a-z]{2,}"
            ),
        ]
        offenders = []
        for path in sorted((repo_root / "skills").rglob("*.md")):
            body = path.read_text(encoding="utf-8")
            for pattern in suspicious:
                for match in pattern.findall(body):
                    offenders.append(f"{path.relative_to(repo_root)}: {match}")
        assert not offenders, "client-specific detail in a public skill: " + "; ".join(offenders)

    def test_every_skill_is_well_formed(self, repo_root):
        """A skill that does not parse is one Hermes silently will not load."""
        from pfa.skills import discover

        library = discover(repo_root / "skills")
        assert not library.problems, [p.to_dict() for p in library.problems]

    def test_no_prospect_or_client_list_is_tracked(self, repo_root):
        forbidden = {"prospects.yaml", "prospects.yml", "clients.yaml", "clients.yml"}
        offenders = [f for f in tracked_files(repo_root) if f.split("/")[-1] in forbidden]
        assert not offenders, f"personal target lists must stay out of the repo: {offenders}"


class TestSecretScannerScript:
    def test_script_is_executable_and_passes_on_a_clean_tree(self, repo_root):
        script = repo_root / "scripts" / "check-secrets.sh"
        assert script.is_file()
        result = subprocess.run(
            ["bash", str(script)], cwd=repo_root, capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, f"secret scanner failed:\n{result.stdout}\n{result.stderr}"
