#!/usr/bin/env python3
"""
Startup script for TIDAL MCP server.

Installs a stdin proxy before importing the server. The proxy forwards data
from real stdin to FastMCP through an internal pipe. When real stdin closes
(the MCP client disconnected), the proxy closes the write end of the pipe,
which causes FastMCP's read loop to see EOF and exit cleanly.

This handles the case where the MCP client process (e.g. Claude) exits without
explicitly terminating the `docker run` process — the container self-terminates
when the underlying pipe connection is broken.
"""

import os
import sys
import threading


def _install_stdin_proxy():
    # Save real stdin before anything else touches fd 0
    real_stdin_fd = os.dup(0)

    # Create an internal pipe. FastMCP will read from the read end (via fd 0).
    r_fd, w_fd = os.pipe()

    # Replace fd 0 with the read end of our pipe. sys.stdin / anyio will now
    # read from the pipe without knowing anything changed.
    os.dup2(r_fd, 0)
    os.close(r_fd)

    def _proxy():
        try:
            while True:
                data = os.read(real_stdin_fd, 65536)
                if not data:
                    # EOF: the docker client closed stdin (Claude disconnected).
                    # Closing the write end propagates EOF to FastMCP.
                    break
                os.write(w_fd, data)
        except OSError:
            pass
        finally:
            try:
                os.close(w_fd)
            except OSError:
                pass
            try:
                os.close(real_stdin_fd)
            except OSError:
                pass

    t = threading.Thread(target=_proxy, daemon=True)
    t.start()


if __name__ == "__main__":
    _install_stdin_proxy()

    # Import after proxy is installed so FastMCP inherits the proxied fd 0
    sys.path.append(".")
    from mcp_server.server import mcp

    print("Starting TIDAL MCP server...", file=sys.stderr)
    mcp.run()
