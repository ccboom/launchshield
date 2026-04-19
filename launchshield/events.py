"""SSE event shaping for LaunchShield Swarm."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


EVENT_TYPES = {
    "run.started",
    "stage.started",
    "tool.invoked",
    "payment.submitted",
    "payment.confirmed",
    "tool.completed",
    "tool.failed",
    "finding.created",
    "stage.completed",
    "run.completed",
    "run.failed",
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StreamEvent:
    type: str
    run_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    emitted_at: str = field(default_factory=_utcnow_iso)

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {self.type}")

    def to_sse(self) -> str:
        body = {
            "type": self.type,
            "run_id": self.run_id,
            "emitted_at": self.emitted_at,
            "payload": self.payload,
        }
        data = json.dumps(body, default=str)
        return f"event: {self.type}\ndata: {data}\n\n"


def make_event(type_: str, run_id: str, **payload: Any) -> StreamEvent:
    return StreamEvent(type=type_, run_id=run_id, payload=payload)
