"""Route a CanvasForge bundle to the chosen agent adapter."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from agent_handoff.adapters import cli as cli_adapter
from agent_handoff.adapters import grok as grok_adapter
from agent_handoff.adapters import hermes as hermes_adapter
from agent_handoff.adapters import http as http_adapter
from agent_handoff.adapters import openclaw as openclaw_adapter
from agent_handoff.adapters import vscode as vscode_adapter
from agent_handoff.models import (
    DEFAULT_PROMPT_TEMPLATE,
    AgentTarget,
    DispatchResult,
    HandoffPayload,
)


def build_prompt(
    template: str,
    *,
    image: Path,
    json_path: Path,
    bundle_dir: Path,
    agent: str,
) -> str:
    text = (template or "").strip() or DEFAULT_PROMPT_TEMPLATE
    return text.format(image=str(image), json=str(json_path), dir=str(bundle_dir), agent=agent)


def build_handoff_payload(
    target: AgentTarget,
    prompt: str,
    png_path: Path,
    json_path: Path,
    bundle_dir: Path,
    *,
    include_image_base64: bool = True,
) -> HandoffPayload:
    annotations = {}
    if json_path.is_file():
        annotations = json.loads(json_path.read_text(encoding="utf-8"))
    image_b64 = ""
    if include_image_base64 and png_path.is_file():
        image_b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
    return HandoffPayload(
        source="CanvasForge",
        target=target.id,
        prompt=prompt,
        bundle_dir=str(bundle_dir),
        image_path=str(png_path),
        annotations_path=str(json_path),
        annotations=annotations,
        image_base64=image_b64,
    )


def dispatch_bundle(
    target: AgentTarget,
    bundle_dir: Path,
    *,
    prompt_template: str = DEFAULT_PROMPT_TEMPLATE,
) -> DispatchResult:
    png_path = next(bundle_dir.glob("*.png"), None)
    json_path = bundle_dir / "annotations.json"
    if png_path is None:
        return DispatchResult(ok=False, message="", error="Bundle is missing a PNG", kind=target.kind)
    prompt = build_prompt(
        prompt_template,
        image=png_path,
        json_path=json_path,
        bundle_dir=bundle_dir,
        agent=target.id,
    )
    send_type = str((target.send or {}).get("type") or target.kind)

    if send_type == "clipboard":
        return DispatchResult(
            ok=False,
            message="",
            error="Clipboard targets must be handled by the canvas window",
            kind="clipboard",
        )
    if send_type == "buzz":
        return DispatchResult(
            ok=False,
            message="",
            error="Buzz channel send is not wired yet",
            kind="buzz",
        )
    if send_type == "hermes":
        url = str((target.send or {}).get("url") or "http://127.0.0.1:8642/v1/chat/completions")
        return hermes_adapter.post_to_hermes(url, prompt, png_path)
    if send_type == "openclaw":
        agent_id = str((target.send or {}).get("agent") or "")
        return openclaw_adapter.send_to_openclaw(agent_id, prompt, bundle_dir)
    if send_type == "grok":
        command = str((target.send or {}).get("command") or "")
        return grok_adapter.send_to_grok_build(prompt, bundle_dir, command)
    if send_type == "vscode":
        return vscode_adapter.send_to_vscode_codex(prompt, png_path, json_path, bundle_dir)
    if send_type == "http":
        url = str((target.send or {}).get("url") or "")
        payload = build_handoff_payload(target, prompt, png_path, json_path, bundle_dir)
        return http_adapter.post_handoff(url, payload)
    if send_type == "cli":
        try:
            argv = cli_adapter.expand_argv(
                target,
                prompt=prompt,
                image=png_path,
                json_path=json_path,
                bundle_dir=bundle_dir,
            )
        except (ValueError, KeyError) as exc:
            return DispatchResult(ok=False, message="", error=str(exc), kind="cli")
        return cli_adapter.run_command(argv, bundle_dir=bundle_dir, target_name=target.name)

    return DispatchResult(
        ok=False,
        message="",
        error=f"Unknown agent send type: {send_type}",
        kind=target.kind,
    )
