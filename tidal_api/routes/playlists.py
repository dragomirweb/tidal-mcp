"""Playlist route implementation logic."""

import sys
from typing import Optional, Tuple

from tidal_api.browser_session import BrowserSession
from tidal_api.utils import format_track_data, fetch_all_items


def _added_tracks_summary(add_result, requested_count: int) -> Tuple[int, int, Optional[list]]:
    """Return added count, skipped count, and added IDs from playlist.add()."""
    if isinstance(add_result, list):
        added_count = len(add_result)
        added_ids = add_result
    else:
        # Older tests/mocks may not model tidalapi's list return value.
        added_count = requested_count if add_result is not False else 0
        added_ids = None

    skipped_count = max(requested_count - added_count, 0)
    return added_count, skipped_count, added_ids


def create_new_playlist(
    session: BrowserSession, title: str, description: str, track_ids: list
) -> Tuple[dict, int]:
    """Implementation logic for creating a new playlist."""
    try:
        if not title or not title.strip():
            return {"error": "title cannot be empty."}, 400

        if not isinstance(track_ids, list):
            return {"error": "'track_ids' must be a list"}, 400

        # Create the playlist
        playlist = session.user.create_playlist(title, description)

        added_count = 0
        skipped_count = 0
        added_ids = None

        # Add tracks to the playlist (skip if empty)
        if track_ids:
            add_result = playlist.add(track_ids)
            added_count, skipped_count, added_ids = _added_tracks_summary(
                add_result, len(track_ids)
            )

        # Return playlist information
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
        }

        return {
            "status": "success" if skipped_count == 0 else "partial_success",
            "message": (
                f"Playlist '{title}' created successfully with "
                f"{added_count} track(s) added"
            ),
            "playlist": playlist_info,
            "tracks_requested": len(track_ids),
            "tracks_added": added_count,
            "tracks_skipped": skipped_count,
            "added_track_ids": added_ids,
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
                "url": f"https://tidal.com/browse/playlist/{playlist.id}?u",
            }
            playlist_list.append(playlist_info)

        # Sort playlists by last_updated in descending order
        sorted_playlists = sorted(
            playlist_list, key=lambda x: x.get("last_updated") or "", reverse=True
        )

        return {"playlists": sorted_playlists}, 200
    except Exception as e:
        return {"error": f"Error fetching playlists: {str(e)}"}, 500


def get_tracks_from_playlist(
    session: BrowserSession, playlist_id: str, limit: Optional[int] = None
) -> Tuple[dict, int]:
    """Implementation logic for getting tracks from a playlist."""
    try:
        if not playlist_id or not playlist_id.strip():
            return {"error": "playlist_id cannot be empty."}, 400

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
        if not playlist_id or not playlist_id.strip():
            return {"error": "playlist_id cannot be empty."}, 400

        playlist = session.playlist(playlist_id)
        if not playlist:
            return {"error": f"Playlist with ID {playlist_id} not found"}, 404

        if not playlist.delete():
            return {"error": f"Playlist {playlist_id} was not deleted."}, 500

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
        if not playlist_id or not playlist_id.strip():
            return {"error": "playlist_id cannot be empty."}, 400

        if not isinstance(track_ids, list):
            return {"error": "'track_ids' must be a list"}, 400

        if not track_ids:
            return {"error": "track_ids cannot be empty."}, 400

        playlist = session.playlist(playlist_id)
        if not playlist:
            return {"error": f"Playlist with ID {playlist_id} not found"}, 404

        add_result = playlist.add(track_ids)
        added_count, skipped_count, added_ids = _added_tracks_summary(
            add_result, len(track_ids)
        )

        if added_count == len(track_ids):
            status = "success"
            message = f"Added {added_count} track(s) to playlist"
        elif added_count > 0:
            status = "partial_success"
            message = (
                f"Added {added_count} of {len(track_ids)} requested track(s) "
                "to playlist"
            )
        else:
            status = "no_changes"
            message = "No tracks were added to playlist"

        return {
            "status": status,
            "message": message,
            "playlist_id": playlist_id,
            "tracks_added": added_count,
            "tracks_requested": len(track_ids),
            "tracks_skipped": skipped_count,
            "added_track_ids": added_ids,
        }, 200

    except Exception as e:
        return {"error": f"Error adding tracks to playlist: {str(e)}"}, 500


def remove_tracks(
    session: BrowserSession,
    playlist_id: str,
    track_ids: Optional[list] = None,
    indices: Optional[list] = None,
) -> Tuple[dict, int]:
    """Implementation logic for removing tracks from a playlist."""
    try:
        if not playlist_id or not playlist_id.strip():
            return {"error": "playlist_id cannot be empty."}, 400

        if track_ids is not None:
            if not isinstance(track_ids, list):
                return {"error": "'track_ids' must be a list"}, 400
            requested_count = len(track_ids)
        elif indices is not None:
            if not isinstance(indices, list):
                return {"error": "'indices' must be a list"}, 400
            requested_count = len(indices)
        else:
            return {"error": "Must provide either 'track_ids' or 'indices'"}, 400

        if requested_count == 0:
            return {"error": "Must provide at least one track to remove"}, 400

        playlist = session.playlist(playlist_id)
        if not playlist:
            return {"error": f"Playlist with ID {playlist_id} not found"}, 404

        removed_count = 0
        failed_count = 0

        # Remove by track IDs
        if track_ids is not None:
            for track_id in track_ids:
                try:
                    if playlist.remove_by_id(track_id):
                        removed_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    failed_count += 1
                    print(
                        f"Could not remove track {track_id}: {str(e)}",
                        file=sys.stderr,
                    )

        # Remove by indices
        elif indices is not None:
            # Sort indices in descending order to avoid shifting issues
            for index in sorted(indices, reverse=True):
                try:
                    if playlist.remove_by_index(index):
                        removed_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    failed_count += 1
                    print(
                        f"Could not remove track at index {index}: {str(e)}",
                        file=sys.stderr,
                    )

        if removed_count == 0:
            return {
                "error": "No tracks were removed from playlist",
                "playlist_id": playlist_id,
                "tracks_requested": requested_count,
                "tracks_removed": 0,
                "tracks_failed": failed_count,
            }, 400

        status = "success" if failed_count == 0 else "partial_success"
        return {
            "status": status,
            "message": f"Removed {removed_count} track(s) from playlist",
            "playlist_id": playlist_id,
            "tracks_requested": requested_count,
            "tracks_removed": removed_count,
            "tracks_failed": failed_count,
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
        if not playlist_id or not playlist_id.strip():
            return {"error": "playlist_id cannot be empty."}, 400

        if title is None and description is None:
            return {"error": "Must provide at least 'title' or 'description'"}, 400

        if title is not None and not title.strip():
            return {"error": "title cannot be empty."}, 400

        if description is not None and not description.strip():
            return {"error": "description cannot be empty."}, 400

        playlist = session.playlist(playlist_id)
        if not playlist:
            return {"error": f"Playlist with ID {playlist_id} not found"}, 404

        if not playlist.edit(title=title, description=description):
            return {"error": "Playlist metadata was not updated."}, 500

        return {
            "status": "success",
            "message": "Playlist updated successfully",
            "playlist_id": playlist_id,
            "updated_fields": {
                "title": title if title is not None else playlist.name,
                "description": description
                if description is not None
                else playlist.description,
            },
        }, 200

    except Exception as e:
        return {"error": f"Error updating playlist: {str(e)}"}, 500


def move_track(
    session: BrowserSession, playlist_id: str, from_index: int, to_index: int
) -> Tuple[dict, int]:
    """Implementation logic for moving a track within a playlist."""
    try:
        if not playlist_id or not playlist_id.strip():
            return {"error": "playlist_id cannot be empty."}, 400

        if not isinstance(from_index, int) or not isinstance(to_index, int):
            return {"error": "'from_index' and 'to_index' must be integers"}, 400

        if from_index < 0 or to_index < 0:
            return {"error": "Indices must be non-negative"}, 400

        playlist = session.playlist(playlist_id)
        if not playlist:
            return {"error": f"Playlist with ID {playlist_id} not found"}, 404

        if not playlist.move_by_index(from_index, to_index):
            return {"error": "Track was not moved."}, 400

        return {
            "status": "success",
            "message": f"Moved track from position {from_index} to {to_index}",
            "playlist_id": playlist_id,
            "from_index": from_index,
            "to_index": to_index,
        }, 200

    except Exception as e:
        return {"error": f"Error moving track in playlist: {str(e)}"}, 500
