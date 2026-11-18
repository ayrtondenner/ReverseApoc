"""The project's MCP servers (.mcp.json): Tavily for research and the two Overleaf servers for the
paper (owner, 2026-11-17). Drive sessions load none of them (session.py's --strict-mcp-config)."""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVERS = json.loads((REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
TAVILY = {"command": "npx", "args": ["-y", "tavily-mcp@latest"],
          "env": {"TAVILY_API_KEY": "${TAVILY_API_KEY}"}}  # fmt: skip


def test_mcp_servers_are_the_known_set():
    """Exactly Tavily (unchanged) and the two Overleaf servers."""
    assert set(SERVERS) == {"tavily", "overleaf", "overleaf-web"}
    assert SERVERS["tavily"] == TAVILY


def test_mcp_secrets_are_env_references():
    """Every env value is a ${NAME} reference to the user's environment, never a literal secret
    (CLAUDE.md: no secrets in tracked files)."""
    values = [value for server in SERVERS.values() for value in server.get("env", {}).values()]
    assert values, "at least one server reads a secret"
    for value in values:
        assert re.fullmatch(r"\$\{[A-Z_]+\}", value), value
    assert SERVERS["overleaf"]["env"] == {
        "OVERLEAF_SESSION": "${OVERLEAF_SESSION}",
        "OVERLEAF_GIT_TOKEN": "${OVERLEAF_GIT_TOKEN}",
    }


def test_mcp_versions_are_pinned():
    """The Overleaf servers run the reviewed releases, not whatever is newest."""
    assert SERVERS["overleaf"]["command"] == "uvx"
    assert SERVERS["overleaf"]["args"] == ["--from", "overleaf-mcp-plus[compile]==0.3.2",
                                           "overleaf-mcp"]  # fmt: skip
    assert SERVERS["overleaf-web"] == {
        "command": "npx",
        "args": ["-y", "overleaf-web-mcp@1.2.0", "serve"],
    }
