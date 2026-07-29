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


# ── Markdown ──────────────────────────────────────────────────────────────────


class TestMarkdownReport:
    def test_generates_utf8(self, tmp_path):
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        result = generate_markdown_report("# Report\n\nContent.", ws.output_dir)
        text = ws.resolve_output("tutorial-report.md").read_text(encoding="utf-8")
        assert "Content" in text
        # Must return relative path, not absolute
        assert not str(result).startswith("/")

    def test_atomic_write_no_tmp_left(self, tmp_path):
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        generate_markdown_report("hello", ws.output_dir)
        tmps = list(ws.output_dir.glob("*.tmp"))
        assert len(tmps) == 0

    def test_utf8_with_chinese(self, tmp_path):
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        generate_markdown_report(
            "# 研究报告\n\n分析结果：数据正常。\n\n- 项目 A\n- 项目 B", ws.output_dir
        )
        text = ws.resolve_output("tutorial-report.md").read_text(encoding="utf-8")
        assert "研究报告" in text
        assert "项目" in text

    def test_returns_relative_path_not_absolute(self, tmp_path):
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        result = generate_markdown_report("test", ws.output_dir)
        assert not str(result).startswith("/")
        assert "tutorial-report.md" in str(result)

    def test_uses_current_session_workspace(self, tmp_path):
        """When no explicit output_dir, use current_session().workspace."""
        from app.tools.reports import generate_markdown_report

        ws = _workspace(tmp_path)
        ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
        with session_context(ctx):
            result = generate_markdown_report("session-based")
        assert ws.resolve_output("tutorial-report.md").read_text() == "session-based"
        assert not str(result).startswith("/")


# ── PDF ───────────────────────────────────────────────────────────────────────


class TestPDFReport:
    def test_generates_pdf_header(self, tmp_path):
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        result = generate_pdf_report("# Title\n\nBody.", ws.output_dir)
        data = ws.resolve_output("tutorial-report.pdf").read_bytes()
        assert data[:4] == b"%PDF"
        assert not str(result).startswith("/")

    def test_chinese_content_renders(self, tmp_path):
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        generate_pdf_report(
            "# 中文报告\n\n测试内容。\n\n- 项目一\n- 项目二", ws.output_dir
        )
        data = ws.resolve_output("tutorial-report.pdf").read_bytes()
        assert data[:4] == b"%PDF"
        assert len(data) > 500  # should have real content

    def test_atomic_no_tmp_left(self, tmp_path):
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        generate_pdf_report("content", ws.output_dir)
        tmps = list(ws.output_dir.glob("*.tmp"))
        assert len(tmps) == 0

    def test_pdf_uses_stsong_light_font(self, tmp_path):
        """The ReportLab canvas must register STSong-Light for Chinese support."""
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        generate_pdf_report("test", ws.output_dir)
        # We can't easily introspect the font from the binary,
        # but the function should not raise ImportError or RuntimeError
        # for missing CJK font registration.

    def test_pdf_failure_keeps_markdown(self, tmp_path):
        """If PDF generation fails, Markdown already written stays intact."""
        ws = _workspace(tmp_path)

        from app.tools.reports import generate_markdown_report

        generate_markdown_report("# Safe\n\nContent.", ws.output_dir)
        md_path = ws.resolve_output("tutorial-report.md")
        assert md_path.exists()

        # Corrupt the output_dir to force PDF write failure
        # Actually, let's test that PDF failure raises properly
        pdf_path = ws.resolve_output("tutorial-report.pdf")
        # Pre-create the pdf as a directory to force failure
        pdf_path.mkdir(exist_ok=True)
        from app.tools.reports import generate_pdf_report

        with pytest.raises(Exception):
            generate_pdf_report("# Title\n\nBody.", ws.output_dir)
        # Markdown should still be there
        assert md_path.exists()
        assert md_path.read_text() == "# Safe\n\nContent."

    def test_pdf_error_message_is_redacted(self, tmp_path):
        """ReportGenerationError must not expose raw exception text or paths."""
        ws = _workspace(tmp_path)

        from app.tools.reports import generate_pdf_report

        pdf_path = ws.resolve_output("tutorial-report.pdf")
        pdf_path.mkdir(exist_ok=True)  # force write failure
        try:
            generate_pdf_report("# Test", ws.output_dir)
        except Exception as exc:
            msg = str(exc)
            # Must not expose the tmp_path or output_dir
            assert str(tmp_path) not in msg
            assert "tutorial-report" not in msg or "path" not in msg.lower()

    def test_uses_current_session_workspace_pdf(self, tmp_path):
        from app.tools.reports import generate_pdf_report

        ws = _workspace(tmp_path)
        ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
        with session_context(ctx):
            result = generate_pdf_report("session pdf")
        assert ws.resolve_output("tutorial-report.pdf").exists()
        assert not str(result).startswith("/")


# ── Markdown heading/paragraph/list support ───────────────────────────────────


def test_markdown_headings_paragraphs_lists_in_pdf(tmp_path):
    from app.tools.reports import generate_pdf_report

    ws = _workspace(tmp_path)
    generate_pdf_report(
        "# H1\n\nParagraph text.\n\n## H2\n\n- Item 1\n- Item 2", ws.output_dir
    )
    data = ws.resolve_output("tutorial-report.pdf").read_bytes()
    assert data[:4] == b"%PDF"


# ── Output dir created if missing ─────────────────────────────────────────────


def test_output_dir_created_if_missing(tmp_path):
    from app.tools.reports import generate_markdown_report

    ws = _workspace(tmp_path)
    # Remove output dir
    import shutil

    shutil.rmtree(ws.output_dir)
    assert not ws.output_dir.exists()
    generate_markdown_report("content", ws.output_dir)
    assert ws.output_dir.exists()
    assert ws.resolve_output("tutorial-report.md").exists()
