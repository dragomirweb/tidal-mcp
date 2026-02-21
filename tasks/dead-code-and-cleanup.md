# Dead Code and Cleanup

Status: **Completed**

All items resolved. See git log for per-file commit history.

## Summary of changes

1. **Orphan functions removed:**
   - `get_single_track_recommendations` from `tracks.py` (never imported by server.py)
   - `login_oauth_simple` and `login_session_file_auto` from `browser_session.py` (never called)
   - `check_auth_status` in `auth.py` was kept (potentially useful as a future MCP tool)

2. **Dead `logger` parameter removed** from 6 functions across `playlists.py` and `search.py`. Replaced useful warning branches in `remove_tracks` with `print(..., file=sys.stderr)`.

3. **Stale Flask/HTTP references fixed** in `server.py`, `utils.py`, `start_mcp.py`, `Dockerfile`, and `server.json`. Fixed false "no threads" claim in `server.py` docstring.

4. **Debug info leak removed** from `search.py` response (was exposing Python type info).

5. **Unused imports and dependencies removed:**
   - `import pytest` from both test files
   - `pytest-mock` from dev dependencies in `pyproject.toml`

6. **Duplicated URL-fixup logic consolidated** into `_ensure_https()` helper in `browser_session.py`, used by both `login_oauth_start` and `auth_cli.py`.

7. **Vestigial Docker/deployment config cleaned:**
   - Removed `EXPOSE 5050` and `ENV TIDAL_MCP_PORT` from `Dockerfile`
   - Replaced `TIDAL_MCP_PORT` with `TIDAL_SESSION_FILE` in `server.json`
