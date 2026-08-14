"""CLI template and argv handoff."""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path

from agent_handoff.models import AgentTarget, DispatchResult


def expand_argv(
    target: AgentTarget,
    *,
    prompt: str,
    image: Path,
    json_path: Path,
    bundle_dir: Path,
) -> list[str]:
    send = target.send or {}
    argv = send.get("argv")
    if isinstance(argv, list) and argv:
        expanded: list[str] = []
        mapping = {
            "{prompt}": prompt,
            "{image}": str(image),
            "{json}": str(json_path),
            "{dir}": str(bundle_dir),
            "{agent}": target.id,
        }
        for part in argv:
            text = str(part)
            for key, value in mapping.items():
                text = text.replace(key, value)
            expanded.append(text)
        return expanded

    template = str(send.get("template") or "").strip()
    if not template:
        raise ValueError("Agent command is not configured")
    command = template.format(
        prompt=prompt,
        image=str(image),
        json=str(json_path),
        dir=str(bundle_dir),
        agent=target.id,
    )
    return shlex.split(command)


def run_command(argv: list[str], *, bundle_dir: Path, target_name: str) -> DispatchResult:
    if not argv:
        return DispatchResult(ok=False, message="", error="Empty agent command", kind="cli")
    resolved = shutil.which(argv[0]) or argv[0]
    cmd = [resolved, *argv[1:]]
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError:
        return DispatchResult(
            ok=False,
            message="",
            error=(
                f"Could not run '{cmd[0]}'. Set the command in Preferences → Agent. "
                f"The annotation bundle is still available at:\n\n{bundle_dir}"
            ),
            kind="cli",
        )
    except OSError as exc:
        return DispatchResult(
            ok=False,
            message="",
            error=f"Could not start the agent command:\n\n{exc}\n\nBundle: {bundle_dir}",
            kind="cli",
        )
    return DispatchResult(
        ok=True,
        message=f"Sent selected image to {target_name}: {cmd[0]} (bundle: {bundle_dir})",
        kind="cli",
    )
