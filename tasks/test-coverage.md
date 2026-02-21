# Test Coverage

Severity: **Medium**

Only `_call()`, `bound_limit`, `fetch_all_items`, and `format_track_data` have tests. Everything else -- 19 route functions, 17 MCP tools, and key helpers -- has zero coverage.

---

## 1. Route functions with zero tests

| Module | Functions | Count |
|---|---|---|
| `tidal_api/routes/auth.py` | `handle_login_start`, `handle_login_poll`, `check_auth_status` | 3 |
| `tidal_api/routes/tracks.py` | `get_user_tracks`, `get_single_track_recommendations`, `get_batch_track_recommendations` | 3 |
| `tidal_api/routes/playlists.py` | `create_new_playlist`, `get_playlists`, `get_tracks_from_playlist`, `delete_playlist_by_id`, `add_tracks`, `remove_tracks`, `update_playlist_metadata`, `move_track` | 8 |
| `tidal_api/routes/search.py` | `comprehensive_search`, `search_tracks_only`, `search_albums_only`, `search_artists_only`, `search_playlists_only` | 5 |

These are all independently testable by passing a `MagicMock()` as the `session` argument.

---

## 2. MCP tools with zero tests

All 17 `@mcp.tool()` functions in `mcp_server/server.py` are untested. Key ones to prioritize:

- `tidal_login` / `tidal_check_login` -- have non-standard error handling (see `error-handling-consistency.md`)
- `recommend_tracks` -- contains significant inline business logic
- `get_favorite_tracks`, `get_playlist_tracks` -- most commonly used tools

---

## 3. Key helpers with zero tests

- `_get_session()` (`server.py:66`) -- the central auth gate for all tools
- `SESSION_FILE` path resolution (`mcp_server/utils.py`) -- env var override logic
- `BrowserSession` class (`tidal_api/browser_session.py`)

---

## 4. Fragile `sys.modules` mocking pattern

**File:** `tests/test_server.py` lines 22-28

The test patches `sys.modules` to mock `mcp`, `tidalapi`, and all `tidal_api` submodules before importing `server.py`. This list must be manually kept in sync with `server.py`'s imports. Adding any new route import to `server.py` will break the test without an obvious error message.

**Fix:** Consider a conftest.py that auto-discovers and mocks all `tidal_api.*` modules, or restructure tests to mock at a higher level.

---

## 5. Suggested testing priorities

**High value, low effort (route functions):**
1. `get_tracks_from_playlist` -- most common operation, exercises pagination
2. `add_tracks` / `remove_tracks` -- mutation operations
3. `comprehensive_search` -- has the redundant API call bug (see `error-handling-consistency.md`)
4. `handle_login_start` / `handle_login_poll` -- auth flow is critical path

**Medium value (server tools):**
5. `recommend_tracks` -- most complex tool, inline business logic
6. `tidal_login` / `tidal_check_login` -- non-standard error format

---

## 6. Additional code quality issues found during review

**Missing `hasattr` guards in `create_new_playlist`:**
`playlists.py` lines 24-32 access `playlist.description`, `playlist.created`, `playlist.last_updated`, `playlist.num_tracks`, `playlist.duration` without `hasattr` guards, unlike `get_playlists` (lines 54-64) which guards every optional attribute. Inconsistent within the same file.

**URL format inconsistency:**
- `playlists.py:65`: `https://tidal.com/playlist/{id}` (no `/browse/`, no `?u`)
- `search.py:136,381`: `https://tidal.com/browse/playlist/{id}?u` (with `/browse/` and `?u`)

**Variable shadowing in tracks.py:**
- Line 60: loop variable `track` shadows outer `track` from line 55
- Line 113: `track_id` reuse shadows outer scope's iteration variable

**`comprehensive_search` calls `session.search()` 4 times for `search_type="all"`:**
`search.py` lines 26, 45, 83, 108 each call `session.search(query, limit=limit)` separately for each content type. A single call returns all types -- 4 calls is 4x the API requests for no reason.
