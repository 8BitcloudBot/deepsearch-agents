"""Tests for report generation."""

from app.tools.reports import generate_markdown_report, generate_pdf_report


class TestMarkdownReport:
    def test_generates_utf8_markdown(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        path = generate_markdown_report(
            content="# Research Report\n\nFindings.",
            output_dir=output_dir,
        )
        assert path.name == "tutorial-report.md"
        text = path.read_text(encoding="utf-8")
        assert "Findings" in text

    def test_path_is_relative_to_output(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        path = generate_markdown_report("content", output_dir=output_dir)
        assert str(path).startswith(str(output_dir))

    def test_atomic_write_no_partial_file(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        path = generate_markdown_report("hello", output_dir=output_dir)
        # No .tmp or partial files left
        temps = list(output_dir.glob("*.tmp"))
        assert len(temps) == 0
        assert path.read_text() == "hello"


class TestPDFReport:
    def test_generates_pdf_with_header(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        path = generate_pdf_report(
            content="# Title\n\nBody text.",
            output_dir=output_dir,
        )
        assert path.name == "tutorial-report.pdf"
        data = path.read_bytes()
        assert data[:4] == b"%PDF"

    def test_pdf_path_is_relative(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        path = generate_pdf_report("hello", output_dir=output_dir)
        assert str(path).startswith(str(output_dir))
