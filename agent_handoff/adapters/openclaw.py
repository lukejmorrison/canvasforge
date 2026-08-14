"""Send a CanvasForge bundle to an OpenClaw agent via the CLI."""

from __future__ import annotations

import shutil
from pathlib import Path

from agent_handoff.adapters.cli import run_command
from agent_handoff.models import DispatchResult


def send_to_openclaw(agent_id: str, prompt: str, bundle_dir: Path) -> DispatchResult:
    binary = shutil.which("openclaw") or "openclaw"
    argv = [binary, "agent"]
    if agent_id:
        argv.extend(["--agent", agent_id])
    argv.extend(["--message", prompt])
    label = agent_id or "OpenClaw"
    return run_command(argv, bundle_dir=bundle_dir, target_name=label)
