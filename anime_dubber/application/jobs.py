from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..core import CommandRunner


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    id: str
    kind: str
    config: Dict[str, Any]
    status: str = "queued"
    stage: str = "queued"
    created_at: str = field(default_factory=_now)
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    result: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    runner: Optional[CommandRunner] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "config": self.config,
            "status": self.status,
            "stage": self.stage,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "result": self.result,
            "error": self.error,
        }
