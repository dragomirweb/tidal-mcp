"""Shared test fixtures and module-level mocking for the tidal-mcp test suite.

This conftest centralises the ``sys.modules`` patching that is required
because the real ``tidalapi`` and ``mcp`` packages may not be installed
in every test environment.  Keeping the mocks here (rather than in each
test file) means that adding a new import to a source module won't
silently break an unrelated test file.

Fixtures
--------
- ``mock_session`` — a fresh ``MagicMock`` suitable for passing as the
  ``session`` argument to any route function.
"""

from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Module-level sys.modules mocking
# ============================================================================
#
# These patches are applied at *import time* (before pytest collects any
# test modules) so that ``from tidal_api.routes.X import ...`` and
# ``from mcp_server import server`` never hit a real ``tidalapi`` or
# ``mcp`` package.
#
# The dictionaries are kept as module-level variables so individual test
# files can reference the mock objects if needed.

_tidalapi_mock = MagicMock()

_tidal_mocks = {
    "tidalapi": _tidalapi_mock,
    "tidalapi.types": _tidalapi_mock.types,
}

# Build a FastMCP mock whose .tool() decorator is a no-op pass-through.
# This ensures @mcp.tool() decorated functions retain their original
# implementation so we can test them directly.
_fastmcp_instance = MagicMock()
_fastmcp_instance.tool.return_value = lambda fn: fn  # no-op decorator

_fastmcp_class = MagicMock(return_value=_fastmcp_instance)

_fastmcp_module = MagicMock()
_fastmcp_module.FastMCP = _fastmcp_class

_mcp_server_module = MagicMock()
_mcp_server_module.fastmcp = _fastmcp_module

_mcp_top = MagicMock()
_mcp_top.server = _mcp_server_module

_mcp_mocks = {
    "mcp": _mcp_top,
    "mcp.server": _mcp_server_module,
    "mcp.server.fastmcp": _fastmcp_module,
}

# Apply tidalapi mock — this stays in effect for the entire test session.
_tidal_patch = patch.dict("sys.modules", _tidal_mocks)
_tidal_patch.start()

# Import route modules (now safe because tidalapi is mocked)
import tidal_api.routes.tracks as tracks_module  # noqa: E402
import tidal_api.routes.playlists as playlists_module  # noqa: E402
import tidal_api.routes.search as search_module  # noqa: E402
import tidal_api.routes.auth as auth_module  # noqa: E402
import tidal_api.utils as utils_module  # noqa: E402

# Apply mcp mock *additionally* for server.py imports.
# server.py also imports from tidal_api.routes/ — those are already real
# modules (imported above), so we also mock the browser_session import
# that server.py does.
_mcp_patch = patch.dict("sys.modules", _mcp_mocks)
_mcp_patch.start()

# Now we need to also mock tidal_api.browser_session for server.py
# since it imports BrowserSession directly.  The route modules imported
# above already have their own reference to browser_session via the real
# (mocked-tidalapi) import, so we must not break that.  We mock it
# only in sys.modules for server.py's benefit.
_server_tidal_mocks = {
    "tidal_api.browser_session": MagicMock(),
    "tidal_api.routes.auth": auth_module,
    "tidal_api.routes.tracks": tracks_module,
    "tidal_api.routes.playlists": playlists_module,
    "tidal_api.routes.search": search_module,
}
_server_patch = patch.dict("sys.modules", _server_tidal_mocks)
_server_patch.start()

import mcp_server.server as server_module  # noqa: E402

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def mock_session():
    """Return a fresh MagicMock suitable as a tidalapi Session stand-in."""
    return MagicMock()
