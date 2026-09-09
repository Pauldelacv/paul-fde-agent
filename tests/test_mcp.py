# PFA-ALLOW-SECRET-FIXTURES: contains synthetic credential-shaped strings by design.
"""MCP connector declarations: parsing, validation and rendering.

The property that matters most here is negative: the rendered Hermes config
must never contain a credential. Two tests assert it directly, because the
rendered file is written to disk, read during debugging, and included in
backups.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from pfa.config import load_config
from pfa.errors import ConfigError
from pfa.hermes import render_config
from pfa.mcp import McpCatalogue, McpServer, load_mcp_config

MINIMAL = """
version: 1
servers:
  vendor:
    transport: http
    url: "https://mcp.example.com/mcp"
    headers:
      X-API-Key: "${VENDOR_KEY}"
    requires_env: [VENDOR_KEY]
    description: A remote server.
  local_files:
    transport: stdio
    command: "npx"
    args: ["-y", "@example/server", "/srv/work"]
"""


def write(tmp_path: Path, text: str, name: str = "mcp.yaml") -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")
    return path


class TestLoading:
    def test_parses_both_transports(self, tmp_path):
        catalogue = load_mcp_config(write(tmp_path, MINIMAL))
        assert [server.name for server in catalogue.servers] == ["vendor", "local_files"]
        assert catalogue.get("vendor").transport == "http"
        assert catalogue.get("local_files").transport == "stdio"

    def test_missing_default_file_is_an_empty_catalogue_not_an_error(self, tmp_path, monkeypatch):
        """MCP connectors are additive; an agent with none is a working agent."""
        monkeypatch.chdir(tmp_path)
        catalogue = load_mcp_config()
        assert catalogue.servers == ()
        assert catalogue.source_path is None

    def test_an_explicitly_named_missing_file_is_an_error(self, tmp_path):
        """Naming a file and having it silently ignored is the failure to avoid."""
        with pytest.raises(ConfigError, match="not found"):
            load_mcp_config(tmp_path / "absent.yaml")

    def test_env_var_is_read_when_no_path_is_given(self, tmp_path, monkeypatch):
        path = write(tmp_path, MINIMAL)
        monkeypatch.setenv("PFA_MCP_CONFIG", str(path))
        assert load_mcp_config().source_path == path

    def test_rejects_an_unknown_version(self, tmp_path):
        with pytest.raises(ConfigError, match="version"):
            load_mcp_config(write(tmp_path, "version: 99\nservers: {}"))

    def test_empty_file_is_an_empty_catalogue(self, tmp_path):
        path = tmp_path / "mcp.yaml"
        path.write_text("", encoding="utf-8")
        assert load_mcp_config(path).servers == ()


class TestValidation:
    def test_http_server_must_have_a_url(self, tmp_path):
        with pytest.raises(ConfigError, match="must define `url`"):
            load_mcp_config(write(tmp_path, "version: 1\nservers:\n  a:\n    transport: http"))

    def test_stdio_server_must_have_a_command(self, tmp_path):
        with pytest.raises(ConfigError, match="must define `command`"):
            load_mcp_config(write(tmp_path, "version: 1\nservers:\n  a:\n    transport: stdio"))

    def test_rejects_an_unknown_transport(self, tmp_path):
        text = "version: 1\nservers:\n  a:\n    transport: carrier-pigeon\n    url: x"
        with pytest.raises(ConfigError, match="transport"):
            load_mcp_config(write(tmp_path, text))

    def test_rejects_a_server_declaring_both_transports(self, tmp_path):
        text = """
        version: 1
        servers:
          a:
            transport: http
            url: "https://example.com"
            command: "npx"
        """
        with pytest.raises(ConfigError, match="both `url` and `command`"):
            load_mcp_config(write(tmp_path, text))

    def test_rejects_an_undeclared_env_reference(self, tmp_path):
        """The guard against Hermes passing an unset ${VAR} through verbatim.

        An undeclared reference is one no check covers, so it reaches the
        network as the literal text of the placeholder.
        """
        text = """
        version: 1
        servers:
          a:
            transport: http
            url: "https://example.com/mcp"
            headers:
              X-API-Key: "${SECRET_KEY}"
        """
        with pytest.raises(ConfigError, match="SECRET_KEY.*requires_env"):
            load_mcp_config(write(tmp_path, text))

    def test_recognises_the_cursor_style_env_reference(self, tmp_path):
        """`${env:VAR}` is a spelling Hermes accepts; it must not evade the check."""
        text = """
        version: 1
        servers:
          a:
            transport: http
            url: "https://example.com/mcp"
            headers:
              X-API-Key: "${env:SECRET_KEY}"
        """
        with pytest.raises(ConfigError, match="SECRET_KEY"):
            load_mcp_config(write(tmp_path, text))

    def test_rejects_a_non_string_header_value(self, tmp_path):
        """A non-string header is usually an inlined number or an inlined secret."""
        text = """
        version: 1
        servers:
          a:
            transport: http
            url: "https://example.com/mcp"
            headers:
              X-Count: 3
        """
        with pytest.raises(ConfigError, match="must be a string"):
            load_mcp_config(write(tmp_path, text))

    def test_rejects_an_invalid_server_name(self, tmp_path):
        text = 'version: 1\nservers:\n  "Bad Name":\n    transport: http\n    url: "x"'
        with pytest.raises(ConfigError, match="must be lowercase"):
            load_mcp_config(write(tmp_path, text))

    def test_explains_a_name_yaml_turned_into_a_boolean(self, tmp_path):
        """`off:` is parsed as False by YAML 1.1. Say that, do not crash on it."""
        text = 'version: 1\nservers:\n  off:\n    transport: http\n    url: "x"'
        with pytest.raises(ConfigError, match="quote the name"):
            load_mcp_config(write(tmp_path, text))


class TestMissingEnv:
    def test_reports_unset_variables_in_declaration_order(self):
        server = McpServer(name="a", transport="http", url="x", requires_env=("ONE", "TWO"))
        assert server.missing_env({"TWO": "set"}) == ("ONE",)

    def test_treats_an_empty_value_as_missing(self):
        """An empty API key is a credential that fails, not a credential."""
        server = McpServer(name="a", transport="http", url="x", requires_env=("KEY",))
        assert server.missing_env({"KEY": ""}) == ("KEY",)

    def test_reports_nothing_when_everything_is_set(self):
        server = McpServer(name="a", transport="http", url="x", requires_env=("KEY",))
        assert server.missing_env({"KEY": "value"}) == ()


class TestRendering:
    def test_http_server_renders_url_and_headers(self, tmp_path):
        rendered = load_mcp_config(write(tmp_path, MINIMAL)).to_hermes()
        assert rendered["vendor"] == {
            "url": "https://mcp.example.com/mcp",
            "headers": {"X-API-Key": "${VENDOR_KEY}"},
        }

    def test_stdio_server_renders_command_and_args(self, tmp_path):
        rendered = load_mcp_config(write(tmp_path, MINIMAL)).to_hermes()
        assert rendered["local_files"] == {
            "command": "npx",
            "args": ["-y", "@example/server", "/srv/work"],
        }

    def test_disabled_servers_are_omitted_entirely(self, tmp_path):
        text = """
        version: 1
        servers:
          retired:
            enabled: false
            transport: http
            url: "https://example.com/mcp"
        """
        catalogue = load_mcp_config(write(tmp_path, text))
        assert catalogue.servers[0].enabled is False
        assert catalogue.to_hermes() == {}

    def test_tool_filters_are_rendered_under_tools(self, tmp_path):
        text = """
        version: 1
        servers:
          a:
            transport: http
            url: "https://example.com/mcp"
            tools:
              include: [read_thing]
              exclude: ["*delete*"]
        """
        rendered = load_mcp_config(write(tmp_path, text)).to_hermes()
        assert rendered["a"]["tools"] == {"include": ["read_thing"], "exclude": ["*delete*"]}

    def test_unset_optional_keys_are_not_emitted_as_nulls(self, tmp_path):
        rendered = load_mcp_config(write(tmp_path, MINIMAL)).to_hermes()
        assert "timeout" not in rendered["local_files"]
        assert "env" not in rendered["local_files"]

    def test_the_reference_survives_rather_than_being_expanded(self, tmp_path, monkeypatch):
        """The whole point: Hermes resolves it at connect time, so we must not.

        Expanding here would write the credential into a file that is read
        during debugging and copied into backups.
        """
        monkeypatch.setenv("VENDOR_KEY", "a-real-looking-secret-value")
        rendered = load_mcp_config(write(tmp_path, MINIMAL)).to_hermes()
        assert rendered["vendor"]["headers"]["X-API-Key"] == "${VENDOR_KEY}"


class TestHermesConfigIntegration:
    def test_servers_appear_under_mcp_servers(self, policy_file, tmp_path):
        catalogue = load_mcp_config(write(tmp_path, MINIMAL))
        document = render_config(load_config(policy_file), catalogue=catalogue)
        assert set(document["mcp_servers"]) == {"vendor", "local_files"}

    def test_no_mcp_block_when_nothing_is_declared(self, policy_file):
        """An installation with no connectors gets no empty block to explain."""
        document = render_config(load_config(policy_file), catalogue=McpCatalogue())
        assert "mcp_servers" not in document

    def test_the_rendered_document_contains_no_credential(self, policy_file, tmp_path, monkeypatch):
        monkeypatch.setenv("VENDOR_KEY", "sk-not-a-real-key-0123456789abcdef")
        catalogue = load_mcp_config(write(tmp_path, MINIMAL))
        text = yaml.safe_dump(render_config(load_config(policy_file), catalogue=catalogue))
        assert "sk-not-a-real-key" not in text
        assert "${VENDOR_KEY}" in text


class TestShippedCatalogue:
    """Assertions about the connectors this repository actually ships."""

    def test_it_loads_and_declares_lemlist(self, repo_root):
        catalogue = load_mcp_config(repo_root / "config" / "mcp.yaml")
        assert catalogue.get("lemlist") is not None

    def test_every_server_declares_the_variables_it_references(self, repo_root):
        # Enforced by the loader; asserted here so the shipped file is covered.
        catalogue = load_mcp_config(repo_root / "config" / "mcp.yaml")
        assert catalogue.servers

    def test_lemlist_cannot_advertise_a_sending_tool(self, repo_root):
        """The agent drafts and a person sends. The connector reflects that."""
        lemlist = load_mcp_config(repo_root / "config" / "mcp.yaml").get("lemlist")
        assert any("send" in pattern for pattern in lemlist.tools_exclude)
        assert any("launch" in pattern for pattern in lemlist.tools_exclude)

    def test_the_shipped_file_holds_no_inlined_credential(self, repo_root):
        raw = (repo_root / "config" / "mcp.yaml").read_text(encoding="utf-8")
        document = yaml.safe_load(raw)
        for name, spec in (document.get("servers") or {}).items():
            for key, value in (spec.get("headers") or {}).items():
                assert value.startswith("${"), f"{name}.{key} inlines a value"
