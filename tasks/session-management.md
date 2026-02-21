# Session Management

Severity: **Medium**

Issues with how the TIDAL session is loaded, validated, and shared across the server and CLI.

---

## 1. `_get_session()` makes a network call on every tool invocation

**File:** `mcp_server/server.py` line 79

`session.check_login()` typically makes an API call to TIDAL to verify the token. Since `_get_session()` is called at the top of every single MCP tool (15 non-auth tools), every tool invocation triggers a network round-trip before doing any actual work. A new `BrowserSession()` is constructed and validated from disk on every call.

Consequences:
- Unnecessary latency on every tool call
- Risk of rate limiting from TIDAL if tools are called rapidly
- Failures if the network is temporarily unreachable, even if the token is still valid

**Fix:** Cache the session in a module-level variable. Re-validate only on first use or after a failure.

---

## 2. Silently swallowed exceptions with misleading error message

**File:** `mcp_server/server.py` lines 77-78

When `load_session_from_file` fails (corrupt JSON, permission error, etc.), the exception is silently swallowed (`except Exception: return None`). The caller returns the generic `AUTH_ERROR_MESSAGE` ("You need to login to TIDAL first"), which is misleading when the real issue is file corruption or permissions.

**Fix:** Log the actual exception to stderr before returning `None`. Consider returning different error messages for different failure modes:
- File doesn't exist -> "No session found. Please use tidal_login()."
- Load/parse fails -> "Session file is corrupt. Please re-authenticate."
- check_login fails -> "Session expired. Please use tidal_login()."

---

## 3. Redundant `exists()` check

**File:** `mcp_server/server.py` line 72

`SESSION_FILE.exists()` is checked before attempting to load. But `load_session_from_file` on line 76 would raise `FileNotFoundError` if the file doesn't exist, which is caught by the `except Exception` on line 77. The `exists()` check is redundant.

**Fix:** Remove the `exists()` check, or keep it but make the error messages more specific (see item 2).

---

## 4. `auth_cli.py` SESSION_FILE diverges from server

**Files:** `auth_cli.py` line 16 vs `mcp_server/utils.py` lines 23-27

`auth_cli.py` hardcodes:
```python
SESSION_FILE = Path(tempfile.gettempdir()) / 'tidal-session-oauth.json'
```

`mcp_server/utils.py` supports an env var override:
```python
SESSION_FILE = Path(os.environ.get("TIDAL_SESSION_FILE", ...))
```

If a user sets `TIDAL_SESSION_FILE` to a custom path, `auth_cli.py` writes the session to the default location while `server.py` reads from the custom location. They will disagree, and authentication will appear to fail.

**Fix:** Have `auth_cli.py` import `SESSION_FILE` from `mcp_server.utils` (requires fixing the `sys.path` hack), or at minimum replicate the env var logic.

---

## 5. Thread safety issues in auth.py

**File:** `tidal_api/routes/auth.py` lines 30-68, 82-115

**TOCTOU in `handle_login_poll`:** The lock is acquired at line 82 to read `_pending` into a local variable, then immediately released. All subsequent operations happen outside the lock. A concurrent call could read the same state and both would race to save the session.

**TOCTOU in `handle_login_start`:** Does not check whether `_pending` is already set before starting a new OAuth flow. A second call overwrites the first `_pending`, orphaning the first OAuth future.

Real-world risk is low since MCP is single-threaded over stdio, but the locking infrastructure implies intent to be thread-safe.

---

## 6. `fetch_all_items` returns partial data silently on exception

**File:** `tidal_api/utils.py` lines 78-83

Any exception during pagination (network error, auth expiry) is caught, a message is printed to stderr, and whatever was fetched so far is returned. The caller has no way to know pagination was incomplete. This could lead to silently truncated data.

**Fix:** Either raise the exception (let the route handle it), or include a flag in the return value indicating incomplete results.

---

## 7. `fetch_all_items` has no infinite loop protection

**File:** `tidal_api/utils.py` lines 52-83

If `fetch_func` ignores the `offset` parameter and always returns the same non-empty list, the loop runs forever when `max_items=None`. There is no maximum iteration guard.

**Fix:** Add a reasonable maximum iteration count (e.g., 1000 pages) as a safety valve.
