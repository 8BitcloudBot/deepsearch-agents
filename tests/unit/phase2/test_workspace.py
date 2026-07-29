"""Tests for SessionWorkspace path isolation."""

import pytest

from app.tools.files import SessionWorkspace


class TestSessionWorkspace:
    def test_for_thread_creates_dirs(self, tmp_path):
        ws = SessionWorkspace.for_thread(
            thread_id="00000000-0000-4000-8000-000000000001",
            base_upload=str(tmp_path / "updated"),
            base_output=str(tmp_path / "output"),
        )
        assert ws.upload_dir.exists()
        assert ws.output_dir.exists()

    def test_resolve_upload_sanitizes_basename(self, tmp_path):
        ws = SessionWorkspace.for_thread(
            thread_id="00000000-0000-4000-8000-000000000001",
            base_upload=str(tmp_path / "updated"),
            base_output=str(tmp_path / "output"),
        )
        path = ws.resolve_upload("../../../etc/passwd")
        assert "/etc/passwd" not in str(path)
        assert str(path).startswith(str(ws.upload_dir))

    def test_resolve_upload_rejects_empty_name(self, tmp_path):
        ws = SessionWorkspace.for_thread(
            thread_id="00000000-0000-4000-8000-000000000001",
            base_upload=str(tmp_path / "updated"),
            base_output=str(tmp_path / "output"),
        )
        with pytest.raises(ValueError):
            ws.resolve_upload("")

    def test_resolve_upload_rejects_absolute_path(self, tmp_path):
        ws = SessionWorkspace.for_thread(
            thread_id="00000000-0000-4000-8000-000000000001",
            base_upload=str(tmp_path / "updated"),
            base_output=str(tmp_path / "output"),
        )
        with pytest.raises(ValueError):
            ws.resolve_upload("/etc/passwd")

    def test_resolve_upload_rejects_symlink_escape(self, tmp_path):
        import os

        ws = SessionWorkspace.for_thread(
            thread_id="00000000-0000-4000-8000-000000000001",
            base_upload=str(tmp_path / "updated"),
            base_output=str(tmp_path / "output"),
        )
        # Create a symlink inside upload dir pointing outside
        outside = tmp_path / "outside.txt"
        outside.write_text("secret")
        link = ws.upload_dir / "link.txt"
        os.symlink(str(outside), str(link))
        with pytest.raises(ValueError):
            ws.resolve_upload("link.txt")

    def test_resolve_output_rejects_escape(self, tmp_path):
        ws = SessionWorkspace.for_thread(
            thread_id="00000000-0000-4000-8000-000000000001",
            base_upload=str(tmp_path / "updated"),
            base_output=str(tmp_path / "output"),
        )
        with pytest.raises(ValueError):
            ws.resolve_output("../outside.txt")

    def test_output_path_is_relative(self, tmp_path):
        ws = SessionWorkspace.for_thread(
            thread_id="00000000-0000-4000-8000-000000000001",
            base_upload=str(tmp_path / "updated"),
            base_output=str(tmp_path / "output"),
        )
        path = ws.resolve_output("tutorial-report.md")
        assert not path.is_absolute()
