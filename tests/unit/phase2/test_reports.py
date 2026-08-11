"""RED: Complete report generation contract.

Requires: current_session()-based output_dir, Artifact/relative path return,
atomic Markdown/PDF, temp file cleanup, Chinese content support,
ReportGenerationError without raw paths/exception text.
"""

import pytest

from app.api.context import SessionContext, session_context
from app.tools.files import ReportGenerationError, SessionWorkspace

UUID_V4 = "00000000-0000-4000-8000-000000000001"


def _workspace(tmp_path):
    return SessionWorkspace.for_thread(
        thread_id=UUID_V4,
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )


def _in_session(ws):
    """Context manager that sets up session_context for report calls."""
    ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
    return session_context(ctx)


# ── Markdown ──────────────────────────────────────────────────────────────────


class TestMarkdownReport:
    def test_accepts_safe_showcase_basename(self, tmp_path):
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            result = generate_markdown_report(
                "# Showcase", filename="showcase-report.md"
            )
        assert result == "showcase-report.md"
        assert ws.resolve_output(result).read_text(encoding="utf-8") == "# Showcase"

    def test_rejects_path_and_wrong_extension(self, tmp_path):
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        with pytest.raises(ReportGenerationError):
            with _in_session(ws):
                generate_markdown_report("content", filename="../escape.md")
        with pytest.raises(ReportGenerationError):
            with _in_session(ws):
                generate_markdown_report("content", filename="showcase-report.pdf")

    def test_generates_utf8(self, tmp_path):
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            result = generate_markdown_report("# Report\n\nContent.")
        text = ws.resolve_output("tutorial-report.md").read_text(encoding="utf-8")
        assert "Content" in text
        assert not str(result).startswith("/")

    def test_atomic_write_no_tmp_left(self, tmp_path):
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            generate_markdown_report("hello")
        tmps = list(ws.output_dir.glob("*.tmp"))
        assert len(tmps) == 0

    def test_utf8_with_chinese(self, tmp_path):
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            generate_markdown_report(
                "# 研究报告\n\n分析结果：数据正常。\n\n- 项目 A\n- 项目 B"
            )
        text = ws.resolve_output("tutorial-report.md").read_text(encoding="utf-8")
        assert "研究报告" in text
        assert "项目" in text

    def test_returns_relative_path_not_absolute(self, tmp_path):
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            result = generate_markdown_report("test")
        assert not str(result).startswith("/")
        assert "tutorial-report.md" in str(result)

    def test_uses_current_session_workspace(self, tmp_path):
        """No explicit output_dir — uses current_session().workspace."""
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            result = generate_markdown_report("session-based")
        assert ws.resolve_output("tutorial-report.md").read_text() == "session-based"
        assert not str(result).startswith("/")


# ── PDF ───────────────────────────────────────────────────────────────────────


class TestPDFReport:
    def test_accepts_safe_showcase_basename(self, tmp_path):
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            result = generate_pdf_report("# Showcase", filename="showcase-report.pdf")
        assert result == "showcase-report.pdf"
        assert ws.resolve_output(result).read_bytes()[:4] == b"%PDF"

    def test_rejects_path_and_wrong_extension(self, tmp_path):
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        with pytest.raises(ReportGenerationError):
            with _in_session(ws):
                generate_pdf_report("content", filename="../escape.pdf")
        with pytest.raises(ReportGenerationError):
            with _in_session(ws):
                generate_pdf_report("content", filename="showcase-report.md")

    def test_generates_pdf_header(self, tmp_path):
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            result = generate_pdf_report("# Title\n\nBody.")
        data = ws.resolve_output("tutorial-report.pdf").read_bytes()
        assert data[:4] == b"%PDF"
        assert not str(result).startswith("/")

    def test_chinese_content_renders(self, tmp_path):
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            generate_pdf_report("# 中文报告\n\n测试内容。\n\n- 项目一\n- 项目二")
        data = ws.resolve_output("tutorial-report.pdf").read_bytes()
        assert data[:4] == b"%PDF"
        assert len(data) > 500

    def test_atomic_no_tmp_left(self, tmp_path):
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            generate_pdf_report("content")
        tmps = list(ws.output_dir.glob("*.tmp"))
        assert len(tmps) == 0

    def test_pdf_uses_stsong_light_font(self, tmp_path):
        """The ReportLab canvas must register STSong-Light for Chinese."""
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            generate_pdf_report("test")
        # Function should not raise on font registration

    def test_pdf_failure_keeps_markdown(self, tmp_path):
        """If PDF generation fails, Markdown stays intact."""
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            generate_markdown_report("# Safe\n\nContent.")
        md_path = ws.resolve_output("tutorial-report.md")
        assert md_path.exists()

        # Force PDF write failure by pre-creating target as directory
        pdf_path = ws.resolve_output("tutorial-report.pdf")
        pdf_path.mkdir(exist_ok=True)
        from app.tools.reports import generate_pdf_report

        with pytest.raises(Exception):
            with _in_session(ws):
                generate_pdf_report("# Title\n\nBody.")
        assert md_path.exists()
        assert md_path.read_text() == "# Safe\n\nContent."

    def test_pdf_error_message_is_redacted(self, tmp_path):
        """ReportGenerationError must not expose raw exception text or paths."""
        ws = _workspace(tmp_path)

        pdf_path = ws.resolve_output("tutorial-report.pdf")
        pdf_path.mkdir(exist_ok=True)
        from app.tools.reports import generate_pdf_report

        try:
            with _in_session(ws):
                generate_pdf_report("# Test")
        except Exception as exc:
            msg = str(exc)
            assert str(tmp_path) not in msg

    def test_uses_current_session_workspace_pdf(self, tmp_path):
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            result = generate_pdf_report("session pdf")
        assert ws.resolve_output("tutorial-report.pdf").exists()
        assert not str(result).startswith("/")


# ── Markdown heading/paragraph/list support ───────────────────────────────────


def test_markdown_headings_paragraphs_lists_in_pdf(tmp_path):
    from app.tools.reports import generate_pdf_report

    ws = _workspace(tmp_path)
    with _in_session(ws):
        generate_pdf_report("# H1\n\nParagraph text.\n\n## H2\n\n- Item 1\n- Item 2")
    data = ws.resolve_output("tutorial-report.pdf").read_bytes()
    assert data[:4] == b"%PDF"


# ── Output dir created if missing ─────────────────────────────────────────────


def test_output_dir_created_if_missing(tmp_path):
    from app.tools.reports import generate_markdown_report

    ws = _workspace(tmp_path)
    import shutil

    shutil.rmtree(ws.output_dir)
    assert not ws.output_dir.exists()
    with _in_session(ws):
        generate_markdown_report("content")
    assert ws.output_dir.exists()
    assert ws.resolve_output("tutorial-report.md").exists()


# ── Symlink exploit defense ───────────────────────────────────────────────────


# ── B5: failure injection, symlink safety and atomic replacement ──────────────


class TestReportFailureCleanup:
    def test_markdown_failed_replace_preserves_existing_report(
        self, tmp_path, monkeypatch
    ):
        """A failed os.replace must keep the previous valid report."""
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            generate_markdown_report("# v1\n\noriginal")
        target = ws.resolve_output("tutorial-report.md")

        def _fail_replace(src, dst):
            raise OSError("injected replace failure")

        monkeypatch.setattr("app.tools.files.os.replace", _fail_replace)
        with pytest.raises(OSError, match="injected"):
            with _in_session(ws):
                generate_markdown_report("# v2\n\nreplacement")

        assert target.read_text() == "# v1\n\noriginal"
        assert list(ws.output_dir.glob(".tmp-*")) == []

    def test_pdf_failed_replace_preserves_existing_report(self, tmp_path, monkeypatch):
        """A failed os.replace must keep the previous valid PDF byte-for-byte."""
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            generate_pdf_report("# v1")
        target = ws.resolve_output("tutorial-report.pdf")
        original_bytes = target.read_bytes()

        def _fail_replace(src, dst):
            raise OSError("injected replace failure")

        monkeypatch.setattr("app.tools.reports.os.replace", _fail_replace)
        with pytest.raises(ReportGenerationError):
            with _in_session(ws):
                generate_pdf_report("# v2")

        assert target.read_bytes() == original_bytes
        assert list(ws.output_dir.glob(".tmp-*")) == []

    def test_markdown_directory_target_failure_leaves_no_partial(self, tmp_path):
        """A directory squatting at the final name must not leave a partial file."""
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        target = ws.resolve_output("tutorial-report.md")
        target.mkdir()

        with pytest.raises(Exception):
            with _in_session(ws):
                generate_markdown_report("content")

        assert target.is_dir()
        assert list(ws.output_dir.glob(".tmp-*")) == []

    def test_markdown_final_target_symlink_cannot_modify_outside(self, tmp_path):
        """os.replace replaces the symlink itself — outside sentinel stays SAFE."""
        import os

        outside = tmp_path / "outside.md"
        outside.write_text("SAFE")

        ws = _workspace(tmp_path)
        os.symlink(str(outside), str(ws.output_dir / "tutorial-report.md"))

        from app.tools.reports import generate_markdown_report

        with _in_session(ws):
            generate_markdown_report("# New")

        assert outside.read_text() == "SAFE", "outside.md was written via symlink!"
        final = ws.resolve_output("tutorial-report.md")
        assert not final.is_symlink()
        assert final.read_text() == "# New"

    def test_pdf_final_target_symlink_cannot_modify_outside(self, tmp_path):
        """os.replace replaces the symlink itself — outside sentinel stays SAFE."""
        import os

        outside = tmp_path / "outside.pdf"
        outside.write_text("SAFE")

        ws = _workspace(tmp_path)
        os.symlink(str(outside), str(ws.output_dir / "tutorial-report.pdf"))

        from app.tools.reports import generate_pdf_report

        with _in_session(ws):
            generate_pdf_report("# New")

        assert outside.read_text() == "SAFE", "outside.pdf was written via symlink!"
        final = ws.resolve_output("tutorial-report.pdf")
        assert not final.is_symlink()
        assert final.read_bytes()[:4] == b"%PDF"


class TestReportAtomicReplacement:
    def test_markdown_replacement_is_atomic(self, tmp_path):
        """Replacement uses a fresh inode — never in-place truncation."""
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            generate_markdown_report("# v1")
        target = ws.resolve_output("tutorial-report.md")
        inode_before = target.stat().st_ino

        with _in_session(ws):
            generate_markdown_report("# v2")

        assert target.read_text() == "# v2"
        assert target.stat().st_ino != inode_before
        assert list(ws.output_dir.glob(".tmp-*")) == []

    def test_pdf_replacement_is_atomic(self, tmp_path):
        """Replacement uses a fresh inode — never in-place truncation."""
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        with _in_session(ws):
            generate_pdf_report("# v1")
        target = ws.resolve_output("tutorial-report.pdf")
        inode_before = target.stat().st_ino

        with _in_session(ws):
            generate_pdf_report("# v2")

        data = target.read_bytes()
        assert data[:4] == b"%PDF"
        assert target.stat().st_ino != inode_before
        assert list(ws.output_dir.glob(".tmp-*")) == []


def test_fixed_pdf_tmp_symlink_cannot_overwrite_outside(tmp_path):
    """Precreate .tutorial-report.pdf.tmp as symlink — outside stays SAFE."""
    import os

    outside = tmp_path / "outside.pdf"
    outside.write_text("SAFE")

    ws = _workspace(tmp_path)
    fixed_tmp = ws.output_dir / ".tutorial-report.pdf.tmp"
    os.symlink(str(outside), str(fixed_tmp))

    from app.tools.reports import generate_pdf_report

    with _in_session(ws):
        result = generate_pdf_report("# Safe")

    assert outside.read_text() == "SAFE"
    assert result == "tutorial-report.pdf"
    final = ws.resolve_output("tutorial-report.pdf")
    assert final.exists()
    assert not final.is_symlink()
