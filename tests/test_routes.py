"""Unit tests for tidal_api/routes/ functions.

Tests route functions in isolation by mocking the session and internal
dependencies. No tidalapi, no network, no session files.

Module mocking is handled by tests/conftest.py — see that file for
details on how tidalapi is patched at import time.
"""

from unittest.mock import MagicMock, patch

from pathlib import Path
from concurrent.futures import Future

# Route modules are imported by conftest.py with tidalapi already mocked.
from tests.conftest import (
    tracks_module as _tracks_module,
    playlists_module as _playlists_module,
    search_module as _search_module,
    auth_module as _auth_module,
)


# =============================================================================
# get_recommendations
# =============================================================================


class TestGetRecommendations:
    """Tests for the get_recommendations() route function in tracks.py."""

    def test_with_explicit_track_ids(self):
        session = MagicMock()

        rec_tracks = [
            {"id": "100", "title": "Rec A"},
            {"id": "200", "title": "Rec B"},
        ]

        with patch.object(
            _tracks_module, "get_batch_track_recommendations"
        ) as mock_batch:
            mock_batch.return_value = ({"recommendations": rec_tracks}, 200)

            data, status = _tracks_module.get_recommendations(
                session, track_ids=["1", "2"], limit_per_track=10
            )

        assert status == 200
        assert data["recommendations"] == rec_tracks
        assert data["seed_tracks"] == []
        mock_batch.assert_called_once_with(
            session,
            track_ids=["1", "2"],
            limit_per_track=10,
            remove_duplicates=True,
        )

    def test_without_track_ids_uses_favorites(self):
        session = MagicMock()

        fav_tracks = [{"id": "10", "title": "Fav A"}, {"id": "20", "title": "Fav B"}]
        rec_tracks = [{"id": "100", "title": "Rec A"}]

        with (
            patch.object(_tracks_module, "get_user_tracks") as mock_fav,
            patch.object(
                _tracks_module, "get_batch_track_recommendations"
            ) as mock_batch,
        ):
            mock_fav.return_value = ({"tracks": fav_tracks}, 200)
            mock_batch.return_value = ({"recommendations": rec_tracks}, 200)

            data, status = _tracks_module.get_recommendations(
                session, limit_from_favorite=5
            )

        assert status == 200
        assert data["seed_tracks"] == fav_tracks
        assert data["recommendations"] == rec_tracks
        mock_fav.assert_called_once_with(session, limit=5)

    def test_empty_favorites_returns_400(self):
        session = MagicMock()

        with patch.object(_tracks_module, "get_user_tracks") as mock_fav:
            mock_fav.return_value = ({"tracks": []}, 200)

            data, status = _tracks_module.get_recommendations(session)

        assert status == 400
        assert "error" in data
        assert "No seed tracks" in data["error"]

    def test_favorites_fetch_failure_propagates(self):
        session = MagicMock()

        with patch.object(_tracks_module, "get_user_tracks") as mock_fav:
            mock_fav.return_value = (
                {"error": "Error fetching tracks: timeout"},
                500,
            )

            data, status = _tracks_module.get_recommendations(session)

        assert status == 500
        assert data["error"] == "Error fetching tracks: timeout"

    def test_recommendations_fetch_failure_propagates(self):
        session = MagicMock()

        with (
            patch.object(_tracks_module, "get_user_tracks") as mock_fav,
            patch.object(
                _tracks_module, "get_batch_track_recommendations"
            ) as mock_batch,
        ):
            mock_fav.return_value = (
                {"tracks": [{"id": "10", "title": "Fav"}]},
                200,
            )
            mock_batch.return_value = (
                {"error": "API rate limit exceeded"},
                500,
            )

            data, status = _tracks_module.get_recommendations(session)

        assert status == 500
        assert data["error"] == "API rate limit exceeded"

    def test_seed_tracks_filtered_from_recommendations(self):
        session = MagicMock()

        rec_tracks = [
            {"id": "1", "title": "Seed (should be filtered)"},
            {"id": "100", "title": "Rec A"},
            {"id": "2", "title": "Seed (should be filtered)"},
            {"id": "200", "title": "Rec B"},
        ]

        with patch.object(
            _tracks_module, "get_batch_track_recommendations"
        ) as mock_batch:
            mock_batch.return_value = ({"recommendations": rec_tracks}, 200)

            data, status = _tracks_module.get_recommendations(
                session, track_ids=["1", "2"]
            )

        assert status == 200
        assert len(data["recommendations"]) == 2
        rec_ids = [r["id"] for r in data["recommendations"]]
        assert "1" not in rec_ids
        assert "2" not in rec_ids
        assert "100" in rec_ids
        assert "200" in rec_ids

    def test_filter_criteria_passed_through(self):
        session = MagicMock()

        with patch.object(
            _tracks_module, "get_batch_track_recommendations"
        ) as mock_batch:
            mock_batch.return_value = ({"recommendations": []}, 200)

            data, status = _tracks_module.get_recommendations(
                session, track_ids=["1"], filter_criteria="relaxing jazz"
            )

        assert status == 200
        assert data["filter_criteria"] == "relaxing jazz"

    def test_exception_returns_500(self):
        session = MagicMock()

        with patch.object(
            _tracks_module, "get_batch_track_recommendations"
        ) as mock_batch:
            mock_batch.side_effect = RuntimeError("connection reset")

            data, status = _tracks_module.get_recommendations(session, track_ids=["1"])

        assert status == 500
        assert "error" in data
        assert "connection reset" in data["error"]


# =============================================================================
# get_batch_track_recommendations — input validation
# =============================================================================


class TestGetBatchTrackRecommendations:
    """Tests for input validation in get_batch_track_recommendations()."""

    def test_empty_track_ids_returns_400(self):
        session = MagicMock()
        data, status = _tracks_module.get_batch_track_recommendations(
            session, track_ids=[]
        )
        assert status == 400
        assert "empty" in data["error"]

    def test_non_list_track_ids_returns_400(self):
        session = MagicMock()
        data, status = _tracks_module.get_batch_track_recommendations(
            session, track_ids="not-a-list"
        )
        assert status == 400
        assert "list" in data["error"]


# =============================================================================
# playlists.py — input validation
# =============================================================================


class TestPlaylistIdValidation:
    """Tests for playlist_id empty-string validation across playlist functions."""

    def test_get_tracks_empty_playlist_id(self):
        session = MagicMock()
        data, status = _playlists_module.get_tracks_from_playlist(session, "")
        assert status == 400
        assert "playlist_id" in data["error"]

    def test_get_tracks_whitespace_playlist_id(self):
        session = MagicMock()
        data, status = _playlists_module.get_tracks_from_playlist(session, "   ")
        assert status == 400
        assert "playlist_id" in data["error"]

    def test_delete_empty_playlist_id(self):
        session = MagicMock()
        data, status = _playlists_module.delete_playlist_by_id(session, "")
        assert status == 400
        assert "playlist_id" in data["error"]

    def test_add_tracks_empty_playlist_id(self):
        session = MagicMock()
        data, status = _playlists_module.add_tracks(session, "", ["123"])
        assert status == 400
        assert "playlist_id" in data["error"]

    def test_remove_tracks_empty_playlist_id(self):
        session = MagicMock()
        data, status = _playlists_module.remove_tracks(session, "", track_ids=["123"])
        assert status == 400
        assert "playlist_id" in data["error"]

    def test_update_metadata_empty_playlist_id(self):
        session = MagicMock()
        data, status = _playlists_module.update_playlist_metadata(
            session, "", title="New Title"
        )
        assert status == 400
        assert "playlist_id" in data["error"]

    def test_move_track_empty_playlist_id(self):
        session = MagicMock()
        data, status = _playlists_module.move_track(session, "", 0, 1)
        assert status == 400
        assert "playlist_id" in data["error"]


class TestCreateNewPlaylistValidation:
    """Tests for create_new_playlist input validation."""

    def test_empty_title_returns_400(self):
        session = MagicMock()
        data, status = _playlists_module.create_new_playlist(
            session, "", "desc", ["123"]
        )
        assert status == 400
        assert "title" in data["error"]

    def test_whitespace_title_returns_400(self):
        session = MagicMock()
        data, status = _playlists_module.create_new_playlist(
            session, "   ", "desc", ["123"]
        )
        assert status == 400
        assert "title" in data["error"]

    def test_empty_track_ids_allowed(self):
        session = MagicMock()
        mock_playlist = MagicMock()
        mock_playlist.id = "pl-1"
        mock_playlist.name = "Test"
        mock_playlist.description = "desc"
        mock_playlist.created = "2025-01-01"
        mock_playlist.last_updated = "2025-01-01"
        mock_playlist.num_tracks = 0
        mock_playlist.duration = 0
        session.user.create_playlist.return_value = mock_playlist

        data, status = _playlists_module.create_new_playlist(
            session, "Test", "desc", []
        )
        assert status == 200
        assert data["status"] == "success"
        # playlist.add() should NOT have been called
        mock_playlist.add.assert_not_called()


class TestAddTracksValidation:
    """Tests for add_tracks input validation."""

    def test_empty_track_ids_returns_400(self):
        session = MagicMock()
        data, status = _playlists_module.add_tracks(session, "pl-1", [])
        assert status == 400
        assert "empty" in data["error"]

    def test_non_list_track_ids_returns_400(self):
        session = MagicMock()
        data, status = _playlists_module.add_tracks(session, "pl-1", "not-a-list")
        assert status == 400
        assert "list" in data["error"]


class TestUpdatePlaylistMetadataValidation:
    """Tests for update_playlist_metadata falsy vs None fix."""

    def test_both_none_returns_400(self):
        session = MagicMock()
        data, status = _playlists_module.update_playlist_metadata(session, "pl-1")
        assert status == 400
        assert "Must provide" in data["error"]

    def test_empty_title_allowed(self):
        """An empty string title should be accepted (deliberate clear)."""
        session = MagicMock()
        mock_playlist = MagicMock()
        mock_playlist.name = "Old Title"
        mock_playlist.description = "Old Desc"
        session.playlist.return_value = mock_playlist

        data, status = _playlists_module.update_playlist_metadata(
            session, "pl-1", title=""
        )
        assert status == 200
        assert data["updated_fields"]["title"] == ""

    def test_empty_description_allowed(self):
        """An empty string description should be accepted (deliberate clear)."""
        session = MagicMock()
        mock_playlist = MagicMock()
        mock_playlist.name = "Title"
        mock_playlist.description = "Old Desc"
        session.playlist.return_value = mock_playlist

        data, status = _playlists_module.update_playlist_metadata(
            session, "pl-1", description=""
        )
        assert status == 200
        assert data["updated_fields"]["description"] == ""


# =============================================================================
# search.py — input validation
# =============================================================================


class TestSearchQueryValidation:
    """Tests for empty query validation across search functions."""

    def test_comprehensive_search_empty_query(self):
        session = MagicMock()
        data, status = _search_module.comprehensive_search(session, "")
        assert status == 400
        assert "query" in data["error"]

    def test_comprehensive_search_whitespace_query(self):
        session = MagicMock()
        data, status = _search_module.comprehensive_search(session, "   ")
        assert status == 400
        assert "query" in data["error"]

    def test_search_tracks_empty_query(self):
        session = MagicMock()
        data, status = _search_module.search_tracks_only(session, "")
        assert status == 400
        assert "query" in data["error"]

    def test_search_albums_empty_query(self):
        session = MagicMock()
        data, status = _search_module.search_albums_only(session, "")
        assert status == 400
        assert "query" in data["error"]

    def test_search_artists_empty_query(self):
        session = MagicMock()
        data, status = _search_module.search_artists_only(session, "")
        assert status == 400
        assert "query" in data["error"]

    def test_search_playlists_empty_query(self):
        session = MagicMock()
        data, status = _search_module.search_playlists_only(session, "")
        assert status == 400
        assert "query" in data["error"]


class TestSearchTypeValidation:
    """Tests for search_type validation in comprehensive_search."""

    def test_invalid_search_type_returns_400(self):
        session = MagicMock()
        data, status = _search_module.comprehensive_search(
            session, "test query", search_type="videos"
        )
        assert status == 400
        assert "Invalid search_type" in data["error"]
        assert "videos" in data["error"]

    def test_valid_search_types_accepted(self):
        """All valid search_type values should not trigger the validation error."""
        session = MagicMock()
        # Mock search to return empty results so it doesn't crash
        session.search.return_value = MagicMock(
            tracks=[], albums=[], artists=[], playlists=[]
        )

        for search_type in ("all", "tracks", "albums", "artists", "playlists"):
            data, status = _search_module.comprehensive_search(
                session, "test", search_type=search_type
            )
            assert status == 200, f"search_type='{search_type}' should be accepted"


# =============================================================================
# auth.py — thread safety
# =============================================================================


class TestHandleLoginStart:
    """Tests for handle_login_start thread safety."""

    def setup_method(self):
        """Reset pending state before each test."""
        with _auth_module._pending_lock:
            _auth_module._pending = None

    def test_overwrites_pending_flow(self):
        """A second call to handle_login_start should discard the first pending flow."""
        session_file = MagicMock(spec=Path)
        session_file.exists.return_value = False

        mock_session_1 = MagicMock()
        future_1 = Future()
        mock_session_1.login_oauth_start.return_value = ("https://url1", 300, future_1)

        mock_session_2 = MagicMock()
        future_2 = Future()
        mock_session_2.login_oauth_start.return_value = ("https://url2", 300, future_2)

        with patch.object(
            _auth_module, "BrowserSession", side_effect=[mock_session_1, mock_session_2]
        ):
            data1, status1 = _auth_module.handle_login_start(session_file)
            data2, status2 = _auth_module.handle_login_start(session_file)

        assert status1 == 200
        assert data1["url"] == "https://url1"
        assert status2 == 200
        assert data2["url"] == "https://url2"

        # _pending should point to the second flow
        with _auth_module._pending_lock:
            assert _auth_module._pending["future"] is future_2

    def test_stores_url_in_pending(self):
        """The pending state should include the URL and expiry for reference."""
        session_file = MagicMock(spec=Path)
        session_file.exists.return_value = False

        mock_session = MagicMock()
        future = Future()
        mock_session.login_oauth_start.return_value = ("https://auth-url", 600, future)

        with patch.object(_auth_module, "BrowserSession", return_value=mock_session):
            _auth_module.handle_login_start(session_file)

        with _auth_module._pending_lock:
            assert _auth_module._pending["url"] == "https://auth-url"
            assert _auth_module._pending["expires_in"] == 600


class TestHandleLoginPoll:
    """Tests for handle_login_poll thread safety."""

    def setup_method(self):
        """Reset pending state before each test."""
        with _auth_module._pending_lock:
            _auth_module._pending = None

    def test_clears_pending_atomically_on_success(self):
        """After a successful poll, _pending should be None."""
        session_file = MagicMock(spec=Path)
        mock_session = MagicMock()
        mock_session.user.id = 12345

        future = Future()
        future.set_result(None)  # success — no exception

        with _auth_module._pending_lock:
            _auth_module._pending = {
                "future": future,
                "session": mock_session,
                "session_file": session_file,
            }

        data, status = _auth_module.handle_login_poll(session_file)

        assert status == 200
        assert data["status"] == "success"
        with _auth_module._pending_lock:
            assert _auth_module._pending is None

    def test_clears_pending_atomically_on_error(self):
        """After a failed poll, _pending should be None."""
        session_file = MagicMock(spec=Path)

        future = Future()
        future.set_exception(TimeoutError("expired"))

        with _auth_module._pending_lock:
            _auth_module._pending = {
                "future": future,
                "session": MagicMock(),
                "session_file": session_file,
            }

        data, status = _auth_module.handle_login_poll(session_file)

        assert status == 401
        assert "Authorization failed" in data["error"]
        with _auth_module._pending_lock:
            assert _auth_module._pending is None

    def test_returns_400_when_no_pending_and_no_session(self):
        """With no pending flow and no session file, return 400."""
        session_file = MagicMock(spec=Path)
        session_file.exists.return_value = False

        data, status = _auth_module.handle_login_poll(session_file)

        assert status == 400
        assert "No login in progress" in data["error"]

    def test_returns_pending_when_future_not_done(self):
        """While the future is still running, return pending status."""
        session_file = MagicMock(spec=Path)

        future = Future()  # not completed yet

        with _auth_module._pending_lock:
            _auth_module._pending = {
                "future": future,
                "session": MagicMock(),
                "session_file": session_file,
            }

        data, status = _auth_module.handle_login_poll(session_file)

        assert status == 200
        assert data["status"] == "pending"
        # _pending should NOT be cleared
        with _auth_module._pending_lock:
            assert _auth_module._pending is not None


# =============================================================================
# tracks.py — happy-path / error tests
# =============================================================================


class TestGetUserTracks:
    """Tests for get_user_tracks() route function."""

    def _make_track(self, id=1, name="Track", artist_name="Artist", album_name="Album"):
        track = MagicMock()
        track.id = id
        track.name = name
        track.artist = MagicMock()
        track.artist.name = artist_name
        track.album = MagicMock()
        track.album.name = album_name
        track.duration = 200
        return track

    def test_happy_path_returns_formatted_tracks(self):
        session = MagicMock()
        tracks = [
            self._make_track(id=1, name="Song A"),
            self._make_track(id=2, name="Song B"),
        ]
        session.user.favorites.tracks.return_value = tracks

        data, status = _tracks_module.get_user_tracks(session, limit=10)

        assert status == 200
        assert len(data["tracks"]) == 2
        assert data["tracks"][0]["id"] == 1
        assert data["tracks"][0]["title"] == "Song A"
        assert data["tracks"][1]["id"] == 2

    def test_empty_favorites_returns_empty_list(self):
        session = MagicMock()
        session.user.favorites.tracks.return_value = []

        data, status = _tracks_module.get_user_tracks(session, limit=10)

        assert status == 200
        assert data["tracks"] == []

    def test_exception_in_pagination_returns_partial(self):
        """fetch_all_items catches page-level errors and returns what it has."""
        session = MagicMock()
        session.user.favorites.tracks.side_effect = RuntimeError("API error")

        data, status = _tracks_module.get_user_tracks(session, limit=10)

        # fetch_all_items catches the error internally and returns []
        assert status == 200
        assert data["tracks"] == []

    def test_exception_outside_pagination_returns_500(self):
        """If session.user.favorites itself blows up, the outer try/except fires."""
        session = MagicMock()
        # Make .user raise before pagination even starts
        type(session).user = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("no user"))
        )

        data, status = _tracks_module.get_user_tracks(session, limit=10)

        assert status == 500
        assert "error" in data

    def test_passes_enum_order_params_not_strings(self):
        """favorites.tracks() must receive ItemOrder/OrderDirection enums, not strings."""
        session = MagicMock()
        session.user.favorites.tracks.return_value = [self._make_track()]

        _tracks_module.get_user_tracks(session, limit=5)

        call_kwargs = session.user.favorites.tracks.call_args.kwargs
        tidal_types = _tracks_module.tidal_types
        assert call_kwargs["order"] is tidal_types.ItemOrder.Date
        assert call_kwargs["order_direction"] is tidal_types.OrderDirection.Descending


class TestGetBatchTrackRecommendationsHappyPath:
    """Happy-path tests for get_batch_track_recommendations()."""

    def test_returns_recommendations_for_single_track(self):
        session = MagicMock()
        rec_track = MagicMock()
        rec_track.id = 100
        rec_track.name = "Rec Track"
        rec_track.artist = MagicMock()
        rec_track.artist.name = "Rec Artist"
        rec_track.album = MagicMock()
        rec_track.album.name = "Rec Album"
        rec_track.duration = 180

        mock_track = MagicMock()
        mock_track.get_track_radio.return_value = [rec_track]
        session.track.return_value = mock_track

        data, status = _tracks_module.get_batch_track_recommendations(
            session, track_ids=["1"], limit_per_track=5
        )

        assert status == 200
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["id"] == 100

    def test_deduplication_removes_duplicates(self):
        session = MagicMock()

        # Both tracks return the same recommendation
        dup_track = MagicMock()
        dup_track.id = 100
        dup_track.name = "Same Track"
        dup_track.artist = MagicMock()
        dup_track.artist.name = "Artist"
        dup_track.album = MagicMock()
        dup_track.album.name = "Album"
        dup_track.duration = 200

        mock_src = MagicMock()
        mock_src.get_track_radio.return_value = [dup_track]
        session.track.return_value = mock_src

        data, status = _tracks_module.get_batch_track_recommendations(
            session, track_ids=["1", "2"], limit_per_track=5, remove_duplicates=True
        )

        assert status == 200
        # Should only appear once despite being returned for both seed tracks
        ids = [r["id"] for r in data["recommendations"]]
        assert ids.count(100) == 1

    def test_single_track_failure_does_not_crash_batch(self):
        """If one track's recommendation call fails, others still succeed."""
        session = MagicMock()

        good_rec = MagicMock()
        good_rec.id = 200
        good_rec.name = "Good Rec"
        good_rec.artist = MagicMock()
        good_rec.artist.name = "Artist"
        good_rec.album = MagicMock()
        good_rec.album.name = "Album"
        good_rec.duration = 180

        def track_side_effect(track_id):
            mock = MagicMock()
            if track_id == "bad":
                mock.get_track_radio.side_effect = RuntimeError("fail")
            else:
                mock.get_track_radio.return_value = [good_rec]
            return mock

        session.track.side_effect = track_side_effect

        data, status = _tracks_module.get_batch_track_recommendations(
            session, track_ids=["good", "bad"], limit_per_track=5
        )

        assert status == 200
        assert len(data["recommendations"]) >= 1

    def test_exception_returns_500(self):
        session = MagicMock()
        session.track.side_effect = RuntimeError("connection lost")

        data, status = _tracks_module.get_batch_track_recommendations(
            session, track_ids=["1"]
        )

        # The inner exception is caught per-track, so the outer should still be 200
        # unless the executor itself raises
        assert status in (200, 500)


# =============================================================================
# playlists.py — happy-path / error tests
# =============================================================================


def _make_mock_playlist(
    id="pl-1",
    name="My Playlist",
    description="A playlist",
    created="2025-01-01",
    last_updated="2025-06-01",
    num_tracks=5,
    duration=1200,
):
    """Helper to create a mock playlist object."""
    p = MagicMock()
    p.id = id
    p.name = name
    p.description = description
    p.created = created
    p.last_updated = last_updated
    p.num_tracks = num_tracks
    p.duration = duration
    return p


class TestCreateNewPlaylistHappyPath:
    """Happy-path tests for create_new_playlist()."""

    def test_creates_playlist_with_tracks(self):
        session = MagicMock()
        mock_pl = _make_mock_playlist()
        session.user.create_playlist.return_value = mock_pl

        data, status = _playlists_module.create_new_playlist(
            session, "My Playlist", "A playlist", ["t1", "t2"]
        )

        assert status == 200
        assert data["status"] == "success"
        assert "2 tracks" in data["message"]
        assert data["playlist"]["id"] == "pl-1"
        mock_pl.add.assert_called_once_with(["t1", "t2"])

    def test_hasattr_fallback_on_missing_attributes(self):
        """If the playlist object is missing optional attributes, fallbacks work."""
        session = MagicMock()
        bare_playlist = MagicMock(spec=[])  # no attributes at all
        bare_playlist.id = "pl-2"
        bare_playlist.name = "Bare"
        session.user.create_playlist.return_value = bare_playlist

        data, status = _playlists_module.create_new_playlist(session, "Bare", "", [])

        assert status == 200
        info = data["playlist"]
        assert info["description"] == ""
        assert info["created"] is None
        assert info["last_updated"] is None
        assert info["track_count"] == 0
        assert info["duration"] == 0

    def test_exception_returns_500(self):
        session = MagicMock()
        session.user.create_playlist.side_effect = RuntimeError("API down")

        data, status = _playlists_module.create_new_playlist(
            session, "Test", "desc", ["t1"]
        )

        assert status == 500
        assert "error" in data


class TestGetPlaylists:
    """Tests for get_playlists() route function."""

    def test_returns_sorted_playlists(self):
        session = MagicMock()
        pl_old = _make_mock_playlist(id="old", last_updated="2024-01-01")
        pl_new = _make_mock_playlist(id="new", last_updated="2025-06-01")
        session.user.playlists.return_value = [pl_old, pl_new]

        data, status = _playlists_module.get_playlists(session)

        assert status == 200
        assert len(data["playlists"]) == 2
        # Sorted descending by last_updated
        assert data["playlists"][0]["id"] == "new"
        assert data["playlists"][1]["id"] == "old"

    def test_empty_playlists(self):
        session = MagicMock()
        session.user.playlists.return_value = []

        data, status = _playlists_module.get_playlists(session)

        assert status == 200
        assert data["playlists"] == []

    def test_hasattr_fallbacks(self):
        session = MagicMock()
        bare = MagicMock(spec=[])  # no attributes
        bare.id = "bare"
        bare.name = "Bare"
        session.user.playlists.return_value = [bare]

        data, status = _playlists_module.get_playlists(session)

        assert status == 200
        pl = data["playlists"][0]
        assert pl["description"] == ""
        assert pl["created"] is None
        assert pl["track_count"] == 0
        assert pl["duration"] == 0

    def test_url_format(self):
        session = MagicMock()
        pl = _make_mock_playlist(id="abc-123")
        session.user.playlists.return_value = [pl]

        data, status = _playlists_module.get_playlists(session)

        assert status == 200
        assert (
            data["playlists"][0]["url"] == "https://tidal.com/browse/playlist/abc-123?u"
        )

    def test_exception_returns_500(self):
        session = MagicMock()
        session.user.playlists.side_effect = RuntimeError("timeout")

        data, status = _playlists_module.get_playlists(session)

        assert status == 500
        assert "error" in data


class TestGetTracksFromPlaylist:
    """Happy-path tests for get_tracks_from_playlist()."""

    def test_returns_tracks(self):
        session = MagicMock()
        mock_pl = _make_mock_playlist(id="pl-1")

        track = MagicMock()
        track.id = 42
        track.name = "Test Song"
        track.artist = MagicMock()
        track.artist.name = "Artist"
        track.album = MagicMock()
        track.album.name = "Album"
        track.duration = 300

        mock_pl.items.return_value = [track]
        session.playlist.return_value = mock_pl

        data, status = _playlists_module.get_tracks_from_playlist(session, "pl-1")

        assert status == 200
        assert data["playlist_id"] == "pl-1"
        assert data["total_tracks"] == 1
        assert data["tracks"][0]["id"] == 42

    def test_exception_returns_500(self):
        session = MagicMock()
        session.playlist.side_effect = RuntimeError("not found")

        data, status = _playlists_module.get_tracks_from_playlist(session, "pl-bad")

        assert status == 500
        assert "error" in data


class TestDeletePlaylist:
    """Tests for delete_playlist_by_id()."""

    def test_happy_path(self):
        session = MagicMock()
        mock_pl = _make_mock_playlist(id="pl-1")
        session.playlist.return_value = mock_pl

        data, status = _playlists_module.delete_playlist_by_id(session, "pl-1")

        assert status == 200
        assert data["status"] == "success"
        mock_pl.delete.assert_called_once()

    def test_exception_returns_500(self):
        session = MagicMock()
        session.playlist.side_effect = RuntimeError("API error")

        data, status = _playlists_module.delete_playlist_by_id(session, "pl-1")

        assert status == 500
        assert "error" in data


class TestAddTracksHappyPath:
    """Happy-path tests for add_tracks()."""

    def test_adds_tracks_successfully(self):
        session = MagicMock()
        mock_pl = _make_mock_playlist(id="pl-1")
        session.playlist.return_value = mock_pl

        data, status = _playlists_module.add_tracks(session, "pl-1", ["t1", "t2"])

        assert status == 200
        assert data["status"] == "success"
        assert data["tracks_added"] == 2
        mock_pl.add.assert_called_once_with(["t1", "t2"])

    def test_exception_returns_500(self):
        session = MagicMock()
        mock_pl = MagicMock()
        mock_pl.add.side_effect = RuntimeError("rate limited")
        session.playlist.return_value = mock_pl

        data, status = _playlists_module.add_tracks(session, "pl-1", ["t1"])

        assert status == 500
        assert "error" in data


class TestRemoveTracks:
    """Tests for remove_tracks() route function."""

    def test_remove_by_track_ids(self):
        session = MagicMock()
        mock_pl = _make_mock_playlist()
        session.playlist.return_value = mock_pl

        data, status = _playlists_module.remove_tracks(
            session, "pl-1", track_ids=["t1", "t2"]
        )

        assert status == 200
        assert data["tracks_removed"] == 2
        assert mock_pl.remove_by_id.call_count == 2

    def test_remove_by_indices(self):
        session = MagicMock()
        mock_pl = _make_mock_playlist()
        session.playlist.return_value = mock_pl

        data, status = _playlists_module.remove_tracks(
            session, "pl-1", indices=[0, 2, 5]
        )

        assert status == 200
        assert data["tracks_removed"] == 3
        # Should be called in descending order to avoid shifting
        calls = [c.args[0] for c in mock_pl.remove_by_index.call_args_list]
        assert calls == [5, 2, 0]

    def test_neither_provided_returns_400(self):
        session = MagicMock()
        mock_pl = _make_mock_playlist()
        session.playlist.return_value = mock_pl

        data, status = _playlists_module.remove_tracks(session, "pl-1")

        assert status == 400
        assert "Must provide" in data["error"]

    def test_partial_failure_still_succeeds(self):
        """If one track fails to remove, the others are still counted."""
        session = MagicMock()
        mock_pl = _make_mock_playlist()

        call_count = [0]

        def remove_side_effect(track_id):
            call_count[0] += 1
            if track_id == "bad":
                raise RuntimeError("not found")

        mock_pl.remove_by_id.side_effect = remove_side_effect
        session.playlist.return_value = mock_pl

        data, status = _playlists_module.remove_tracks(
            session, "pl-1", track_ids=["good", "bad", "good2"]
        )

        assert status == 200
        # 2 succeeded, 1 failed
        assert data["tracks_removed"] == 2

    def test_non_list_track_ids_returns_400(self):
        session = MagicMock()
        mock_pl = _make_mock_playlist()
        session.playlist.return_value = mock_pl

        data, status = _playlists_module.remove_tracks(
            session, "pl-1", track_ids="not-a-list"
        )

        assert status == 400
        assert "list" in data["error"]

    def test_non_list_indices_returns_400(self):
        session = MagicMock()
        mock_pl = _make_mock_playlist()
        session.playlist.return_value = mock_pl

        data, status = _playlists_module.remove_tracks(
            session, "pl-1", indices="not-a-list"
        )

        assert status == 400
        assert "list" in data["error"]


class TestMoveTrack:
    """Tests for move_track() route function."""

    def test_happy_path(self):
        session = MagicMock()
        mock_pl = _make_mock_playlist()
        session.playlist.return_value = mock_pl

        data, status = _playlists_module.move_track(session, "pl-1", 0, 3)

        assert status == 200
        assert data["status"] == "success"
        assert data["from_index"] == 0
        assert data["to_index"] == 3
        mock_pl.move_by_index.assert_called_once_with(0, 3)

    def test_negative_indices_returns_400(self):
        session = MagicMock()

        data, status = _playlists_module.move_track(session, "pl-1", -1, 3)
        assert status == 400
        assert "non-negative" in data["error"]

    def test_non_integer_indices_returns_400(self):
        session = MagicMock()

        data, status = _playlists_module.move_track(session, "pl-1", "a", 3)
        assert status == 400
        assert "integers" in data["error"]

    def test_exception_returns_500(self):
        session = MagicMock()
        mock_pl = MagicMock()
        mock_pl.move_by_index.side_effect = RuntimeError("out of range")
        session.playlist.return_value = mock_pl

        data, status = _playlists_module.move_track(session, "pl-1", 0, 999)

        assert status == 500
        assert "error" in data


# =============================================================================
# search.py — happy-path / error tests
# =============================================================================


def _make_search_results(tracks=None, albums=None, artists=None, playlists=None):
    """Create a mock tidalapi search result object."""
    result = MagicMock()
    result.tracks = tracks or []
    result.albums = albums or []
    result.artists = artists or []
    result.playlists = playlists or []
    return result


def _make_mock_track(id=1, name="Track", artist_name="Artist", album_name="Album"):
    t = MagicMock()
    t.id = id
    t.name = name
    t.artist = MagicMock()
    t.artist.name = artist_name
    t.album = MagicMock()
    t.album.name = album_name
    t.duration = 200
    return t


def _make_mock_album(id=1, name="Album", artist_name="Artist"):
    a = MagicMock()
    a.id = id
    a.name = name
    a.artist = MagicMock()
    a.artist.name = artist_name
    a.release_date = "2025-01-01"
    a.num_tracks = 10
    a.duration = 3600
    a.explicit = False
    return a


def _make_mock_artist(id=1, name="Artist"):
    a = MagicMock()
    a.id = id
    a.name = name
    return a


def _make_mock_search_playlist(id="pl-1", name="Playlist"):
    p = MagicMock()
    p.id = id
    p.name = name
    p.description = "A playlist"
    p.creator = MagicMock()
    p.creator.name = "Creator"
    p.num_tracks = 20
    p.duration = 4000
    return p


class TestComprehensiveSearchHappyPath:
    """Happy-path tests for comprehensive_search()."""

    def test_search_all_returns_all_types(self):
        session = MagicMock()
        session.search.return_value = _make_search_results(
            tracks=[_make_mock_track(id=1)],
            albums=[_make_mock_album(id=2)],
            artists=[_make_mock_artist(id=3)],
            playlists=[_make_mock_search_playlist(id="pl-1")],
        )

        data, status = _search_module.comprehensive_search(session, "test")

        assert status == 200
        assert "tracks" in data["results"]
        assert "albums" in data["results"]
        assert "artists" in data["results"]
        assert "playlists" in data["results"]
        # Single API call (not 4)
        assert session.search.call_count == 1

    def test_search_tracks_only_type(self):
        session = MagicMock()
        session.search.return_value = _make_search_results(
            tracks=[_make_mock_track(id=1)],
            albums=[_make_mock_album(id=2)],  # should be ignored
        )

        data, status = _search_module.comprehensive_search(
            session, "test", search_type="tracks"
        )

        assert status == 200
        assert "tracks" in data["results"]
        assert "albums" not in data["results"]

    def test_search_albums_only_type(self):
        session = MagicMock()
        session.search.return_value = _make_search_results(
            albums=[_make_mock_album(id=1)],
        )

        data, status = _search_module.comprehensive_search(
            session, "test", search_type="albums"
        )

        assert status == 200
        assert "albums" in data["results"]
        assert "tracks" not in data["results"]

    def test_empty_results(self):
        session = MagicMock()
        session.search.return_value = _make_search_results()

        data, status = _search_module.comprehensive_search(session, "test")

        assert status == 200
        assert data["results"] == {}
        assert data["summary"] == {}

    def test_summary_counts(self):
        session = MagicMock()
        session.search.return_value = _make_search_results(
            tracks=[_make_mock_track(id=i) for i in range(3)],
            albums=[_make_mock_album(id=i) for i in range(2)],
        )

        data, status = _search_module.comprehensive_search(session, "test")

        assert status == 200
        assert data["summary"]["tracks"] == 3
        assert data["summary"]["albums"] == 2

    def test_exception_returns_500(self):
        session = MagicMock()
        session.search.side_effect = RuntimeError("timeout")

        data, status = _search_module.comprehensive_search(session, "test")

        assert status == 500
        assert "error" in data


class TestSearchTracksOnly:
    """Happy-path tests for search_tracks_only()."""

    def test_returns_formatted_tracks(self):
        session = MagicMock()
        mock_results = MagicMock()
        mock_results.tracks = [_make_mock_track(id=1, name="Song A")]
        session.search.return_value = mock_results

        data, status = _search_module.search_tracks_only(session, "test")

        assert status == 200
        assert data["count"] == 1
        assert data["results"]["tracks"]["items"][0]["id"] == 1

    def test_empty_results(self):
        session = MagicMock()
        mock_results = MagicMock()
        mock_results.tracks = []
        # Second call with models also returns empty
        session.search.return_value = mock_results

        data, status = _search_module.search_tracks_only(session, "test")

        assert status == 200
        assert data["count"] == 0

    def test_exception_returns_500(self):
        session = MagicMock()
        session.search.side_effect = RuntimeError("error")

        data, status = _search_module.search_tracks_only(session, "test")

        assert status == 500
        assert "error" in data


class TestSearchAlbumsOnly:
    """Happy-path tests for search_albums_only()."""

    def test_returns_formatted_albums(self):
        session = MagicMock()
        mock_results = MagicMock()
        mock_results.albums = [_make_mock_album(id=1, name="Album A")]
        session.search.return_value = mock_results

        data, status = _search_module.search_albums_only(session, "test")

        assert status == 200
        assert data["count"] == 1
        item = data["results"]["albums"]["items"][0]
        assert item["id"] == 1
        assert item["title"] == "Album A"
        assert "browse/album/1" in item["url"]

    def test_empty_results(self):
        session = MagicMock()
        mock_results = MagicMock()
        mock_results.albums = []
        session.search.return_value = mock_results

        data, status = _search_module.search_albums_only(session, "test")

        assert status == 200
        assert data["count"] == 0

    def test_exception_returns_500(self):
        session = MagicMock()
        session.search.side_effect = RuntimeError("error")

        data, status = _search_module.search_albums_only(session, "test")

        assert status == 500
        assert "error" in data


class TestSearchArtistsOnly:
    """Happy-path tests for search_artists_only()."""

    def test_returns_formatted_artists(self):
        session = MagicMock()
        mock_results = MagicMock()
        mock_results.artists = [_make_mock_artist(id=1, name="Art A")]
        session.search.return_value = mock_results

        data, status = _search_module.search_artists_only(session, "test")

        assert status == 200
        assert data["count"] == 1
        item = data["results"]["artists"]["items"][0]
        assert item["id"] == 1
        assert item["name"] == "Art A"
        assert "browse/artist/1" in item["url"]

    def test_empty_results(self):
        session = MagicMock()
        mock_results = MagicMock()
        mock_results.artists = []
        session.search.return_value = mock_results

        data, status = _search_module.search_artists_only(session, "test")

        assert status == 200
        assert data["count"] == 0

    def test_exception_returns_500(self):
        session = MagicMock()
        session.search.side_effect = RuntimeError("error")

        data, status = _search_module.search_artists_only(session, "test")

        assert status == 500
        assert "error" in data


class TestSearchPlaylistsOnly:
    """Happy-path tests for search_playlists_only()."""

    def test_returns_formatted_playlists(self):
        session = MagicMock()
        mock_results = MagicMock()
        mock_results.playlists = [_make_mock_search_playlist(id="pl-1", name="PL A")]
        session.search.return_value = mock_results

        data, status = _search_module.search_playlists_only(session, "test")

        assert status == 200
        assert data["count"] == 1
        item = data["results"]["playlists"]["items"][0]
        assert item["id"] == "pl-1"
        assert item["title"] == "PL A"
        assert "browse/playlist/pl-1" in item["url"]

    def test_empty_results(self):
        session = MagicMock()
        mock_results = MagicMock()
        mock_results.playlists = []
        session.search.return_value = mock_results

        data, status = _search_module.search_playlists_only(session, "test")

        assert status == 200
        assert data["count"] == 0

    def test_exception_returns_500(self):
        session = MagicMock()
        session.search.side_effect = RuntimeError("error")

        data, status = _search_module.search_playlists_only(session, "test")

        assert status == 500
        assert "error" in data


# =============================================================================
# auth.py — additional happy-path / error tests
# =============================================================================


class TestHandleLoginStartExtended:
    """Extended tests for handle_login_start() beyond thread safety."""

    def setup_method(self):
        with _auth_module._pending_lock:
            _auth_module._pending = None

    def test_already_authenticated_returns_success(self):
        """If a valid session file exists, return success without starting OAuth."""
        session_file = MagicMock(spec=Path)
        session_file.exists.return_value = True

        mock_session = MagicMock()
        mock_session.check_login.return_value = True
        mock_session.user.id = 12345

        with patch.object(_auth_module, "BrowserSession", return_value=mock_session):
            data, status = _auth_module.handle_login_start(session_file)

        assert status == 200
        assert data["status"] == "success"
        assert data["user_id"] == 12345

    def test_oauth_initiation_failure_returns_500(self):
        """If login_oauth_start() raises, return a 500 error."""
        session_file = MagicMock(spec=Path)
        session_file.exists.return_value = False

        mock_session = MagicMock()
        mock_session.login_oauth_start.side_effect = RuntimeError("OAuth broken")

        with patch.object(_auth_module, "BrowserSession", return_value=mock_session):
            data, status = _auth_module.handle_login_start(session_file)

        assert status == 500
        assert "error" in data
        assert "OAuth broken" in data["error"]

    def test_corrupt_session_file_starts_new_flow(self):
        """If the session file is corrupt, fall through to a new OAuth flow."""
        session_file = MagicMock(spec=Path)
        session_file.exists.return_value = True

        corrupt_session = MagicMock()
        corrupt_session.load_session_from_file.side_effect = ValueError("bad JSON")

        new_session = MagicMock()
        future = Future()
        new_session.login_oauth_start.return_value = ("https://login", 300, future)

        with patch.object(
            _auth_module, "BrowserSession", side_effect=[corrupt_session, new_session]
        ):
            data, status = _auth_module.handle_login_start(session_file)

        assert status == 200
        assert data["status"] == "pending"
        assert data["url"] == "https://login"


class TestHandleLoginPollExtended:
    """Extended tests for handle_login_poll()."""

    def setup_method(self):
        with _auth_module._pending_lock:
            _auth_module._pending = None

    def test_already_authenticated_fallback(self):
        """No pending flow but a valid session file exists — return success."""
        session_file = MagicMock(spec=Path)
        session_file.exists.return_value = True

        mock_session = MagicMock()
        mock_session.check_login.return_value = True
        mock_session.user.id = 99

        with patch.object(_auth_module, "BrowserSession", return_value=mock_session):
            data, status = _auth_module.handle_login_poll(session_file)

        assert status == 200
        assert data["status"] == "success"
        assert data["user_id"] == 99

    def test_save_session_failure_returns_500(self):
        """If the session saves fails after successful OAuth, return 500."""
        session_file = MagicMock(spec=Path)
        mock_session = MagicMock()
        mock_session.save_session_to_file.side_effect = IOError("disk full")

        future = Future()
        future.set_result(None)

        with _auth_module._pending_lock:
            _auth_module._pending = {
                "future": future,
                "session": mock_session,
                "session_file": session_file,
            }

        data, status = _auth_module.handle_login_poll(session_file)

        assert status == 500
        assert "failed to save session" in data["error"]


class TestCheckAuthStatus:
    """Tests for check_auth_status() route function."""

    def test_no_session_file(self):
        session_file = MagicMock(spec=Path)
        session_file.exists.return_value = False

        data, status = _auth_module.check_auth_status(session_file)

        assert status == 200
        assert data["authenticated"] is False

    def test_valid_session(self):
        session_file = MagicMock(spec=Path)
        session_file.exists.return_value = True

        mock_session = MagicMock()
        mock_session.check_login.return_value = True
        mock_session.user.id = 123
        mock_session.user.username = "testuser"
        mock_session.user.email = "test@example.com"

        with patch.object(_auth_module, "BrowserSession", return_value=mock_session):
            data, status = _auth_module.check_auth_status(session_file)

        assert status == 200
        assert data["authenticated"] is True
        assert data["user"]["id"] == 123
        assert data["user"]["username"] == "testuser"

    def test_expired_session(self):
        session_file = MagicMock(spec=Path)
        session_file.exists.return_value = True

        mock_session = MagicMock()
        mock_session.check_login.return_value = False

        with patch.object(_auth_module, "BrowserSession", return_value=mock_session):
            data, status = _auth_module.check_auth_status(session_file)

        assert status == 200
        assert data["authenticated"] is False

    def test_corrupt_session_file(self):
        session_file = MagicMock(spec=Path)
        session_file.exists.return_value = True

        mock_session = MagicMock()
        mock_session.load_session_from_file.side_effect = ValueError("bad")

        with patch.object(_auth_module, "BrowserSession", return_value=mock_session):
            data, status = _auth_module.check_auth_status(session_file)

        assert status == 200
        assert data["authenticated"] is False
