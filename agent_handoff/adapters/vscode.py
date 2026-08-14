"""VS Code Codex folder handoff."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from agent_handoff.models import DispatchResult


def send_to_vscode_codex(
    prompt: str, png_path: Path, json_path: Path, bundle_dir: Path
) -> DispatchResult:
    prompt_path = bundle_dir / "codex_prompt.md"
    prompt_path.write_text(
        "# CanvasForge to VS Code Codex\n\n"
        f"{prompt}\n\n"
        "## Bundle\n\n"
        f"- Image: `{png_path}`\n"
        f"- Annotations: `{json_path}`\n"
        f"- Folder: `{bundle_dir}`\n\n"
        "Open the image and annotations in this folder, then use this prompt in the VS Code Codex/OpenAI panel.\n",
        encoding="utf-8",
    )
    prompt_text = prompt_path.read_text(encoding="utf-8")
    code_path = shutil.which("code")
    if not code_path:
        return DispatchResult(
            ok=False,
            message="",
            error=(
                "Could not find the 'code' command. The Codex prompt was copied "
                f"to the clipboard and the bundle is available at:\n\n{bundle_dir}"
            ),
            kind="vscode",
            clipboard_text=prompt_text,
        )
    try:
        subprocess.Popen(
            [code_path, "--reuse-window", str(bundle_dir)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return DispatchResult(
            ok=False,
            message="",
            error=(
                f"Could not open VS Code:\n\n{exc}\n\n"
                f"The Codex prompt was copied and the bundle is at:\n\n{bundle_dir}"
            ),
            kind="vscode",
            clipboard_text=prompt_text,
        )
    return DispatchResult(
        ok=True,
        message=f"Opened VS Code Codex bundle: {bundle_dir} (prompt copied)",
        kind="vscode",
        clipboard_text=prompt_text,
    )
