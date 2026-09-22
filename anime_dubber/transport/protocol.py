from __future__ import annotations

import json
from typing import Any, Dict


def encode_message(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def decode_request(line: str) -> dict:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON request: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Request must be a JSON object")
    if payload.get("type", "request") != "request":
        raise ValueError("Message type must be 'request'")
    if not payload.get("id"):
        raise ValueError("Request id is required")
    if not payload.get("method"):
        raise ValueError("Request method is required")
    params = payload.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError("Request params must be an object")
    payload["params"] = params
    return payload


def response_ok(request_id: str, result: Any) -> dict:
    return {"type": "response", "id": request_id, "ok": True, "result": result}


def response_error(request_id: str, message: str, error_type: str = "BackendError") -> dict:
    return {
        "type": "response",
        "id": request_id,
        "ok": False,
        "error": {"type": error_type, "message": message},
    }
