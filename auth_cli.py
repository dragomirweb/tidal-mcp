#!/usr/bin/env python3
"""
TIDAL Authentication CLI
Handles OAuth device flow authentication for TIDAL MCP.
"""

import sys
import tempfile
from pathlib import Path

# Add tidal_api to path
sys.path.insert(0, str(Path(__file__).parent / "tidal_api"))

from browser_session import BrowserSession, _ensure_https

SESSION_FILE = Path(tempfile.gettempdir()) / "tidal-session-oauth.json"


def print_auth_url(auth_url: str, expires_in: int):
    """Print the OAuth URL in a formatted way."""
    print("\n" + "=" * 60, file=sys.stderr)
    print("TIDAL LOGIN REQUIRED", file=sys.stderr)
    print("Please open this URL in your browser:", file=sys.stderr)
    print(f"\n{auth_url}\n", file=sys.stderr)
    print(f"Expires in {expires_in} seconds", file=sys.stderr)
    print("=" * 60 + "\n", file=sys.stderr)


def main():
    print("Authenticating with TIDAL...")

    session = BrowserSession()

    # Check if already authenticated
    if SESSION_FILE.exists():
        session.load_session_from_file(SESSION_FILE)
        if session.check_login():
            print(f"✓ Already authenticated! (User ID: {session.user.id})")
            print(f"Session file: {SESSION_FILE}")
            return 0

    # Need new authentication
    login, future = session.login_oauth()

    # Format and print the auth URL
    auth_url = _ensure_https(login.verification_uri_complete)

    print_auth_url(auth_url, login.expires_in)

    # Wait for user to complete authentication
    try:
        future.result()

        if session.check_login():
            session.save_session_to_file(SESSION_FILE)
            print(f"\n✓ Authentication successful!")
            print(f"User ID: {session.user.id}")
            print(f"Session saved to: {SESSION_FILE}\n")
            return 0
        else:
            print("\n✗ Authentication failed", file=sys.stderr)
            return 1

    except TimeoutError:
        print("\n✗ Authentication timed out", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
