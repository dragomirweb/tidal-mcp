"""
MCP server utilities.

This module provides only the SESSION_FILE path constant used by the MCP
tools to locate the persisted TIDAL OAuth session on disk.

There is NO Flask server, no HTTP client, and no threading here. The MCP
tools call tidal_api/routes/ implementation functions directly.
"""

import os
import tempfile
from pathlib import Path

# =============================================================================
# SESSION FILE
# =============================================================================

# The TIDAL OAuth session is persisted to this file. The path is controlled
# by the TEMP environment variable so that Claude Desktop (which sets
# TEMP=C:\Windows\Temp in claude_desktop_config.json) and any standalone
# auth scripts all agree on the same location.
SESSION_FILE: Path = Path(
    os.environ.get(
        "TIDAL_SESSION_FILE",
        os.path.join(tempfile.gettempdir(), "tidal-session-oauth.json"),
    )
)
