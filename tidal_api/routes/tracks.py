"""Track and recommendation route implementation logic."""

import sys
import concurrent.futures
from typing import Tuple

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
                        order="DATE",
                        order_direction="DESC",
                    )
                )
            except TypeError:
                # If offset isn't supported, try without it
                if offset == 0:
                    return list(
                        favorites.tracks(
                            limit=limit, order="DATE", order_direction="DESC"
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
            max_workers=len(track_ids)
        ) as executor:
            future_to_track_id = {
                executor.submit(get_track_recommendations, track_id): track_id
                for track_id in track_ids
            }

            for future in concurrent.futures.as_completed(future_to_track_id):
                track_recommendations = future.result()

                for track_data in track_recommendations:
                    track_id = track_data.get("id")

                    if remove_duplicates and track_id in seen_track_ids:
                        continue

                    all_recommendations.append(track_data)
                    seen_track_ids.add(track_id)

        return {"recommendations": all_recommendations}, 200
    except Exception as e:
        return {"error": f"Error fetching batch recommendations: {str(e)}"}, 500
