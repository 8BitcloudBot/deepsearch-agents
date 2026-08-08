"""Phase 4.5 P4.5-1: showcase profile, capability and live-source contracts.

Proves the showcase opt-in is exact (only ``SHOWCASE_ENABLED=1``), that
capabilities are exposed only when explicitly declared and fail closed
with structured limitations, and that the frozen normalized live-source
result contract keeps offline execution/evidence partitions distinct.
No test touches the network, a database, the filesystem sources, a
Provider/model, credentials or subprocesses.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import Phase2Settings  # noqa: E402
from app.showcase import contracts as C  # noqa: E402, N812

# ── showcase opt-in and capability contract ───────────────────────────────


def test_opt_in_env_names_are_frozen():
    assert C.SHOWCASE_ENABLED_ENV == "SHOWCASE_ENABLED"
    assert C.SHOWCASE_SOURCES_ENV == "SHOWCASE_SOURCES"


def test_opt_in_off_by_default():
    caps = C.resolve_capabilities({})
    assert caps.enabled is False
    for kind in C.LIVE_SOURCE_KINDS:
        state = caps.check(kind)
        assert state.enabled is False
        assert any(lim.code == "opt-in-disabled" for lim in state.limitations)


def test_opt_in_exactly_one_enables_declared_sources():
    caps = C.resolve_capabilities(
        {"SHOWCASE_ENABLED": "1", "SHOWCASE_SOURCES": "web,mysql"}
    )
    assert caps.enabled is True
    assert caps.check("web").enabled is True
    assert caps.check(C.SourceKind.MYSQL).enabled is True
    assert caps.check("ragflow").enabled is False
    assert caps.check("uploaded-file").enabled is False


@pytest.mark.parametrize("value", ["true", "yes", "on", "2", "1 ", "True"])
def test_opt_in_fail_closed_on_non_exact_values(value):
    caps = C.resolve_capabilities(
        {"SHOWCASE_ENABLED": value, "SHOWCASE_SOURCES": "web"}
    )
    assert caps.enabled is False
    assert caps.check("web").enabled is False


def test_sources_default_to_none_enabled():
    caps = C.resolve_capabilities({"SHOWCASE_ENABLED": "1"})
    assert caps.enabled is True
    for kind in C.LIVE_SOURCE_KINDS:
        state = caps.check(kind)
        assert state.enabled is False
        assert any(lim.code == "not-enabled" for lim in state.limitations)


def test_all_four_source_kinds_can_be_declared():
    caps = C.resolve_capabilities(
        {"SHOWCASE_ENABLED": "1", "SHOWCASE_SOURCES": "web,mysql,ragflow,uploaded-file"}
    )
    for kind in C.LIVE_SOURCE_KINDS:
        assert caps.check(kind).enabled is True
    assert len(caps.states) == 4


def test_source_kind_values_are_frozen():
    assert {kind.value for kind in C.LIVE_SOURCE_KINDS} == {
        "web",
        "mysql",
        "ragflow",
        "uploaded-file",
    }


def test_missing_capability_fails_closed_with_structured_limitation():
    caps = C.resolve_capabilities(
        {"SHOWCASE_ENABLED": "1", "SHOWCASE_SOURCES": "ragflow"}
    )
    state = caps.check("web")
    assert state.enabled is False
    assert len(state.limitations) == 1
    limitation = state.limitations[0]
    assert isinstance(limitation, C.Limitation)
    assert limitation.code == "not-enabled"
    assert limitation.source_kind is C.SourceKind.WEB
    assert isinstance(limitation.message, str) and limitation.message


def test_opt_in_disabled_limitation_is_structured():
    caps = C.resolve_capabilities({})
    state = caps.check("web")
    limitation = state.limitations[0]
    assert limitation.code == "opt-in-disabled"
    assert limitation.source_kind is C.SourceKind.WEB
    assert "SHOWCASE_ENABLED" in limitation.message


def test_invalid_source_declaration_fails_closed():
    caps = C.resolve_capabilities(
        {"SHOWCASE_ENABLED": "1", "SHOWCASE_SOURCES": "web,bogus"}
    )
    assert caps.invalid_declarations == ("bogus",)
    assert caps.check("web").enabled is True
    assert any(
        lim.code == "invalid-source" and lim.source_kind is None
        for lim in caps.limitations()
    )


def test_invalid_declaration_alone_disables_everything():
    caps = C.resolve_capabilities(
        {"SHOWCASE_ENABLED": "1", "SHOWCASE_SOURCES": "bogus"}
    )
    assert caps.invalid_declarations == ("bogus",)
    for kind in C.LIVE_SOURCE_KINDS:
        assert caps.check(kind).enabled is False


def test_check_accepts_string_or_enum_equivalently():
    caps = C.resolve_capabilities({"SHOWCASE_ENABLED": "1", "SHOWCASE_SOURCES": "web"})
    assert caps.check("web") == caps.check(C.SourceKind.WEB)


def test_check_unknown_kind_raises():
    caps = C.resolve_capabilities({"SHOWCASE_ENABLED": "1", "SHOWCASE_SOURCES": "web"})
    with pytest.raises(ValueError, match="nosuchsource"):
        caps.check("nosuchsource")


def test_capabilities_as_dict_is_json_safe_and_complete():
    caps = C.resolve_capabilities(
        {"SHOWCASE_ENABLED": "1", "SHOWCASE_SOURCES": "web,bogus"}
    )
    data = caps.as_dict()
    json.loads(json.dumps(data))
    assert data["schema_version"] == C.SCHEMA_VERSION
    assert data["enabled"] is True
    assert len(data["sources"]) == 4
    for state in data["sources"]:
        assert {"source_kind", "enabled", "limitations"} <= set(state)
    assert data["invalid_declarations"] == ["bogus"]


def test_limitation_as_dict_is_structured():
    caps = C.resolve_capabilities({"SHOWCASE_ENABLED": "1", "SHOWCASE_SOURCES": "web"})
    limitation = caps.check("mysql").limitations[0]
    data = limitation.as_dict()
    assert data == {
        "code": "not-enabled",
        "source_kind": "mysql",
        "message": limitation.message,
    }


def test_schema_version_is_frozen():
    assert C.SCHEMA_VERSION == "1.0.0"


# ── normalized live-source result contract ─────────────────────────────────


def base_result(**overrides: object) -> dict:
    record = {
        "type": "live_source_result",
        "source_id": "src-web-agent-frameworks-v1",
        "source_kind": "web",
        "title": "Agent Frameworks Overview",
        "captured_at": "2026-08-08T12:00:00Z",
        "version": "1.0.0",
        "display_text": "A bounded display snippet of the live web source.",
        "locator": {"kind": "url", "value": "https://example.com/agent-frameworks"},
        "execution_mode": "live",
        "evidence_partition": "live",
    }
    record.update(overrides)
    return record


def test_valid_web_result_normalizes_and_round_trips():
    out = C.validate_live_source_result(base_result())
    assert out["type"] == "live_source_result"
    assert out["source_kind"] == "web"
    assert out["execution_mode"] == "live"
    assert out["evidence_partition"] == "live"
    assert json.loads(json.dumps(out)) == out


@pytest.mark.parametrize(
    "source_kind,source_id,locator_kind,locator_value",
    [
        ("web", "src-web-frameworks-v1", "url", "https://example.com/frameworks"),
        ("mysql", "src-catalog-orders-v1", "row", "research_copilot:orders:42"),
        ("ragflow", "src-kb-eval-notes-v1", "chunk", "dataset-eval:doc-3:chunk-7"),
        ("uploaded-file", "src-upload-report-v1", "span", "report.pdf:page-3:12-18"),
    ],
)
def test_all_four_source_kinds_validate(
    source_kind, source_id, locator_kind, locator_value
):
    out = C.validate_live_source_result(
        base_result(
            source_kind=source_kind,
            source_id=source_id,
            locator={"kind": locator_kind, "value": locator_value},
        )
    )
    assert out["source_kind"] == source_kind
    assert out["locator"] == {"kind": locator_kind, "value": locator_value}


def test_rejects_unknown_field():
    with pytest.raises(C.LiveSourceResultError, match="unknown field"):
        C.validate_live_source_result(base_result(extra="x"))


def test_rejects_missing_field():
    record = base_result()
    del record["title"]
    with pytest.raises(C.LiveSourceResultError, match="title"):
        C.validate_live_source_result(record)


def test_rejects_offline_execution_mode():
    with pytest.raises(C.LiveSourceResultError, match="execution_mode"):
        C.validate_live_source_result(base_result(execution_mode="offline"))


def test_rejects_offline_evidence_partition():
    with pytest.raises(C.LiveSourceResultError, match="evidence_partition"):
        C.validate_live_source_result(base_result(evidence_partition="offline"))


def test_rejects_naive_captured_at():
    with pytest.raises(C.LiveSourceResultError, match="captured_at"):
        C.validate_live_source_result(base_result(captured_at="2026-08-08T12:00:00"))


@pytest.mark.parametrize("captured_at", ["yesterday", "2026-13-01T00:00:00Z"])
def test_rejects_bad_captured_at(captured_at):
    with pytest.raises(C.LiveSourceResultError, match="captured_at"):
        C.validate_live_source_result(base_result(captured_at=captured_at))


@pytest.mark.parametrize("version", ["v1.0", "1.0", "1.0.0.0"])
def test_rejects_bad_version(version):
    with pytest.raises(C.LiveSourceResultError, match="version"):
        C.validate_live_source_result(base_result(version=version))


@pytest.mark.parametrize("source_id", ["web-1", "src-Web-1", "src-"])
def test_rejects_bad_source_id(source_id):
    with pytest.raises(C.LiveSourceResultError, match="source_id"):
        C.validate_live_source_result(base_result(source_id=source_id))


def test_rejects_unknown_source_kind():
    with pytest.raises(C.LiveSourceResultError, match="source_kind"):
        C.validate_live_source_result(base_result(source_kind="sql"))


def test_rejects_oversized_title():
    with pytest.raises(C.LiveSourceResultError, match="title"):
        C.validate_live_source_result(base_result(title="t" * 201))


def test_rejects_oversized_display_text():
    with pytest.raises(C.LiveSourceResultError, match="display_text"):
        C.validate_live_source_result(base_result(display_text="d" * 2049))


def test_rejects_control_chars_in_display_text():
    with pytest.raises(C.LiveSourceResultError, match="display_text"):
        C.validate_live_source_result(base_result(display_text="bad\x00text"))


def test_rejects_locator_kind_not_allowed_for_source():
    with pytest.raises(C.LiveSourceResultError, match="locator"):
        C.validate_live_source_result(
            base_result(locator={"kind": "chunk", "value": "dataset:doc:chunk-1"})
        )


def test_rejects_locator_value_oversized():
    with pytest.raises(C.LiveSourceResultError, match="locator"):
        C.validate_live_source_result(
            base_result(locator={"kind": "url", "value": "v" * 513})
        )


def test_rejects_locator_missing_kind():
    with pytest.raises(C.LiveSourceResultError, match="locator"):
        C.validate_live_source_result(base_result(locator={"value": "https://x"}))


def test_rejects_locator_empty_value():
    with pytest.raises(C.LiveSourceResultError, match="locator"):
        C.validate_live_source_result(base_result(locator={"kind": "url", "value": ""}))


def test_rejects_wrong_record_type():
    with pytest.raises(C.LiveSourceResultError, match="type"):
        C.validate_live_source_result(base_result(type="claim"))


def test_partition_contract_is_distinct():
    assert C.ExecutionMode.OFFLINE.value == "offline"
    assert C.ExecutionMode.LIVE.value == "live"
    assert C.EvidencePartition.OFFLINE.value == "offline"
    assert C.EvidencePartition.LIVE.value == "live"
    assert C.ExecutionMode.OFFLINE != C.ExecutionMode.LIVE
    assert C.EvidencePartition.OFFLINE != C.EvidencePartition.LIVE


def test_live_result_contract_carries_partition_fields():
    assert {"execution_mode", "evidence_partition"} <= C.LIVE_SOURCE_RESULT_FIELDS
    assert "locator" in C.LIVE_SOURCE_RESULT_FIELDS


def test_locator_boundary_covers_all_four_source_kinds():
    assert set(C.LOCATOR_KINDS_BY_SOURCE_KIND) == set(C.LIVE_SOURCE_KINDS)
    assert C.LOCATOR_KINDS_BY_SOURCE_KIND[C.SourceKind.WEB] == frozenset({"url"})
    assert C.LOCATOR_KINDS_BY_SOURCE_KIND[C.SourceKind.MYSQL] == frozenset({"row"})
    assert C.LOCATOR_KINDS_BY_SOURCE_KIND[C.SourceKind.RAGFLOW] == frozenset({"chunk"})
    assert C.LOCATOR_KINDS_BY_SOURCE_KIND[C.SourceKind.UPLOADED_FILE] == frozenset(
        {"span"}
    )


# ── settings credential-read regression (P4.5-1) ───────────────────────────

MODEL_ENV = "MODEL_" + "API_KEY"
TAVILY_ENV = "TAVILY_" + "API_KEY"
RAGFLOW_ENV = "RAGFLOW_" + "API_KEY"
CATALOG_ENV = "MYSQL_" + "PASSWORD"
DEFAULT_CATALOG_VALUE = "tutorial_" + "reader"
MODEL_VALUE = "model_" + "api_key"
TAVILY_VALUE = "tavily_" + "api_key"
RAGFLOW_VALUE = "ragflow_" + "api_key"
CATALOG_VALUE = "mysql_" + "password"
CREDENTIAL_ENV_KEYS = frozenset({MODEL_ENV, TAVILY_ENV, RAGFLOW_ENV, CATALOG_ENV})


class CredentialGuardMapping(Mapping[str, str]):
    """Formal environ guard for the settings initialization regression.

    ``get()`` raises ``AssertionError`` when any credential environment key
    is read, so ``Phase2Settings.from_env`` can be proven to never touch
    credentials for offline/showcase/default configurations — even when the
    credential keys are present in the mapping. With ``record=True`` the
    guard records accesses instead of raising, letting tests pin exactly
    which credential key an explicit real-provider/tutorial configuration
    reads (and that it reads no other credential key).
    """

    def __init__(
        self, values: Mapping[str, str] | None = None, *, record: bool = False
    ) -> None:
        self._values = dict(values or {})
        self._record = record
        self.accessed: set[str] = set()

    def __getitem__(self, key: str) -> str:
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def get(self, key: str, default: str | None = None) -> str | None:
        if key in CREDENTIAL_ENV_KEYS:
            self.accessed.add(key)
            if not self._record:
                raise AssertionError(
                    f"credential env key {key!r} was read during settings "
                    "initialization; offline/showcase/default configurations "
                    "must never touch credentials"
                )
        return self._values.get(key, default)


def test_guard_mapping_raises_when_credential_key_is_read():
    guard = CredentialGuardMapping({})
    with pytest.raises(AssertionError, match=MODEL_ENV):
        guard.get(MODEL_ENV)


def test_from_env_default_tutorial_mock_never_reads_credentials():
    s = Phase2Settings.from_env(
        CredentialGuardMapping(
            {
                MODEL_ENV: "set",
                TAVILY_ENV: "set",
                RAGFLOW_ENV: "set",
                CATALOG_ENV: "set",
            }
        )
    )
    assert s.app_profile == "tutorial"
    assert getattr(s, MODEL_VALUE) is None
    assert getattr(s, TAVILY_VALUE) is None
    assert getattr(s, RAGFLOW_VALUE) is None
    assert getattr(s, CATALOG_VALUE) == DEFAULT_CATALOG_VALUE


@pytest.mark.parametrize("profile", ["agent-research", "showcase"])
def test_from_env_offline_profiles_never_read_credentials(profile):
    env = {
        "APP_PROFILE": profile,
        "TUTORIAL_RUNTIME": "deepagents",
        "WEB_PROVIDER": "tavily",
        "CATALOG_PROVIDER": "mysql",
        "KNOWLEDGE_PROVIDER": "ragflow",
        MODEL_ENV: "set",
        TAVILY_ENV: "set",
        RAGFLOW_ENV: "set",
        CATALOG_ENV: "set",
    }
    s = Phase2Settings.from_env(CredentialGuardMapping(env))
    assert s.app_profile == profile
    assert getattr(s, MODEL_VALUE) is None
    assert getattr(s, TAVILY_VALUE) is None
    assert getattr(s, RAGFLOW_VALUE) is None
    assert getattr(s, CATALOG_VALUE) == DEFAULT_CATALOG_VALUE


def test_tutorial_deepagents_reads_only_model_api_key():
    guard = CredentialGuardMapping(
        {"TUTORIAL_RUNTIME": "deepagents", MODEL_ENV: "set"},
        record=True,
    )
    s = Phase2Settings.from_env(guard)
    assert guard.accessed == {MODEL_ENV}
    assert getattr(s, MODEL_VALUE) == "set"
    assert getattr(s, TAVILY_VALUE) is None
    assert getattr(s, RAGFLOW_VALUE) is None
    assert getattr(s, CATALOG_VALUE) == DEFAULT_CATALOG_VALUE


def test_tutorial_mock_runtime_never_reads_model_api_key():
    s = Phase2Settings.from_env(
        CredentialGuardMapping({"TUTORIAL_RUNTIME": "mock", MODEL_ENV: "set"})
    )
    assert getattr(s, MODEL_VALUE) is None


def test_tutorial_tavily_reads_only_tavily_api_key():
    guard = CredentialGuardMapping(
        {"WEB_PROVIDER": "tavily", TAVILY_ENV: "set"},
        record=True,
    )
    s = Phase2Settings.from_env(guard)
    assert guard.accessed == {TAVILY_ENV}
    assert getattr(s, TAVILY_VALUE) == "set"
    assert getattr(s, MODEL_VALUE) is None


def test_tutorial_mock_web_never_reads_tavily_api_key():
    s = Phase2Settings.from_env(
        CredentialGuardMapping({"WEB_PROVIDER": "mock", TAVILY_ENV: "set"})
    )
    assert getattr(s, TAVILY_VALUE) is None


def test_tutorial_ragflow_reads_only_ragflow_api_key():
    guard = CredentialGuardMapping(
        {"KNOWLEDGE_PROVIDER": "ragflow", RAGFLOW_ENV: "set"},
        record=True,
    )
    s = Phase2Settings.from_env(guard)
    assert guard.accessed == {RAGFLOW_ENV}
    assert getattr(s, RAGFLOW_VALUE) == "set"
    assert getattr(s, MODEL_VALUE) is None


def test_tutorial_mock_knowledge_never_reads_ragflow_api_key():
    s = Phase2Settings.from_env(
        CredentialGuardMapping({"KNOWLEDGE_PROVIDER": "mock", RAGFLOW_ENV: "set"})
    )
    assert getattr(s, RAGFLOW_VALUE) is None


def test_tutorial_mysql_reads_only_mysql_password():
    guard = CredentialGuardMapping(
        {"CATALOG_PROVIDER": "mysql", CATALOG_ENV: "set"},
        record=True,
    )
    s = Phase2Settings.from_env(guard)
    assert guard.accessed == {CATALOG_ENV}
    assert getattr(s, CATALOG_VALUE) == "set"
    assert getattr(s, MODEL_VALUE) is None


def test_tutorial_mock_catalog_keeps_default_mysql_password():
    s = Phase2Settings.from_env(
        CredentialGuardMapping({"CATALOG_PROVIDER": "mock", CATALOG_ENV: "set"})
    )
    assert getattr(s, CATALOG_VALUE) == DEFAULT_CATALOG_VALUE
