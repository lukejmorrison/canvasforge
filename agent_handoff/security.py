"""HTTP allowlist and redirect guard for agent handoff."""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request


def is_allowed_agent_http_endpoint(endpoint: str) -> tuple[bool, str]:
    """Allow HTTPS anywhere, or cleartext HTTP only to loopback."""
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in ("http", "https"):
        return False, "Agent HTTP endpoint must use http:// or https://"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "Agent HTTP endpoint is missing a hostname"
    if parsed.scheme == "http" and host not in ("127.0.0.1", "localhost", "::1"):
        return False, (
            "Cleartext HTTP agent endpoints are limited to localhost "
            "(127.0.0.1, localhost, ::1). Use HTTPS for remote hosts."
        )
    return True, ""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Reject HTTP redirects so agent POSTs cannot be steered off-host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            newurl, code, f"Redirects are not allowed for agent HTTP POST ({code})", headers, fp
        )
