"""Unit tests for mcp_server/server.py helper functions.

Tests the pure helper functions only — no MCP framework, no tidalapi,
no network, no session file. These are safe to run in CI.
"""

import pytest

# Import only the helper, not the full module (which needs mcp installed)
# We test _call() by importing the function directly after patching FastMCP.
from unittest.mock import patch, MagicMock


# Patch FastMCP at import time so we don't need the mcp package installed
# in test environments that don't have it.
_fastmcp_mock = MagicMock()
with patch.dict(
    "sys.modules",
    {"mcp": MagicMock(), "mcp.server": MagicMock(), "mcp.server.fastmcp": MagicMock()},
):
    # Also patch tidal_api imports that require tidalapi
    tidal_mocks = {
        "tidalapi": MagicMock(),
        "tidal_api.browser_session": MagicMock(),
        "tidal_api.routes.auth": MagicMock(),
        "tidal_api.routes.tracks": MagicMock(),
        "tidal_api.routes.playlists": MagicMock(),
        "tidal_api.routes.search": MagicMock(),
    }
    with patch.dict("sys.modules", tidal_mocks):
        from mcp_server import server as _server_module


# =============================================================================
# _call helper
# =============================================================================


class TestCall:
    """Tests for the _call() helper that unwraps (dict, int) route tuples."""

    def test_200_returns_data_directly(self):
        result = _server_module._call(({"tracks": [1, 2, 3]}, 200))
        assert result == {"tracks": [1, 2, 3]}

    def test_200_empty_dict(self):
        result = _server_module._call(({}, 200))
        assert result == {}

    def test_non_200_returns_error_from_data(self):
        result = _server_module._call(({"error": "not found"}, 404))
        assert result == {"error": "not found"}

    def test_non_200_fallback_message_when_no_error_key(self):
        result = _server_module._call(({}, 500))
        assert "error" in result
        assert "500" in result["error"]

    def test_401_returns_error(self):
        result = _server_module._call(({"error": "unauthorized"}, 401))
        assert result["error"] == "unauthorized"

    def test_400_returns_error(self):
        result = _server_module._call(({"error": "bad input"}, 400))
        assert result["error"] == "bad input"

    def test_data_passthrough_on_success(self):
        data = {"query": "test", "results": {"tracks": {"items": [], "total": 0}}}
        result = _server_module._call((data, 200))
        assert result is data  # same object, no copy
