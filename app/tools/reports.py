"""Markdown and PDF report generation.

Report output_dir comes from current_session().workspace — callers
never pass arbitrary directories. Returns relative paths.
Uses ReportLab with STSong-Light for CJK support.
"""

from app.tools.files import ReportGenerationError, _atomic_write_bytes

# ── Public API ────────────────────────────────────────────────────────────────


def generate_markdown_report(content: str) -> str:
    """Write tutorial-report.md atomically. Returns relative path."""
    from app.api.context import current_session

    output_dir = current_session().workspace.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "tutorial-report.md"
    _atomic_write_bytes(target, content.encode("utf-8"))
    return "tutorial-report.md"


def generate_pdf_report(content: str) -> str:
    """Generate tutorial-report.pdf atomically. Returns relative path.

    Uses ReportLab with STSong-Light for Chinese support.
    On failure: Markdown already written stays; PDF tmp is cleaned;
    no raw paths or exception text in error message.
    """
    import os
    import tempfile

    from app.api.context import current_session

    output_dir = current_session().workspace.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "tutorial-report.pdf"

    fd = -1
    tmp_path = None
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise RuntimeError("reportlab not installed. Run: uv sync --extra dev") from exc

    try:
        # Register CJK font
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        style_cjk = ParagraphStyle(
            "CJK", fontName="STSong-Light", fontSize=11, leading=16
        )
        style_h1 = ParagraphStyle(
            "CJK_H1",
            fontName="STSong-Light",
            fontSize=18,
            leading=24,
            spaceAfter=12,
        )
        style_h2 = ParagraphStyle(
            "CJK_H2",
            fontName="STSong-Light",
            fontSize=14,
            leading=20,
            spaceAfter=8,
        )

        fd, tmp_path = tempfile.mkstemp(
            dir=str(output_dir), prefix=".tmp-", suffix=".tmp"
        )
        os.close(fd)
        fd = -1

        doc = SimpleDocTemplate(tmp_path, pagesize=A4)
        story = []

        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped:
                story.append(Spacer(1, 6))
                continue

            if stripped.startswith("# "):
                story.append(Paragraph(stripped[2:], style_h1))
            elif stripped.startswith("## "):
                story.append(Paragraph(stripped[3:], style_h2))
            elif stripped.startswith("|"):
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                story.append(Paragraph("  |  ".join(cells), style_cjk))
            elif stripped.startswith("- "):
                story.append(Paragraph(f"\u2022 {stripped[2:]}", style_cjk))
            else:
                story.append(Paragraph(stripped, style_cjk))

        doc.build(story)
        os.replace(tmp_path, target)
        tmp_path = None
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise ReportGenerationError(
            "PDF report generation failed — see server logs for details"
        )
    finally:
        if fd >= 0:
            os.close(fd)

    return "tutorial-report.pdf"
