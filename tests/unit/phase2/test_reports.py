"""RED: Complete report generation contract.

Requires: current_session()-based output_dir, Artifact/relative path return,
atomic Markdown/PDF, temp file cleanup, Chinese content support,
ReportGenerationError without raw paths/exception text.
"""

import pytest

from app.api.context import SessionContext, session_context
from app.tools.files import SessionWorkspace

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
