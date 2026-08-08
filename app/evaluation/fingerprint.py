"""Canonical SHA-256 fingerprint helpers (P3-6).

Every auditable run/input fingerprint is a SHA-256 digest over strict
canonical JSON: keys sorted recursively, compact separators, ASCII-safe
output (``ensure_ascii``) and hard rejection of ``NaN``/``Infinity`` so
a fingerprint can never encode a non-JSON float. The canonical text is
pure ASCII regardless of source encoding, which makes digests stable
across processes, hosts and Python versions.

The helpers are generic over any JSON-serializable value; run manifests
hash dicts, but lists and leaf values hash identically.
"""

import hashlib
import json


def canonical_json(payload) -> str:
    """Return strict canonical JSON text for a JSON-serializable payload.

    - Keys are sorted recursively (``sort_keys=True``).
    - Separators are compact (``,`` / ``:``).
    - Non-ASCII text is escaped (``ensure_ascii=True``) so the output
      is pure ASCII, i.e. a stable byte string under strict UTF-8.
    - Non-finite floats (``NaN``/``Infinity``/``-Infinity``) raise
      :class:`ValueError` (``allow_nan=False``) instead of being
      serialized into non-JSON output.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_hex(data: str | bytes) -> str:
    """SHA-256 hex digest of text (strict UTF-8) or raw bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def fingerprint(payload) -> str:
    """SHA-256 over the canonical JSON of ``payload`` (64 lowercase hex).

    Raises :class:`ValueError` when the payload contains non-finite
    floats and :class:`TypeError` when it is not JSON-serializable.
    """
    return sha256_hex(canonical_json(payload))


__all__ = ["canonical_json", "fingerprint", "sha256_hex"]
