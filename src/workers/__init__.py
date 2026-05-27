"""Workers package - background task implementations."""

from __future__ import annotations

import json


def parse_part_keys_json(part_keys_json: str | None) -> list[str]:
    """Decode a JSON-encoded list of S3 object part keys with defensive validation."""
    if not part_keys_json:
        return []
    try:
        parsed = json.loads(part_keys_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str)]
