"""Unit: canonical SHA-256 fingerprint helpers (P3-6).

Covers the canonical-JSON contract that all run/input fingerprints are
built on: keys sorted recursively, compact separators, ASCII-safe
output over strict UTF-8, and hard rejection of ``NaN``/``Infinity`` so
a fingerprint can never encode a non-JSON float. Also pins the SHA-256
wrapper: 64 lowercase hex digits, stable across key order, distinct for
distinct payloads.
"""

import hashlib
import re
from dataclasses import dataclass

import pytest

from app.evaluation.fingerprint import canonical_json, fingerprint, sha256_hex


def test_canonical_json_sorts_keys_recursively():
    left = {"b": 1, "a": 2}
    right = {"a": 2, "b": 1}
    assert canonical_json(left) == canonical_json(right)
    assert canonical_json(left) == '{"a":2,"b":1}'

    nested = {"b": {"y": 1, "x": 2}, "a": 3}
    assert canonical_json(nested) == '{"a":3,"b":{"x":2,"y":1}}'


def test_canonical_json_is_compact_and_ascii_safe():
    # ensure_ascii escapes non-ASCII so the canonical bytes are pure
    # ASCII regardless of source encoding — deterministic across hosts.
    text = canonical_json({"msg": "café 中文"})
    assert text == '{"msg":"caf\\u00e9 \\u4e2d\\u6587"}'
    # Strict UTF-8 round-trip: the canonical text re-encodes losslessly.
    assert text.encode("utf-8").decode("utf-8") == text


@pytest.mark.parametrize(
    "bad",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "inf", "neg-inf"],
)
def test_canonical_json_rejects_non_finite_floats(bad):
    with pytest.raises(ValueError):
        canonical_json({"value": bad})


def test_canonical_json_rejects_nested_non_finite_floats():
    with pytest.raises(ValueError):
        canonical_json({"outer": {"inner": [1.0, float("inf")]}})


def test_sha256_hex_matches_hashlib():
    assert sha256_hex(b"abc") == hashlib.sha256(b"abc").hexdigest()
    assert sha256_hex("abc") == hashlib.sha256(b"abc").hexdigest()
    assert sha256_hex("café") == hashlib.sha256("café".encode()).hexdigest()


def test_fingerprint_is_64_hex_sha256():
    digest = fingerprint({"a": 1})
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert digest == sha256_hex(canonical_json({"a": 1}))


def test_fingerprint_is_stable_across_key_order():
    payload = {"dataset_id": "seed-10-v1", "nested": {"b": 2, "a": 1}, "z": None}
    reordered = dict(reversed(list(payload.items())))
    assert fingerprint(payload) == fingerprint(reordered)


def test_fingerprint_is_distinct_for_distinct_payloads():
    base = {"dataset_id": "seed-10-v1", "git_dirty": False}
    assert fingerprint(base) != fingerprint({**base, "git_dirty": True})
    assert fingerprint(base) != fingerprint({**base, "dataset_id": "dev-40-v1"})


def test_fingerprint_accepts_json_lists_and_leaf_values():
    # Canonical JSON helpers are generic over JSON values, not only dicts.
    assert fingerprint([1, 2, {"b": 1, "a": 2}]) == fingerprint(
        [1, 2, {"a": 2, "b": 1}]
    )
    assert fingerprint("leaf") == sha256_hex('"leaf"')
    assert isinstance(fingerprint(None), str)
    assert len(fingerprint(None)) == 64


def test_fingerprint_is_deterministic_across_instances():
    payload = {
        "strategy_id": "s0-single-agent",
        "prompt_sha256": "ab" * 32,
        "git_dirty": True,
    }
    assert fingerprint(payload) == fingerprint(dict(payload))


def test_fingerprint_binds_unicode_content_stably():
    payload = {"question": "什么是 AI Agent？", "score": 0.5}
    first = fingerprint(payload)
    rebuilt = {"question": "什么是 AI Agent？", "score": 0.5}
    assert fingerprint(rebuilt) == first
    assert fingerprint({"score": 0.5, "question": "什么是 AI Agent？"}) == first


def test_canonical_json_rejects_non_json_serializable_payload():
    @dataclass
    class NotJson:
        value: int

    with pytest.raises(TypeError):
        canonical_json({"bad": NotJson(1)})
