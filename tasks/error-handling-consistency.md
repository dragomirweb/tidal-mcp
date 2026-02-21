# Error Handling Consistency

Severity: **High**

The error handling patterns are inconsistent across layers, which means LLM clients checking for errors may miss failures entirely.

---

## 1. Auth tools return a different error shape than all other tools

**Files:** `mcp_server/server.py` lines 120-129 (`tidal_login`), lines 150-159 (`tidal_check_login`)

Auth tools return errors as:
```python
{"status": "error", "message": "Login initiation failed."}
```

All 15 other tools return errors as:
```python
{"error": "some error message"}
```

An LLM or client checking `result.get("error")` to detect failures will miss auth errors entirely. These should use the same `{"error": ...}` shape, ideally by using the `_call()` helper like every other tool.

---

## 2. `recommend_tracks` bypasses `_call()` with inline business logic

**File:** `mcp_server/server.py` lines 262-309

This tool manually destructures `(data, status)` tuples and checks `fav_status != 200` / `rec_status != 200` inline, rather than using `_call()`. It also contains ~50 lines of business logic (building seed lists, filtering duplicates, assembling the response) that should live in a route function in `tidal_api/routes/tracks.py`.

**Fix:** Extract the orchestration logic into a new route function and have the tool use `_call()` like all other non-auth tools.

---

## 3. Search routes double-validate auth; other routes don't

**File:** `tidal_api/routes/search.py` lines 19, 172, 252, 309, 357

All five search functions call `session.check_login()` at the top and return 401 if it fails. No function in `tracks.py` or `playlists.py` does this. This is redundant with `_get_session()` in `server.py` which already validates the session before calling any route.

**Fix:** Remove the `check_login()` calls from search routes. The server layer already handles this.

---

## 4. `_call()` docstring says "HTTP" but there is no HTTP

**File:** `mcp_server/server.py` lines 85-96

The docstring references "http_status" (line 85), "HTTP 200" (line 88), and the fallback error message says `f"Operation failed (HTTP {status})."` (line 96). These are conventional status codes in a direct-call architecture -- the word "HTTP" is misleading.

**Fix:** Replace "HTTP" with "status" throughout the `_call()` docstring and fallback message.

---

## 5. Inconsistent status codes across routes

The specific non-200 codes (400, 401, 404, 500) are never surfaced to callers since `_call()` only checks `== 200` vs everything else. However, the inconsistency is confusing for maintenance:

- `search.py` returns 401 for auth failures
- `auth.py` returns 400 for "no login in progress" and 401 for "authorization failed"
- `tracks.py` and `playlists.py` only use 400 and 500

Low priority, but worth normalizing if touching these files for other reasons.
