# PFA-ALLOW-SECRET-FIXTURES: contains synthetic credential-shaped strings by design.
"""Structured logging and, above all, redaction."""

from __future__ import annotations

import json

import pytest

from pfa.observability import REDACTED, RunRecord, redact, write_record


class TestRedaction:
    @pytest.mark.parametrize(
        "secret",
        [
            "sk-abcdefghijklmnopqrstuvwxyz123456",
            "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
            "xoxb-1234567890-abcdefghijk",
            "123456789:AAErOF7bqXW7ZlnPmS8kQvJhK2mNpQrStUv",
            "AKIAIOSFODNN7EXAMPLE",
        ],
    )
    def test_credential_shapes_are_stripped_from_free_text(self, secret):
        assert secret not in redact(f"the value is {secret} ok")

    def test_bearer_headers_are_stripped(self):
        assert "abcdefghijklmnop123456" not in redact(
            "Authorization: Bearer abcdefghijklmnop123456"
        )

    def test_sensitive_keys_are_replaced_whatever_the_value(self):
        source = {"password": "hunter2", "api_key": "short", "token": "x" * 5}
        assert redact(source) == {"password": REDACTED, "api_key": REDACTED, "token": REDACTED}

    def test_key_matching_is_case_insensitive_and_partial(self):
        assert redact({"OPENAI_API_KEY": "anything"})["OPENAI_API_KEY"] == REDACTED

    def test_redacts_inside_nested_structures(self):
        source = {"outer": [{"inner": {"secret": "value"}}]}
        assert redact(source)["outer"][0]["inner"]["secret"] == REDACTED

    def test_harmless_values_survive_untouched(self):
        source = {"model": "gemma4:e4b", "duration_ms": 120, "status": "success"}
        assert redact(source) == source


class TestRunRecord:
    def test_generates_a_unique_task_id(self):
        assert RunRecord().task_id != RunRecord().task_id

    def test_timestamp_is_iso_utc(self):
        assert RunRecord().timestamp.endswith("+00:00")

    def test_record_is_redacted_on_serialisation(self):
        record = RunRecord(error="failed with key sk-abcdefghijklmnopqrstuvwxyz")
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in json.dumps(record.to_dict())

    def test_contains_the_fields_the_spec_requires(self):
        fields = RunRecord().to_dict()
        for key in ("task_id", "model", "duration_ms", "tools", "status"):
            assert key in fields


class TestWriting:
    def test_writes_one_json_object_per_line(self, tmp_path):
        for _ in range(3):
            path = write_record(RunRecord(task="research", status="success"), tmp_path)
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        assert all(json.loads(line)["task"] == "research" for line in lines)

    def test_file_is_named_by_date(self, tmp_path):
        record = RunRecord()
        path = write_record(record, tmp_path)
        assert path.name == f"runs-{record.timestamp[:10]}.jsonl"

    def test_creates_the_directory_if_absent(self, tmp_path):
        target = tmp_path / "deep" / "nested"
        assert write_record(RunRecord(), target).is_file()

    def test_written_record_never_contains_a_credential(self, tmp_path):
        record = RunRecord(error="Authorization: Bearer ghp_abcdefghijklmnopqrstuvwxyz1234567890")
        body = write_record(record, tmp_path).read_text(encoding="utf-8")
        assert "ghp_" not in body


class TestRedactionPrecision:
    """Redaction must not corrupt the values it is not there to protect."""

    def test_token_counts_survive_the_token_key_hint(self):
        # `input_tokens` matches the "token" hint but holds a count, not a
        # credential. Redacting it would silently break cost accounting.
        record = RunRecord(input_tokens=4096, output_tokens=512)
        payload = record.to_dict()
        assert payload["input_tokens"] == 4096
        assert payload["output_tokens"] == 512

    def test_an_unset_count_stays_null(self):
        assert RunRecord().to_dict()["input_tokens"] is None

    def test_a_string_under_a_hinted_key_is_still_redacted(self):
        assert redact({"access_token": "anything at all"})["access_token"] == REDACTED

    def test_a_nested_structure_under_a_hinted_key_is_still_redacted(self):
        assert redact({"credentials": {"user": "paul", "pass": "hunter2"}})["credentials"] == (
            REDACTED
        )

    def test_a_boolean_flag_is_not_mistaken_for_a_credential(self):
        assert redact({"has_api_key": False})["has_api_key"] is False
