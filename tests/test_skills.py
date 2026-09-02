"""The skill library: parsing, validation, resolution and installation.

Every test here builds its own throwaway library under `tmp_path`. Nothing
asserts on the skills this repository ships except the two classes at the end,
which are deliberately about the shipped library as committed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_skill

from pfa.config import load_config
from pfa.doctor import FAIL, PASS, SKIP, WARN, check_skills
from pfa.errors import SkillError
from pfa.skills import (
    Library,
    discover,
    install,
    install_state,
    load_skill,
    resolve,
    skills_dir,
    split_frontmatter,
)


class TestFrontmatter:
    def test_splits_metadata_from_body(self):
        front, body = split_frontmatter("---\nname: x\n---\n\n# Body\n")
        assert front == {"name": "x"}
        assert body.strip() == "# Body"

    def test_missing_fence_is_an_error(self):
        with pytest.raises(SkillError, match="missing YAML frontmatter"):
            split_frontmatter("# Just markdown\n")

    def test_unparseable_yaml_names_the_problem(self):
        with pytest.raises(SkillError, match="not valid YAML"):
            split_frontmatter("---\nname: [unclosed\n---\nbody\n")

    def test_scalar_frontmatter_is_rejected(self):
        with pytest.raises(SkillError, match="must be a mapping"):
            split_frontmatter("---\njust a string\n---\nbody\n")

    def test_tolerates_a_byte_order_mark(self):
        front, _ = split_frontmatter("﻿---\nname: x\n---\nbody\n")
        assert front["name"] == "x"


class TestLoadSkill:
    def test_reads_name_version_description_and_tags(self, tmp_path):
        path = write_skill(tmp_path, "alpha-procedure", description="Does alpha things.")
        skill = load_skill(path)
        assert skill.name == "alpha-procedure"
        assert skill.category == "fde"
        assert skill.version == "1.0.0"
        assert skill.description == "Does alpha things."
        assert skill.tags == ("test",)
        assert skill.reference == "fde/alpha-procedure"

    def test_body_excludes_the_frontmatter(self, tmp_path):
        path = write_skill(tmp_path, "alpha-procedure", body="# Procedure\n\nStep one.\n")
        assert "name:" not in load_skill(path).body()
        assert "Step one." in load_skill(path).body()

    @pytest.mark.parametrize("key", ["name", "description", "version"])
    def test_missing_required_key_is_reported_by_name(self, tmp_path, key):
        path = write_skill(tmp_path, "alpha-procedure")
        text = path.read_text(encoding="utf-8")
        stripped = "\n".join(line for line in text.splitlines() if not line.startswith(f"{key}:"))
        path.write_text(stripped, encoding="utf-8")
        with pytest.raises(SkillError, match=key):
            load_skill(path)

    def test_frontmatter_name_must_match_the_directory(self, tmp_path):
        # The two are how a skill is addressed — by `--skill <name>` and by the
        # path Hermes loads. Disagreement means one of them silently misses.
        path = write_skill(tmp_path, "alpha-procedure", frontmatter_name="something-else")
        with pytest.raises(SkillError, match="does not match its directory"):
            load_skill(path)

    def test_name_must_be_hyphenated_lowercase(self, tmp_path):
        path = write_skill(tmp_path, "Alpha_Procedure", frontmatter_name="Alpha_Procedure")
        with pytest.raises(SkillError, match="lowercase words joined by hyphens"):
            load_skill(path)

    def test_version_must_be_major_minor_patch(self, tmp_path):
        path = write_skill(tmp_path, "alpha-procedure", version="1.0")
        with pytest.raises(SkillError, match="MAJOR.MINOR.PATCH"):
            load_skill(path)

    def test_empty_body_is_rejected(self, tmp_path):
        path = write_skill(tmp_path, "alpha-procedure", body="   \n")
        with pytest.raises(SkillError, match="no body"):
            load_skill(path)

    def test_declared_category_must_match_the_directory(self, tmp_path):
        path = write_skill(tmp_path, "alpha-procedure", category="fde")
        path.write_text(
            path.read_text(encoding="utf-8").replace("category: fde", "category: elsewhere"),
            encoding="utf-8",
        )
        with pytest.raises(SkillError, match="but the skill sits under"):
            load_skill(path)


class TestDiscover:
    def test_finds_every_skill_sorted(self, tmp_path):
        write_skill(tmp_path, "beta-procedure")
        write_skill(tmp_path, "alpha-procedure")
        library = discover(tmp_path)
        assert library.names == ("alpha-procedure", "beta-procedure")
        assert library.problems == ()

    def test_a_broken_skill_does_not_hide_the_working_ones(self, tmp_path):
        write_skill(tmp_path, "alpha-procedure")
        broken = tmp_path / "fde" / "broken-procedure"
        broken.mkdir(parents=True)
        (broken / "SKILL.md").write_text("no frontmatter here\n", encoding="utf-8")

        library = discover(tmp_path)
        assert library.names == ("alpha-procedure",)
        assert len(library.problems) == 1
        assert "frontmatter" in library.problems[0].message

    def test_reports_a_directory_with_no_skill_file(self, tmp_path):
        write_skill(tmp_path, "alpha-procedure")
        (tmp_path / "fde" / "empty-procedure").mkdir(parents=True)
        library = discover(tmp_path)
        assert any("no SKILL.md" in p.message for p in library.problems)

    def test_duplicate_names_across_categories_are_reported(self, tmp_path):
        write_skill(tmp_path, "alpha-procedure", category="fde")
        write_skill(tmp_path, "alpha-procedure", category="other")
        library = discover(tmp_path)
        assert len(library.skills) == 1
        assert any("duplicate skill name" in p.message for p in library.problems)

    def test_absent_directory_is_empty_not_an_error(self, tmp_path):
        library = discover(tmp_path / "nothing-here")
        assert library.skills == () and library.problems == ()

    def test_honours_pfa_skills_dir(self, tmp_path, monkeypatch):
        write_skill(tmp_path, "alpha-procedure")
        monkeypatch.setenv("PFA_SKILLS_DIR", str(tmp_path))
        assert skills_dir() == tmp_path
        assert discover().names == ("alpha-procedure",)


class TestRequire:
    def test_returns_the_skill(self, tmp_path):
        write_skill(tmp_path, "alpha-procedure")
        assert discover(tmp_path).require("alpha-procedure").name == "alpha-procedure"

    def test_unknown_name_lists_what_is_available(self, tmp_path):
        write_skill(tmp_path, "alpha-procedure")
        with pytest.raises(SkillError, match="Available: alpha-procedure"):
            discover(tmp_path).require("nope")

    def test_empty_library_says_where_it_looked(self, tmp_path):
        with pytest.raises(SkillError, match="no skills loaded from"):
            discover(tmp_path).require("nope")


class TestResolve:
    def test_preserves_order_and_drops_duplicates(self, tmp_path):
        write_skill(tmp_path, "alpha-procedure")
        write_skill(tmp_path, "beta-procedure")
        library = discover(tmp_path)
        resolved = resolve(["beta-procedure", "alpha-procedure", "beta-procedure"], library)
        assert resolved == ("beta-procedure", "alpha-procedure")

    def test_an_unknown_name_is_rejected(self, tmp_path):
        write_skill(tmp_path, "alpha-procedure")
        with pytest.raises(SkillError):
            resolve(["alpha-procedure", "typo"], discover(tmp_path))

    def test_nothing_requested_never_touches_the_library(self):
        # An empty request must not depend on a library existing at all.
        assert resolve([], Library(root=Path("/nonexistent"))) == ()


class TestInstall:
    def test_copies_into_the_hermes_tree(self, tmp_path):
        source = tmp_path / "skills"
        write_skill(source, "alpha-procedure")
        home = tmp_path / "hermes"

        written = install(discover(source), home)
        target = home / "skills" / "fde" / "alpha-procedure" / "SKILL.md"
        assert written == [target]
        assert target.read_text(encoding="utf-8") == (
            source / "fde" / "alpha-procedure" / "SKILL.md"
        ).read_text(encoding="utf-8")

    def test_carries_reference_files_beside_the_procedure(self, tmp_path):
        source = tmp_path / "skills"
        write_skill(source, "alpha-procedure")
        (source / "fde" / "alpha-procedure" / "checklist.md").write_text(
            "- one\n", encoding="utf-8"
        )
        home = tmp_path / "hermes"

        install(discover(source), home)
        assert (home / "skills" / "fde" / "alpha-procedure" / "checklist.md").is_file()

    def test_overwrites_because_the_repository_is_the_source_of_truth(self, tmp_path):
        source = tmp_path / "skills"
        write_skill(source, "alpha-procedure", body="# New\n\nCurrent procedure.\n")
        home = tmp_path / "hermes"
        target = home / "skills" / "fde" / "alpha-procedure"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("stale content", encoding="utf-8")

        install(discover(source), home)
        assert "Current procedure." in (target / "SKILL.md").read_text(encoding="utf-8")

    def test_an_empty_library_refuses_rather_than_silently_doing_nothing(self, tmp_path):
        with pytest.raises(SkillError, match="No valid skills to install"):
            install(discover(tmp_path / "empty"), tmp_path / "hermes")

    def test_invalid_skills_are_skipped_not_half_copied(self, tmp_path):
        source = tmp_path / "skills"
        write_skill(source, "alpha-procedure")
        broken = source / "fde" / "broken-procedure"
        broken.mkdir(parents=True)
        (broken / "SKILL.md").write_text("no frontmatter\n", encoding="utf-8")
        home = tmp_path / "hermes"

        install(discover(source), home)
        assert (home / "skills" / "fde" / "alpha-procedure").is_dir()
        assert not (home / "skills" / "fde" / "broken-procedure").exists()


class TestInstallState:
    def test_reports_missing_before_installation(self, tmp_path):
        source = tmp_path / "skills"
        write_skill(source, "alpha-procedure")
        installed, missing, stale = install_state(discover(source), tmp_path / "hermes")
        assert (installed, [s.name for s in missing], stale) == ([], ["alpha-procedure"], [])

    def test_reports_clean_after_installation(self, tmp_path):
        source = tmp_path / "skills"
        write_skill(source, "alpha-procedure")
        home = tmp_path / "hermes"
        install(discover(source), home)
        installed, missing, stale = install_state(discover(source), home)
        assert ([s.name for s in installed], missing, stale) == (["alpha-procedure"], [], [])

    def test_detects_drift_between_the_repository_and_hermes(self, tmp_path):
        # The silent failure: a procedure edited here that the agent never loads.
        source = tmp_path / "skills"
        write_skill(source, "alpha-procedure")
        home = tmp_path / "hermes"
        install(discover(source), home)
        write_skill(source, "alpha-procedure", body="# Procedure\n\nRevised.\n")

        _, missing, stale = install_state(discover(source), home)
        assert missing == [] and [s.name for s in stale] == ["alpha-procedure"]


class TestDoctorReporting:
    """How the skill library shows up in `pfa doctor`."""

    def status(self, checks, name):
        return next(c.status for c in checks if c.name == name)

    def test_a_clean_library_passes(self, tmp_path, monkeypatch):
        write_skill(tmp_path / "skills", "alpha-procedure")
        monkeypatch.setenv("PFA_SKILLS_DIR", str(tmp_path / "skills"))
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
        assert self.status(check_skills(None), "skill library") == PASS

    def test_a_broken_skill_fails_and_names_the_file(self, tmp_path, monkeypatch):
        root = tmp_path / "skills"
        write_skill(root, "alpha-procedure")
        broken = root / "fde" / "broken-procedure"
        broken.mkdir(parents=True)
        (broken / "SKILL.md").write_text("no frontmatter\n", encoding="utf-8")
        monkeypatch.setenv("PFA_SKILLS_DIR", str(root))
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))

        checks = check_skills(None)
        library = next(c for c in checks if c.name == "skill library")
        assert library.status == FAIL
        assert "broken-procedure" in library.detail
        assert library.remedy == "pfa skills validate"

    def test_an_absent_library_skips_rather_than_passing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PFA_SKILLS_DIR", str(tmp_path / "nowhere"))
        assert self.status(check_skills(None), "skill library") == SKIP

    def test_a_policy_naming_a_missing_skill_fails(self, tmp_path, monkeypatch, policy_with_skills):
        write_skill(tmp_path / "skills", "alpha-procedure")  # beta is absent
        monkeypatch.setenv("PFA_SKILLS_DIR", str(tmp_path / "skills"))
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))

        checks = check_skills(load_config(policy_with_skills))
        reference = next(c for c in checks if c.name == "policy skill references")
        assert reference.status == FAIL
        assert "beta-procedure" in reference.detail

    def test_unreachable_skills_skip_until_hermes_is_configured(self, tmp_path, monkeypatch):
        write_skill(tmp_path / "skills", "alpha-procedure")
        monkeypatch.setenv("PFA_SKILLS_DIR", str(tmp_path / "skills"))
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
        assert self.status(check_skills(None), "skills reachable by hermes") == SKIP

    def test_an_external_dir_pointing_at_the_library_passes_without_a_copy(
        self, tmp_path, monkeypatch, policy_file
    ):
        # The preferred integration: Hermes scans the repository in place, so
        # there is no copy to drift.
        from pfa.hermes import write_config

        root = tmp_path / "skills"
        home = tmp_path / "hermes"
        write_skill(root, "alpha-procedure")
        monkeypatch.setenv("PFA_SKILLS_DIR", str(root))
        monkeypatch.setenv("HERMES_HOME", str(home))
        write_config(load_config(policy_file), home=home)

        check = next(c for c in check_skills(None) if c.name == "skills reachable by hermes")
        assert check.status == PASS
        assert "external_dirs" in check.detail
        assert not (home / "skills").exists()

    def test_an_external_dir_pointing_somewhere_else_does_not_count(
        self, tmp_path, monkeypatch, policy_file
    ):
        # Hermes silently skips a path that does not resolve, so "configured"
        # is not the same as "configured correctly".
        import yaml

        from pfa.hermes import write_config

        root = tmp_path / "skills"
        home = tmp_path / "hermes"
        write_skill(root, "alpha-procedure")
        monkeypatch.setenv("PFA_SKILLS_DIR", str(root))
        monkeypatch.setenv("HERMES_HOME", str(home))
        write_config(load_config(policy_file), home=home)

        document = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
        document["skills"]["external_dirs"] = [str(tmp_path / "somewhere-else")]
        (home / "config.yaml").write_text(yaml.safe_dump(document), encoding="utf-8")

        check = next(c for c in check_skills(None) if c.name == "skills reachable by hermes")
        assert check.status == SKIP
        assert "but not" in check.detail

    def test_drift_from_the_installed_copy_warns_with_a_remedy(self, tmp_path, monkeypatch):
        root = tmp_path / "skills"
        home = tmp_path / "hermes"
        write_skill(root, "alpha-procedure")
        monkeypatch.setenv("PFA_SKILLS_DIR", str(root))
        monkeypatch.setenv("HERMES_HOME", str(home))
        install(discover(root), home)
        write_skill(root, "alpha-procedure", body="# Procedure\n\nRevised.\n")

        check = next(c for c in check_skills(None) if c.name == "skills reachable by hermes")
        assert check.status == WARN
        assert "alpha-procedure" in check.detail
        assert "pfa skills install" in check.remedy

    def test_a_matching_installation_passes(self, tmp_path, monkeypatch):
        root = tmp_path / "skills"
        home = tmp_path / "hermes"
        write_skill(root, "alpha-procedure")
        monkeypatch.setenv("PFA_SKILLS_DIR", str(root))
        monkeypatch.setenv("HERMES_HOME", str(home))
        install(discover(root), home)
        assert self.status(check_skills(None), "skills reachable by hermes") == PASS


class TestShippedLibrary:
    """Assertions about the skills this repository actually ships."""

    def test_every_shipped_skill_is_well_formed(self, repo_root):
        library = discover(repo_root / "skills")
        assert not library.problems, [p.to_dict() for p in library.problems]
        assert len(library.skills) >= 5

    def test_the_phase_two_skills_are_present(self, repo_root):
        names = set(discover(repo_root / "skills").names)
        assert {
            "fde-methodology",
            "technical-research",
            "github-workflow",
            "api-integration",
            "technical-writing",
        } <= names

    def test_every_skill_carries_the_sections_that_make_it_usable(self, repo_root):
        # A procedure with no verification step is advice, not a procedure.
        for skill in discover(repo_root / "skills").skills:
            body = skill.body()
            for heading in ("## When to Use", "## Procedure", "## Pitfalls", "## Verification"):
                assert heading in body, f"{skill.name} is missing {heading}"

    def test_every_skill_named_by_the_shipped_policy_exists(self, repo_root):
        config = load_config(repo_root / "config" / "routing.yaml")
        available = set(discover(repo_root / "skills").names)
        for task, route in config.routes.items():
            missing = set(route.skills) - available
            assert not missing, f"route {task} names skills that do not exist: {missing}"
