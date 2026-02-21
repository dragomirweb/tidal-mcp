# Input Validation

Severity: **High**

Multiple route functions are missing basic input validation. AGENTS.md documents empty-string validation as the expected pattern, but most functions don't implement it.

---

## 1. Missing empty-string validation on `playlist_id`

None of these functions validate that `playlist_id` is non-empty before calling `session.playlist()`:

| Function | File | Line |
|---|---|---|
| `get_tracks_from_playlist` | `tidal_api/routes/playlists.py` | 79 |
| `delete_playlist_by_id` | `tidal_api/routes/playlists.py` | 114 |
| `add_tracks` | `tidal_api/routes/playlists.py` | 134 |
| `remove_tracks` | `tidal_api/routes/playlists.py` | 159 |
| `update_playlist_metadata` | `tidal_api/routes/playlists.py` | 216 |
| `move_track` | `tidal_api/routes/playlists.py` | 247 |

**Expected pattern** (from AGENTS.md):
```python
if not playlist_id or not playlist_id.strip():
    return {"error": "playlist_id cannot be empty."}, 400
```

---

## 2. Missing empty-string validation on `query` in search functions

All five search functions in `tidal_api/routes/search.py` (lines 10, 167, 247, 304, 352) accept `query` without checking for empty/whitespace-only strings.

---

## 3. Missing `search_type` validation

**File:** `tidal_api/routes/search.py` line 10

`comprehensive_search` accepts `search_type` with no validation that it is one of the valid values (`"all"`, `"tracks"`, `"albums"`, `"artists"`, `"playlists"`). An invalid value like `"videos"` silently returns empty results.

**Fix:** Validate against allowed values and return 400 for invalid input.

---

## 4. Unbounded `ThreadPoolExecutor`

**File:** `tidal_api/routes/tracks.py` lines 101-102

```python
with ThreadPoolExecutor(max_workers=len(track_ids)) as executor:
```

- If `track_ids` has 1000 entries, this creates 1000 threads.
- If `track_ids` is empty (`len=0`), `ThreadPoolExecutor(max_workers=0)` raises `ValueError`.

**Fix:** Cap `max_workers` at a reasonable limit (e.g., `min(len(track_ids), 10)`) and validate the list is non-empty.

---

## 5. Empty-list validation missing on `track_ids`

These functions check `isinstance(track_ids, list)` but not whether the list is empty:

- `get_batch_track_recommendations` (`tracks.py:67`)
- `add_tracks` (`playlists.py:134`)
- `create_new_playlist` (`playlists.py:9`) -- `track_ids` is optional here, but if provided as `[]` it proceeds silently

---

## 6. `update_playlist_metadata` uses falsy check instead of None check

**File:** `tidal_api/routes/playlists.py` line 224

```python
if not title and not description:
```

This means `title=""` is treated the same as `title=None`, preventing a user from deliberately clearing a title to an empty string.

**Fix:** Use `if title is None and description is None:` for correctness.

---

## 7. `format_track_data` doesn't guard `track.artist` with `hasattr`

**File:** `tidal_api/utils.py` line 15

`track.artist.name` has a `hasattr` guard on `.name`, but if `track` has no `artist` attribute at all, `AttributeError` is raised before the `.name` check executes.

**Fix:** Guard the full chain: `track.artist.name if hasattr(track, "artist") and hasattr(track.artist, "name") else "Unknown"`

---

## 8. `bound_limit` has no type guard for `None`

**File:** `tidal_api/utils.py` line 28

If called with `limit=None` (which can happen if a caller passes through an unvalidated optional), the `<` comparison with `1` raises `TypeError`. The type hint says `int` but there is no runtime check.

**Fix:** Handle `None` gracefully, e.g., `if limit is None: return max_n`.
