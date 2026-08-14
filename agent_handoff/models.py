"""Shared types for local-agent cards and CanvasForge handoff."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CARD_SCHEMA = "local-agent.card/1"
HANDOFF_SCHEMA = "local-agent.handoff/1"
BUNDLE_SCHEMA = "canvasforge.agent.bundle/1"

DEFAULT_PROMPT_TEMPLATE = (
    "Please review the annotated screenshot at {image}. "
    "Structured annotations are at {json}. "
    "Tell me what changes the user is asking for and propose code edits."
)

# Older Preferences combo values → new target ids.
LEGACY_TARGET_MAP = {
    "clipboard": "clipboard:path",
    "clipboard_base64": "clipboard:jpeg",
    "vscode_codex": "vscode:codex",
    "claude": "cli:claude",
    "codex": "cli:codex",
    "openclaw": "openclaw:namshub",
    "wizwam": "http:custom",
}

SENDABLE_STATUSES = frozenset({"online", "available"})


@dataclass
class AgentTarget:
    """One row in the Send to Agent picker."""

    id: str
    name: str
    kind: str
    status: str
    reason: str = ""
    send: dict[str, Any] = field(default_factory=dict)
    accepts: list[str] = field(default_factory=list)
    pinned: bool = False
    last_used: bool = False

    @property
    def can_send(self) -> bool:
        return self.status in SENDABLE_STATUSES

    def status_label(self) -> str:
        if self.status == "online":
            return "online"
        if self.status == "available":
            return "available"
        if self.status == "unavailable":
            return self.reason or "not wired yet"
        return self.reason or "offline"


@dataclass
class LocalAgentCard:
    """Parsed local-agent.card/1 document."""

    schema: str
    id: str
    name: str
    kind: str
    status: str = "available"
    accepts: list[str] = field(default_factory=list)
    send: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def to_target(self) -> AgentTarget:
        return AgentTarget(
            id=self.id,
            name=self.name,
            kind=self.kind,
            status=self.status or "available",
            reason=self.reason,
            send=dict(self.send),
            accepts=list(self.accepts),
        )


@dataclass
class HandoffPayload:
    """local-agent.handoff/1 body plus legacy CanvasForge keys."""

    source: str
    target: str
    prompt: str
    bundle_dir: str
    image_path: str
    annotations_path: str
    annotations: Any
    image_base64: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": HANDOFF_SCHEMA,
            "source": self.source,
            "target": self.target,
            "prompt": self.prompt,
            "bundle_dir": self.bundle_dir,
            "image_path": self.image_path,
            "annotations_path": self.annotations_path,
            "image_base64": self.image_base64,
            "annotations": self.annotations,
        }


@dataclass
class DispatchResult:
    ok: bool
    message: str
    error: str = ""
    kind: str = ""
    clipboard_text: str = ""
