"""Unit tests for tidal_api/utils.py pure functions.

These tests have no external dependencies — no tidalapi, no network calls,
no session files. They run instantly and are safe to run in CI.
"""

from unittest.mock import MagicMock

from tidal_api.utils import bound_limit, fetch_all_items, format_track_data
import tidal_api.utils as _utils_module


# =============================================================================
# bound_limit
# =============================================================================


class TestBoundLimit:
    def test_returns_limit_within_range(self):
        assert bound_limit(10) == 10

    def test_clamps_below_minimum(self):
        assert bound_limit(0) == 1
        assert bound_limit(-5) == 1

    def test_clamps_above_default_max(self):
        assert bound_limit(100) == 50

    def test_clamps_above_custom_max(self):
        assert bound_limit(200, max_n=100) == 100

    def test_exactly_at_max(self):
        assert bound_limit(50) == 50
        assert bound_limit(50, max_n=50) == 50

    def test_exactly_at_min(self):
        assert bound_limit(1) == 1

    def test_custom_max_within_range(self):
        assert bound_limit(30, max_n=100) == 30

    def test_none_returns_default_max(self):
        assert bound_limit(None) == 50

    def test_none_returns_custom_max(self):
        assert bound_limit(None, max_n=100) == 100


# =============================================================================
# fetch_all_items
# =============================================================================


class TestFetchAllItems:
    def test_fetches_single_page(self):
        items = [1, 2, 3]
        fetch = MagicMock(return_value=items)
        result = fetch_all_items(fetch, max_items=None, page_size=100)
        assert result == items
        fetch.assert_called_once_with(limit=100, offset=0)

    def test_fetches_multiple_pages(self):
        # Simulate 250 items: pages of 100, 100, 50
        def make_fetch(total):
            def fetch(limit, offset):
                end = min(offset + limit, total)
                return list(range(offset, end))

            return fetch

        result = fetch_all_items(make_fetch(250), max_items=None, page_size=100)
        assert result == list(range(250))

    def test_respects_max_items(self):
        def fetch(limit, offset):
            return list(range(offset, offset + limit))

        result = fetch_all_items(fetch, max_items=25, page_size=100)
        assert len(result) == 25
        assert result == list(range(25))

    def test_stops_on_empty_page(self):
        # Use page_size=3 so the first page is "full" (triggers another fetch),
        # and the second fetch returns [] which stops the loop.
        call_count = [0]

        def fetch(limit, offset):
            call_count[0] += 1
            if offset == 0:
                return [1, 2, 3]
            return []

        result = fetch_all_items(fetch, max_items=None, page_size=3)
        assert result == [1, 2, 3]
        assert call_count[0] == 2

    def test_stops_on_partial_page(self):
        # First page is full (100 items), second is partial (30 items < page_size).
        # The partial page signals the end; total = 130.
        def fetch(limit, offset):
            if offset == 0:
                return list(range(100))  # full page
            return list(range(30))  # partial — signals end

        result = fetch_all_items(fetch, max_items=None, page_size=100)
        assert len(result) == 130

    def test_handles_fetch_exception(self):
        call_count = [0]

        def fetch(limit, offset):
            call_count[0] += 1
            if offset == 0:
                return [1, 2, 3]
            raise RuntimeError("API error")

        result = fetch_all_items(fetch, max_items=None, page_size=100)
        # Returns what was collected before the error
        assert result == [1, 2, 3]

    def test_returns_empty_list_when_first_fetch_empty(self):
        fetch = MagicMock(return_value=[])
        result = fetch_all_items(fetch, max_items=None, page_size=100)
        assert result == []

    def test_max_items_zero_returns_empty(self):
        fetch = MagicMock(return_value=[1, 2, 3])
        result = fetch_all_items(fetch, max_items=0, page_size=100)
        assert result == []
        fetch.assert_not_called()

    def test_max_pages_guard_prevents_infinite_loop(self):
        """If fetch_func ignores offset and always returns full pages,
        the loop must stop after _MAX_PAGES iterations."""
        from unittest.mock import patch as _patch

        # Always return a full page (same data each time)
        fetch = MagicMock(return_value=list(range(10)))

        with _patch.object(_utils_module, "_MAX_PAGES", 5):
            result = fetch_all_items(fetch, max_items=None, page_size=10)

        # 5 pages * 10 items = 50 items
        assert len(result) == 50
        assert fetch.call_count == 5


# =============================================================================
# format_track_data
# =============================================================================


class TestFormatTrackData:
    def _make_track(
        self,
        id=123,
        name="Test Track",
        artist_name="Test Artist",
        album_name="Test Album",
        duration=200,
    ):
        track = MagicMock()
        track.id = id
        track.name = name
        track.artist = MagicMock()
        track.artist.name = artist_name
        track.album = MagicMock()
        track.album.name = album_name
        track.duration = duration
        return track

    def test_basic_fields(self):
        track = self._make_track()
        result = format_track_data(track)
        assert result["id"] == 123
        assert result["title"] == "Test Track"
        assert result["artist"] == "Test Artist"
        assert result["album"] == "Test Album"
        assert result["duration"] == 200
        assert result["url"] == "https://tidal.com/browse/track/123?u"

    def test_url_contains_track_id(self):
        track = self._make_track(id=99999)
        result = format_track_data(track)
        assert "99999" in result["url"]

    def test_source_track_id_included_when_provided(self):
        track = self._make_track()
        result = format_track_data(track, source_track_id="456")
        assert result["source_track_id"] == "456"

    def test_source_track_id_absent_when_not_provided(self):
        track = self._make_track()
        result = format_track_data(track)
        assert "source_track_id" not in result

    def test_artist_fallback_when_no_name_attr(self):
        track = self._make_track()
        # artist has no .name attribute
        del track.artist.name
        track.artist = object()  # plain object with no .name
        result = format_track_data(track)
        assert result["artist"] == "Unknown"

    def test_artist_fallback_when_no_artist_attr(self):
        track = self._make_track()
        del track.artist
        result = format_track_data(track)
        assert result["artist"] == "Unknown"

    def test_album_fallback_when_no_name_attr(self):
        track = self._make_track()
        track.album = object()  # plain object with no .name
        result = format_track_data(track)
        assert result["album"] == "Unknown"

    def test_album_fallback_when_no_album_attr(self):
        track = self._make_track()
        del track.album
        result = format_track_data(track)
        assert result["album"] == "Unknown"

    def test_duration_fallback_when_missing(self):
        track = self._make_track()
        del track.duration
        result = format_track_data(track)
        assert result["duration"] == 0
