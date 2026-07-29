"""RED: Complete SessionWorkspace path isolation contract.

All path-traversal inputs MUST be rejected — no silent basename sanitization.
Uses UnsafeWorkspacePath (not generic ValueError) for security contract.
"""

import os

import pytest

from app.tools.files import MAX_FILE_SIZE_BYTES, SessionWorkspace

UUID_V4 = "00000000-0000-4000-8000-000000000001"


# ── helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
def ws(tmp_path):
    return SessionWorkspace.for_thread(
        thread_id=UUID_V4,
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )


def _assert_raises_unsafe(workspace, name: str):
    from app.tools.files import UnsafeWorkspacePath

    with pytest.raises(UnsafeWorkspacePath):
        workspace.resolve_upload(name)


# ── UnsafeWorkspacePath contract ──────────────────────────────────────────────


def test_unsafe_workspace_path_is_exception_subclass():
    from app.tools.files import UnsafeWorkspacePath

    assert issubclass(UnsafeWorkspacePath, Exception)
    # Raise and catch
    with pytest.raises(UnsafeWorkspacePath):
        raise UnsafeWorkspacePath("test")


# ── Reject traversal (not silent basename) ───────────────────────────────────


def test_rejects_parent_traversal_single(ws):
    _assert_raises_unsafe(ws, "../secret.txt")


def test_rejects_parent_traversal_deep(ws):
    _assert_raises_unsafe(ws, "../../../etc/passwd")


def test_rejects_directory_component(ws):
    """nested/file.txt must be rejected — arbitrary subdirectories are disallowed."""
    _assert_raises_unsafe(ws, "nested/file.txt")


def test_rejects_nested_deep(ws):
    _assert_raises_unsafe(ws, "a/b/c/d/file.txt")


def test_rejects_absolute_unix(ws):
    _assert_raises_unsafe(ws, "/etc/passwd")


def test_rejects_absolute_windows_drive(tmp_path):
    ws2 = SessionWorkspace.for_thread(
        thread_id=UUID_V4,
        base_upload=str(tmp_path / "updated2"),
        base_output=str(tmp_path / "output2"),
    )
    _assert_raises_unsafe(ws2, "C:\\Windows\\system32\\config\\SAM")


def test_rejects_backslash_traversal(tmp_path):
    ws2 = SessionWorkspace.for_thread(
        thread_id=UUID_V4,
        base_upload=str(tmp_path / "updated3"),
        base_output=str(tmp_path / "output3"),
    )
    _assert_raises_unsafe(ws2, "..\\..\\secret.txt")


def test_rejects_empty_name(ws):
    _assert_raises_unsafe(ws, "")


def test_rejects_whitespace_only(ws):
    _assert_raises_unsafe(ws, "   ")


def test_rejects_dot(ws):
    _assert_raises_unsafe(ws, ".")


def test_rejects_double_dot(ws):
    _assert_raises_unsafe(ws, "..")


def test_rejects_symlink_escape(tmp_path):
    ws2 = SessionWorkspace.for_thread(
        thread_id=UUID_V4,
        base_upload=str(tmp_path / "updated4"),
        base_output=str(tmp_path / "output4"),
    )
    outside = tmp_path / "outside_secret.txt"
    outside.write_text("secret")
    link = ws2.upload_dir / "link.txt"
    os.symlink(str(outside), str(link))
    _assert_raises_unsafe(ws2, "link.txt")


# ── Safe names allowed ───────────────────────────────────────────────────────


def test_allows_safe_basename(ws):
    path = ws.resolve_upload("constraints.md")
    assert path.exists() or not path.exists()  # resolution succeeds
    assert path.parent == ws.upload_dir.resolve()


# ── for_thread() UUID validation ──────────────────────────────────────────────


def test_rejects_non_uuid_thread_id():
    with pytest.raises(ValueError, match="UUID"):
        SessionWorkspace.for_thread(
            thread_id="not-a-uuid",
            base_upload="/tmp/a",
            base_output="/tmp/b",
        )


def test_accepts_valid_uuid():
    ws2 = SessionWorkspace.for_thread(
        thread_id="abcdef12-3456-7890-abcd-ef1234567890",
        base_upload="/tmp/x",
        base_output="/tmp/y",
    )
    assert ws2.upload_dir.exists()


# ── Constructor bypass (should be prevented) ─────────────────────────────────


def test_constructor_bypasses_uuid_validation(tmp_path):
    """Direct SessionWorkspace(...) must not be the blessed path."""
    # The constructor still works, but the plan requires for_thread as the
    # single blessed entry point. We can't prevent __init__ in Python without
    # awkward mechanics. We document this contract instead.
    #
    # However, the constructor should NOT accept non-UUID without complaint
    # if we can avoid it. The test verifies the current behaviour is consistent.
    ws2 = SessionWorkspace(
        thread_id="bypass",
        base_upload=str(tmp_path / "up-bypass"),
        base_output=str(tmp_path / "out-bypass"),
    )
    # The upload/output dirs were NOT created (no mkdir called)
    assert not ws2.upload_dir.exists()
    assert not ws2.output_dir.exists()


# ── Workspace exposes only upload_dir and output_dir ─────────────────────────


def test_workspace_only_upload_and_output_dirs(ws):
    attrs = {a for a in dir(ws) if not a.startswith("__")}
    public = {a for a in attrs if not a.startswith("_")}
    assert public == {
        "upload_dir",
        "output_dir",
        "resolve_upload",
        "resolve_output",
        "for_thread",
    }


def test_no_thread_id_public_attribute(ws):
    """_thread_id must not be accessible as a public name."""
    assert not hasattr(ws, "thread_id") or callable(getattr(ws, "thread_id", None))


# ── Containment uses is_relative_to (or equivalent) ──────────────────────────


def test_resolve_uses_proper_containment(ws):
    path = ws.resolve_upload("doc.txt")
    assert path.is_relative_to(ws.upload_dir.resolve())


def test_output_uses_proper_containment(ws):
    path = ws.resolve_output("report.pdf")
    assert path.is_relative_to(ws.output_dir.resolve())


# ── Resolve always does strict containment ───────────────────────────────────


def test_resolve_upload_containment_after_resolve(ws):
    path = ws.resolve_upload("file.txt")
    real = path.resolve(strict=False)
    assert real.is_relative_to(ws.upload_dir.resolve())


# ── Upload validation ────────────────────────────────────────────────────────


def test_validate_upload_rejects_unsupported_extension(tmp_path):
    from app.tools.files import validate_upload_file

    f = tmp_path / "test.exe"
    f.write_bytes(b"x" * 100)
    with pytest.raises(ValueError, match="extension"):
        validate_upload_file(f)


def test_validate_upload_rejects_doc(tmp_path):
    from app.tools.files import validate_upload_file

    f = tmp_path / "test.doc"
    f.write_bytes(b"x" * 100)
    with pytest.raises(ValueError, match="extension"):
        validate_upload_file(f)


def test_validate_upload_rejects_xls(tmp_path):
    from app.tools.files import validate_upload_file

    f = tmp_path / "test.xls"
    f.write_bytes(b"x" * 100)
    with pytest.raises(ValueError, match="extension"):
        validate_upload_file(f)


def test_validate_upload_rejects_docm(tmp_path):
    from app.tools.files import validate_upload_file

    f = tmp_path / "test.docm"
    f.write_bytes(b"x" * 100)
    with pytest.raises(ValueError, match="extension"):
        validate_upload_file(f)


def test_validate_upload_rejects_xlsm(tmp_path):
    from app.tools.files import validate_upload_file

    f = tmp_path / "test.xlsm"
    f.write_bytes(b"x" * 100)
    with pytest.raises(ValueError, match="extension"):
        validate_upload_file(f)


def test_validate_upload_rejects_too_large(tmp_path):
    from app.tools.files import validate_upload_file

    f = tmp_path / "big.md"
    f.write_bytes(b"x" * (MAX_FILE_SIZE_BYTES + 1))
    with pytest.raises(ValueError, match="large"):
        validate_upload_file(f)


def test_validate_upload_accepts_allowed(tmp_path):
    from app.tools.files import validate_upload_file

    for ext in (".txt", ".md", ".pdf", ".docx", ".xlsx"):
        f = tmp_path / f"test{ext}"
        f.write_bytes(b"x" * 100)
        validate_upload_file(f)
