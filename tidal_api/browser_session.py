import tidalapi
from concurrent.futures import Future
from typing import Tuple


def _ensure_https(url: str) -> str:
    """Prepend https:// if the URL has no scheme."""
    if not url.startswith("http"):
        return "https://" + url
    return url


class BrowserSession(tidalapi.Session):
    """
    Extended tidalapi.Session that automatically opens the login URL in a browser.
    """

    def login_oauth_start(self) -> Tuple[str, int, Future]:
        """
        Start the TIDAL OAuth device flow without blocking.

        Returns the authorization URL, the expiry time in seconds, and a Future
        that resolves when the user completes authorization. Does NOT open a
        browser or block -- the caller is responsible for surfacing the URL and
        waiting on (or polling) the future.

        :return: (url, expires_in, future)
        :raises: Exception if the OAuth initiation itself fails
        """
        login, future = self.login_oauth()
        auth_url = _ensure_https(login.verification_uri_complete)
        return auth_url, login.expires_in, future
