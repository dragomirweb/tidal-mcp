"""Unit tests for mcp_server/server.py helper functions.

Tests the pure helper functions only — no MCP framework, no tidalapi,
no network, no session file. These are safe to run in CI.

Module mocking is handled by tests/conftest.py — see that file for
details on how tidalapi and mcp are patched at import time.
"""

import pytest
from unittest.mock import patch, MagicMock

# The server module is imported by conftest.py; grab it from there.
from tests.conftest import server_module as _server_module


# =============================================================================
# _call helper
# =============================================================================


class TestCall:
    """Tests for the _call() helper that unwraps (dict, int) route tuples."""

    def test_200_returns_data_directly(self):
        result = _server_module._call(({"tracks": [1, 2, 3]}, 200))
        assert result == {"tracks": [1, 2, 3]}

    def test_200_empty_dict(self):
        result = _server_module._call(({}, 200))
        assert result == {}

    def test_non_200_returns_error_from_data(self):
        result = _server_module._call(({"error": "not found"}, 404))
        assert result == {"error": "not found"}

    def test_non_200_fallback_message_when_no_error_key(self):
        result = _server_module._call(({}, 500))
        assert "error" in result
        assert "500" in result["error"]

    def test_401_returns_error(self):
        result = _server_module._call(({"error": "unauthorized"}, 401))
        assert result["error"] == "unauthorized"

    def test_400_returns_error(self):
        result = _server_module._call(({"error": "bad input"}, 400))
        assert result["error"] == "bad input"

    def test_data_passthrough_on_success(self):
        data = {"query": "test", "results": {"tracks": {"items": [], "total": 0}}}
        result = _server_module._call((data, 200))
        assert result is data  # same object, no copy


# =============================================================================
# _get_session / _invalidate_session / SessionError
# =============================================================================


class TestGetSession:
    """Tests for session caching, specific error messages, and invalidation."""

    def setup_method(self):
        """Clear the cached session before each test."""
        _server_module._invalidate_session()

    def test_raises_when_no_session_file(self):
        with patch.object(_server_module, "SESSION_FILE") as mock_path:
            mock_path.exists.return_value = False

            with pytest.raises(_server_module.SessionError) as exc_info:
                _server_module._get_session()

            assert "No session found" in str(exc_info.value)

    def test_raises_when_file_corrupt(self):
        mock_session = MagicMock()
        mock_session.load_session_from_file.side_effect = ValueError("bad JSON")

        with (
            patch.object(_server_module, "SESSION_FILE") as mock_path,
            patch.object(_server_module, "BrowserSession", return_value=mock_session),
        ):
            mock_path.exists.return_value = True

            with pytest.raises(_server_module.SessionError) as exc_info:
                _server_module._get_session()

            assert "corrupt or unreadable" in str(exc_info.value)

    def test_raises_when_login_expired(self):
        mock_session = MagicMock()
        mock_session.check_login.return_value = False

        with (
            patch.object(_server_module, "SESSION_FILE") as mock_path,
            patch.object(_server_module, "BrowserSession", return_value=mock_session),
        ):
            mock_path.exists.return_value = True

            with pytest.raises(_server_module.SessionError) as exc_info:
                _server_module._get_session()

            assert "expired or invalid" in str(exc_info.value)

    def test_returns_session_on_success(self):
        mock_session = MagicMock()
        mock_session.check_login.return_value = True

        with (
            patch.object(_server_module, "SESSION_FILE") as mock_path,
            patch.object(_server_module, "BrowserSession", return_value=mock_session),
        ):
            mock_path.exists.return_value = True

            result = _server_module._get_session()

        assert result is mock_session

    def test_caches_session_on_second_call(self):
        mock_session = MagicMock()
        mock_session.check_login.return_value = True

        with (
            patch.object(_server_module, "SESSION_FILE") as mock_path,
            patch.object(
                _server_module, "BrowserSession", return_value=mock_session
            ) as mock_cls,
        ):
            mock_path.exists.return_value = True

            first = _server_module._get_session()
            second = _server_module._get_session()

        assert first is second
        # BrowserSession constructor should only be called once
        assert mock_cls.call_count == 1

    def test_invalidate_clears_cache(self):
        mock_session_1 = MagicMock()
        mock_session_1.check_login.return_value = True
        mock_session_2 = MagicMock()
        mock_session_2.check_login.return_value = True

        with (
            patch.object(_server_module, "SESSION_FILE") as mock_path,
            patch.object(
                _server_module,
                "BrowserSession",
                side_effect=[mock_session_1, mock_session_2],
            ),
        ):
            mock_path.exists.return_value = True

            first = _server_module._get_session()
            _server_module._invalidate_session()
            second = _server_module._get_session()

        assert first is mock_session_1
        assert second is mock_session_2
        assert first is not second


# =============================================================================
# MCP TOOL TESTS — all 17 @mcp.tool() functions
# =============================================================================
#
# Each non-auth tool follows the same pattern:
#   1. _get_session() -> delegates to route function -> returns result
#   2. SessionError -> returns {"error": <message>}
#   3. Unexpected exception -> returns {"error": "Unexpected error: ..."}
#
# Auth tools (tidal_login, tidal_check_login) have a slightly different
# pattern because they call _invalidate_session() and don't use SessionError.


class TestTidalLoginTool:
    """Tests for the tidal_login() MCP tool."""

    def test_success(self):
        with patch.object(
            _server_module,
            "handle_login_start",
            return_value=({"status": "pending", "url": "https://auth"}, 200),
        ):
            result = _server_module.tidal_login()

        assert result == {"status": "pending", "url": "https://auth"}

    def test_invalidates_session(self):
        with (
            patch.object(
                _server_module,
                "handle_login_start",
                return_value=({"status": "pending", "url": "https://auth"}, 200),
            ),
            patch.object(_server_module, "_invalidate_session") as mock_inv,
        ):
            _server_module.tidal_login()

        mock_inv.assert_called_once()

    def test_unexpected_exception(self):
        with patch.object(
            _server_module,
            "handle_login_start",
            side_effect=RuntimeError("boom"),
        ):
            result = _server_module.tidal_login()

        assert "error" in result
        assert "Unexpected error" in result["error"]
        assert "boom" in result["error"]


class TestTidalCheckLoginTool:
    """Tests for the tidal_check_login() MCP tool."""

    def test_pending(self):
        with patch.object(
            _server_module,
            "handle_login_poll",
            return_value=({"status": "pending"}, 200),
        ):
            result = _server_module.tidal_check_login()

        assert result == {"status": "pending"}

    def test_success_invalidates_session(self):
        with (
            patch.object(
                _server_module,
                "handle_login_poll",
                return_value=({"status": "success", "user_id": 1}, 200),
            ),
            patch.object(_server_module, "_invalidate_session") as mock_inv,
        ):
            result = _server_module.tidal_check_login()

        assert result["status"] == "success"
        mock_inv.assert_called_once()

    def test_pending_does_not_invalidate(self):
        with (
            patch.object(
                _server_module,
                "handle_login_poll",
                return_value=({"status": "pending"}, 200),
            ),
            patch.object(_server_module, "_invalidate_session") as mock_inv,
        ):
            _server_module.tidal_check_login()

        mock_inv.assert_not_called()

    def test_unexpected_exception(self):
        with patch.object(
            _server_module,
            "handle_login_poll",
            side_effect=RuntimeError("boom"),
        ):
            result = _server_module.tidal_check_login()

        assert "Unexpected error" in result["error"]


class TestGetFavoriteTracksTool:
    """Tests for the get_favorite_tracks() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "get_user_tracks",
                return_value=({"tracks": [{"id": 1}]}, 200),
            ),
        ):
            result = _server_module.get_favorite_tracks(limit=5)

        assert result == {"tracks": [{"id": 1}]}

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("No session found"),
        ):
            result = _server_module.get_favorite_tracks()

        assert result == {"error": "No session found"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "get_user_tracks",
                side_effect=RuntimeError("crash"),
            ),
        ):
            result = _server_module.get_favorite_tracks()

        assert "Unexpected error" in result["error"]


class TestRecommendTracksTool:
    """Tests for the recommend_tracks() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "get_recommendations",
                return_value=({"recommendations": [], "seed_tracks": []}, 200),
            ),
        ):
            result = _server_module.recommend_tracks(track_ids=["1"])

        assert "recommendations" in result

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("expired"),
        ):
            result = _server_module.recommend_tracks()

        assert result == {"error": "expired"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "get_recommendations",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.recommend_tracks()

        assert "Unexpected error" in result["error"]


class TestCreateTidalPlaylistTool:
    """Tests for the create_tidal_playlist() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "create_new_playlist",
                return_value=({"status": "success"}, 200),
            ),
        ):
            result = _server_module.create_tidal_playlist("My PL", ["t1"])

        assert result == {"status": "success"}

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("no session"),
        ):
            result = _server_module.create_tidal_playlist("My PL", ["t1"])

        assert result == {"error": "no session"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "create_new_playlist",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.create_tidal_playlist("PL", ["t1"])

        assert "Unexpected error" in result["error"]


class TestGetUserPlaylistsTool:
    """Tests for the get_user_playlists() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "get_playlists",
                return_value=({"playlists": []}, 200),
            ),
        ):
            result = _server_module.get_user_playlists()

        assert result == {"playlists": []}

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("no session"),
        ):
            result = _server_module.get_user_playlists()

        assert result == {"error": "no session"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "get_playlists",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.get_user_playlists()

        assert "Unexpected error" in result["error"]


class TestGetPlaylistTracksTool:
    """Tests for the get_playlist_tracks() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "get_tracks_from_playlist",
                return_value=({"tracks": [], "total_tracks": 0}, 200),
            ),
        ):
            result = _server_module.get_playlist_tracks("pl-1")

        assert result == {"tracks": [], "total_tracks": 0}

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("expired"),
        ):
            result = _server_module.get_playlist_tracks("pl-1")

        assert result == {"error": "expired"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "get_tracks_from_playlist",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.get_playlist_tracks("pl-1")

        assert "Unexpected error" in result["error"]


class TestDeleteTidalPlaylistTool:
    """Tests for the delete_tidal_playlist() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "delete_playlist_by_id",
                return_value=({"status": "success"}, 200),
            ),
        ):
            result = _server_module.delete_tidal_playlist("pl-1")

        assert result == {"status": "success"}

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("no session"),
        ):
            result = _server_module.delete_tidal_playlist("pl-1")

        assert result == {"error": "no session"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "delete_playlist_by_id",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.delete_tidal_playlist("pl-1")

        assert "Unexpected error" in result["error"]


class TestAddTracksToPlaylistTool:
    """Tests for the add_tracks_to_playlist() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "add_tracks",
                return_value=({"status": "success", "tracks_added": 2}, 200),
            ),
        ):
            result = _server_module.add_tracks_to_playlist("pl-1", ["t1", "t2"])

        assert result["tracks_added"] == 2

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("no session"),
        ):
            result = _server_module.add_tracks_to_playlist("pl-1", ["t1"])

        assert result == {"error": "no session"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "add_tracks",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.add_tracks_to_playlist("pl-1", ["t1"])

        assert "Unexpected error" in result["error"]


class TestRemoveTracksFromPlaylistTool:
    """Tests for the remove_tracks_from_playlist() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "remove_tracks",
                return_value=({"status": "success", "tracks_removed": 1}, 200),
            ),
        ):
            result = _server_module.remove_tracks_from_playlist(
                "pl-1", track_ids=["t1"]
            )

        assert result["tracks_removed"] == 1

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("no session"),
        ):
            result = _server_module.remove_tracks_from_playlist(
                "pl-1", track_ids=["t1"]
            )

        assert result == {"error": "no session"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "remove_tracks",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.remove_tracks_from_playlist(
                "pl-1", track_ids=["t1"]
            )

        assert "Unexpected error" in result["error"]


class TestUpdatePlaylistMetadataTool:
    """Tests for the update_playlist_metadata() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "update_playlist_metadata_impl",
                return_value=({"status": "success"}, 200),
            ),
        ):
            result = _server_module.update_playlist_metadata("pl-1", title="New")

        assert result == {"status": "success"}

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("no session"),
        ):
            result = _server_module.update_playlist_metadata("pl-1", title="New")

        assert result == {"error": "no session"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "update_playlist_metadata_impl",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.update_playlist_metadata("pl-1", title="New")

        assert "Unexpected error" in result["error"]


class TestReorderPlaylistTracksTool:
    """Tests for the reorder_playlist_tracks() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "move_track",
                return_value=({"status": "success"}, 200),
            ),
        ):
            result = _server_module.reorder_playlist_tracks("pl-1", 0, 3)

        assert result == {"status": "success"}

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("no session"),
        ):
            result = _server_module.reorder_playlist_tracks("pl-1", 0, 3)

        assert result == {"error": "no session"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "move_track",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.reorder_playlist_tracks("pl-1", 0, 3)

        assert "Unexpected error" in result["error"]


class TestSearchTidalTool:
    """Tests for the search_tidal() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "comprehensive_search",
                return_value=({"results": {}, "summary": {}}, 200),
            ),
        ):
            result = _server_module.search_tidal("test query")

        assert "results" in result

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("no session"),
        ):
            result = _server_module.search_tidal("test")

        assert result == {"error": "no session"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "comprehensive_search",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.search_tidal("test")

        assert "Unexpected error" in result["error"]


class TestSearchTracksTool:
    """Tests for the search_tracks() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "search_tracks_only",
                return_value=({"results": {"tracks": {"items": []}}, "count": 0}, 200),
            ),
        ):
            result = _server_module.search_tracks("test")

        assert result["count"] == 0

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("no session"),
        ):
            result = _server_module.search_tracks("test")

        assert result == {"error": "no session"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "search_tracks_only",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.search_tracks("test")

        assert "Unexpected error" in result["error"]


class TestSearchAlbumsTool:
    """Tests for the search_albums() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "search_albums_only",
                return_value=({"results": {"albums": {"items": []}}, "count": 0}, 200),
            ),
        ):
            result = _server_module.search_albums("test")

        assert result["count"] == 0

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("no session"),
        ):
            result = _server_module.search_albums("test")

        assert result == {"error": "no session"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "search_albums_only",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.search_albums("test")

        assert "Unexpected error" in result["error"]


class TestSearchArtistsTool:
    """Tests for the search_artists() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "search_artists_only",
                return_value=({"results": {"artists": {"items": []}}, "count": 0}, 200),
            ),
        ):
            result = _server_module.search_artists("test")

        assert result["count"] == 0

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("no session"),
        ):
            result = _server_module.search_artists("test")

        assert result == {"error": "no session"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "search_artists_only",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.search_artists("test")

        assert "Unexpected error" in result["error"]


class TestSearchPlaylistsTool:
    """Tests for the search_playlists() MCP tool."""

    def setup_method(self):
        _server_module._invalidate_session()

    def test_success(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "search_playlists_only",
                return_value=(
                    {"results": {"playlists": {"items": []}}, "count": 0},
                    200,
                ),
            ),
        ):
            result = _server_module.search_playlists("test")

        assert result["count"] == 0

    def test_session_error(self):
        with patch.object(
            _server_module,
            "_get_session",
            side_effect=_server_module.SessionError("no session"),
        ):
            result = _server_module.search_playlists("test")

        assert result == {"error": "no session"}

    def test_unexpected_exception(self):
        mock_session = MagicMock()
        with (
            patch.object(_server_module, "_get_session", return_value=mock_session),
            patch.object(
                _server_module,
                "search_playlists_only",
                side_effect=RuntimeError("fail"),
            ),
        ):
            result = _server_module.search_playlists("test")

        assert "Unexpected error" in result["error"]
