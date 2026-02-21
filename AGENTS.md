# AGENTS.md — tidal-mcp

Guidance for agentic coding agents (Claude Code, Copilot, Cursor, etc.) working in this repository.

## Project Overview

`tidal-mcp` is a Python MCP (Model Context Protocol) server that connects AI assistants to the TIDAL music streaming API. **Direct-call architecture** — no Flask, no HTTP, no subprocess, no ports.

```
Claude Desktop / Cursor  →  start_mcp.py (entry point)
  →  mcp_server/server.py (FastMCP, 17 @mcp.tool()s)
    →  tidal_api/routes/ (business logic: auth, tracks, playlists, search)
      →  tidal_api/browser_session.py (tidalapi.Session wrapper)
        →  TIDAL REST API
```

`server.py` imports route functions directly from `tidal_api/routes/`. No intermediate HTTP layer.

---

## Build, Run & Check Commands

**Package manager:** `uv` (see `uv.lock`). Python 3.10+ required.

```bash
uv sync                          # Install dependencies
uv run python start_mcp.py      # Run the MCP server
uv run python auth_cli.py       # Run the auth CLI (standalone OAuth flow)

# Syntax-check all source files (what CI runs)
python -m compileall mcp_server/ tidal_api/

# Run the full test suite
pytest tests/ -v

# Run a single test file
pytest tests/test_utils.py -v

# Run a single test class
pytest tests/test_utils.py::TestFetchAllItems -v

# Run a single test by name
pytest tests/test_utils.py::TestFetchAllItems::test_fetches_multiple_pages -v

# Docker
docker build -t tidal-mcp .
docker-compose -f docker-compose.auth.yml run --rm tidal-auth   # OAuth flow
```

CI (`ci.yml`) runs on push/PR to `main`: builds the Docker image, runs `py_compile`, and runs `pytest tests/ -v`. Note that CI installs via `pip install -e ".[dev]"` (not `uv sync`). Do not push directly to `main`; open a PR. Releases trigger on `v*` tags.

Known issues and cleanup tasks are tracked in `tasks/`.

---

## Code Style

### Formatting

- Python 3.10+ syntax only.
- No enforced formatter. `ruff check .` can be run locally but is not in CI. Follow PEP 8 manually: 4-space indentation, ~100 char line length, two blank lines between top-level definitions.

### Imports

Standard library → third-party → internal, each group separated by a blank line. Use absolute package paths for internal imports:

```python
import os
from typing import Optional, Dict, Any, List, Tuple

import tidalapi

from tidal_api.browser_session import BrowserSession
from tidal_api.utils import format_track_data, fetch_all_items
```

Use `as ..._impl` aliasing when an import would shadow a local name:
```python
from tidal_api.routes.playlists import update_playlist_metadata as update_playlist_metadata_impl
```

### Naming

| Kind | Convention | Examples |
|---|---|---|
| Functions / variables | `snake_case` | `get_favorite_tracks`, `fetch_all_items` |
| Classes | `PascalCase` | `BrowserSession` |
| Constants | `UPPER_SNAKE_CASE` | `SESSION_FILE`, `AUTH_ERROR_MESSAGE` |
| Private helpers | `_leading_underscore` | `_get_session`, `_call`, `_proxy` |

### Type Annotations & Docstrings

Annotate all public function signatures. Use `from typing import ...` forms for Python 3.10 compatibility — prefer `Optional[X]` over `X | None`. For docstrings: **MCP tool functions** get verbose docstrings (LLMs read these to decide when/how to call tools); **route/utility functions** get a short one-liner. Triple double-quotes, imperative mood, no blank line after `"""`. Use `# ====...` section banners to group related definitions within modules.

---

## Error Handling

Two distinct patterns — one per layer.

### `tidal_api/routes/` — return `(dict, int)` tuples

```python
def get_tracks_from_playlist(session, playlist_id, limit=None):
    """Fetch all tracks from a playlist."""
    if not playlist_id or not playlist_id.strip():
        return {"error": "playlist_id cannot be empty."}, 400
    try:
        playlist = session.playlist(playlist_id)
        return {"playlist_id": playlist.id, "tracks": track_list}, 200
    except Exception as e:
        return {"error": f"Error fetching playlist tracks: {str(e)}"}, 500
```

Validate inputs before any API call; return an error tuple early with 400.

### `mcp_server/server.py` — return plain dicts; never raise

```python
@mcp.tool()
def get_playlist_tracks(playlist_id: str, limit: Optional[int] = None) -> dict:
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(get_tracks_from_playlist(session, playlist_id, limit))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
```

`_call((data, status))` unwraps route return values: passes `data` through on status 200, otherwise returns `{"error": data.get("error", fallback_message)}`.

---

## Architecture Rules

- **Direct-call only.** `mcp_server/` imports from `tidal_api/routes/` directly. Never add HTTP calls, Flask, or `requests` between the layers.
- **New MCP tools** go in `mcp_server/server.py` as `@mcp.tool()` decorated functions. They must call `_get_session()` first and delegate business logic to `tidal_api/routes/`.
- **New business logic** goes in `tidal_api/routes/` as plain functions returning `(dict, int)` tuples. Keep them independently testable — accept `session: BrowserSession` as a parameter rather than loading session state themselves. **Exception:** auth routes (`tidal_api/routes/auth.py`) accept `session_file: Path` instead, since they manage session creation.
- **Session state** lives in `tidal_api/browser_session.BrowserSession` (a `tidalapi.Session` subclass). The session JSON is persisted to `SESSION_FILE` (controlled by `TIDAL_SESSION_FILE` env var, defaults to `{tempdir}/tidal-session-oauth.json`).

### Defensive `tidalapi` Access

`tidalapi` objects may be missing attributes. Always guard with `hasattr`:

```python
"description": playlist.description if hasattr(playlist, "description") else "",
"duration":    track.duration       if hasattr(track, "duration")       else 0,
```

### Pagination

Use `fetch_all_items(fetch_func, max_items, page_size)` from `tidal_api/utils.py` for any paginated TIDAL API call. The `fetch_func` must accept `(limit, offset)` as **keyword arguments**:

```python
def fetch_page(limit, offset):
    return list(playlist.items(limit=limit, offset=offset))

all_tracks = fetch_all_items(fetch_page, max_items=limit, page_size=100)
```

---

## Testing

Tests live in `tests/`. No external dependencies — mock `tidalapi` and `mcp` at import time using `unittest.mock`.

- `tests/test_utils.py` — unit tests for `bound_limit`, `fetch_all_items`, `format_track_data`
- `tests/test_server.py` — unit tests for `_call()` (patches FastMCP and tidalapi at import)

When adding tests for route functions, pass a `MagicMock()` as the `session` argument and assert on what methods were called and what the function returned. No live TIDAL credentials needed.
