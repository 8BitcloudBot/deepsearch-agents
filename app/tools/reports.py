"""Markdown and PDF report generation.

Report output_dir comes from current_session().workspace — callers
never pass arbitrary directories. Returns relative paths.
Uses ReportLab with STSong-Light for CJK support.
"""

from app.tools.files import ReportGenerationError

# ── Public API ────────────────────────────────────────────────────────────────


def generate_markdown_report(
    content: str,
) -> str:
    """Write tutorial-report.md atomically. Returns relative path."""
    from app.api.context import current_session

    output_dir = current_session().workspace.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "tutorial-report.md"
    tmp = output_dir / ".tutorial-report.md.tmp"

    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(target)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise

    return "tutorial-report.md"


def generate_pdf_report(
    content: str,
) -> str:
    """Generate tutorial-report.pdf atomically. Returns relative path.

    Uses ReportLab with STSong-Light for Chinese support.
    On failure: Markdown already written stays; PDF tmp is cleaned;
    no raw paths or exception text in error message.
    """
    from app.api.context import current_session

    output_dir = current_session().workspace.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp = output_dir / ".tutorial-report.pdf.tmp"

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
            "CJK",
            fontName="STSong-Light",
            fontSize=11,
            leading=16,
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

        doc = SimpleDocTemplate(str(tmp), pagesize=A4)
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
                # simple pipe table — render as paragraph
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                story.append(Paragraph("  |  ".join(cells), style_cjk))
            elif stripped.startswith("- "):
                story.append(Paragraph(f"• {stripped[2:]}", style_cjk))
            else:
                story.append(Paragraph(stripped, style_cjk))

        doc.build(story)
        target = output_dir / "tutorial-report.pdf"
        tmp.replace(target)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise ReportGenerationError(
            "PDF report generation failed — see server logs for details"
        )

    return "tutorial-report.pdf"
