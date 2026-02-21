"""Track and recommendation route implementation logic."""

import sys
import concurrent.futures
from typing import Optional, List, Dict, Any, Tuple

import tidalapi.types as tidal_types

from tidal_api.browser_session import BrowserSession
from tidal_api.utils import format_track_data, bound_limit, fetch_all_items


def get_user_tracks(session: BrowserSession, limit: int = 10) -> Tuple[dict, int]:
    """Implementation logic for getting user's favorite tracks."""
    try:
        favorites = session.user.favorites

        # Use pagination helper to fetch tracks beyond the 50-item limit
        def fetch_page(limit, offset):
            try:
                return list(
                    favorites.tracks(
                        limit=limit,
                        offset=offset,
                        order=tidal_types.ItemOrder.Date,
                        order_direction=tidal_types.OrderDirection.Descending,
                    )
                )
            except TypeError:
                # If offset isn't supported, try without it
                if offset == 0:
                    return list(
                        favorites.tracks(
                            limit=limit,
                            order=tidal_types.ItemOrder.Date,
                            order_direction=tidal_types.OrderDirection.Descending,
                        )
                    )
                else:
                    return []

        # Fetch up to the requested limit with pagination
        all_tracks = fetch_all_items(fetch_page, max_items=limit, page_size=100)

        track_list = [format_track_data(track) for track in all_tracks]

        return {"tracks": track_list}, 200
    except Exception as e:
        return {"error": f"Error fetching tracks: {str(e)}"}, 500


def get_batch_track_recommendations(
    session: BrowserSession,
    track_ids: list,
    limit_per_track: int = 20,
    remove_duplicates: bool = True,
) -> Tuple[dict, int]:
    """Implementation logic for getting batch recommendations."""
    try:
        if not isinstance(track_ids, list):
            return {"error": "track_ids must be a list"}, 400

        if not track_ids:
            return {"error": "track_ids cannot be empty."}, 400

        limit_per_track = bound_limit(limit_per_track)

        def get_track_recommendations(track_id):
            """Function to get recommendations for a single track."""
            try:
                track = session.track(track_id)
                recommendations = track.get_track_radio(limit=limit_per_track)
                formatted_recommendations = [
                    format_track_data(rec, source_track_id=track_id)
                    for rec in recommendations
                ]
                return formatted_recommendations
            except Exception as e:
                print(
                    f"Error getting recommendations for track {track_id}: {str(e)}",
                    file=sys.stderr,
                )
                return []

        all_recommendations = []
        seen_track_ids = set()

        # Use ThreadPoolExecutor to process tracks concurrently
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(track_ids), 10)
        ) as executor:
            future_to_track_id = {
                executor.submit(get_track_recommendations, track_id): track_id
                for track_id in track_ids
            }

            for future in concurrent.futures.as_completed(future_to_track_id):
                track_recommendations = future.result()

                for track_data in track_recommendations:
                    rec_id = track_data.get("id")

                    if remove_duplicates and rec_id in seen_track_ids:
                        continue

                    all_recommendations.append(track_data)
                    seen_track_ids.add(rec_id)

        return {"recommendations": all_recommendations}, 200
    except Exception as e:
        return {"error": f"Error fetching batch recommendations: {str(e)}"}, 500


def get_recommendations(
    session: BrowserSession,
    track_ids: Optional[list] = None,
    filter_criteria: Optional[str] = None,
    limit_per_track: int = 20,
    limit_from_favorite: int = 20,
) -> Tuple[dict, int]:
    """Recommend tracks based on provided IDs or the user's favorites."""
    try:
        seed_tracks: List[Dict[str, Any]] = []
        seeds: List[str] = []

        if track_ids:
            seeds = [str(tid) for tid in track_ids]
        else:
            fav_data, fav_status = get_user_tracks(session, limit=limit_from_favorite)
            if fav_status != 200:
                return {
                    "error": fav_data.get("error", "Failed to fetch favorite tracks.")
                }, fav_status
            seed_tracks = fav_data.get("tracks", [])
            seeds = [str(t["id"]) for t in seed_tracks]

        if not seeds:
            return {
                "error": (
                    "No seed tracks found. Make sure you have saved tracks in your "
                    "TIDAL favorites, or provide explicit track_ids."
                )
            }, 400

        rec_data, rec_status = get_batch_track_recommendations(
            session,
            track_ids=seeds,
            limit_per_track=limit_per_track,
            remove_duplicates=True,
        )
        if rec_status != 200:
            return {
                "error": rec_data.get("error", "Failed to fetch recommendations.")
            }, rec_status

        seed_id_set = set(seeds)
        filtered_recs = [
            r
            for r in rec_data.get("recommendations", [])
            if str(r.get("id")) not in seed_id_set
        ]

        return {
            "seed_tracks": seed_tracks,
            "recommendations": filtered_recs,
            "filter_criteria": filter_criteria,
        }, 200
    except Exception as e:
        return {"error": f"Error fetching recommendations: {str(e)}"}, 500
