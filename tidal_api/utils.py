def format_track_data(track, source_track_id=None):
    """
    Format a track object into a standardized dictionary.

    Args:
        track: TIDAL track object
        source_track_id: Optional ID of the track that led to this recommendation

    Returns:
        Dictionary with standardized track information
    """
    track_data = {
        "id": track.id,
        "title": track.name,
        "artist": track.artist.name if hasattr(track.artist, "name") else "Unknown",
        "album": track.album.name if hasattr(track.album, "name") else "Unknown",
        "duration": track.duration if hasattr(track, "duration") else 0,
        "url": f"https://tidal.com/browse/track/{track.id}?u",
    }

    # Include source track ID if provided
    if source_track_id:
        track_data["source_track_id"] = source_track_id

    return track_data


def bound_limit(limit: int, max_n: int = 50) -> int:
    """Clamp limit to the range [1, max_n]."""
    if limit < 1:
        limit = 1
    elif limit > max_n:
        limit = max_n
    return limit


def fetch_all_items(fetch_func, max_items=None, page_size=100):
    """
    Generic pagination helper to fetch all items from a paginated TIDAL API.

    Args:
        fetch_func: Callable that takes (limit, offset) and returns items
        max_items: Optional maximum number of items to fetch (None = fetch all)
        page_size: Number of items to fetch per page (default: 100)

    Returns:
        List of all fetched items
    """
    all_items = []
    offset = 0

    while True:
        # Calculate how many items to fetch in this batch
        if max_items is not None:
            remaining = max_items - len(all_items)
            if remaining <= 0:
                break
            batch_size = min(page_size, remaining)
        else:
            batch_size = page_size

        # Fetch this batch
        try:
            items = fetch_func(limit=batch_size, offset=offset)

            # If no items returned or empty list, we've reached the end
            if not items:
                break

            all_items.extend(items)

            # If we got fewer items than requested, we've reached the end
            if len(items) < batch_size:
                break

            offset += len(items)

        except Exception as e:
            # If pagination fails, return what we have so far
            import sys

            print(f"Pagination stopped at offset {offset}: {str(e)}", file=sys.stderr)
            break

    return all_items
