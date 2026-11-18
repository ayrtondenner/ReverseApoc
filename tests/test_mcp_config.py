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
    """Every credential-named env value (a session, token or key) is a ${NAME} reference to the
    user's environment, never a literal secret (CLAUDE.md: no secrets in tracked files)."""
    secrets = {name: value for server in SERVERS.values()
               for name, value in server.get("env", {}).items()
               if re.search(r"SESSION|TOKEN|KEY", name)}  # fmt: skip
    assert len(secrets) == 3, secrets
    for name, value in secrets.items():
        assert value == "${" + name + "}", name


def test_overleaf_cache_stays_outside_the_checkout():
    """overleaf-mcp-plus clones each project into OVERLEAF_TEMP_DIR, by default ./overleaf_cache
    under its working directory, which is the checkout; a stray there stops a drive (first use,
    2026-11-18). It goes under the user's home instead, and the env holds nothing else."""
    assert SERVERS["overleaf"]["env"] == {
        "OVERLEAF_SESSION": "${OVERLEAF_SESSION}",
        "OVERLEAF_GIT_TOKEN": "${OVERLEAF_GIT_TOKEN}",
        "OVERLEAF_TEMP_DIR": "~/.overleaf-mcp/cache",
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
