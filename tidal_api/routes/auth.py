"""Authentication route implementation logic."""

import threading
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from tidal_api.browser_session import BrowserSession


# =============================================================================
# PENDING LOGIN STATE
# Holds the in-progress OAuth flow between handle_login_start() and
# handle_login_poll(). Only one login flow is supported at a time.
# =============================================================================

_pending: Optional[Dict[str, Any]] = None
_pending_lock = threading.Lock()


def handle_login_start(session_file: Path) -> Tuple[dict, int]:
    """
    Start the TIDAL OAuth login flow without blocking.

    If a valid session already exists the function returns success immediately.
    Otherwise it initiates the OAuth device flow, stores the pending future,
    and returns the authorization URL for the user to visit in their browser.
    A subsequent call to handle_login_poll() checks whether the user has
    completed authorization.
    """
    global _pending

    # Fast-path: check whether the existing session is still valid
    if session_file.exists():
        session = BrowserSession()
        try:
            session.load_session_from_file(session_file)
            if session.check_login():
                return {
                    "status": "success",
                    "message": "Already authenticated with TIDAL",
                    "user_id": session.user.id,
                }, 200
        except Exception:
            pass  # session file corrupt or expired — fall through to new login

    # Start a fresh OAuth device flow (non-blocking).
    # Any previously pending flow is silently discarded.
    try:
        session = BrowserSession()
        url, expires_in, future = session.login_oauth_start()
    except Exception as e:
        return {
            "error": f"Failed to initiate TIDAL login: {str(e)}",
            "status": "error",
        }, 500

    with _pending_lock:
        _pending = {
            "future": future,
            "session": session,
            "session_file": session_file,
            "url": url,
            "expires_in": expires_in,
        }

    return {
        "status": "pending",
        "message": "Authorization required. Please open the URL in your browser.",
        "url": url,
        "expires_in": expires_in,
    }, 200


def handle_login_poll(session_file: Path) -> Tuple[dict, int]:
    """
    Poll whether the user has completed the OAuth authorization flow.

    Returns one of three statuses:
    - "pending"  — the user has not yet approved the request
    - "success"  — authorization is complete; session saved to disk
    - "error"    — authorization failed or timed out
    """
    global _pending

    # Read and (if completed) clear _pending atomically to avoid TOCTOU races.
    with _pending_lock:
        state = _pending

        if state is None:
            # No login in progress — check if we already have a valid session
            if session_file.exists():
                session = BrowserSession()
                try:
                    session.load_session_from_file(session_file)
                    if session.check_login():
                        return {
                            "status": "success",
                            "message": "Already authenticated with TIDAL",
                            "user_id": session.user.id,
                        }, 200
                except Exception:
                    pass
            return {
                "error": "No login in progress. Call tidal_login first.",
                "status": "error",
            }, 400

        future = state["future"]

        if not future.done():
            return {
                "status": "pending",
                "message": "Waiting for user to authorize in browser.",
            }, 200

        # Future completed — clear pending state while still under the lock
        exc = future.exception()
        _pending = None

    # Lock released — perform I/O outside the lock

    if exc is not None:
        return {
            "error": f"Authorization failed: {str(exc)}",
            "status": "error",
        }, 401

    # Success — save the session
    try:
        session = state["session"]
        session.save_session_to_file(state["session_file"])
        return {
            "status": "success",
            "message": "Successfully authenticated with TIDAL",
            "user_id": session.user.id,
        }, 200
    except Exception as e:
        return {
            "error": f"Login succeeded but failed to save session: {str(e)}",
            "status": "error",
        }, 500


def check_auth_status(session_file: Path) -> Tuple[dict, int]:
    """Check whether there is an active, valid TIDAL session on disk."""
    if not session_file.exists():
        return {"authenticated": False, "message": "No session file found"}, 200

    session = BrowserSession()
    try:
        session.load_session_from_file(session_file)
        if session.check_login():
            user_info = {
                "id": session.user.id,
                "username": session.user.username
                if hasattr(session.user, "username")
                else "N/A",
                "email": session.user.email
                if hasattr(session.user, "email")
                else "N/A",
            }
            return {
                "authenticated": True,
                "message": "Valid TIDAL session",
                "user": user_info,
            }, 200
    except Exception:
        pass

    return {"authenticated": False, "message": "Invalid or expired session"}, 200
