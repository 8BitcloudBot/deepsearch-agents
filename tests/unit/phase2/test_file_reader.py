"""Tests for safe file readers."""

import zipfile
from pathlib import Path

import pytest

from app.tools.files import (
    TRUNCATION_SUFFIX,
    read_docx_file,
    read_pdf_file,
    read_text_file,
    read_xlsx_file,
)


class TestTextReader:
    def test_reads_utf8_txt(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        content = read_text_file(f)
        assert "hello world" in content

    def test_truncates_large_text(self, tmp_path):
        f = tmp_path / "large.txt"
        f.write_text("x" * 200_000, encoding="utf-8")
        content = read_text_file(f, max_chars=100_000)
        assert len(content) <= 100_000 + len(TRUNCATION_SUFFIX) + 10

    def test_rejects_non_utf8(self, tmp_path):
        f = tmp_path / "bad.txt"
        f.write_bytes(b"\xff\xfe\x00\x00")
        with pytest.raises(ValueError):
            read_text_file(f)


class TestPDFReader:
    def test_reads_valid_pdf(self, tmp_path):
        f = tmp_path / "doc.pdf"
        pdf_bytes = b"".join(
            [
                b"%PDF-1.4\n",
                b"1 0 obj\n<<>>\nendobj\n",
                b"xref\n0 1\n0000000000 65535 f \n",
                b"trailer\n<<>>\nstartxref\n9\n%%EOF",
            ]
        )
        f.write_bytes(pdf_bytes)
        content = read_pdf_file(f)
        assert len(content) > 0

    def test_rejects_non_pdf(self, tmp_path):
        f = tmp_path / "fake.pdf"
        f.write_text("not a pdf")
        with pytest.raises(ValueError):
            read_pdf_file(f)

    def test_rejects_large_pdf(self, tmp_path):
        f = tmp_path / "big.pdf"
        # Simulate 300+ pages with /Type/Page markers
        pages = b"".join(b"/Type /Page\n" for _ in range(250))
        f.write_bytes(b"%PDF-1.4\n" + pages + b"%%EOF")
        with pytest.raises(ValueError, match="max pages"):
            read_pdf_file(f, max_pages=200)


class TestDOCXReader:
    def test_reads_valid_docx(self, tmp_path):
        f = tmp_path / "doc.docx"
        _write_minimal_ooxml(f, doc_type="word")
        content = read_docx_file(f)
        assert len(content) > 0

    def test_rejects_non_zip(self, tmp_path):
        f = tmp_path / "fake.docx"
        f.write_text("not a zip")
        with pytest.raises(ValueError):
            read_docx_file(f)

    def test_rejects_missing_content_types(self, tmp_path):
        f = tmp_path / "bad.docx"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("word/document.xml", "<root/>")
        with pytest.raises(ValueError):
            read_docx_file(f)


class TestXLSXReader:
    def test_reads_valid_xlsx(self, tmp_path):
        f = tmp_path / "doc.xlsx"
        _write_minimal_ooxml(f, doc_type="excel")
        content = read_xlsx_file(f)
        assert len(content) > 0

    def test_rejects_non_zip(self, tmp_path):
        f = tmp_path / "fake.xlsx"
        f.write_text("not a zip")
        with pytest.raises(ValueError):
            read_xlsx_file(f)


# ---- helpers ----


def _write_minimal_ooxml(path: Path, doc_type: str):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        if doc_type == "word":
            zf.writestr(
                "word/document.xml",
                "<w:document "
                "xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
                "<w:body><w:p><w:r><w:t>Hello world</w:t></w:r></w:p></w:body>"
                "</w:document>",
            )
        elif doc_type == "excel":
            zf.writestr("xl/workbook.xml", "<workbook xmlns='urn:...'/>")
            zf.writestr(
                "xl/sharedStrings.xml",
                '<sst xmlns="urn:..."><si><t>Hello</t></si></sst>',
            )
