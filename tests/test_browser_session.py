"""Unit tests for tidal_api/browser_session.py.

Tests the _ensure_https helper and the login_oauth_start method.

The conftest mocks tidalapi with a MagicMock, which makes BrowserSession
itself a MagicMock (losing the real method definitions).  To test
login_oauth_start, we reimport the module with a tidalapi mock where
Session is a real (empty) class, so BrowserSession becomes a real class
with the actual method body preserved.
"""

import importlib
import sys
import types
from unittest.mock import MagicMock

from concurrent.futures import Future


# ============================================================================
# Reimport browser_session with a tidalapi mock that uses a real base class.
# ============================================================================
#
# conftest.py mocks tidalapi as a MagicMock, which causes
# ``class BrowserSession(tidalapi.Session)`` to produce a MagicMock —
# losing the method definitions entirely.  Here we temporarily replace
# the tidalapi module with one whose Session is a plain ``type``, force
# a reimport of browser_session, then restore the original mock.

_orig_tidalapi = sys.modules.get("tidalapi")

_tidalapi_real = types.ModuleType("tidalapi")
_tidalapi_real.Session = type("Session", (), {})  # real empty class
sys.modules["tidalapi"] = _tidalapi_real

# Remove cached module so importlib re-executes it with our new mock.
sys.modules.pop("tidal_api.browser_session", None)
_bs_module = importlib.import_module("tidal_api.browser_session")

# Restore the original tidalapi mock for other test modules.
if _orig_tidalapi is not None:
    sys.modules["tidalapi"] = _orig_tidalapi
else:
    del sys.modules["tidalapi"]


# =============================================================================
# _ensure_https
# =============================================================================


class TestEnsureHttps:
    """Tests for the _ensure_https() helper."""

    def test_adds_scheme_when_missing(self):
        assert (
            _bs_module._ensure_https("example.com/auth") == "https://example.com/auth"
        )

    def test_preserves_existing_https(self):
        assert _bs_module._ensure_https("https://example.com") == "https://example.com"

    def test_preserves_existing_http(self):
        assert _bs_module._ensure_https("http://example.com") == "http://example.com"

    def test_handles_empty_string(self):
        assert _bs_module._ensure_https("") == "https://"


# =============================================================================
# BrowserSession.login_oauth_start
# =============================================================================


class TestLoginOAuthStart:
    """Tests for BrowserSession.login_oauth_start().

    Because we reimported browser_session with a real base class,
    BrowserSession is a genuine Python class and login_oauth_start is
    the real method.  We instantiate normally and mock login_oauth on
    the instance.
    """

    def test_returns_url_expiry_and_future(self):
        mock_login = MagicMock()
        mock_login.verification_uri_complete = "https://login.tidal.com/device"
        mock_login.expires_in = 300
        mock_future = Future()

        instance = _bs_module.BrowserSession()
        instance.login_oauth = MagicMock(return_value=(mock_login, mock_future))

        url, expires_in, future = instance.login_oauth_start()

        assert url == "https://login.tidal.com/device"
        assert expires_in == 300
        assert future is mock_future
        instance.login_oauth.assert_called_once()

    def test_adds_https_when_missing(self):
        mock_login = MagicMock()
        mock_login.verification_uri_complete = "login.tidal.com/device"
        mock_login.expires_in = 300
        mock_future = Future()

        instance = _bs_module.BrowserSession()
        instance.login_oauth = MagicMock(return_value=(mock_login, mock_future))

        url, _, _ = instance.login_oauth_start()

        assert url == "https://login.tidal.com/device"
