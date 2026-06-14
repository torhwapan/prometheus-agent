"""In-memory inspection state store for v3."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, List, Mapping, Optional
from uuid import uuid4


class InspectionStore:
    """Thread-safe in-memory store.

    The company platform keeps orchestration control, while this service keeps
    plan, query results, analysis, AI inputs, AI findings, correlation, and report
    by inspection id.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._items: Dict[str, Dict[str, Any]] = {}

    def create(self, intent: Mapping[str, Any], plan_payload: Mapping[str, Any]) -> Dict[str, Any]:
        inspection_id = str(uuid4())
        record = {
            "inspection_id": inspection_id,
            "created_at": _now(),
            "updated_at": _now(),
            "status": "planned",
            "intent": deepcopy(dict(intent)),
            "plan": deepcopy(plan_payload.get("plan")),
            "plain_plan": deepcopy(plan_payload.get("plain")),
            "query": None,
            "analysis": None,
            "ai_series_inputs": None,
            "ai_series_findings": None,
            "ai_correlation": None,
            "report": None,
            "errors": [],
        }
        with self._lock:
            self._items[inspection_id] = record
        return deepcopy(record)

    def get(self, inspection_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._items.get(inspection_id)
            return deepcopy(item) if item else None

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "inspection_id": item["inspection_id"],
                    "created_at": item["created_at"],
                    "updated_at": item["updated_at"],
                    "status": item["status"],
                    "intent": item.get("intent"),
                    "summary": _summary(item),
                }
                for item in self._items.values()
            ]

    def update(self, inspection_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._items.get(inspection_id)
            if item is None:
                return None
            for key, value in fields.items():
                item[key] = deepcopy(value)
            item["updated_at"] = _now()
            return deepcopy(item)

    def append_error(self, inspection_id: str, error: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._items.get(inspection_id)
            if item is None:
                return None
            item.setdefault("errors", []).append(deepcopy(dict(error)))
            item["updated_at"] = _now()
            item["status"] = "error"
            return deepcopy(item)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _summary(item: Mapping[str, Any]) -> Dict[str, Any]:
    analysis = item.get("analysis")
    if not isinstance(analysis, Mapping):
        return {}
    return {
        "severity": analysis.get("severity"),
        "counts": analysis.get("counts"),
        "risky_count": len(analysis.get("risky_items", [])) if isinstance(analysis.get("risky_items"), list) else 0,
    }
