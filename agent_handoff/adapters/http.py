"""Generic HTTP POST of a local-agent.handoff/1 payload."""

from __future__ import annotations

import json
import urllib.request

from agent_handoff.models import DispatchResult, HandoffPayload
from agent_handoff.security import NoRedirect, is_allowed_agent_http_endpoint


def post_handoff(endpoint: str, payload: HandoffPayload, timeout: float = 15) -> DispatchResult:
    allowed, reason = is_allowed_agent_http_endpoint(endpoint)
    if not allowed:
        return DispatchResult(ok=False, message="", error=reason, kind="http")
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload.to_dict()).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(NoRedirect)
    try:
        opener.open(request, timeout=timeout).read()
    except Exception as exc:
        return DispatchResult(
            ok=False,
            message="",
            error=f"Could not POST to {endpoint}: {exc}",
            kind="http",
        )
    return DispatchResult(
        ok=True,
        message=f"Posted selected image via {endpoint}",
        kind="http",
    )
