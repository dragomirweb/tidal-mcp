# TIDAL MCP

A Model Context Protocol (MCP) server that connects AI assistants to the TIDAL music streaming API. Search, manage playlists, get recommendations, and control your TIDAL library through Claude or Cursor.

## Supported Tags

- `latest`, `v1.0.1` — Python 3.13, all dependencies up to date, zero known CVEs
- `v1.0.0` — Python 3.11, initial release

## Supported Architectures

`amd64`, `arm64` (Apple Silicon)

## Quick Start

### 1. Pull the image

```bash
docker pull dragomirweb/tidal-mcp
```

### 2. Authenticate with TIDAL

Create a directory for the session file and run the auth CLI:

```bash
mkdir -p session-data
docker run -it --rm \
  -v "$(pwd)/session-data:/app/session-data" \
  -e TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json \
  dragomirweb/tidal-mcp \
  .venv/bin/python auth_cli.py
```

Open the URL shown in the output, log in to TIDAL, and the session is saved to `session-data/tidal-session-oauth.json`.

### 3. Configure your MCP client

**Claude Desktop** — edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

**Cursor** — add the same configuration to `~/.cursor/mcp.json`.

Restart your MCP client after saving the config.

## Available Tools

### Authentication

| Tool | Description |
|---|---|
| `tidal_login` | Starts the OAuth device flow. Returns a URL to open in your browser. |
| `tidal_check_login` | Polls whether the browser OAuth has been completed. |

### Tracks & Recommendations

| Tool | Description |
|---|---|
| `get_favorite_tracks` | Retrieve your favorited tracks, sorted by date added. |
| `recommend_tracks` | Get personalized recommendations via TIDAL's track-radio feature. |

### Playlist Management

| Tool | Description |
|---|---|
| `create_tidal_playlist` | Create a new playlist and populate it with tracks. |
| `get_user_playlists` | List all your playlists, sorted by last updated. |
| `get_playlist_tracks` | Fetch all tracks from a playlist (auto-paginated). |
| `delete_tidal_playlist` | Delete a playlist permanently. |
| `add_tracks_to_playlist` | Append tracks to an existing playlist. |
| `remove_tracks_from_playlist` | Remove tracks by ID or position index. |
| `update_playlist_metadata` | Rename a playlist or update its description. |
| `reorder_playlist_tracks` | Move a track to a different position. |

### Search & Discovery

| Tool | Description |
|---|---|
| `search_tidal` | Search across all content types: tracks, albums, artists, playlists. |
| `search_tracks` | Search for tracks. |
| `search_albums` | Search for albums. |
| `search_artists` | Search for artists. |
| `search_playlists` | Search for playlists. |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TIDAL_SESSION_FILE` | `{tempdir}/tidal-session-oauth.json` | Path to the OAuth session file. Set this when using a volume mount to persist the session. |

## Source & Documentation

Full documentation, development setup, and source code: [github.com/dragomirweb/tidal-mcp](https://github.com/dragomirweb/tidal-mcp)

## License

[MIT](https://github.com/dragomirweb/tidal-mcp/blob/main/LICENSE)
