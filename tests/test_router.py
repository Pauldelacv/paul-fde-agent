"""Routing: classification, resolution and cost estimation."""

from __future__ import annotations

import pytest

from pfa.config import load_config
from pfa.errors import RoutingError
from pfa.router import classify, estimate_cost, route


@pytest.fixture
def config(policy_file):
    return load_config(policy_file)


class TestClassification:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Implement the retry logic", "coding"),
            ("Please refactor this module", "coding"),
            ("Research the MCP ecosystem", "research"),
            ("Compare these two vendors", "research"),
        ],
    )
    def test_keyword_routes(self, config, text, expected):
        task, basis, _ = classify(text, config)
        assert (task, basis) == (expected, "keyword")

    def test_case_insensitive(self, config):
        assert classify("IMPLEMENT this", config)[0] == "coding"

    def test_falls_back_to_default(self, config):
        task, basis, keyword = classify("What is the weather", config)
        assert (task, basis, keyword) == ("simple", "default", None)

    def test_first_matching_rule_wins(self, config):
        # "implement" (coding) is declared before "research"; order is meaningful.
        assert classify("implement a research tool", config)[0] == "coding"

    def test_matches_on_word_boundaries_only(self, config):
        # "compare" must not fire on "comparable"; otherwise routing is noise.
        assert classify("this is comparable to that", config)[0] == "simple"

    def test_substring_inside_longer_word_ignored(self, config):
        assert classify("reimplementation", config)[0] == "simple"


class TestResolution:
    def test_explicit_task_overrides_keywords(self, config):
        decision = route("implement everything", config, task="research")
        assert decision.task == "research"
        assert decision.basis == "explicit"

    def test_unknown_explicit_task_is_rejected(self, config):
        with pytest.raises(RoutingError, match="Unknown task category"):
            route("anything", config, task="nonsense")

    def test_null_model_resolves_to_provider_default(self, config):
        decision = route("research this", config)
        assert decision.model == "gemma4:e4b"

    def test_explicit_model_overrides_provider_default(self, config):
        decision = route("something ordinary", config)
        assert decision.task == "simple"
        assert decision.model == "gemma4:e2b"

    def test_model_ref_is_provider_slash_model(self, config):
        assert route("implement it", config).model_ref == "cloud/vendor/big-model"

    def test_coding_goes_to_cloud_and_research_stays_local(self, config):
        assert route("implement it", config).provider.is_local is False
        assert route("research it", config).provider.is_local is True

    def test_explanation_never_states_a_guess_as_fact(self, config):
        explanation = route("what is this", config).explain()
        assert "no rule matched" in explanation
        assert "fell back to default_task" in explanation


class TestCostEstimation:
    def test_local_provider_costs_nothing(self, config):
        decision = route("research this", config)
        assert estimate_cost(decision, 1_000_000, 1_000_000) == 0.0

    def test_cloud_cost_uses_policy_pricing(self, config):
        decision = route("implement this", config)
        # 1M in at $3 + 1M out at $15
        assert estimate_cost(decision, 1_000_000, 1_000_000) == pytest.approx(18.0)

    def test_cost_scales_linearly(self, config):
        decision = route("implement this", config)
        assert estimate_cost(decision, 500_000, 0) == pytest.approx(1.5)

    def test_zero_tokens_is_zero(self, config):
        assert estimate_cost(route("implement this", config), 0, 0) == 0.0


class TestShippedPolicyFlagshipScenarios:
    """The four workflows the project is built to serve must route sensibly.

    These run against the policy actually shipped in `config/routing.yaml`, not
    a fixture, because a routing regression here is a product regression: sending
    repository analysis to the smallest local model produces shallow answers on
    exactly the task that matters.
    """

    @pytest.fixture
    def shipped(self, repo_root):
        return load_config(repo_root / "config" / "routing.yaml")

    @pytest.mark.parametrize(
        "text,expected_task",
        [
            (
                "Research the latest developments in MCP and tell me what "
                "matters for a freelance FDE",
                "research",
            ),
            (
                "Inspect this GitHub repository and identify the three highest-value improvements",
                "coding",
            ),
            ("Debug this API integration", "debugging"),
            ("Prepare my morning FDE briefing", "summarization"),
        ],
    )
    def test_flagship_scenario_routes(self, shipped, text, expected_task):
        decision = route(text, shipped)
        assert decision.task == expected_task
        assert decision.basis == "keyword", (
            f"{text!r} fell through to the default route; it would run on the "
            f"cheapest model regardless of difficulty"
        )

    def test_repository_analysis_does_not_use_the_smallest_model(self, shipped):
        decision = route("Inspect this repository and find the weak points", shipped)
        assert decision.model != "gemma4:e2b"

    def test_every_route_resolves_to_a_concrete_model(self, shipped):
        for task in shipped.routes:
            decision = route("", shipped, task=task)
            assert decision.model, f"route {task} resolved to an empty model"
            assert decision.provider.name in shipped.providers


class TestAttachedSkills:
    """The policy attaches procedures to a category; the decision carries them."""

    @pytest.fixture
    def config_with_skills(self, policy_with_skills):
        return load_config(policy_with_skills)

    def test_decision_carries_the_policy_skills(self, config_with_skills):
        assert route("research this", config_with_skills).skills == ("alpha-procedure",)

    def test_a_route_with_no_skills_carries_none(self, config_with_skills):
        assert route("something ordinary", config_with_skills).skills == ()

    def test_order_follows_the_policy(self, config_with_skills):
        decision = route("implement this", config_with_skills)
        assert decision.skills == ("alpha-procedure", "beta-procedure")

    def test_explicit_task_still_gets_its_skills(self, config_with_skills):
        assert route("anything", config_with_skills, task="research").skills == ("alpha-procedure",)

    def test_auto_skills_off_drops_them(self, config_with_skills):
        assert route("research this", config_with_skills, auto_skills=False).skills == ()

    def test_auto_skills_off_does_not_change_the_model(self, config_with_skills):
        # Suppressing a procedure must never quietly re-route the task.
        with_skills = route("research this", config_with_skills)
        without = route("research this", config_with_skills, auto_skills=False)
        assert (with_skills.task, with_skills.model_ref) == (without.task, without.model_ref)

    def test_explanation_names_the_skills(self, config_with_skills):
        assert "skills: alpha-procedure" in route("research this", config_with_skills).explain()

    def test_explanation_omits_the_clause_when_there_are_none(self, config_with_skills):
        assert "skills:" not in route("something ordinary", config_with_skills).explain()
