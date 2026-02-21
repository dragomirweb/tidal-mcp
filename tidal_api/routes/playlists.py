"""Playlist route implementation logic."""

from typing import Optional, Tuple

from tidal_api.browser_session import BrowserSession
from tidal_api.utils import format_track_data, fetch_all_items


def create_new_playlist(
    session: BrowserSession, title: str, description: str, track_ids: list
) -> Tuple[dict, int]:
    """Implementation logic for creating a new playlist."""
    try:
        if not isinstance(track_ids, list):
            return {"error": "'track_ids' must be a list"}, 400

        # Create the playlist
        playlist = session.user.create_playlist(title, description)

        # Add tracks to the playlist
        playlist.add(track_ids)

        # Return playlist information
        playlist_info = {
            "id": playlist.id,
            "title": playlist.name,
            "description": playlist.description,
            "created": playlist.created,
            "last_updated": playlist.last_updated,
            "track_count": playlist.num_tracks,
            "duration": playlist.duration,
        }

        return {
            "status": "success",
            "message": f"Playlist '{title}' created successfully with {len(track_ids)} tracks",
            "playlist": playlist_info,
        }, 200

    except Exception as e:
        return {"error": f"Error creating playlist: {str(e)}"}, 500


def get_playlists(session: BrowserSession) -> Tuple[dict, int]:
    """Implementation logic for getting user playlists."""
    try:
        playlists = session.user.playlists()

        playlist_list = []
        for playlist in playlists:
            playlist_info = {
                "id": playlist.id,
                "title": playlist.name,
                "description": playlist.description
                if hasattr(playlist, "description")
                else "",
                "created": playlist.created if hasattr(playlist, "created") else None,
                "last_updated": playlist.last_updated
                if hasattr(playlist, "last_updated")
                else None,
                "track_count": playlist.num_tracks
                if hasattr(playlist, "num_tracks")
                else 0,
                "duration": playlist.duration if hasattr(playlist, "duration") else 0,
                "url": f"https://tidal.com/playlist/{playlist.id}",
            }
            playlist_list.append(playlist_info)

        # Sort playlists by last_updated in descending order
        sorted_playlists = sorted(
            playlist_list, key=lambda x: x.get("last_updated", ""), reverse=True
        )

        return {"playlists": sorted_playlists}, 200
    except Exception as e:
        return {"error": f"Error fetching playlists: {str(e)}"}, 500


def get_tracks_from_playlist(
    session: BrowserSession, playlist_id: str, limit: Optional[int] = None
) -> Tuple[dict, int]:
    """Implementation logic for getting tracks from a playlist."""
    try:
        playlist = session.playlist(playlist_id)
        if not playlist:
            return {"error": f"Playlist with ID {playlist_id} not found"}, 404

        # Use pagination helper to fetch all tracks
        def fetch_page(limit, offset):
            try:
                return list(playlist.items(limit=limit, offset=offset))
            except TypeError:
                # If offset isn't supported, try without it
                if offset == 0:
                    return list(playlist.items(limit=limit))
                else:
                    return []

        # Fetch all tracks (or up to limit if specified)
        all_tracks = fetch_all_items(fetch_page, max_items=limit, page_size=100)

        track_list = [format_track_data(track) for track in all_tracks]

        return {
            "playlist_id": playlist.id,
            "tracks": track_list,
            "total_tracks": len(track_list),
        }, 200

    except Exception as e:
        return {"error": f"Error fetching playlist tracks: {str(e)}"}, 500


def delete_playlist_by_id(
    session: BrowserSession, playlist_id: str
) -> Tuple[dict, int]:
    """Implementation logic for deleting a playlist."""
    try:
        playlist = session.playlist(playlist_id)
        if not playlist:
            return {"error": f"Playlist with ID {playlist_id} not found"}, 404

        playlist.delete()

        return {
            "status": "success",
            "message": f"Playlist {playlist_id} deleted successfully",
        }, 200

    except Exception as e:
        return {"error": f"Error deleting playlist: {str(e)}"}, 500


def add_tracks(
    session: BrowserSession, playlist_id: str, track_ids: list
) -> Tuple[dict, int]:
    """Implementation logic for adding tracks to a playlist."""
    try:
        if not isinstance(track_ids, list):
            return {"error": "'track_ids' must be a list"}, 400

        playlist = session.playlist(playlist_id)
        if not playlist:
            return {"error": f"Playlist with ID {playlist_id} not found"}, 404

        playlist.add(track_ids)

        return {
            "status": "success",
            "message": f"Added {len(track_ids)} track(s) to playlist",
            "playlist_id": playlist_id,
            "tracks_added": len(track_ids),
        }, 200

    except Exception as e:
        return {"error": f"Error adding tracks to playlist: {str(e)}"}, 500


def remove_tracks(
    session: BrowserSession,
    playlist_id: str,
    track_ids: Optional[list] = None,
    indices: Optional[list] = None,
    logger=None,
) -> Tuple[dict, int]:
    """Implementation logic for removing tracks from a playlist."""
    try:
        playlist = session.playlist(playlist_id)
        if not playlist:
            return {"error": f"Playlist with ID {playlist_id} not found"}, 404

        removed_count = 0

        # Remove by track IDs
        if track_ids is not None:
            if not isinstance(track_ids, list):
                return {"error": "'track_ids' must be a list"}, 400

            for track_id in track_ids:
                try:
                    playlist.remove_by_id(track_id)
                    removed_count += 1
                except Exception as e:
                    if logger:
                        logger.warning(f"Could not remove track {track_id}: {str(e)}")

        # Remove by indices
        elif indices is not None:
            if not isinstance(indices, list):
                return {"error": "'indices' must be a list"}, 400

            # Sort indices in descending order to avoid shifting issues
            for index in sorted(indices, reverse=True):
                try:
                    playlist.remove_by_index(index)
                    removed_count += 1
                except Exception as e:
                    if logger:
                        logger.warning(
                            f"Could not remove track at index {index}: {str(e)}"
                        )
        else:
            return {"error": "Must provide either 'track_ids' or 'indices'"}, 400

        return {
            "status": "success",
            "message": f"Removed {removed_count} track(s) from playlist",
            "playlist_id": playlist_id,
            "tracks_removed": removed_count,
        }, 200

    except Exception as e:
        return {"error": f"Error removing tracks from playlist: {str(e)}"}, 500


def update_playlist_metadata(
    session: BrowserSession,
    playlist_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> Tuple[dict, int]:
    """Implementation logic for updating playlist metadata."""
    try:
        if not title and not description:
            return {"error": "Must provide at least 'title' or 'description'"}, 400

        playlist = session.playlist(playlist_id)
        if not playlist:
            return {"error": f"Playlist with ID {playlist_id} not found"}, 404

        playlist.edit(title=title, description=description)

        return {
            "status": "success",
            "message": "Playlist updated successfully",
            "playlist_id": playlist_id,
            "updated_fields": {
                "title": title if title else playlist.name,
                "description": description if description else playlist.description,
            },
        }, 200

    except Exception as e:
        return {"error": f"Error updating playlist: {str(e)}"}, 500


def move_track(
    session: BrowserSession, playlist_id: str, from_index: int, to_index: int
) -> Tuple[dict, int]:
    """Implementation logic for moving a track within a playlist."""
    try:
        if not isinstance(from_index, int) or not isinstance(to_index, int):
            return {"error": "'from_index' and 'to_index' must be integers"}, 400

        if from_index < 0 or to_index < 0:
            return {"error": "Indices must be non-negative"}, 400

        playlist = session.playlist(playlist_id)
        if not playlist:
            return {"error": f"Playlist with ID {playlist_id} not found"}, 404

        playlist.move(from_index, to_index)

        return {
            "status": "success",
            "message": f"Moved track from position {from_index} to {to_index}",
            "playlist_id": playlist_id,
            "from_index": from_index,
            "to_index": to_index,
        }, 200

    except Exception as e:
        return {"error": f"Error moving track in playlist: {str(e)}"}, 500
