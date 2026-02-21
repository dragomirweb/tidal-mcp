"""Search route implementation logic."""

import tidalapi
from typing import Optional, Tuple

from tidal_api.browser_session import BrowserSession
from tidal_api.utils import format_track_data, bound_limit


def comprehensive_search(
    session: BrowserSession,
    query: str,
    search_type: str = "all",
    limit: int = 50,
) -> Tuple[dict, int]:
    """Implementation logic for comprehensive search."""
    try:
        if not session.check_login():
            return {"error": "Not authenticated with TIDAL"}, 401

        limit = bound_limit(limit)
        results = {}

        if search_type == "all" or search_type == "tracks":
            track_results = session.search(query, limit=limit)

            tracks = []
            if hasattr(track_results, "tracks") and track_results.tracks:
                tracks = track_results.tracks
            elif isinstance(track_results, dict) and "tracks" in track_results:
                tracks = track_results["tracks"]
            elif isinstance(track_results, list):
                tracks = track_results

            if tracks:
                results["tracks"] = {
                    "items": [format_track_data(track) for track in tracks[:limit]],
                    "total": len(tracks[:limit]),
                }

        if search_type == "all" or search_type == "albums":
            album_results = session.search(query, limit=limit)

            albums = []
            if hasattr(album_results, "albums") and album_results.albums:
                albums = album_results.albums
            elif isinstance(album_results, dict) and "albums" in album_results:
                albums = album_results["albums"]

            if albums:
                formatted_albums = []
                for album in albums[:limit]:
                    album_data = {
                        "id": album.id,
                        "title": album.name,
                        "artist": album.artist.name
                        if album.artist
                        else "Unknown Artist",
                        "release_date": str(album.release_date)
                        if hasattr(album, "release_date") and album.release_date
                        else None,
                        "num_tracks": album.num_tracks
                        if hasattr(album, "num_tracks")
                        else 0,
                        "duration": album.duration if hasattr(album, "duration") else 0,
                        "explicit": album.explicit
                        if hasattr(album, "explicit")
                        else False,
                        "url": f"https://tidal.com/browse/album/{album.id}?u",
                    }
                    formatted_albums.append(album_data)
                results["albums"] = {
                    "items": formatted_albums,
                    "total": len(formatted_albums),
                }

        if search_type == "all" or search_type == "artists":
            artist_results = session.search(query, limit=limit)

            artists = []
            if hasattr(artist_results, "artists") and artist_results.artists:
                artists = artist_results.artists
            elif isinstance(artist_results, dict) and "artists" in artist_results:
                artists = artist_results["artists"]

            if artists:
                formatted_artists = []
                for artist in artists[:limit]:
                    artist_data = {
                        "id": artist.id,
                        "name": artist.name,
                        "url": f"https://tidal.com/browse/artist/{artist.id}?u",
                    }
                    formatted_artists.append(artist_data)
                results["artists"] = {
                    "items": formatted_artists,
                    "total": len(formatted_artists),
                }

        if search_type == "all" or search_type == "playlists":
            playlist_results = session.search(query, limit=limit)

            playlists = []
            if hasattr(playlist_results, "playlists") and playlist_results.playlists:
                playlists = playlist_results.playlists
            elif isinstance(playlist_results, dict) and "playlists" in playlist_results:
                playlists = playlist_results["playlists"]

            if playlists:
                formatted_playlists = []
                for playlist in playlists[:limit]:
                    playlist_data = {
                        "id": playlist.id,
                        "title": playlist.name,
                        "description": playlist.description
                        if hasattr(playlist, "description")
                        else None,
                        "creator": playlist.creator.name
                        if hasattr(playlist, "creator") and playlist.creator
                        else "Unknown",
                        "num_tracks": playlist.num_tracks
                        if hasattr(playlist, "num_tracks")
                        else 0,
                        "duration": playlist.duration
                        if hasattr(playlist, "duration")
                        else 0,
                        "url": f"https://tidal.com/browse/playlist/{playlist.id}?u",
                    }
                    formatted_playlists.append(playlist_data)
                results["playlists"] = {
                    "items": formatted_playlists,
                    "total": len(formatted_playlists),
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


def search_tracks_only(
    session: BrowserSession, query: str, limit: int = 50
) -> Tuple[dict, int]:
    """Implementation logic for tracks-only search."""
    try:
        if not session.check_login():
            return {"error": "Not authenticated with TIDAL"}, 401

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
        if not session.check_login():
            return {"error": "Not authenticated with TIDAL"}, 401

        limit = bound_limit(limit)
        results = session.search(query, models=[tidalapi.Album], limit=limit)

        if results and results.albums:
            formatted_results = []
            for album in results.albums:
                album_data = {
                    "id": album.id,
                    "title": album.name,
                    "artist": album.artist.name if album.artist else "Unknown Artist",
                    "release_date": str(album.release_date)
                    if hasattr(album, "release_date") and album.release_date
                    else None,
                    "num_tracks": album.num_tracks
                    if hasattr(album, "num_tracks")
                    else 0,
                    "duration": album.duration if hasattr(album, "duration") else 0,
                    "explicit": album.explicit if hasattr(album, "explicit") else False,
                    "url": f"https://tidal.com/browse/album/{album.id}?u",
                }
                formatted_results.append(album_data)

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
        if not session.check_login():
            return {"error": "Not authenticated with TIDAL"}, 401

        limit = bound_limit(limit)
        results = session.search(query, models=[tidalapi.Artist], limit=limit)

        if results and results.artists:
            formatted_results = []
            for artist in results.artists:
                artist_data = {
                    "id": artist.id,
                    "name": artist.name,
                    "url": f"https://tidal.com/browse/artist/{artist.id}?u",
                }
                formatted_results.append(artist_data)

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
        if not session.check_login():
            return {"error": "Not authenticated with TIDAL"}, 401

        limit = bound_limit(limit)
        results = session.search(query, models=[tidalapi.Playlist], limit=limit)

        if results and results.playlists:
            formatted_results = []
            for playlist in results.playlists:
                playlist_data = {
                    "id": playlist.id,
                    "title": playlist.name,
                    "description": playlist.description
                    if hasattr(playlist, "description")
                    else None,
                    "creator": playlist.creator.name
                    if hasattr(playlist, "creator") and playlist.creator
                    else "Unknown",
                    "num_tracks": playlist.num_tracks
                    if hasattr(playlist, "num_tracks")
                    else 0,
                    "duration": playlist.duration
                    if hasattr(playlist, "duration")
                    else 0,
                    "url": f"https://tidal.com/browse/playlist/{playlist.id}?u",
                }
                formatted_results.append(playlist_data)

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
