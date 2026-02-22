# TIDAL MCP

[![Docker Hub](https://img.shields.io/docker/v/dragomirweb/tidal-mcp?label=Docker%20Hub&sort=semver)](https://hub.docker.com/r/dragomirweb/tidal-mcp)

A Model Context Protocol (MCP) server that connects AI assistants to the TIDAL music streaming API. Search, manage playlists, get recommendations, and control your TIDAL library through Claude or Cursor.

## How It Works

```
Claude Desktop / Cursor
        │
        │  MCP JSON-RPC over stdio
        ▼
  start_mcp.py          ← entry point + stdin proxy for clean shutdown
        │
  mcp_server/server.py  ← FastMCP app, 17 tool definitions
        │
        │  direct Python function calls
        ▼
  tidal_api/routes/     ← business logic (tracks, playlists, search, auth)
        │
  tidal_api/browser_session.py  ← tidalapi.Session wrapper
        │
        │  TIDAL REST API
        ▼
      TIDAL
```

Every tool call loads the OAuth session from disk, calls the relevant `tidal_api/routes/` function directly, and returns. No internal HTTP server, no child processes, no ports.

## Installation

### Prerequisites

- Python 3.10+ **or** Docker
- [uv](https://github.com/astral-sh/uv) — only required for local (non-Docker) installation
- A TIDAL subscription

### Option 1: Docker Hub (easiest)

No cloning or building required — pull the pre-built image directly from Docker Hub. Supports both amd64 and arm64 (Apple Silicon).

1. Pull the image:
   ```bash
   docker pull dragomirweb/tidal-mcp
   ```

2. Create a directory for the session file and authenticate with TIDAL:
   ```bash
   mkdir -p session-data
   docker run -it --rm \
     -v "$(pwd)/session-data:/app/session-data" \
     -e TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json \
     dragomirweb/tidal-mcp \
     .venv/bin/python auth_cli.py
   ```

   The output will show an OAuth URL:
   ```
   ============================================================
   TIDAL LOGIN REQUIRED
   Please open this URL in your browser:

   https://link.tidal.com/XXXXX

   Expires in 300 seconds
   ============================================================
   ```

   Open the URL in your browser, log in, and the session is saved to `session-data/tidal-session-oauth.json`.

3. Configure your MCP client (see [MCP Client Configuration](#mcp-client-configuration)) and restart it.

### Option 2: Docker (build from source)

1. Clone the repository:
   ```bash
   git clone https://github.com/dragomirweb/tidal-mcp.git
   cd tidal-mcp
   ```

2. Build the image:
   ```bash
   docker build -t dragomirweb/tidal-mcp .
   ```

3. Authenticate with TIDAL (run once — saves the session to `session-data/`):
   ```bash
   docker-compose -f docker-compose.auth.yml run --rm tidal-auth
   ```

   The output will show an OAuth URL:
   ```
   ============================================================
   TIDAL LOGIN REQUIRED
   Please open this URL in your browser:

   https://link.tidal.com/XXXXX

   Expires in 300 seconds
   ============================================================
   ```

   Open the URL in your browser, log in, and the session is saved to `session-data/tidal-session-oauth.json`.

4. Configure your MCP client (see [MCP Client Configuration](#mcp-client-configuration)) and restart it.

### Option 3: Local Python

1. Clone the repository:
   ```bash
   git clone https://github.com/dragomirweb/tidal-mcp.git
   cd tidal-mcp
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Configure your MCP client (see below) and restart it. Authentication is handled through the `tidal_login` tool — no separate auth step needed.

## MCP Client Configuration

### Claude Desktop

Edit the config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**Docker — macOS / Linux:**
```json
{
  "mcpServers": {
    "TIDAL Integration": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "./session-data:/app/session-data",
        "-e", "TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json",
        "dragomirweb/tidal-mcp"
      ]
    }
  }
}
```

Replace `./session-data` with the absolute path to your `session-data/` directory if the relative path doesn't resolve.

**Docker — Windows:**
```json
{
  "mcpServers": {
    "TIDAL Integration": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "C:\\path\\to\\session-data:/app/session-data",
        "-e", "TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json",
        "dragomirweb/tidal-mcp"
      ]
    }
  }
}
```

> Docker is the recommended approach on Windows, especially when using WSL. It avoids path and venv compatibility issues between Windows and WSL Python environments.

**Local — macOS / Linux:**
```json
{
  "mcpServers": {
    "TIDAL Integration": {
      "command": "/path/to/tidal-mcp/.venv/bin/python",
      "args": ["/path/to/tidal-mcp/start_mcp.py"]
    }
  }
}
```

**Local — Windows (native Python):**
```json
{
  "mcpServers": {
    "TIDAL Integration": {
      "command": "C:\\path\\to\\tidal-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\tidal-mcp\\start_mcp.py"]
    }
  }
}
```

> Requires a native Windows Python installation (not WSL). Run `uv sync` from a Windows terminal to create the `.venv\Scripts\` venv.

### Cursor

Add to `~/.cursor/mcp.json`. The configuration is the same as Claude Desktop above — use the Docker or local variant that matches your setup:

**Docker:**
```json
{
  "mcpServers": {
    "TIDAL Integration": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "./session-data:/app/session-data",
        "-e", "TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json",
        "dragomirweb/tidal-mcp"
      ]
    }
  }
}
```

**Local:**
```json
{
  "mcpServers": {
    "TIDAL Integration": {
      "command": "/path/to/tidal-mcp/.venv/bin/python",
      "args": ["/path/to/tidal-mcp/start_mcp.py"]
    }
  }
}
```

## Authentication

The first time you use TIDAL MCP (or after your session expires), ask your AI assistant to log you in:

> _"Log me into TIDAL"_

The assistant calls `tidal_login`, which returns a URL immediately. Open the URL in your browser and approve the TIDAL authorization. The assistant then polls `tidal_check_login` automatically until the login completes.

**Docker users** can also pre-authenticate before using the MCP client:
```bash
docker-compose -f docker-compose.auth.yml run --rm tidal-auth
```
The session is saved to `session-data/tidal-session-oauth.json` and persists across container restarts via the volume mount.

## Available Tools

### Authentication

| Tool | Description |
|---|---|
| `tidal_login` | Starts the OAuth device flow. Returns immediately with a URL to open, or `success` if already authenticated. |
| `tidal_check_login` | Polls whether the browser OAuth has been completed. Call after `tidal_login` returns `pending`. |

### Tracks & Recommendations

| Tool | Description |
|---|---|
| `get_favorite_tracks(limit)` | Retrieve your TIDAL favorited tracks, sorted by date added (newest first). |
| `recommend_tracks(track_ids, filter_criteria, limit_per_track, limit_from_favorite)` | Get personalized recommendations via TIDAL's track-radio feature. Seeds from explicit track IDs or auto-fetched favorites. |

### Playlist Management

| Tool | Description |
|---|---|
| `create_tidal_playlist(title, track_ids, description)` | Create a new playlist and populate it with tracks in one call. |
| `get_user_playlists` | List all your playlists, sorted by last updated. |
| `get_playlist_tracks(playlist_id, limit)` | Fetch all tracks from a playlist (auto-paginated — no size limit). |
| `delete_tidal_playlist(playlist_id)` | Delete a playlist permanently. |
| `add_tracks_to_playlist(playlist_id, track_ids)` | Append tracks to an existing playlist. |
| `remove_tracks_from_playlist(playlist_id, track_ids, indices)` | Remove tracks by TIDAL ID or 0-based position index. |
| `update_playlist_metadata(playlist_id, title, description)` | Rename a playlist or update its description. |
| `reorder_playlist_tracks(playlist_id, from_index, to_index)` | Move a track to a different position (0-based indices). |

### Search & Discovery

| Tool | Description |
|---|---|
| `search_tidal(query, search_type, limit)` | Search across all content types: `all`, `tracks`, `albums`, `artists`, `playlists`. |
| `search_tracks(query, limit)` | Search for tracks. |
| `search_albums(query, limit)` | Search for albums. |
| `search_artists(query, limit)` | Search for artists. |
| `search_playlists(query, limit)` | Search for playlists. |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TIDAL_SESSION_FILE` | `{tempdir}/tidal-session-oauth.json` | Override the path to the OAuth session file. Useful when running multiple instances or on systems where the default temp path differs between processes. |

## Development

### Setup

```bash
uv sync              # Install dependencies
uv run pytest tests/ -v   # Run the test suite (199 tests)
```

### Testing

The test suite covers all 17 MCP tools, all 19 route functions, and all utility helpers. Tests use `unittest.mock` to mock `tidalapi` and `mcp` at import time -- no TIDAL credentials or network access needed.

```bash
uv run pytest tests/ -v                          # Full suite
uv run pytest tests/test_routes.py -v            # Route function tests only
uv run pytest tests/test_server.py -v            # MCP tool tests only
uv run pytest tests/test_routes.py::TestComprehensiveSearchHappyPath -v  # Single class
```

| Test file | Tests | Covers |
|---|---|---|
| `test_routes.py` | 98 | All route functions (auth, tracks, playlists, search) |
| `test_server.py` | 65 | All 17 MCP tools, `_call()`, `_get_session()` |
| `test_utils.py` | 27 | `bound_limit`, `fetch_all_items`, `format_track_data` |
| `test_browser_session.py` | 6 | `_ensure_https`, `BrowserSession.login_oauth_start` |
| `test_mcp_utils.py` | 3 | `SESSION_FILE` env var override logic |

### Docker

After making code changes, rebuild the image:
```bash
docker build -t dragomirweb/tidal-mcp .
```

### Other useful commands

```bash
python -m compileall mcp_server/ tidal_api/   # Syntax-check all source files
uv run python auth_cli.py                     # Standalone OAuth CLI
uv run python start_mcp.py                    # Run the MCP server directly
```

### Project structure

```
mcp_server/
  server.py          # FastMCP app, 17 @mcp.tool() definitions, session management
  utils.py           # SESSION_FILE path constant (env var controlled)

tidal_api/
  browser_session.py # BrowserSession (tidalapi.Session wrapper)
  utils.py           # format_track_data, bound_limit, fetch_all_items
  routes/
    auth.py          # handle_login_start, handle_login_poll, check_auth_status
    tracks.py        # get_user_tracks, get_recommendations, get_batch_track_recommendations
    playlists.py     # CRUD: create, get, delete, add/remove tracks, update, reorder
    search.py        # comprehensive_search + 4 type-specific search functions

tests/               # 199 unit tests (mocked deps, no credentials needed)
  conftest.py        # Centralized sys.modules mocking for tidalapi + mcp
```

## License

[MIT License](LICENSE)

## Acknowledgements

**Original Projects:**
- [yuhuacheng/tidal-mcp](https://github.com/yuhuacheng/tidal-mcp) — Original TIDAL MCP implementation
- [ibeal/tidal-mcp](https://github.com/ibeal/tidal-mcp) — Community fork with direct-call architecture, search, and Docker support

**Libraries & Frameworks:**
- [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol/python-sdk)
- [TIDAL Python API](https://github.com/tamland/python-tidal)
