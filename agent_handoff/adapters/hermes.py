"""Send a CanvasForge bundle to a running Hermes gateway."""

from __future__ import annotations

import base64
import json
import threading
import urllib.request
from pathlib import Path

from agent_handoff.discovery import read_hermes_api_key
from agent_handoff.models import DispatchResult
from agent_handoff.security import NoRedirect, is_allowed_agent_http_endpoint


def _image_data_url(image_path: Path) -> str:
    payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
    suffix = image_path.suffix.lower()
    media = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    return f"data:{media};base64,{payload}"


def post_to_hermes(
    url: str,
    prompt: str,
    image_path: Path,
    *,
    api_key: str = "",
    timeout: float = 20,
    wait: bool = False,
) -> DispatchResult:
    allowed, reason = is_allowed_agent_http_endpoint(url)
    if not allowed:
        return DispatchResult(ok=False, message="", error=reason, kind="hermes")
    key = api_key or read_hermes_api_key()
    body = {
        "model": "hermes-agent",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": _image_data_url(image_path)}},
                ],
            }
        ],
    }
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    def _send() -> None:
        opener = urllib.request.build_opener(NoRedirect)
        try:
            opener.open(request, timeout=timeout).read()
        except Exception:
            return

    if wait:
        try:
            opener = urllib.request.build_opener(NoRedirect)
            opener.open(request, timeout=timeout).read()
        except Exception as exc:
            return DispatchResult(
                ok=False,
                message="",
                error=f"Could not POST to Hermes: {exc}",
                kind="hermes",
            )
        return DispatchResult(ok=True, message="Sent selected image to Hermes", kind="hermes")

    thread = threading.Thread(target=_send, name="canvasforge-hermes-handoff", daemon=True)
    thread.start()
    return DispatchResult(
        ok=True,
        message="Sent selected image to Hermes",
        kind="hermes",
    )
