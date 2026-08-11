"""Markdown and PDF report generation.

Report output_dir comes from current_session().workspace.
Returns relative paths. Uses ReportLab Table for pipe tables
and STSong-Light for CJK. XML-escapes cell content.
"""

import os
import tempfile
from pathlib import Path

from app.tools.files import ReportGenerationError, _atomic_write_bytes


def _escape_xml(text: str) -> str:
    """Escape < and & for safe ReportLab Paragraph/Table content."""
    return text.replace("&", "&amp;").replace("<", "&lt;")


def _report_target(filename: str, expected_extension: str) -> tuple[Path, str]:
    """Resolve one safe report basename without exposing workspace details."""
    from app.api.context import current_session

    workspace = current_session().workspace
    try:
        clean = Path(filename)
        if clean.suffix.lower() != expected_extension or clean.name != filename:
            raise ValueError("invalid report extension")
        target = workspace.resolve_output(filename)
    except Exception:
        # Replacing an existing final symlink is safe: os.replace() operates on
        # the link itself and never follows it to an external target.
        try:
            if (
                isinstance(filename, str)
                and clean.name == filename
                and clean.suffix.lower() == expected_extension
            ):
                symlink_target = workspace.output_dir / clean.name
                if symlink_target.is_symlink():
                    target = symlink_target
                else:
                    raise ValueError("invalid report filename")
            else:
                raise ValueError("invalid report filename")
        except Exception as symlink_exc:
            raise ReportGenerationError("invalid report filename") from symlink_exc
    target.parent.mkdir(parents=True, exist_ok=True)
    return target, target.name


def generate_markdown_report(
    content: str, *, filename: str = "tutorial-report.md"
) -> str:
    """Write a Markdown report atomically. Returns its safe basename."""
    target, relative_name = _report_target(filename, ".md")
    _atomic_write_bytes(target, content.encode("utf-8"))
    return relative_name


def generate_pdf_report(content: str, *, filename: str = "tutorial-report.pdf") -> str:
    """Generate a PDF report with ReportLab Table + CJK."""
    target, relative_name = _report_target(filename, ".pdf")
    output_dir = target.parent

    fd = -1
    tmp_path = None
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError("reportlab not installed. Run: uv sync --extra dev") from exc

    try:
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
        table_rows: list[list[str]] = []

        def _flush_table():
            nonlocal table_rows
            if not table_rows:
                return
            filtered = [
                r
                for r in table_rows
                if not all(c.strip().replace("-", "") == "" for c in r)
            ]
            if filtered:
                escaped = [
                    [Paragraph(_escape_xml(c), style_cjk) for c in r] for r in filtered
                ]
                tbl = Table(escaped)
                tbl.setStyle(
                    TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
                        ]
                    )
                )
                story.append(tbl)
            table_rows = []

        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped:
                _flush_table()
                story.append(Spacer(1, 6))
                continue

            if stripped.startswith("|") and stripped.endswith("|"):
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                table_rows.append(cells)
                continue
            else:
                _flush_table()

            if stripped.startswith("# "):
                story.append(Paragraph(_escape_xml(stripped[2:]), style_h1))
            elif stripped.startswith("## "):
                story.append(Paragraph(_escape_xml(stripped[3:]), style_h2))
            elif stripped.startswith("- "):
                story.append(
                    Paragraph(f"\u2022 {_escape_xml(stripped[2:])}", style_cjk)
                )
            else:
                story.append(Paragraph(_escape_xml(stripped), style_cjk))

        _flush_table()
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

    return relative_name
