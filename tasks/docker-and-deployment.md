# Docker and Deployment

Severity: **Medium**

Vestigial configuration from the old Flask architecture, security concerns in the Docker setup, and import hacks in entry points.

---

## 1. Vestigial port and env var in Dockerfile

**File:** `Dockerfile` lines 22-23, 26

```dockerfile
# Expose the Flask port (default 5050, configurable via TIDAL_MCP_PORT)
EXPOSE 5050
ENV TIDAL_MCP_PORT=5050
```

The MCP server uses stdio transport, not HTTP. No code reads `TIDAL_MCP_PORT`. The comment references Flask which no longer exists.

**Fix:** Remove `EXPOSE 5050`, `ENV TIDAL_MCP_PORT=5050`, and the Flask comment.

---

## 2. Vestigial env var in server.json

**File:** `server.json` lines 17-25

```json
"environmentVariables": {
  "TIDAL_MCP_PORT": {
    "description": "Port for the TIDAL API Flask server (default: 5050)",
    "required": false,
    "default": "5050"
  }
}
```

Never read by any code. References non-existent Flask server.

**Fix:** Replace with `TIDAL_SESSION_FILE` (which IS respected by the code) or remove the block entirely.

---

## 3. Baked-in session file (security risk)

**File:** `Dockerfile` lines 28-29

```dockerfile
COPY tidal-session-oauth.json /tmp/tidal-session-oauth.json
```

This bakes OAuth credentials into the Docker image. Anyone who pulls the image gets the user's TIDAL session token. The build also fails if the file doesn't exist locally.

**Fix:** Remove the `COPY` line. Use a volume mount at runtime instead:
```yaml
volumes:
  - ./tidal-session-oauth.json:/tmp/tidal-session-oauth.json:ro
```

---

## 4. Container runs as root

**File:** `Dockerfile`

No `USER` directive. The container runs as root, which is a security anti-pattern.

**Fix:** Add a non-root user:
```dockerfile
RUN useradd -m appuser
USER appuser
```

---

## 5. Broken Docker layer caching

**File:** `Dockerfile` lines 13-16, 20

Source files (`mcp_server/`, `tidal_api/`, etc.) are copied before `RUN uv sync --frozen`. Any source code change invalidates the dependency install cache.

**Fix:** Copy `pyproject.toml` + `uv.lock` first, run `uv sync`, then copy source files:
```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY mcp_server/ mcp_server/
COPY tidal_api/ tidal_api/
COPY start_mcp.py auth_cli.py ./
```

---

## 6. `.dockerignore` missing key exclusions

**File:** `.dockerignore`

Not excluded from build context:
- `tidal-session-oauth.json` and `*.oauth.json` (credentials)
- `.env` and `.env.*` files (secrets)
- `tests/` (not needed at runtime)

**Fix:** Add these patterns to `.dockerignore`.

---

## 7. `sys.path` hacks in entry points

**`start_mcp.py` line 61:** `sys.path.append(".")` -- unnecessary when the package is installed via `uv sync` or `pip install -e .`.

**`auth_cli.py` lines 11-14:** Uses `sys.path.insert(0, ...)` then bare `from browser_session import BrowserSession` instead of the standard `from tidal_api.browser_session import BrowserSession`.

**Fix:** Remove `sys.path` manipulation. Use proper absolute imports. Ensure the package is installed before running these scripts.

---

## 8. `docker-compose.auth.yml` overly broad volume mount

**File:** `docker-compose.auth.yml` lines 7-8

```yaml
volumes:
  - /tmp:/tmp
```

Mounts the entire host `/tmp` into the container. Exposes all host temp files.

**Fix:** Mount only the session file path:
```yaml
volumes:
  - /tmp/tidal-session-oauth.json:/tmp/tidal-session-oauth.json
```

---

## 9. `pyproject.toml` missing sub-package declaration

**File:** `pyproject.toml` line 43

```toml
packages = ["mcp_server", "tidal_api"]
```

`tidal_api.routes` sub-package is not listed. With `setuptools`, sub-packages need explicit declaration unless `find:` is used. This would cause `tidal_api.routes` to be missing from built wheels.

**Fix:** Either add `"tidal_api.routes"` to the list, or switch to `find_packages()`.
