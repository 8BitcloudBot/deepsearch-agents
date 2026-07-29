"""Markdown and PDF report generation.

All reports are written inside the current session's output directory.
Returns relative artifact paths.
"""

from pathlib import Path


def generate_markdown_report(content: str, output_dir: Path) -> Path:
    """Write tutorial-report.md atomically into output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "tutorial-report.md"
    tmp = output_dir / ".tutorial-report.md.tmp"
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(target)
    return target


def generate_pdf_report(content: str, output_dir: Path) -> Path:
    """Generate tutorial-report.pdf from Markdown content using ReportLab."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "tutorial-report.pdf"
    tmp = output_dir / ".tutorial-report.pdf.tmp"

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate
    except ImportError as exc:
        raise RuntimeError("reportlab not installed. Run: uv sync --extra dev") from exc

    doc = SimpleDocTemplate(str(tmp), pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    for line in content.split("\n"):
        if line.startswith("# "):
            story.append(Paragraph(line[2:], styles["Heading1"]))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], styles["Heading2"]))
        elif line.startswith("- "):
            story.append(Paragraph(f"• {line[2:]}", styles["BodyText"]))
        elif line.strip():
            story.append(Paragraph(line, styles["BodyText"]))

    doc.build(story)
    tmp.rename(target)
    return target
