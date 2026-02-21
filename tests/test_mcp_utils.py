"""Unit tests for mcp_server/utils.py — SESSION_FILE path resolution.

Tests the env-var override logic for the session file path.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestSessionFile:
    """Tests for SESSION_FILE path resolution."""

    def test_default_path_uses_tempdir(self):
        """Without TIDAL_SESSION_FILE env var, default to tempdir."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove the env var if present
            env = os.environ.copy()
            env.pop("TIDAL_SESSION_FILE", None)
            with patch.dict(os.environ, env, clear=True):
                # Re-import to get fresh module state
                import importlib
                import mcp_server.utils as mod

                importlib.reload(mod)

                expected = Path(
                    os.path.join(tempfile.gettempdir(), "tidal-session-oauth.json")
                )
                assert mod.SESSION_FILE == expected
                assert isinstance(mod.SESSION_FILE, Path)

    def test_env_var_overrides_default(self):
        """TIDAL_SESSION_FILE env var overrides the default path."""
        custom_path = "/tmp/custom-session.json"
        with patch.dict(os.environ, {"TIDAL_SESSION_FILE": custom_path}):
            import importlib
            import mcp_server.utils as mod

            importlib.reload(mod)

            assert mod.SESSION_FILE == Path(custom_path)

    def test_result_is_path_object(self):
        """SESSION_FILE should always be a pathlib.Path."""
        import mcp_server.utils as mod

        assert isinstance(mod.SESSION_FILE, Path)
