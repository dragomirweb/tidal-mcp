# TIDAL MCP

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

### Option 1: Docker

1. Clone the repository:
   ```bash
   git clone https://github.com/dragomirweb/tidal-mcp.git
   cd tidal-mcp
   ```

2. Authenticate with TIDAL (run once — saves the session to `/tmp`):
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

   Open the URL, log in, and the session is saved to `/tmp/tidal-session-oauth.json`.

3. Build the image:
   ```bash
   docker build -t tidal-mcp .
   ```

4. Configure your MCP client (see [MCP Client Configuration](#mcp-client-configuration)) and restart it.

### Option 2: Local Python

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

**Docker:**
```json
{
  "mcpServers": {
    "TIDAL Integration": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--network", "host",
        "-v", "/tmp:/tmp",
        "tidal-mcp"
      ]
    }
  }
}
```

- `--network host` — lets the container reach the host network
- `-v /tmp:/tmp` — mounts host `/tmp` so the TIDAL session persists across container restarts

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

**Local — Windows:**
```json
{
  "mcpServers": {
    "TIDAL Integration": {
      "command": "C:\\path\\to\\tidal-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\tidal-mcp\\start_mcp.py"],
      "env": {
        "TEMP": "C:\\Windows\\Temp"
      }
    }
  }
}
```

> **Windows note:** The `TEMP` env var ensures the OAuth session file is written to a consistent path accessible by both the MCP server and any external auth scripts.

### Cursor

Add to `~/.cursor/mcp.json`:

**macOS / Linux:**
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

**Windows:**
```json
{
  "mcpServers": {
    "TIDAL Integration": {
      "command": "C:\\path\\to\\tidal-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\tidal-mcp\\start_mcp.py"],
      "env": {
        "TEMP": "C:\\Windows\\Temp"
      }
    }
  }
}
```

## Authentication

The first time you use TIDAL MCP (or after your session expires), ask your AI assistant to log you in:

> _"Log me into TIDAL"_

The assistant calls `tidal_login`, which returns a URL immediately. Open the URL in your browser and approve the TIDAL authorization. The assistant then polls `tidal_check_login` automatically until the login completes.

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

```bash
# Install dependencies
uv sync

# Syntax-check all source files (what CI runs)
python -m compileall mcp_server/ tidal_api/

# Run the auth CLI (one-shot OAuth flow, writes session to /tmp)
python auth_cli.py
```

Tests live under `tests/` and run with `pytest`. CI validates syntax and runs the test suite on every push to `main`.

## License

[MIT License](LICENSE)

## Acknowledgements

**Original Projects:**
- [yuhuacheng/tidal-mcp](https://github.com/yuhuacheng/tidal-mcp) — Original TIDAL MCP implementation
- [ibeal/tidal-mcp](https://github.com/ibeal/tidal-mcp) — Community fork with direct-call architecture, search, and Docker support

**Libraries & Frameworks:**
- [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol/python-sdk)
- [TIDAL Python API](https://github.com/tamland/python-tidal)
