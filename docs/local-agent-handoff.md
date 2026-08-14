# Local agent cards and CanvasForge handoff

Open, local-first contracts so any desktop app can discover agents and send a screenshot bundle. CanvasForge consumes these; agents may publish cards but do not have to — built-in probes fill the same list.

## `local-agent.card/1`

Drop a JSON file at:

- `$XDG_RUNTIME_DIR/local-agents/<id>.json` — process is running
- `$XDG_DATA_HOME/local-agents/<id>.json` — installed, may be idle  
  (`~/.local/share/local-agents/` when `XDG_DATA_HOME` is unset)

Runtime cards win when the same `id` appears in both places.

```json
{
  "schema": "local-agent.card/1",
  "id": "openclaw:namshub",
  "name": "Namshub",
  "kind": "openclaw",
  "status": "online",
  "accepts": ["image/png", "application/json"],
  "send": {
    "type": "cli",
    "argv": ["openclaw", "agent", "--agent", "namshub", "--message", "{prompt}"]
  }
}
```

| Field | Required | Notes |
|-------|----------|--------|
| `schema` | yes | Must be `local-agent.card/1` |
| `id` | yes | Stable, unique (`kind:name`) |
| `name` | yes | Human label |
| `kind` | yes | `hermes`, `openclaw`, `grok`, `clipboard`, `cli`, `http`, `vscode`, `buzz`, or a custom kind |
| `status` | no | `online`, `available`, `offline`, `unavailable` |
| `accepts` | no | MIME types the agent can take |
| `send` | yes to receive | See send types below |
| `reason` | no | Shown when the row cannot be sent to |

`send.type` values CanvasForge understands:

| `type` | Fields | Behaviour |
|--------|--------|-----------|
| `cli` | `argv` and/or `template` | Placeholders `{prompt}`, `{image}`, `{json}`, `{dir}`, `{agent}` |
| `http` | `url` | POST `local-agent.handoff/1` (localhost HTTP or any HTTPS) |
| `hermes` | `url` | OpenAI-style chat completions with an inline image |
| `openclaw` | `agent` | `openclaw agent --agent <id> --message` |
| `grok` | `command` | `grok -p` |
| `clipboard` | `mode` `jpeg` or `path` | System clipboard |
| `vscode` | — | Open the bundle folder in VS Code |

Unknown `send.type` values are listed but cannot be sent until an adapter exists.

## `local-agent.handoff/1`

HTTP receivers get:

```json
{
  "schema": "local-agent.handoff/1",
  "source": "CanvasForge",
  "target": "http:custom",
  "prompt": "Please review the annotated screenshot at …",
  "bundle_dir": "/tmp/canvasforge_agent_…",
  "image_path": "/tmp/canvasforge_agent_…/selected.png",
  "annotations_path": "/tmp/canvasforge_agent_…/annotations.json",
  "image_base64": "…",
  "annotations": { "schema": "canvasforge.agent.bundle/1" }
}
```

The sibling files remain the source of truth. `canvasforge.agent.bundle/1` is unchanged: `selected.png` or `canvas.png` plus structured `annotations.json`.

## Built-in probes

If no card is present, CanvasForge still looks for:

- Hermes at `http://127.0.0.1:8642/health` and `~/.hermes/`
- OpenClaw agents in `~/.openclaw/openclaw.json` and `http://127.0.0.1:18789/health`
- `grok`, `claude`, `codex`, `code`, and `buzz` on `PATH`
- Clipboard JPEG (Grok TUI) and clipboard path, always

This is not ACP, MCP, or a Buzz NIP. Those stay the native protocols; this file is only discovery plus a thin handoff envelope.
