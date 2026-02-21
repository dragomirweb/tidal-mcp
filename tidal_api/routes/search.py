"""Search route implementation logic."""

import tidalapi
from typing import Optional, Tuple

from tidal_api.browser_session import BrowserSession
from tidal_api.utils import format_track_data, bound_limit

VALID_SEARCH_TYPES = {"all", "tracks", "albums", "artists", "playlists"}


def comprehensive_search(
    session: BrowserSession,
    query: str,
    search_type: str = "all",
    limit: int = 50,
) -> Tuple[dict, int]:
    """Implementation logic for comprehensive search."""
    try:
        if not query or not query.strip():
            return {"error": "query cannot be empty."}, 400

        if search_type not in VALID_SEARCH_TYPES:
            return {
                "error": f"Invalid search_type '{search_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_SEARCH_TYPES))}"
            }, 400

        limit = bound_limit(limit)
        results = {}

        # Single API call — tidalapi returns all content types at once.
        search_results = session.search(query, limit=limit)

        if search_type == "all" or search_type == "tracks":
            tracks = _extract_tracks(search_results)
            if tracks:
                results["tracks"] = {
                    "items": [format_track_data(track) for track in tracks[:limit]],
                    "total": len(tracks[:limit]),
                }

        if search_type == "all" or search_type == "albums":
            albums = _extract_albums(search_results)
            if albums:
                results["albums"] = {
                    "items": [_format_album(a) for a in albums[:limit]],
                    "total": len(albums[:limit]),
                }

        if search_type == "all" or search_type == "artists":
            artists = _extract_artists(search_results)
            if artists:
                results["artists"] = {
                    "items": [_format_artist(a) for a in artists[:limit]],
                    "total": len(artists[:limit]),
                }

        if search_type == "all" or search_type == "playlists":
            playlists = _extract_playlists(search_results)
            if playlists:
                results["playlists"] = {
                    "items": [_format_playlist(p) for p in playlists[:limit]],
                    "total": len(playlists[:limit]),
                }

        # Create summary
        summary = {}
        for result_type, data in results.items():
            if "total" in data:
                summary[result_type] = data["total"]

        return {
            "query": query,
            "searchType": search_type,
            "limit": limit,
            "results": results,
            "summary": summary,
        }, 200

    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}, 500


# =============================================================================
# Extraction helpers — pull typed lists from tidalapi search results
# =============================================================================


def _extract_tracks(search_results):
    """Extract tracks list from a tidalapi search result object."""
    if hasattr(search_results, "tracks") and search_results.tracks:
        return search_results.tracks
    if isinstance(search_results, dict) and "tracks" in search_results:
        return search_results["tracks"]
    if isinstance(search_results, list):
        return search_results
    return []


def _extract_albums(search_results):
    """Extract albums list from a tidalapi search result object."""
    if hasattr(search_results, "albums") and search_results.albums:
        return search_results.albums
    if isinstance(search_results, dict) and "albums" in search_results:
        return search_results["albums"]
    return []


def _extract_artists(search_results):
    """Extract artists list from a tidalapi search result object."""
    if hasattr(search_results, "artists") and search_results.artists:
        return search_results.artists
    if isinstance(search_results, dict) and "artists" in search_results:
        return search_results["artists"]
    return []


def _extract_playlists(search_results):
    """Extract playlists list from a tidalapi search result object."""
    if hasattr(search_results, "playlists") and search_results.playlists:
        return search_results.playlists
    if isinstance(search_results, dict) and "playlists" in search_results:
        return search_results["playlists"]
    return []


# =============================================================================
# Formatting helpers — convert tidalapi objects to plain dicts
# =============================================================================


def _format_album(album) -> dict:
    """Format a tidalapi Album object into a plain dict."""
    return {
        "id": album.id,
        "title": album.name,
        "artist": album.artist.name if album.artist else "Unknown Artist",
        "release_date": str(album.release_date)
        if hasattr(album, "release_date") and album.release_date
        else None,
        "num_tracks": album.num_tracks if hasattr(album, "num_tracks") else 0,
        "duration": album.duration if hasattr(album, "duration") else 0,
        "explicit": album.explicit if hasattr(album, "explicit") else False,
        "url": f"https://tidal.com/browse/album/{album.id}?u",
    }


def _format_artist(artist) -> dict:
    """Format a tidalapi Artist object into a plain dict."""
    return {
        "id": artist.id,
        "name": artist.name,
        "url": f"https://tidal.com/browse/artist/{artist.id}?u",
    }


def _format_playlist(playlist) -> dict:
    """Format a tidalapi Playlist object into a plain dict."""
    return {
        "id": playlist.id,
        "title": playlist.name,
        "description": playlist.description
        if hasattr(playlist, "description")
        else None,
        "creator": playlist.creator.name
        if hasattr(playlist, "creator") and playlist.creator
        else "Unknown",
        "num_tracks": playlist.num_tracks if hasattr(playlist, "num_tracks") else 0,
        "duration": playlist.duration if hasattr(playlist, "duration") else 0,
        "url": f"https://tidal.com/browse/playlist/{playlist.id}?u",
    }


def search_tracks_only(
    session: BrowserSession, query: str, limit: int = 50
) -> Tuple[dict, int]:
    """Implementation logic for tracks-only search."""
    try:
        if not query or not query.strip():
            return {"error": "query cannot be empty."}, 400

        limit = bound_limit(limit)

        # Try the basic search first
        results = session.search(query, limit=limit)

        # Check if results is a dict or has tracks attribute
        if hasattr(results, "tracks") and results.tracks:
            formatted_results = [format_track_data(track) for track in results.tracks]
        elif isinstance(results, dict) and "tracks" in results:
            formatted_results = [
                format_track_data(track) for track in results["tracks"]
            ]
        elif isinstance(results, list):
            formatted_results = [format_track_data(track) for track in results]
        else:
            # Try with specific models parameter
            results = session.search(query, models=[tidalapi.Track], limit=limit)

            if hasattr(results, "tracks") and results.tracks:
                formatted_results = [
                    format_track_data(track) for track in results.tracks
                ]
            elif isinstance(results, dict) and "tracks" in results:
                formatted_results = [
                    format_track_data(track) for track in results["tracks"]
                ]
            elif isinstance(results, list):
                formatted_results = [format_track_data(track) for track in results]
            else:
                return {
                    "query": query,
                    "type": "tracks",
                    "limit": limit,
                    "results": {"tracks": {"items": [], "total": 0}},
                    "count": 0,
                }, 200

        return {
            "query": query,
            "type": "tracks",
            "limit": limit,
            "results": {
                "tracks": {"items": formatted_results, "total": len(formatted_results)}
            },
            "count": len(formatted_results),
        }, 200

    except Exception as e:
        return {"error": f"Track search failed: {str(e)}"}, 500


def search_albums_only(
    session: BrowserSession, query: str, limit: int = 50
) -> Tuple[dict, int]:
    """Implementation logic for albums-only search."""
    try:
        if not query or not query.strip():
            return {"error": "query cannot be empty."}, 400

        limit = bound_limit(limit)
        results = session.search(query, models=[tidalapi.Album], limit=limit)

        albums = _extract_albums(results)
        if albums:
            formatted_results = [_format_album(a) for a in albums]
            return {
                "query": query,
                "type": "albums",
                "limit": limit,
                "results": {
                    "albums": {
                        "items": formatted_results,
                        "total": len(formatted_results),
                    }
                },
                "count": len(formatted_results),
            }, 200
        else:
            return {
                "query": query,
                "type": "albums",
                "limit": limit,
                "results": {"albums": {"items": [], "total": 0}},
                "count": 0,
            }, 200

    except Exception as e:
        return {"error": f"Album search failed: {str(e)}"}, 500


def search_artists_only(
    session: BrowserSession, query: str, limit: int = 50
) -> Tuple[dict, int]:
    """Implementation logic for artists-only search."""
    try:
        if not query or not query.strip():
            return {"error": "query cannot be empty."}, 400

        limit = bound_limit(limit)
        results = session.search(query, models=[tidalapi.Artist], limit=limit)

        artists = _extract_artists(results)
        if artists:
            formatted_results = [_format_artist(a) for a in artists]
            return {
                "query": query,
                "type": "artists",
                "limit": limit,
                "results": {
                    "artists": {
                        "items": formatted_results,
                        "total": len(formatted_results),
                    }
                },
                "count": len(formatted_results),
            }, 200
        else:
            return {
                "query": query,
                "type": "artists",
                "limit": limit,
                "results": {"artists": {"items": [], "total": 0}},
                "count": 0,
            }, 200

    except Exception as e:
        return {"error": f"Artist search failed: {str(e)}"}, 500


def search_playlists_only(
    session: BrowserSession, query: str, limit: int = 50
) -> Tuple[dict, int]:
    """Implementation logic for playlists-only search."""
    try:
        if not query or not query.strip():
            return {"error": "query cannot be empty."}, 400

        limit = bound_limit(limit)
        results = session.search(query, models=[tidalapi.Playlist], limit=limit)

        playlists = _extract_playlists(results)
        if playlists:
            formatted_results = [_format_playlist(p) for p in playlists]
            return {
                "query": query,
                "type": "playlists",
                "limit": limit,
                "results": {
                    "playlists": {
                        "items": formatted_results,
                        "total": len(formatted_results),
                    }
                },
                "count": len(formatted_results),
            }, 200
        else:
            return {
                "query": query,
                "type": "playlists",
                "limit": limit,
                "results": {"playlists": {"items": [], "total": 0}},
                "count": 0,
            }, 200

    except Exception as e:
        return {"error": f"Playlist search failed: {str(e)}"}, 500
