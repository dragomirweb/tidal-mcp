"""
TIDAL MCP server — direct-call architecture.

All MCP tools call tidal_api/routes/ implementation functions directly.
There is no Flask server, no HTTP, no threads, and no port in this process.
stdout is reserved exclusively for the MCP JSON-RPC protocol.
"""

import sys
from typing import Optional, List, Dict, Any, Tuple

from mcp.server.fastmcp import FastMCP

# Route implementation functions (called directly, not via HTTP)
from tidal_api.routes.auth import (
    handle_login_start,
    handle_login_poll,
)
from tidal_api.routes.tracks import (
    get_user_tracks,
    get_batch_track_recommendations,
)
from tidal_api.routes.playlists import (
    create_new_playlist,
    get_playlists,
    get_tracks_from_playlist,
    delete_playlist_by_id,
    add_tracks,
    remove_tracks,
    update_playlist_metadata as update_playlist_metadata_impl,
    move_track,
)
from tidal_api.routes.search import (
    comprehensive_search,
    search_tracks_only,
    search_albums_only,
    search_artists_only,
    search_playlists_only,
)

from tidal_api.browser_session import BrowserSession
from mcp_server.utils import SESSION_FILE

print("TIDAL MCP server starting (direct-call mode, no Flask)", file=sys.stderr)

# =============================================================================
# MCP APP
# =============================================================================

mcp = FastMCP("TIDAL MCP")

# =============================================================================
# CONSTANTS
# =============================================================================

AUTH_ERROR_MESSAGE = (
    "You need to login to TIDAL first before using this feature. "
    "Please use the tidal_login() function."
)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _get_session() -> Optional[BrowserSession]:
    """Load and validate the persisted TIDAL session from disk.

    Returns a ready BrowserSession if the session is valid, or None if the
    user needs to authenticate.
    """
    if not SESSION_FILE.exists():
        return None
    session = BrowserSession()
    try:
        session.load_session_from_file(SESSION_FILE)
    except Exception:
        return None
    if not session.check_login():
        return None
    return session


def _call(result: Tuple[dict, int]) -> dict:
    """Convert a (dict, http_status) tuple from a route function into a plain
    dict suitable for returning directly from an MCP tool.

    On success (HTTP 200) the route dict is returned as-is so the caller gets
    e.g. {"tracks": [...]} rather than a double-wrapped envelope.
    On error the route's "error" key is preserved under "error".
    """
    data, status = result
    if status == 200:
        return data
    # Normalise error responses — route functions use "error" key
    error_msg = data.get("error", f"Operation failed (HTTP {status}).")
    return {"error": error_msg}


# =============================================================================
# AUTHENTICATION TOOLS
# =============================================================================


@mcp.tool()
def tidal_login() -> dict:
    """
    Start TIDAL authentication via the OAuth device flow.

    This tool returns immediately — it never blocks. Two outcomes are possible:

    1. {"status": "success"} — already authenticated, no action needed.
    2. {"status": "pending", "url": "https://...", "expires_in": N}
       — Present the URL to the user and ask them to open it in their browser.
         Then call tidal_check_login() every few seconds until it returns
         {"status": "success"} (or "error" if the link expires).

    Always call this tool first if another tool returns an authentication error.
    """
    try:
        body, status = handle_login_start(SESSION_FILE)
        if status == 200:
            return body
        return {
            "status": "error",
            "message": body.get("message", "Login initiation failed."),
        }
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


@mcp.tool()
def tidal_check_login() -> dict:
    """
    Check whether the user has completed TIDAL authorization in their browser.

    Call this tool after tidal_login() returned {"status": "pending"} and you
    have shown the user the authorization URL.

    Poll every 3–5 seconds until the status changes from "pending".

    Possible return values:
    - {"status": "pending"}  — user has not yet approved; call again shortly
    - {"status": "success"}  — user approved; TIDAL is ready to use
    - {"status": "error"}    — authorization failed or the link expired;
                               call tidal_login() again to get a fresh URL

    Do NOT call this tool before calling tidal_login() first.
    """
    try:
        body, status = handle_login_poll(SESSION_FILE)
        if status in (200, 400):
            return body
        return {
            "status": "error",
            "message": body.get("message", "Poll failed."),
        }
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


# =============================================================================
# TRACK & RECOMMENDATION TOOLS
# =============================================================================


@mcp.tool()
def get_favorite_tracks(limit: int = 20) -> dict:
    """
    Retrieves tracks from the user's TIDAL account favorites.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "What are my favorite tracks?"
    - "Show me my TIDAL favorites"
    - "What music do I have saved?"
    - "Get my favorite songs"
    - Any request to view their saved/favorite tracks

    This function retrieves the user's favorite tracks from TIDAL.

    Args:
        limit: Maximum number of tracks to retrieve (default: 20, note it should
               be large enough by default unless specified otherwise).

    Returns:
        A dictionary with a "tracks" list, each item containing track ID, title,
        artist, album, and duration. Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(get_user_tracks(session, limit=limit))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def recommend_tracks(
    track_ids: Optional[List[str]] = None,
    filter_criteria: Optional[str] = None,
    limit_per_track: int = 20,
    limit_from_favorite: int = 20,
) -> dict:
    """
    Recommends music tracks based on specified track IDs or the user's TIDAL
    favorites if no IDs are provided.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - Music recommendations
    - Track suggestions
    - Music similar to their TIDAL favorites or specific tracks
    - "What should I listen to?"
    - Any request to recommend songs/tracks/music based on their TIDAL history
      or specific tracks

    This function gets recommendations based on provided track IDs or retrieves
    the user's favorite tracks as seeds if no IDs are specified.

    When processing the results of this tool:
    1. Analyze the seed tracks to understand the music taste or direction
    2. Review the recommended tracks from TIDAL
    3. IMPORTANT: Do NOT include any tracks from the seed tracks in your recommendations
    4. Ensure there are NO DUPLICATES in your recommended tracks list
    5. Select and rank the most appropriate tracks based on the seed tracks and
       filter criteria
    6. Group recommendations by similar styles, artists, or moods with
       descriptive headings
    7. For each recommended track, provide:
       - The track name, artist, album
       - Always include the track's URL to make it easy for users to listen
       - A brief explanation of why this track might appeal to the user based
         on the seed tracks
       - If applicable, how this track matches their specific filter criteria
    8. Format your response as a nicely presented list of recommendations with
       helpful context (remember to include the track's URL!)
    9. Begin with a brief introduction explaining your selection strategy
    10. Unless specified otherwise, recommend MINIMUM 20 tracks (or more if
        possible) to give the user a good variety to choose from.

    [IMPORTANT NOTE] If you're not familiar with any artists or tracks
    mentioned, use internet search capabilities if available to provide more
    accurate information.

    Args:
        track_ids: Optional list of TIDAL track IDs to use as seeds.
                   If not provided, will use the user's favorite tracks.
        filter_criteria: Specific preferences for filtering recommendations
                         (e.g., "relaxing music," "recent releases," "upbeat,"
                         "jazz influences")
        limit_per_track: Maximum recommendations per seed track (default: 20)
        limit_from_favorite: Maximum favorite tracks to use as seeds (default: 20)

    Returns:
        A dictionary containing "seed_tracks", "recommendations", and
        "filter_criteria". Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}

    try:
        # Build the list of seed track IDs
        seed_tracks: List[Dict[str, Any]] = []
        seeds: List[str] = []

        if track_ids:
            seeds = [str(tid) for tid in track_ids]
        else:
            fav_data, fav_status = get_user_tracks(session, limit=limit_from_favorite)
            if fav_status != 200:
                return {
                    "error": fav_data.get("error", "Failed to fetch favorite tracks.")
                }
            seed_tracks = fav_data.get("tracks", [])
            seeds = [str(t["id"]) for t in seed_tracks]

        if not seeds:
            return {
                "error": (
                    "No seed tracks found. Make sure you have saved tracks in your "
                    "TIDAL favorites, or provide explicit track_ids."
                )
            }

        # Fetch recommendations for all seeds in one batch call
        rec_data, rec_status = get_batch_track_recommendations(
            session,
            track_ids=seeds,
            limit_per_track=limit_per_track,
            remove_duplicates=True,
        )
        if rec_status != 200:
            return {"error": rec_data.get("error", "Failed to fetch recommendations.")}

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
        }
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# =============================================================================
# PLAYLIST MANAGEMENT TOOLS
# =============================================================================


@mcp.tool()
def create_tidal_playlist(title: str, track_ids: list, description: str = "") -> dict:
    """
    Creates a new TIDAL playlist with the specified tracks.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Create a playlist with these songs"
    - "Make a TIDAL playlist"
    - "Save these tracks to a playlist"
    - "Create a collection of songs"
    - Any request to create a new playlist in their TIDAL account

    This function creates a new playlist in the user's TIDAL account and adds
    the specified tracks to it. The user must be authenticated with TIDAL first.

    NAMING CONVENTION GUIDANCE:
    When suggesting or creating a playlist, first check the user's existing
    playlists using get_user_playlists() to understand their naming preferences.
    Some patterns to look for:
    - Do they use emoji in playlist names?
    - Do they use all caps, title case, or lowercase?
    - Do they include dates or seasons in names?
    - Do they name by mood, genre, activity, or artist?
    - Do they use specific prefixes or formatting?

    Try to match their style when suggesting new playlist names. If they have
    no playlists yet or you can't determine a pattern, use a clear, descriptive
    name based on the tracks' common themes.

    When processing the results of this tool:
    1. Confirm the playlist was created successfully
    2. Provide the playlist title, number of tracks added, and URL
    3. Always include the direct TIDAL URL (https://tidal.com/playlist/{id})
    4. Suggest that the user can now access this playlist in their TIDAL account

    Args:
        title: The name of the playlist to create
        track_ids: List of TIDAL track IDs to add to the playlist
        description: Optional description for the playlist (default: "")

    Returns:
        A dictionary containing the status and details about the created playlist.
        Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(create_new_playlist(session, title, description, track_ids))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def get_user_playlists() -> dict:
    """
    Fetches the user's playlists from their TIDAL account.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Show me my playlists"
    - "List my TIDAL playlists"
    - "What playlists do I have?"
    - "Get my music collections"
    - Any request to view or list their TIDAL playlists

    This function retrieves the user's playlists from TIDAL and returns them
    sorted by last updated date (most recent first).

    When processing the results of this tool:
    1. Present the playlists in a clear, organized format
    2. Include key information like title, track count, and the TIDAL URL
    3. Mention when each playlist was last updated if available
    4. If the user has many playlists, focus on the most recently updated ones

    Returns:
        A dictionary with a "playlists" list. Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(get_playlists(session))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def get_playlist_tracks(playlist_id: str, limit: Optional[int] = None) -> dict:
    """
    Retrieves all tracks from a specified TIDAL playlist.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Show me the songs in my playlist"
    - "What tracks are in my [playlist name] playlist?"
    - "List the songs from my playlist"
    - "Get tracks from my playlist"
    - "View contents of my TIDAL playlist"
    - Any request to see what songs/tracks are in a specific playlist

    This function retrieves tracks from a specific playlist in the user's TIDAL
    account. By default, it fetches ALL tracks using automatic pagination.
    The playlist_id must be provided, which can be obtained from the
    get_user_playlists() function.

    When processing the results of this tool:
    1. Present the playlist information (title, description, track count)
    2. List the tracks in a clear, organized format with track name, artist, album
    3. Include track durations where available
    4. Mention the total number of tracks in the playlist
    5. If there are many tracks, highlight interesting patterns or variety

    Args:
        playlist_id: The TIDAL ID of the playlist to retrieve (required)
        limit: Maximum number of tracks to retrieve (default: None = all tracks)

    Returns:
        A dictionary with "playlist_id", "tracks", and "total_tracks".
        Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(get_tracks_from_playlist(session, playlist_id, limit))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def delete_tidal_playlist(playlist_id: str) -> dict:
    """
    Deletes a TIDAL playlist by its ID.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Delete my playlist"
    - "Remove a playlist from my TIDAL account"
    - "Get rid of this playlist"
    - "Delete the playlist with ID X"
    - Any request to delete or remove a TIDAL playlist

    This function deletes a specific playlist from the user's TIDAL account.
    The user must be authenticated with TIDAL first.

    When processing the results of this tool:
    1. Confirm the playlist was deleted successfully
    2. Provide a clear message about the deletion

    Args:
        playlist_id: The TIDAL ID of the playlist to delete (required)

    Returns:
        A dictionary with a "status" and "message". Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(delete_playlist_by_id(session, playlist_id))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def add_tracks_to_playlist(playlist_id: str, track_ids: list) -> dict:
    """
    Add tracks to an existing TIDAL playlist.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Add these songs to my playlist"
    - "Add [track] to [playlist name]"
    - "Put these tracks in my playlist"
    - Any request to add songs/tracks to an existing playlist

    This function adds tracks to a user's existing TIDAL playlist. The playlist
    must already exist, and the user must have permission to edit it.

    When processing the results of this tool:
    1. Confirm how many tracks were added successfully
    2. Provide clear feedback about the operation
    3. If any tracks failed to add, explain why

    Args:
        playlist_id: The TIDAL ID of the playlist (required)
        track_ids: A list of TIDAL track IDs to add to the playlist (required)

    Returns:
        A dictionary with "status", "tracks_added". Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(add_tracks(session, playlist_id, track_ids))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def remove_tracks_from_playlist(
    playlist_id: str,
    track_ids: Optional[list] = None,
    indices: Optional[list] = None,
) -> dict:
    """
    Remove tracks from a TIDAL playlist by track IDs or position indices.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Remove this song from my playlist"
    - "Delete tracks from [playlist name]"
    - "Take out these songs from the playlist"
    - Any request to remove songs/tracks from a playlist

    This function removes specific tracks from a user's TIDAL playlist. You can
    remove tracks either by their TIDAL IDs or by their position in the playlist
    (0-based index).

    When processing the results of this tool:
    1. Confirm how many tracks were removed successfully
    2. Provide clear feedback about what was removed
    3. If using indices, remind the user they are 0-based (first track = index 0)

    Args:
        playlist_id: The TIDAL ID of the playlist (required)
        track_ids: A list of TIDAL track IDs to remove (use this OR indices)
        indices: A list of track positions (0-based) to remove (use this OR track_ids)

    Returns:
        A dictionary with "status", "tracks_removed". Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(remove_tracks(session, playlist_id, track_ids, indices))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def update_playlist_metadata(
    playlist_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    """
    Update a TIDAL playlist's title and/or description.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Rename my playlist to [new name]"
    - "Change the playlist description"
    - "Update playlist [name] with new title/description"
    - Any request to modify playlist metadata

    This function updates the title and/or description of a user's TIDAL
    playlist. At least one of title or description must be provided.

    When processing the results of this tool:
    1. Confirm what was updated (title, description, or both)
    2. Show the new values
    3. Provide clear feedback that the changes were saved

    Args:
        playlist_id: The TIDAL ID of the playlist (required)
        title: New title for the playlist (optional)
        description: New description for the playlist (optional)

    Returns:
        A dictionary with "status" and "updated_fields". Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(
            update_playlist_metadata_impl(session, playlist_id, title, description)
        )
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def reorder_playlist_tracks(playlist_id: str, from_index: int, to_index: int) -> dict:
    """
    Move/reorder a track within a TIDAL playlist.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Move track at position X to position Y"
    - "Reorder my playlist"
    - "Put song #5 at the beginning"
    - Any request to change the order of tracks in a playlist

    This function moves a track from one position to another within a playlist.
    Indices are 0-based (first track is index 0).

    When processing the results of this tool:
    1. Confirm the track was moved successfully
    2. Remind the user that indices are 0-based
    3. Describe the move clearly (e.g., "moved from position 5 to position 2")

    Args:
        playlist_id: The TIDAL ID of the playlist (required)
        from_index: Current position of the track (0-based) (required)
        to_index: New position for the track (0-based) (required)

    Returns:
        A dictionary with "status" and move details. Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(move_track(session, playlist_id, from_index, to_index))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# =============================================================================
# SEARCH TOOLS
# =============================================================================


@mcp.tool()
def search_tidal(query: str, search_type: str = "all", limit: int = 20) -> dict:
    """
    Search TIDAL for tracks, albums, artists, or playlists.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Search for [song/artist/album] on TIDAL"
    - "Find songs by [artist]"
    - "Look for [song title]"
    - "Search TIDAL for [anything]"
    - Any general search request for music content

    This function provides comprehensive search across all TIDAL content types.

    When processing the results of this tool:
    1. Present search results in a clear, organized format by type
    2. Include key information: name, duration, TIDAL URLs
    3. Highlight the most relevant results first
    4. Always include TIDAL URLs so users can easily access the content

    Args:
        query: The search term (song title, artist name, album name, etc.)
        search_type: Type of search — "all", "tracks", "albums", "artists",
                     or "playlists" (default: "all")
        limit: Maximum number of results per type (default: 20)

    Returns:
        A dictionary with "results" organized by content type and a "summary".
        Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(comprehensive_search(session, query, search_type, limit))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def search_tracks(query: str, limit: int = 20) -> dict:
    """
    Search specifically for tracks/songs on TIDAL.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Find the song [title]"
    - "Search for tracks by [artist]"
    - "Look for [song title] by [artist]"
    - Any specific track/song search request

    Args:
        query: The search term (song title, artist name, or combination)
        limit: Maximum number of tracks to return (default: 20)

    Returns:
        A dictionary with "results.tracks.items" list and "count".
        Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(search_tracks_only(session, query, limit))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def search_albums(query: str, limit: int = 20) -> dict:
    """
    Search specifically for albums on TIDAL.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Find the album [title]"
    - "Search for albums by [artist]"
    - "Look for [album name]"
    - Any specific album search request

    Args:
        query: The search term (album title, artist name, or combination)
        limit: Maximum number of albums to return (default: 20)

    Returns:
        A dictionary with "results.albums.items" list and "count".
        Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(search_albums_only(session, query, limit))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def search_artists(query: str, limit: int = 20) -> dict:
    """
    Search specifically for artists on TIDAL.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Find the artist [name]"
    - "Search for [artist name]"
    - "Look up [artist]"
    - Any specific artist search request

    Args:
        query: The search term (artist name)
        limit: Maximum number of artists to return (default: 20)

    Returns:
        A dictionary with "results.artists.items" list and "count".
        Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(search_artists_only(session, query, limit))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.tool()
def search_playlists(query: str, limit: int = 20) -> dict:
    """
    Search specifically for playlists on TIDAL.

    USE THIS TOOL WHENEVER A USER ASKS FOR:
    - "Find playlists about [topic]"
    - "Search for [playlist name]"
    - "Look for playlists with [genre/mood]"
    - Any playlist discovery request

    Args:
        query: The search term (playlist name, genre, mood, etc.)
        limit: Maximum number of playlists to return (default: 20)

    Returns:
        A dictionary with "results.playlists.items" list and "count".
        Returns an "error" key on failure.
    """
    session = _get_session()
    if session is None:
        return {"error": AUTH_ERROR_MESSAGE}
    try:
        return _call(search_playlists_only(session, query, limit))
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
