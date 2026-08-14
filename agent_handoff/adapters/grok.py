"""Grok Build CLI handoff."""

from __future__ import annotations

import shutil
from pathlib import Path

from agent_handoff.adapters.cli import run_command
from agent_handoff.models import DispatchResult


def send_to_grok_build(prompt: str, bundle_dir: Path, command: str = "") -> DispatchResult:
    binary = command or shutil.which("grok") or "grok"
    argv = [binary, "-p", prompt]
    return run_command(argv, bundle_dir=bundle_dir, target_name="Grok Build")
