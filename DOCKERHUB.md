# TIDAL MCP

A Model Context Protocol (MCP) server that connects AI assistants to the TIDAL music streaming API. Search, manage playlists, get recommendations, and control your TIDAL library through Claude Desktop, Cursor, OpenCode, or Claude Code.

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

### 2. Create the session directory and authenticate

**macOS / Linux:**
```bash
mkdir -p ~/.tidal-mcp
docker run -it --rm \
  -v ~/.tidal-mcp:/app/session-data \
  -e TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json \
  dragomirweb/tidal-mcp \
  .venv/bin/python auth_cli.py
```

**Windows (PowerShell):**
```powershell
mkdir "$env:APPDATA\tidal-mcp"
docker run -it --rm `
  -v "$env:APPDATA\tidal-mcp:/app/session-data" `
  -e TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json `
  dragomirweb/tidal-mcp `
  .venv/bin/python auth_cli.py
```

Open the URL shown in the output and log in to TIDAL. The session is saved automatically.

### 3. Configure your MCP client

**Claude Desktop** — edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows).

**Cursor** — edit `~/.cursor/mcp.json`.

**macOS / Linux:**
```json
{
  "mcpServers": {
    "TIDAL Integration": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/Users/YOUR_USERNAME/.tidal-mcp:/app/session-data",
        "-e", "TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json",
        "dragomirweb/tidal-mcp"
      ]
    }
  }
}
```

Replace `/Users/YOUR_USERNAME/.tidal-mcp` with the output of `echo ~/.tidal-mcp`.

**Windows:**
```json
{
  "mcpServers": {
    "TIDAL Integration": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "C:\\Users\\YOUR_USERNAME\\AppData\\Roaming\\tidal-mcp:/app/session-data",
        "-e", "TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json",
        "dragomirweb/tidal-mcp"
      ]
    }
  }
}
```

Replace `C:\Users\YOUR_USERNAME\AppData\Roaming\tidal-mcp` with the output of `echo %APPDATA%\tidal-mcp`.

**OpenCode** — add to `opencode.json` in your project root or `~/.config/opencode/opencode.json` for global access.

**macOS / Linux:**
```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "tidal": {
      "type": "local",
      "command": [
        "docker", "run", "-i", "--rm",
        "-v", "/Users/YOUR_USERNAME/.tidal-mcp:/app/session-data",
        "-e", "TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json",
        "dragomirweb/tidal-mcp"
      ]
    }
  }
}
```

**Windows:**
```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "tidal": {
      "type": "local",
      "command": [
        "docker", "run", "-i", "--rm",
        "-v", "C:\\Users\\YOUR_USERNAME\\AppData\\Roaming\\tidal-mcp:/app/session-data",
        "-e", "TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json",
        "dragomirweb/tidal-mcp"
      ]
    }
  }
}
```

**Claude Code** — uses the `claude mcp add` CLI command. Config is stored in `~/.claude.json`.

**macOS / Linux:**
```bash
claude mcp add --transport stdio --scope user tidal-mcp -- \
  docker run -i --rm \
  -v /Users/YOUR_USERNAME/.tidal-mcp:/app/session-data \
  -e TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json \
  dragomirweb/tidal-mcp
```

**Windows:**
```bash
claude mcp add --transport stdio --scope user tidal-mcp -- ^
  docker run -i --rm ^
  -v C:\Users\YOUR_USERNAME\AppData\Roaming\tidal-mcp:/app/session-data ^
  -e TIDAL_SESSION_FILE=/app/session-data/tidal-session-oauth.json ^
  dragomirweb/tidal-mcp
```

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
