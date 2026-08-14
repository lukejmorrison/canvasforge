"""Parse and load local-agent.card/1 files from XDG directories."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agent_handoff.models import CARD_SCHEMA, AgentTarget, LocalAgentCard


def xdg_card_directories(
    environ: dict[str, str] | None = None,
    home: Path | None = None,
) -> list[Path]:
    env = environ if environ is not None else os.environ
    home_path = home if home is not None else Path.home()
    dirs: list[Path] = []
    runtime = env.get("XDG_RUNTIME_DIR", "").strip()
    if runtime:
        dirs.append(Path(runtime) / "local-agents")
    data = env.get("XDG_DATA_HOME", "").strip()
    data_root = Path(data) if data else home_path / ".local" / "share"
    dirs.append(data_root / "local-agents")
    return dirs


def parse_card(data: Any) -> LocalAgentCard | None:
    if not isinstance(data, dict):
        return None
    schema = str(data.get("schema") or "")
    if schema != CARD_SCHEMA:
        return None
    card_id = str(data.get("id") or "").strip()
    name = str(data.get("name") or "").strip()
    kind = str(data.get("kind") or "").strip()
    if not card_id or not name or not kind:
        return None
    send = data.get("send") if isinstance(data.get("send"), dict) else {}
    accepts = data.get("accepts") if isinstance(data.get("accepts"), list) else []
    status = str(data.get("status") or "available").strip() or "available"
    reason = str(data.get("reason") or "")
    return LocalAgentCard(
        schema=schema,
        id=card_id,
        name=name,
        kind=kind,
        status=status,
        accepts=[str(item) for item in accepts],
        send=dict(send),
        reason=reason,
    )


def load_cards_from_directories(directories: list[Path]) -> list[AgentTarget]:
    seen: set[str] = set()
    targets: list[AgentTarget] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            card = parse_card(data)
            if card is None or card.id in seen:
                continue
            seen.add(card.id)
            targets.append(card.to_target())
    return targets
