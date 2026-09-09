"""The lead-generation vertical.

Three guarantees are asserted here rather than documented, because all three
concern personal data and a comment enforces nothing:

  1. nothing in this module sends,
  2. a suppressed address is never drafted for,
  3. a prospect with no recorded provenance is never drafted for.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pfa.leads import (
    COLUMNS,
    LeadsError,
    Prospect,
    Suppression,
    draft_for,
    draft_path,
    draft_prompt,
    init_private_dir,
    load_prospects,
    normalise_email,
    preflight,
    private_dir,
)

COMPLETE = {
    "email": "ada@example.com",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "role": "CTO",
    "company": "Example Analytical",
    "source": "conference attendee list published by the organiser",
    "collected_at": "2026-09-01",
    "trigger": "posted a role mentioning GDPR",
    "trigger_source": "their careers page",
    "notes": "",
}


def write_prospects(path: Path, *rows: dict) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in COLUMNS})
    return path


@pytest.fixture
def private(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "private"
    root.mkdir()
    monkeypatch.setenv("PFA_PRIVATE_DIR", str(root))
    return root


class TestPrivateDir:
    def test_defaults_to_private(self, monkeypatch):
        monkeypatch.delenv("PFA_PRIVATE_DIR", raising=False)
        assert private_dir() == Path("private")

    def test_env_var_overrides(self, private):
        assert private_dir() == private


class TestNormalisation:
    def test_lowercases_and_strips(self):
        assert normalise_email("  Ada@Example.COM ") == "ada@example.com"

    def test_does_not_strip_plus_tags(self):
        """Provider-specific rules; a wrong guess re-contacts someone who objected."""
        assert normalise_email("ada+news@example.com") == "ada+news@example.com"


class TestLoading:
    def test_reads_a_complete_row(self, private):
        write_prospects(private / "prospects.csv", COMPLETE)
        (prospect,) = load_prospects()
        assert prospect.email == "ada@example.com"
        assert prospect.name == "Ada Lovelace"
        assert prospect.blockers() == ()

    def test_missing_file_names_the_command_that_fixes_it(self, private):
        with pytest.raises(LeadsError, match="pfa leads init"):
            load_prospects()

    def test_missing_required_column_is_reported(self, private):
        path = private / "prospects.csv"
        path.write_text("email,first_name\nada@example.com,Ada\n", encoding="utf-8")
        with pytest.raises(LeadsError, match="source, collected_at"):
            load_prospects()

    def test_comment_lines_are_ignored(self, private):
        """The file carries a banner saying it is personal data; that is not a header."""
        path = write_prospects(private / "prospects.csv", COMPLETE)
        path.write_text("# PERSONAL DATA\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
        assert len(load_prospects()) == 1

    def test_row_numbers_point_at_the_real_line(self, private):
        path = write_prospects(private / "prospects.csv", COMPLETE)
        path.write_text("# one\n# two\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
        (prospect,) = load_prospects()
        assert prospect.row == 4  # two comments, the header, then the row

    def test_blank_rows_are_skipped(self, private):
        path = write_prospects(private / "prospects.csv", COMPLETE)
        path.write_text(path.read_text(encoding="utf-8") + ",,,,,,,,,\n", encoding="utf-8")
        assert len(load_prospects()) == 1

    def test_addresses_are_normalised_on_load(self, private):
        write_prospects(private / "prospects.csv", {**COMPLETE, "email": " ADA@Example.com "})
        assert load_prospects()[0].email == "ada@example.com"


class TestBlockers:
    def test_a_complete_prospect_has_none(self):
        assert Prospect(**COMPLETE).blockers() == ()

    def test_missing_source_blocks(self):
        """Article 14: you must say where the data came from."""
        blockers = Prospect(**{**COMPLETE, "source": ""}).blockers()
        assert any("Article 14" in blocker for blocker in blockers)

    def test_missing_collected_at_blocks(self):
        blockers = Prospect(**{**COMPLETE, "collected_at": ""}).blockers()
        assert any("collected_at" in blocker for blocker in blockers)

    def test_non_iso_collected_at_blocks(self):
        blockers = Prospect(**{**COMPLETE, "collected_at": "last tuesday"}).blockers()
        assert any("YYYY-MM-DD" in blocker for blocker in blockers)

    def test_implausible_address_blocks(self):
        assert Prospect(**{**COMPLETE, "email": "not-an-address"}).blockers()

    def test_missing_trigger_warns_but_does_not_block(self):
        """A weak message is a quality problem; an unlawful one is not."""
        prospect = Prospect(**{**COMPLETE, "trigger": "", "trigger_source": ""})
        assert prospect.blockers() == ()
        assert any("trigger" in warning for warning in prospect.warnings())

    def test_a_trigger_without_a_source_warns(self):
        prospect = Prospect(**{**COMPLETE, "trigger_source": ""})
        assert any("unverifiable" in warning for warning in prospect.warnings())


class TestSuppression:
    def test_missing_file_is_an_empty_list(self, tmp_path):
        assert Suppression.load(tmp_path / "absent.txt").entries == set()

    def test_ignores_comments_and_blank_lines(self, tmp_path):
        path = tmp_path / "suppression.txt"
        path.write_text("# header\n\nada@example.com  # objected\n", encoding="utf-8")
        suppression = Suppression.load(path)
        assert suppression.entries == {"ada@example.com"}

    def test_matching_is_case_insensitive(self, tmp_path):
        path = tmp_path / "s.txt"
        path.write_text("ada@example.com\n", encoding="utf-8")
        assert Suppression.load(path).contains("ADA@Example.COM")

    def test_add_appends_and_is_idempotent(self, tmp_path):
        path = tmp_path / "s.txt"
        suppression = Suppression.load(path)
        assert suppression.add("ada@example.com", "asked to stop") is True
        assert suppression.add("ADA@example.com") is False
        assert path.read_text(encoding="utf-8").count("ada@example.com") == 1

    def test_add_records_the_date_and_reason(self, tmp_path):
        suppression = Suppression.load(tmp_path / "s.txt")
        suppression.add("ada@example.com", "replied stop")
        assert "replied stop" in suppression.path.read_text(encoding="utf-8")

    def test_add_refuses_an_empty_address(self, tmp_path):
        with pytest.raises(LeadsError):
            Suppression.load(tmp_path / "s.txt").add("   ")


class TestPreflight:
    def test_classifies_each_prospect(self, tmp_path):
        prospects = [
            Prospect(**COMPLETE),
            Prospect(**{**COMPLETE, "email": "b@example.com", "source": ""}),
            Prospect(**{**COMPLETE, "email": "c@example.com", "trigger": ""}),
            Prospect(**{**COMPLETE, "email": "d@example.com"}),
        ]
        suppression = Suppression.load(tmp_path / "s.txt")
        suppression.add("d@example.com")
        report = preflight(prospects, suppression)
        assert report.counts() == {"ready": 1, "weak": 1, "blocked": 1, "suppressed": 1}

    def test_suppression_short_circuits_other_problems(self, tmp_path):
        """Someone who objected is not a data-quality problem to be fixed."""
        suppression = Suppression.load(tmp_path / "s.txt")
        suppression.add("ada@example.com")
        report = preflight([Prospect(**{**COMPLETE, "source": ""})], suppression)
        entry = report.entries[0]
        assert entry.suppressed and entry.blockers == () and entry.state == "suppressed"

    def test_duplicates_are_reported(self, tmp_path):
        report = preflight(
            [Prospect(**COMPLETE), Prospect(**COMPLETE)],
            Suppression.load(tmp_path / "s.txt"),
        )
        assert report.duplicates == ("ada@example.com",)

    def test_only_ready_and_weak_prospects_are_draftable(self, tmp_path):
        report = preflight(
            [Prospect(**COMPLETE), Prospect(**{**COMPLETE, "email": "b@e.com", "source": ""})],
            Suppression.load(tmp_path / "s.txt"),
        )
        assert [entry.prospect.email for entry in report.draftable] == ["ada@example.com"]


class TestDraftPrompt:
    def test_states_the_provenance(self):
        prompt = draft_prompt(Prospect(**COMPLETE))
        assert COMPLETE["source"] in prompt
        assert "Article 14" in prompt

    def test_forbids_invention(self):
        prompt = draft_prompt(Prospect(**COMPLETE))
        assert "do not invent" in prompt.lower()

    def test_says_it_will_not_be_sent(self):
        assert "not be sent" in draft_prompt(Prospect(**COMPLETE)).lower()

    def test_flags_a_trigger_with_no_source(self):
        prompt = draft_prompt(Prospect(**{**COMPLETE, "trigger_source": ""}))
        assert "NO SOURCE RECORDED" in prompt


class TestDrafting:
    def test_refuses_a_suppressed_prospect(self, tmp_path, policy_file):
        """The guarantee that has to hold even for a caller that skipped preflight."""
        from pfa.config import load_config

        suppression = Suppression.load(tmp_path / "s.txt")
        suppression.add("ada@example.com")
        with pytest.raises(LeadsError, match="permanent"):
            draft_for(
                Prospect(**COMPLETE),
                load_config(policy_file),
                suppression=suppression,
                drafts_root=tmp_path / "drafts",
            )

    def test_refuses_a_prospect_with_no_provenance(self, tmp_path, policy_file):
        from pfa.config import load_config

        with pytest.raises(LeadsError, match="Article 14"):
            draft_for(
                Prospect(**{**COMPLETE, "source": ""}),
                load_config(policy_file),
                suppression=Suppression.load(tmp_path / "s.txt"),
                drafts_root=tmp_path / "drafts",
            )

    def test_writes_a_draft_marked_as_not_sent(self, tmp_path, policy_with_skills, monkeypatch):
        from pfa.config import load_config
        from pfa.observability import RunRecord
        from pfa.router import route
        from pfa.runner import RunResult

        config = load_config(policy_with_skills)
        decision = route("x", config, task="coding")

        captured: dict = {}

        def fake_run_task(text, cfg, **kwargs):
            captured.update(kwargs)
            return RunResult(
                decision=decision,
                record=RunRecord(status="success", exit_code=0),
                stdout="Subject: a short specific line\n\nBody of the draft.",
            )

        monkeypatch.setattr("pfa.leads.run_task", fake_run_task)
        path, result = draft_for(
            Prospect(**COMPLETE),
            config,
            suppression=Suppression.load(tmp_path / "s.txt"),
            drafts_root=tmp_path / "drafts",
        )
        body = path.read_text(encoding="utf-8")
        # The route is forced rather than classified: a prospect's own words
        # must never decide which model sees their data.
        assert captured["task"] == "prospecting"
        assert captured["skills"] == ["outreach-writing"]
        assert result.ok
        assert "awaiting human review. Not sent." in body
        assert "Body of the draft." in body
        assert COMPLETE["source"] in body

    def test_draft_path_is_dated_and_slugged(self):
        from datetime import date

        path = draft_path(Prospect(**COMPLETE), Path("/drafts"), on=date(2026, 9, 9))
        assert path == Path("/drafts/2026-09-09/ada-example-com.md")


class TestNothingSends:
    """The structural guarantee: there is no send path in this module at all."""

    def test_the_module_names_no_transport(self):
        source = Path("src/pfa/leads.py").read_text(encoding="utf-8")
        for forbidden in ("smtplib", "sendmail", "urllib.request", "requests", "httpx"):
            assert forbidden not in source, f"leads.py must not import {forbidden}"

    def test_no_public_function_is_named_send(self):
        import pfa.leads as module

        assert not [name for name in dir(module) if name.startswith("send")]


class TestInit:
    def test_creates_both_files(self, private):
        prospects, suppression = init_private_dir()
        assert prospects.is_file() and suppression.is_file()

    def test_the_template_row_parses(self, private):
        init_private_dir()
        (prospect,) = load_prospects()
        assert prospect.blockers() == ()

    def test_the_template_uses_an_example_address(self, private):
        """A template shipped with a real address would be a real person."""
        init_private_dir()
        assert load_prospects()[0].email.endswith("@example.com")

    def test_refuses_to_overwrite(self, private):
        init_private_dir()
        with pytest.raises(LeadsError, match="Refusing to overwrite"):
            init_private_dir()
