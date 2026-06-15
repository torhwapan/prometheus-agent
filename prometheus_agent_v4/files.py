"""File-backed inspection storage for v4."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from uuid import uuid4


DEFAULT_DATA_DIR = Path("data_v4") / "inspections"


class InspectionFiles:
    def __init__(self, root: Path | str = DEFAULT_DATA_DIR) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, intent: Mapping[str, Any], plan_payload: Mapping[str, Any]) -> Dict[str, Any]:
        inspection_id = str(uuid4())
        base = self.base(inspection_id)
        for child in [
            "raw",
            "compact",
            "analysis",
            "ai_input",
            "ai_output",
            "report",
        ]:
            (base / child).mkdir(parents=True, exist_ok=True)
        meta = {
            "inspection_id": inspection_id,
            "created_at": _now(),
            "updated_at": _now(),
            "status": "planned",
            "intent": dict(intent),
            "paths": {
                "base": str(base),
                "plan": str(base / "plan.json"),
                "meta": str(base / "meta.json"),
            },
            "summary": {},
        }
        plain_plan = plan_payload.get("plain")
        self.write_json(inspection_id, "meta.json", meta)
        self.write_json(inspection_id, "plan.json", plain_plan)
        self.write_json(inspection_id, "plain_plan.json", plain_plan)
        return meta

    def base(self, inspection_id: str) -> Path:
        return self.root / inspection_id

    def exists(self, inspection_id: str) -> bool:
        return self.base(inspection_id).exists()

    def list(self) -> List[Dict[str, Any]]:
        items = []
        for path in sorted(self.root.iterdir()) if self.root.exists() else []:
            if not path.is_dir():
                continue
            meta_path = path / "meta.json"
            if meta_path.exists():
                items.append(_read_json(meta_path))
        return items

    def meta(self, inspection_id: str) -> Optional[Dict[str, Any]]:
        path = self.base(inspection_id) / "meta.json"
        if not path.exists():
            return None
        return _read_json(path)

    def update_meta(self, inspection_id: str, **fields: Any) -> Dict[str, Any]:
        meta = self.meta(inspection_id)
        if meta is None:
            raise KeyError(f"inspection not found: {inspection_id}")
        meta.update(fields)
        meta["updated_at"] = _now()
        self.write_json(inspection_id, "meta.json", meta)
        return meta

    def read_json(self, inspection_id: str, relative: str) -> Any:
        path = self.base(inspection_id) / relative
        return _read_json(path)

    def write_json(self, inspection_id: str, relative: str, value: Any) -> Path:
        path = self.base(inspection_id) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(path, value)
        return path

    def append_jsonl(self, inspection_id: str, relative: str, value: Mapping[str, Any]) -> Path:
        path = self.base(inspection_id) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, default=str))
            handle.write("\n")
        return path


def safe_part(value: Any) -> str:
    text = str(value or "unknown")
    for char in [":", "/", "\\", " ", "*", "?", '"', "<", ">", "|"]:
        text = text.replace(char, "_")
    return text[:120] or "unknown"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
