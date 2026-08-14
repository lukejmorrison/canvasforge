"""Discover local agents from cards, config files, PATH, and health probes."""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from agent_handoff.cards import load_cards_from_directories, xdg_card_directories
from agent_handoff.models import LEGACY_TARGET_MAP, AgentTarget

HealthFn = Callable[[str, float], tuple[bool, str]]

HERMES_HEALTH_URL = "http://127.0.0.1:8642/health"
OPENCLAW_HEALTH_URL = "http://127.0.0.1:18789/health"
GROK_ACP_URL = "http://127.0.0.1:2419/"
BUZZ_RELAY_URL = "http://127.0.0.1:3000/"
PROBE_TIMEOUT = 0.4


def probe_http(url: str, timeout: float = PROBE_TIMEOUT) -> tuple[bool, str]:
    """Return (up, reason). 401/403 still count as up."""
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(256)
        return True, ""
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return True, ""
        return False, f"HTTP {exc.code}"
    except Exception:
        return False, "not reachable"


def _read_dotenv_key(path: Path, key: str) -> str:
    if not path.is_file():
        return ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        if name.strip() == key:
            return value.strip().strip("'\"")
    return ""


def read_hermes_api_key(home: Path | None = None) -> str:
    """Read the local Hermes API server key. Never log the return value."""
    env_key = os.environ.get("HERMES_API_SERVER_KEY") or os.environ.get("API_SERVER_KEY") or ""
    if env_key.strip():
        return env_key.strip()
    root = home if home is not None else Path.home()
    for candidate in (root / ".hermes" / ".env", root / ".hermes" / "profiles" / "metatron" / ".env"):
        value = _read_dotenv_key(candidate, "API_SERVER_KEY")
        if value:
            return value
    return ""


def _hermes_display_name(home: Path) -> str:
    config = home / ".hermes" / "config.yaml"
    if not config.is_file():
        return "Hermes"
    in_agent = False
    try:
        for line in config.read_text(encoding="utf-8").splitlines():
            if line.startswith("agent:"):
                in_agent = True
                continue
            if in_agent and line.startswith("  name:"):
                return line.split(":", 1)[1].strip().strip("'\"") or "Hermes"
            if in_agent and line and not line.startswith(" ") and not line.startswith("\t"):
                break
    except OSError:
        return "Hermes"
    return "Hermes"


def _openclaw_agents(home: Path) -> list[dict]:
    path = home / ".openclaw" / "openclaw.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    agents = data.get("agents") if isinstance(data, dict) else None
    listing = agents.get("list") if isinstance(agents, dict) else None
    if not isinstance(listing, list):
        return []
    return [item for item in listing if isinstance(item, dict) and item.get("id")]


def discover_agents(
    *,
    home: Path | None = None,
    environ: dict[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
    health: HealthFn | None = None,
    extra_cards: list[Path] | None = None,
    command_template: str = "",
    http_endpoint: str = "",
) -> list[AgentTarget]:
    """Return discovered targets. Cards win on id collision."""
    home_path = home if home is not None else Path.home()
    env = environ if environ is not None else os.environ
    which_fn = which if which is not None else shutil.which
    health_fn = health if health is not None else probe_http

    by_id: dict[str, AgentTarget] = {}

    def add(target: AgentTarget) -> None:
        if target.id not in by_id:
            by_id[target.id] = target

    card_dirs = list(xdg_card_directories(env, home_path))
    if extra_cards:
        card_dirs.extend(extra_cards)
    for card in load_cards_from_directories(card_dirs):
        add(card)

    probe_urls = (HERMES_HEALTH_URL, OPENCLAW_HEALTH_URL, GROK_ACP_URL, BUZZ_RELAY_URL)
    health_results: dict[str, tuple[bool, str]] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {url: pool.submit(health_fn, url, PROBE_TIMEOUT) for url in probe_urls}
        for url, future in futures.items():
            try:
                health_results[url] = future.result()
            except Exception:
                health_results[url] = (False, "not reachable")

    hermes_up, hermes_reason = health_results[HERMES_HEALTH_URL]
    hermes_cli = which_fn("hermes")
    if hermes_up or hermes_cli or (home_path / ".hermes").is_dir():
        add(
            AgentTarget(
                id="hermes:default",
                name=_hermes_display_name(home_path),
                kind="hermes",
                status="online" if hermes_up else "offline",
                reason="" if hermes_up else (hermes_reason or "gateway not running"),
                send={
                    "type": "hermes",
                    "url": "http://127.0.0.1:8642/v1/chat/completions",
                },
                accepts=["image/png", "application/json"],
            )
        )

    openclaw_up, openclaw_reason = health_results[OPENCLAW_HEALTH_URL]
    openclaw_cli = which_fn("openclaw")
    for agent in _openclaw_agents(home_path):
        agent_id = str(agent.get("id"))
        identity = agent.get("identity") if isinstance(agent.get("identity"), dict) else {}
        name = str(identity.get("name") or agent_id)
        add(
            AgentTarget(
                id=f"openclaw:{agent_id}",
                name=name,
                kind="openclaw",
                status="online" if openclaw_up else "offline",
                reason="" if openclaw_up else (openclaw_reason or "gateway not running"),
                send={"type": "openclaw", "agent": agent_id},
                accepts=["image/png", "application/json"],
            )
        )
    if not _openclaw_agents(home_path) and (openclaw_cli or openclaw_up):
        add(
            AgentTarget(
                id="openclaw:default",
                name="OpenClaw",
                kind="openclaw",
                status="online" if openclaw_up else "offline",
                reason="" if openclaw_up else (openclaw_reason or "gateway not running"),
                send={"type": "openclaw", "agent": ""},
                accepts=["image/png", "application/json"],
            )
        )

    add(
        AgentTarget(
            id="clipboard:jpeg",
            name="Grok TUI (clipboard JPEG)",
            kind="clipboard",
            status="available",
            send={"type": "clipboard", "mode": "jpeg"},
            accepts=["image/jpeg"],
        )
    )
    add(
        AgentTarget(
            id="clipboard:path",
            name="Clipboard (image path)",
            kind="clipboard",
            status="available",
            send={"type": "clipboard", "mode": "path"},
            accepts=["image/png"],
        )
    )

    grok_cli = which_fn("grok")
    grok_acp_up, _ = health_results[GROK_ACP_URL]
    if grok_cli or grok_acp_up:
        add(
            AgentTarget(
                id="grok:build",
                name="Grok Build",
                kind="grok",
                status="available" if grok_cli else "offline",
                reason="" if grok_cli else "grok CLI not on PATH",
                send={"type": "grok", "command": grok_cli or "grok"},
                accepts=["image/png", "application/json"],
            )
        )

    buzz_cli = which_fn("buzz")
    buzz_up, _ = health_results[BUZZ_RELAY_URL]
    if buzz_cli or buzz_up:
        add(
            AgentTarget(
                id="buzz:local",
                name="Buzz",
                kind="buzz",
                status="unavailable",
                reason="channel send is not wired yet",
                send={"type": "buzz"},
            )
        )

    if which_fn("code"):
        add(
            AgentTarget(
                id="vscode:codex",
                name="VS Code Codex",
                kind="vscode",
                status="available",
                send={"type": "vscode"},
                accepts=["image/png", "application/json"],
            )
        )

    claude = which_fn("claude")
    if claude:
        add(
            AgentTarget(
                id="cli:claude",
                name="Claude",
                kind="cli",
                status="available",
                send={"type": "cli", "argv": [claude, "-p", "{prompt}"]},
                accepts=["image/png", "application/json"],
            )
        )

    codex = which_fn("codex")
    if codex:
        add(
            AgentTarget(
                id="cli:codex",
                name="Codex",
                kind="cli",
                status="available",
                send={"type": "cli", "argv": [codex, "{prompt}"]},
                accepts=["image/png", "application/json"],
            )
        )

    if command_template.strip():
        add(
            AgentTarget(
                id="cli:custom",
                name="Custom command",
                kind="cli",
                status="available",
                send={"type": "cli", "template": command_template.strip()},
                accepts=["image/png", "application/json"],
            )
        )

    if http_endpoint.strip():
        add(
            AgentTarget(
                id="http:custom",
                name="Custom HTTP endpoint",
                kind="http",
                status="available",
                send={"type": "http", "url": http_endpoint.strip()},
                accepts=["image/png", "application/json"],
            )
        )

    return list(by_id.values())


def resolve_pin_id(saved: str, targets: list[AgentTarget]) -> str:
    """Map a saved Preferences value onto a discovered target id."""
    raw = (saved or "").strip()
    if not raw:
        return ""
    mapped = LEGACY_TARGET_MAP.get(raw, raw)
    ids = {target.id for target in targets}
    if mapped in ids:
        return mapped
    if raw in ids:
        return raw
    if mapped.startswith("openclaw:"):
        for target in targets:
            if target.kind == "openclaw":
                return target.id
    return mapped


def annotate_targets(
    targets: list[AgentTarget],
    *,
    pin_id: str = "",
    last_used_id: str = "",
) -> list[AgentTarget]:
    for target in targets:
        target.pinned = bool(pin_id) and target.id == pin_id
        target.last_used = bool(last_used_id) and target.id == last_used_id
    return sort_targets(targets)


def sort_targets(targets: list[AgentTarget]) -> list[AgentTarget]:
    kind_order = {
        "hermes": 0,
        "openclaw": 1,
        "grok": 2,
        "clipboard": 3,
        "cli": 4,
        "vscode": 5,
        "http": 6,
        "buzz": 7,
    }

    def key(target: AgentTarget) -> tuple:
        return (
            0 if target.pinned else 1,
            0 if target.last_used else 1,
            0 if target.can_send else 1,
            kind_order.get(target.kind, 20),
            target.name.lower(),
        )

    return sorted(targets, key=key)


def find_target(targets: list[AgentTarget], target_id: str) -> AgentTarget | None:
    for target in targets:
        if target.id == target_id:
            return target
    return None
