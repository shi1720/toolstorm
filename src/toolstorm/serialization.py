"""Bounded JSON and conservative payload capture; never call user repr()."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .errors import ConfigurationError

MAX_DOCUMENT_BYTES = 8_000_000
MAX_VALUE_BYTES = 128_000
MAX_DEPTH = 32
REDACTED = "[REDACTED]"
SECRET_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "set_cookie",
        "credentials",
        "private_key",
        "client_secret",
        "session_token",
    }
)


def json_value(value: Any, *, depth: int = 0) -> Any:
    """Copy JSON-native data, rejecting non-finite floats and executable objects."""
    if depth > MAX_DEPTH:
        raise ConfigurationError(f"JSON nesting exceeds {MAX_DEPTH}")
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) in (list, tuple):
        return [json_value(v, depth=depth + 1) for v in value]
    if type(value) is dict and all(type(k) is str for k in value):
        return {k: json_value(v, depth=depth + 1) for k, v in value.items()}
    raise ConfigurationError("ToolStorm accepts only finite JSON-compatible data")


def canonical(value: Any) -> str:
    try:
        return json.dumps(
            json_value(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
    except (ValueError, OverflowError, RecursionError) as exc:
        raise ConfigurationError("Value cannot be safely serialized as JSON") from exc


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def load_json(text: str, *, max_bytes: int = MAX_DOCUMENT_BYTES) -> Any:
    if not isinstance(text, str) or len(text.encode("utf-8")) > max_bytes:
        raise ConfigurationError("JSON document exceeds size limit")

    def reject_constant(_: str) -> None:
        raise ConfigurationError("Non-finite JSON numbers are not allowed")

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, val in pairs:
            if key in result:
                raise ConfigurationError("Duplicate JSON object key")
            result[key] = val
        return result

    try:
        value = json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_pairs)
        return json_value(value)
    except (ValueError, RecursionError, TypeError) as exc:
        raise ConfigurationError("Invalid or excessively nested JSON") from exc


def require_keys(value: Any, required: set[str], optional: set[str] | None = None) -> None:
    if type(value) is not dict or not required.issubset(value):
        raise ConfigurationError("Missing required document fields")
    if set(value) - required - (optional or set()):
        raise ConfigurationError("Unknown document fields")


class Redactor:
    """Key-based redaction plus caller-provided literal secrets, applied to copies.

    Heuristics are not a PII detector. Supply secrets for free text or disable
    payload capture. Exception messages are never recorded.
    """

    def __init__(self, *, keys: tuple[str, ...] = (), secrets: tuple[str, ...] = ()) -> None:
        if any(not isinstance(s, str) or not s for s in secrets + keys):
            raise ConfigurationError("Redaction keys and secrets must be nonempty strings")
        self.keys = SECRET_KEYS | frozenset(self._key(k) for k in keys)
        self.secrets = tuple(sorted(secrets, key=len, reverse=True))

    @staticmethod
    def _key(key: str) -> str:
        return key.lower().replace("-", "_")

    def scrub(self, value: Any) -> Any:
        data = json_value(value)

        def visit(item: Any) -> Any:
            if isinstance(item, dict):
                cleaned: dict[str, Any] = {}
                for key, val in item.items():
                    safe_key = visit(key)
                    if safe_key in cleaned:
                        raise ConfigurationError("Redaction creates ambiguous dictionary keys")
                    cleaned[safe_key] = REDACTED if self._key(key) in self.keys else visit(val)
                return cleaned
            if isinstance(item, list):
                return [visit(v) for v in item]
            if isinstance(item, str):
                for secret in self.secrets:
                    item = item.replace(secret, REDACTED)
            return item

        result = visit(data)
        if len(canonical(result).encode()) > MAX_VALUE_BYTES:
            raise ConfigurationError("Captured value exceeds 128 KB")
        return result
