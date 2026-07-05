"""Optional LLM enrichment for V6 inspection findings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LlmError(RuntimeError):
    """Raised when LLM enrichment fails."""


@dataclass(frozen=True)
class LlmSettings:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> Optional["LlmSettings"]:
        base_url = str(os.getenv("LLM_BASE_URL") or "").strip().rstrip("/")
        api_key = str(os.getenv("LLM_API_KEY") or "").strip()
        model = str(os.getenv("LLM_MODEL") or "").strip()
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS") or "30")
        if not base_url or not api_key or not model:
            return None
        return cls(base_url=base_url, api_key=api_key, model=model, timeout_seconds=timeout)


class LlmClient:
    def __init__(self, settings: LlmSettings) -> None:
        self.settings = settings

    def enrich(self, summary: Mapping[str, Any], findings: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        risky = [item for item in findings if str(item.get("severity")) in {"critical", "warning", "info"}][:8]
        if not risky:
            return {"summary": None, "comments": []}

        payload = {
            "model": self.settings.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 Prometheus 巡检报告的辅助解释器。"
                        "你不能修改规则判级，只能补充简短原因、影响和建议。"
                        "必须返回 JSON，格式为 "
                        '{"summary":"...","comments":[{"finding_key":"...","comment":"..."}]}。'
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "report_summary": summary,
                            "findings": [
                                {
                                    "finding_key": item.get("finding_key"),
                                    "job": item.get("job"),
                                    "instance": item.get("instance"),
                                    "metric_name": item.get("metric_name"),
                                    "severity": item.get("severity"),
                                    "current_value": item.get("current_value"),
                                    "unit": item.get("analysis", {}).get("unit"),
                                    "reason": item.get("reason"),
                                }
                                for item in risky
                            ],
                            "requirements": {
                                "summary_length": "80字以内",
                                "comment_length": "40字以内",
                                "tone": "客观、简洁、可执行",
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }

        endpoint = f"{self.settings.base_url}/chat/completions"
        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise LlmError(f"LLM HTTP {exc.code}: {details}") from exc
        except (URLError, TimeoutError) as exc:
            raise LlmError(f"LLM connection failed: {exc}") from exc

        try:
            response_payload = json.loads(raw)
            content = response_payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LlmError(f"LLM response parse failed: {raw[:200]}") from exc

        structured = _parse_json_content(content)
        summary_text = structured.get("summary")
        comments = structured.get("comments")
        if not isinstance(comments, list):
            comments = []
        return {
            "summary": str(summary_text).strip() if summary_text else None,
            "comments": [
                {
                    "finding_key": str(item.get("finding_key") or "").strip(),
                    "comment": str(item.get("comment") or "").strip(),
                }
                for item in comments
                if str(item.get("finding_key") or "").strip()
            ],
        }


def _parse_json_content(content: Any) -> Dict[str, Any]:
    if isinstance(content, list):
        text = "".join(str(item.get("text") or "") if isinstance(item, Mapping) else str(item) for item in content)
    else:
        text = str(content or "")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    return json.loads(cleaned or "{}")
