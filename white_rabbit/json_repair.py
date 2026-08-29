from __future__ import annotations

import json
import re
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def parse_structured(text: str, schema: Type[T]) -> T:
    """Parse model JSON, recovering a partial object when Gemini truncates output."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return schema.model_validate_json(raw)
    except Exception:
        repaired = _repair_truncated_object(raw)
        return schema.model_validate_json(repaired)


def _repair_truncated_object(raw: str) -> str:
    start = raw.find("{")
    if start < 0:
        raise ValueError("no JSON object in Gemini response")
    blob = raw[start:]
    try:
        json.loads(blob)
        return blob
    except Exception:
        pass

    items_key = blob.find('"items"')
    if items_key >= 0:
        bracket = blob.find("[", items_key)
        if bracket >= 0:
            items, consumed = _complete_objects(blob[bracket + 1 :])
            relevant = True
            if '"relevant"' in blob[:items_key]:
                relevant = "false" not in blob[blob.find('"relevant"'): items_key].lower()
            payload = {"relevant": relevant, "source_summary": "(recovered from truncated Gemini JSON)", "items": items}
            return json.dumps(payload)

    closed = blob.rsplit("}", 1)[0] + "}"
    try:
        json.loads(closed)
        return closed
    except Exception as exc:
        raise ValueError(f"could not repair truncated JSON: {exc}") from exc


def _complete_objects(after_bracket: str) -> tuple[list[dict], int]:
    objs: list[dict] = []
    decoder = json.JSONDecoder()
    i = 0
    text = after_bracket
    while i < len(text):
        while i < len(text) and text[i] in " \n\r\t,":
            i += 1
        if i >= len(text) or text[i] in "]}":
            break
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            break
        if isinstance(obj, dict):
            objs.append(obj)
        i = end
    return objs, i
