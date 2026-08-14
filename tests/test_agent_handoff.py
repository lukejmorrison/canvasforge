import json
from pathlib import Path

from agent_handoff.cards import load_cards_from_directories, parse_card, xdg_card_directories
from agent_handoff.dispatch import build_handoff_payload, build_prompt, dispatch_bundle
from agent_handoff.discovery import annotate_targets, discover_agents, find_target, resolve_pin_id
from agent_handoff.models import CARD_SCHEMA, HANDOFF_SCHEMA, AgentTarget
from agent_handoff.security import is_allowed_agent_http_endpoint


def test_http_allowlist_localhost_ok():
    allowed, reason = is_allowed_agent_http_endpoint("http://127.0.0.1:18789/inbox")
    assert allowed is True
    assert reason == ""


def test_http_allowlist_blocks_cleartext_remote():
    allowed, reason = is_allowed_agent_http_endpoint("http://example.com/inbox")
    assert allowed is False
    assert "localhost" in reason


def test_http_allowlist_https_remote_ok():
    allowed, _ = is_allowed_agent_http_endpoint("https://example.com/inbox")
    assert allowed is True


def test_parse_card_requires_schema_and_ids():
    assert parse_card({"name": "Namshub"}) is None
    card = parse_card(
        {
            "schema": CARD_SCHEMA,
            "id": "openclaw:namshub",
            "name": "Namshub",
            "kind": "openclaw",
            "status": "online",
            "send": {"type": "openclaw", "agent": "namshub"},
        }
    )
    assert card is not None
    assert card.id == "openclaw:namshub"
    target = card.to_target()
    assert target.can_send is True


def test_load_cards_from_directories(tmp_path):
    folder = tmp_path / "local-agents"
    folder.mkdir()
    (folder / "namshub.json").write_text(
        json.dumps(
            {
                "schema": CARD_SCHEMA,
                "id": "openclaw:namshub",
                "name": "Namshub",
                "kind": "openclaw",
                "send": {"type": "cli", "argv": ["openclaw", "agent", "--message", "{prompt}"]},
            }
        )
    )
    (folder / "bad.json").write_text("{not json")
    targets = load_cards_from_directories([folder])
    assert [item.id for item in targets] == ["openclaw:namshub"]


def test_xdg_card_directories_prefer_runtime(tmp_path):
    runtime = tmp_path / "run"
    data = tmp_path / "data"
    dirs = xdg_card_directories(
        {"XDG_RUNTIME_DIR": str(runtime), "XDG_DATA_HOME": str(data)},
        home=tmp_path / "home",
    )
    assert dirs[0] == runtime / "local-agents"
    assert dirs[1] == data / "local-agents"


def test_discover_agents_uses_cards_and_probes(tmp_path):
    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "custom.json").write_text(
        json.dumps(
            {
                "schema": CARD_SCHEMA,
                "id": "custom:reviewer",
                "name": "Reviewer",
                "kind": "cli",
                "status": "available",
                "send": {"type": "cli", "argv": ["echo", "{prompt}"]},
            }
        )
    )
    home = tmp_path / "home"
    (home / ".openclaw").mkdir(parents=True)
    (home / ".openclaw" / "openclaw.json").write_text(
        json.dumps(
            {
                "agents": {
                    "list": [
                        {"id": "namshub", "identity": {"name": "Namshub"}},
                        {"id": "dr-voss-thorne", "identity": {"name": "Dr Voss Thorne"}},
                    ]
                }
            }
        )
    )
    (home / ".hermes").mkdir()
    (home / ".hermes" / "config.yaml").write_text("agent:\n  name: Metatron (Tron)\n")

    def fake_which(name: str) -> str | None:
        return {"grok": "/usr/bin/grok", "claude": "/usr/bin/claude"}.get(name)

    def fake_health(url: str, timeout: float) -> tuple[bool, str]:
        if "8642" in url:
            return True, ""
        if "18789" in url:
            return True, ""
        return False, "not reachable"

    targets = discover_agents(
        home=home,
        environ={"XDG_RUNTIME_DIR": "", "XDG_DATA_HOME": str(tmp_path / "unused")},
        which=fake_which,
        health=fake_health,
        extra_cards=[cards],
        command_template="echo {prompt}",
        http_endpoint="http://127.0.0.1:9/inbox",
    )
    ids = {item.id: item for item in targets}
    assert ids["custom:reviewer"].name == "Reviewer"
    assert ids["hermes:default"].name == "Metatron (Tron)"
    assert ids["hermes:default"].status == "online"
    assert ids["openclaw:namshub"].status == "online"
    assert ids["openclaw:dr-voss-thorne"].name == "Dr Voss Thorne"
    assert ids["clipboard:jpeg"].can_send is True
    assert ids["grok:build"].can_send is True
    assert ids["cli:claude"].can_send is True
    assert ids["cli:custom"].can_send is True
    assert ids["http:custom"].can_send is True


def test_resolve_pin_id_maps_legacy_and_openclaw_fallback():
    targets = [
        AgentTarget(id="openclaw:namshub", name="Namshub", kind="openclaw", status="online"),
        AgentTarget(id="clipboard:jpeg", name="Grok", kind="clipboard", status="available"),
    ]
    assert resolve_pin_id("clipboard_base64", targets) == "clipboard:jpeg"
    assert resolve_pin_id("openclaw", targets) == "openclaw:namshub"
    assert resolve_pin_id("missing", targets) == "missing"


def test_annotate_and_find_targets():
    targets = [
        AgentTarget(id="a", name="A", kind="cli", status="available"),
        AgentTarget(id="b", name="B", kind="hermes", status="online"),
    ]
    ordered = annotate_targets(targets, pin_id="a", last_used_id="b")
    assert ordered[0].id == "a"
    assert ordered[0].pinned is True
    assert find_target(ordered, "b").last_used is True


def test_build_prompt_and_handoff_payload(tmp_path):
    png = tmp_path / "selected.png"
    png.write_bytes(b"png")
    annotations = tmp_path / "annotations.json"
    annotations.write_text(json.dumps({"schema": "canvasforge.agent.bundle/1", "annotations": []}))
    prompt = build_prompt(
        "Look at {image} and {json} for {agent}",
        image=png,
        json_path=annotations,
        bundle_dir=tmp_path,
        agent="hermes:default",
    )
    assert str(png) in prompt
    target = AgentTarget(id="http:custom", name="HTTP", kind="http", status="available")
    payload = build_handoff_payload(target, prompt, png, annotations, tmp_path)
    body = payload.to_dict()
    assert body["schema"] == HANDOFF_SCHEMA
    assert body["image_base64"]
    assert body["source"] == "CanvasForge"


def test_dispatch_routes_openclaw_and_rejects_clipboard(tmp_path, monkeypatch):
    png = tmp_path / "selected.png"
    png.write_bytes(b"png")
    (tmp_path / "annotations.json").write_text("{}")
    captured = {}

    def fake_send(agent_id, prompt, bundle_dir):
        captured["agent"] = agent_id
        captured["prompt"] = prompt
        from agent_handoff.models import DispatchResult

        return DispatchResult(ok=True, message="sent", kind="openclaw")

    monkeypatch.setattr("agent_handoff.adapters.openclaw.send_to_openclaw", fake_send)
    target = AgentTarget(
        id="openclaw:namshub",
        name="Namshub",
        kind="openclaw",
        status="online",
        send={"type": "openclaw", "agent": "namshub"},
    )
    result = dispatch_bundle(target, tmp_path)
    assert result.ok is True
    assert captured["agent"] == "namshub"
    assert "selected.png" in captured["prompt"]

    clip = AgentTarget(
        id="clipboard:jpeg",
        name="Grok TUI",
        kind="clipboard",
        status="available",
        send={"type": "clipboard", "mode": "jpeg"},
    )
    clip_result = dispatch_bundle(clip, tmp_path)
    assert clip_result.ok is False
    assert "Clipboard" in clip_result.error


def test_dispatch_http_blocked_for_cleartext_remote(tmp_path):
    png = tmp_path / "selected.png"
    png.write_bytes(b"png")
    (tmp_path / "annotations.json").write_text("{}")
    target = AgentTarget(
        id="http:custom",
        name="Remote",
        kind="http",
        status="available",
        send={"type": "http", "url": "http://example.com/inbox"},
    )
    result = dispatch_bundle(target, tmp_path)
    assert result.ok is False
    assert "localhost" in result.error


def test_picker_disables_offline_rows(qapp):
    from PyQt6.QtCore import Qt

    from agent_handoff.picker import AgentPickerDialog

    targets = [
        AgentTarget(id="offline", name="Down", kind="hermes", status="offline", reason="not reachable"),
        AgentTarget(id="up", name="Up", kind="clipboard", status="available"),
    ]
    dialog = AgentPickerDialog(targets)
    assert dialog.list_widget.count() == 2
    offline = dialog.list_widget.item(0)
    online = dialog.list_widget.item(1)
    assert not (offline.flags() & Qt.ItemFlag.ItemIsEnabled)
    assert online.flags() & Qt.ItemFlag.ItemIsEnabled
    dialog.close()


def test_cli_expand_argv_placeholders():
    from agent_handoff.adapters.cli import expand_argv

    target = AgentTarget(
        id="cli:echo",
        name="Echo",
        kind="cli",
        status="available",
        send={"type": "cli", "argv": ["echo", "{prompt}", "{image}"]},
    )
    argv = expand_argv(
        target,
        prompt="hello",
        image=Path("/tmp/a.png"),
        json_path=Path("/tmp/a.json"),
        bundle_dir=Path("/tmp"),
    )
    assert argv == ["echo", "hello", "/tmp/a.png"]
