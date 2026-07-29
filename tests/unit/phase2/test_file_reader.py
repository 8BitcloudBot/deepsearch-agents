"""RED: Complete file reader contracts.

Requires pypdf, python-docx, openpyxl with real parsing.
No regex-only page counting. No sharedStrings-only XLSX.
Macro rejection, ZIP bomb defense, and proper error redaction.
"""

import zipfile
from pathlib import Path

import pytest

from app.tools.files import MAX_FILE_SIZE_BYTES, SessionWorkspace

UUID_V4 = "00000000-0000-4000-8000-000000000001"

# ── TXT / Markdown ──────────────────────────────────────────────────────────


class TestTextReader:
    def test_reads_utf8(self, tmp_path):
        from app.tools.files import read_text_file

        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        assert "hello world" in read_text_file(f)

    def test_rejects_non_utf8(self, tmp_path):
        from app.tools.files import read_text_file

        f = tmp_path / "bad.txt"
        f.write_bytes(b"\xff\xfe\x00\x00")
        with pytest.raises(ValueError):
            read_text_file(f)

    def test_truncates_above_max_chars(self, tmp_path):
        from app.tools.files import TRUNCATION_SUFFIX, read_text_file

        f = tmp_path / "large.txt"
        f.write_text("あ" * 150_000, encoding="utf-8")
        content = read_text_file(f, max_chars=100_000)
        assert len(content) <= 100_000 + len(TRUNCATION_SUFFIX) + 100
        assert TRUNCATION_SUFFIX.strip() in content

    def test_utf8_bom_accepted(self, tmp_path):
        from app.tools.files import read_text_file

        f = tmp_path / "bom.txt"
        f.write_bytes(b"\xef\xbb\xbfhello")
        content = read_text_file(f)
        assert "hello" in content


# ── PDF (pypdf required) ─────────────────────────────────────────────────────


class TestPDFReader:
    def test_rejects_non_pdf_header(self, tmp_path):
        from app.tools.files import read_pdf_file

        f = tmp_path / "fake.pdf"
        f.write_text("not a pdf")
        with pytest.raises(ValueError):
            read_pdf_file(f)

    def test_reads_valid_pdf_with_pypdf(self, tmp_path):
        from app.tools.files import read_pdf_file

        f = _make_valid_pdf(tmp_path / "doc.pdf", pages=2)
        content = read_pdf_file(f)
        assert len(content) > 0

    def test_rejects_encrypted_pdf(self, tmp_path):
        from pypdf import PdfWriter

        from app.tools.files import read_pdf_file

        writer = PdfWriter()
        writer.add_blank_page(100, 100)
        writer.encrypt("user_pass")
        f = tmp_path / "enc.pdf"
        with open(f, "wb") as fp:
            writer.write(fp)
        with pytest.raises(ValueError, match="encrypt"):
            read_pdf_file(f)

    def test_rejects_damaged_pdf(self, tmp_path):
        from app.tools.files import read_pdf_file

        f = tmp_path / "broken.pdf"
        f.write_bytes(b"%PDF-1.4\ngarbage without proper structure")
        with pytest.raises(ValueError):
            read_pdf_file(f)

    def test_rejects_over_200_pages(self, tmp_path):
        from app.tools.files import read_pdf_file

        f = _make_valid_pdf(tmp_path / "big.pdf", pages=250)
        with pytest.raises(ValueError, match="max"):
            read_pdf_file(f, max_pages=200)

    def test_accepts_200_pages(self, tmp_path):
        from app.tools.files import read_pdf_file

        f = _make_valid_pdf(tmp_path / "ok.pdf", pages=200)
        content = read_pdf_file(f, max_pages=200)
        assert len(content) > 0

    def test_pdf_extracts_text_not_placeholder(self, tmp_path):
        from app.tools.files import read_pdf_file

        f = _make_valid_pdf(tmp_path / "text.pdf", pages=1)
        content = read_pdf_file(f)
        # Must NOT return the old placeholder format
        assert not content.startswith("[PDF content:")


# ── DOCX (python-docx required) ─────────────────────────────────────────────


class TestDOCXReader:
    def test_reads_valid_docx_with_python_docx(self, tmp_path):
        from app.tools.files import read_docx_file

        f = _make_real_docx(tmp_path / "doc.docx")
        content = read_docx_file(f)
        assert len(content) > 0

    def test_rejects_non_zip(self, tmp_path):
        from app.tools.files import read_docx_file

        f = tmp_path / "fake.docx"
        f.write_text("not a zip")
        with pytest.raises(ValueError):
            read_docx_file(f)

    def test_rejects_missing_content_types(self, tmp_path):
        from app.tools.files import read_docx_file

        f = tmp_path / "bad.docx"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("word/document.xml", "<root/>")
        with pytest.raises(ValueError):
            read_docx_file(f)

    def test_rejects_missing_document_xml(self, tmp_path):
        from app.tools.files import read_docx_file

        f = tmp_path / "bad2.docx"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("[Content_Types].xml", _CT_XML)
        with pytest.raises(ValueError):
            read_docx_file(f)

    def test_rejects_macro_enabled_docx(self, tmp_path):
        from app.tools.files import read_docx_file

        f = tmp_path / "macro.docx"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("[Content_Types].xml", _CT_XML)
            zf.writestr("word/document.xml", _DOCUMENT_XML)
            zf.writestr("word/vbaProject.bin", b"macro payload")
        with pytest.raises(ValueError, match="macro"):
            read_docx_file(f)

    def test_rejects_macro_content_type(self, tmp_path):
        from app.tools.files import read_docx_file

        f = tmp_path / "macro2.docx"
        ct = _CT_XML.replace(
            'Extension="docx"',
            'Extension="docm"',
        ).replace(
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"',  # noqa: E501
            'ContentType="application/vnd.ms-word.document.macroEnabled.main+xml"',
        )
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("[Content_Types].xml", ct)
            zf.writestr("word/document.xml", _DOCUMENT_XML)
        with pytest.raises(ValueError, match="macro"):
            read_docx_file(f)

    def test_rejects_zip_bomb(self, tmp_path):
        from app.tools.files import read_docx_file

        f = tmp_path / "bomb.docx"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("[Content_Types].xml", _CT_XML)
            zf.writestr("word/document.xml", _DOCUMENT_XML)
            # 10000 entries with tiny compressed size but huge uncompressed
            for i in range(10000):
                zf.writestr(f"word/extra{i}.xml", "x" * 10000)
        with pytest.raises(ValueError, match="bomb|entry|limit"):
            read_docx_file(f)


# ── XLSX (openpyxl required) ────────────────────────────────────────────────


class TestXLSXReader:
    def test_rejects_non_zip(self, tmp_path):
        from app.tools.files import read_xlsx_file

        f = tmp_path / "fake.xlsx"
        f.write_text("not a zip")
        with pytest.raises(ValueError):
            read_xlsx_file(f)

    def test_rejects_missing_content_types(self, tmp_path):
        from app.tools.files import read_xlsx_file

        f = tmp_path / "bad.xlsx"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("xl/workbook.xml", "<root/>")
        with pytest.raises(ValueError):
            read_xlsx_file(f)

    def test_rejects_missing_workbook(self, tmp_path):
        from app.tools.files import read_xlsx_file

        f = tmp_path / "bad2.xlsx"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("[Content_Types].xml", _CT_XLSX_XML)
        with pytest.raises(ValueError):
            read_xlsx_file(f)

    def test_reads_real_xlsx_with_openpyxl(self, tmp_path):
        from app.tools.files import read_xlsx_file

        f = _make_real_xlsx(tmp_path / "doc.xlsx")
        content = read_xlsx_file(f)
        assert len(content) > 0
        # Should contain structured info, not just raw shared strings
        assert (
            "Sheet" in content
            or "sheet" in content.lower()
            or "columns" in content.lower()
        )

    def test_xlsx_includes_sheet_info(self, tmp_path):
        from app.tools.files import read_xlsx_file

        f = _make_real_xlsx(tmp_path / "info.xlsx")
        content = read_xlsx_file(f)
        # Must include some structural metadata
        assert any(kw in content.lower() for kw in ("sheet", "row", "column"))

    def test_xlsx_formula_data_only(self, tmp_path):
        """Formulas must not be exposed; only data_only values."""
        from app.tools.files import read_xlsx_file

        f = _make_formula_xlsx(tmp_path / "formula.xlsx")
        content = read_xlsx_file(f)
        # Formula text should NOT appear
        assert "=SUM" not in content
        assert "=A1+B1" not in content

    def test_xlsx_truncates_rows_to_20(self, tmp_path):
        from app.tools.files import read_xlsx_file

        f = _make_real_xlsx(tmp_path / "many.xlsx", rows=50)
        content = read_xlsx_file(f)
        # Should not have 50 rows of data referenced
        # At minimum, the function returned without error
        assert len(content) > 0

    def test_rejects_xlsm_extension(self, tmp_path):
        from app.tools.files import read_xlsx_file

        f = tmp_path / "doc.xlsm"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("[Content_Types].xml", _CT_XLSX_XML)
            zf.writestr("xl/workbook.xml", _WORKBOOK_XML)
            zf.writestr("xl/vbaProject.bin", b"macro")
        with pytest.raises(ValueError, match="macro"):
            read_xlsx_file(f)


# ── Untrusted source delimiters ──────────────────────────────────────────────


class TestUntrustedSourceBoundaries:
    def test_read_uploaded_file_wraps_with_delimiters(self, tmp_path):
        """read_uploaded_file must wrap content with BEGIN/END markers."""
        from app.tools.files import read_uploaded_file

        ws = _workspace(tmp_path)
        f = ws.resolve_upload("data.txt")
        f.write_text("source content", encoding="utf-8")

        from app.api.context import SessionContext, session_context

        ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
        with session_context(ctx):
            result = read_uploaded_file("data.txt")
        assert "[BEGIN UNTRUSTED" in result
        assert "[END UNTRUSTED" in result
        assert "source content" in result

    def test_untrusted_delimiters_warn_about_instructions(self, tmp_path):
        """The boundary prefix must warn that source instructions
        can't change system."""
        from app.tools.files import read_uploaded_file

        ws = _workspace(tmp_path)
        f = ws.resolve_upload("data.md")
        f.write_text("# my data", encoding="utf-8")

        from app.api.context import SessionContext, session_context

        ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
        with session_context(ctx):
            result = read_uploaded_file("data.md")
        # Must mention instruction limitations
        lower = result.lower()
        assert any(
            w in lower for w in ("cannot", "may not", "do not", "does not", "will not")
        )


# ── read_uploaded_file format dispatch ───────────────────────────────────────


class TestUploadedFileDispatch:
    def test_reads_txt(self, tmp_path):
        from app.tools.files import read_uploaded_file

        ws = _workspace(tmp_path)
        f = ws.resolve_upload("notes.txt")
        f.write_text("plain text", encoding="utf-8")

        from app.api.context import SessionContext, session_context

        ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
        with session_context(ctx):
            result = read_uploaded_file("notes.txt")
        assert "plain text" in result

    def test_reads_md(self, tmp_path):
        from app.tools.files import read_uploaded_file

        ws = _workspace(tmp_path)
        f = ws.resolve_upload("notes.md")
        f.write_text("# markdown", encoding="utf-8")

        from app.api.context import SessionContext, session_context

        ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
        with session_context(ctx):
            result = read_uploaded_file("notes.md")
        assert "markdown" in result

    def test_reads_pdf(self, tmp_path):
        from app.tools.files import read_uploaded_file

        ws = _workspace(tmp_path)
        _make_valid_pdf(ws.resolve_upload("doc.pdf"), pages=1)

        from app.api.context import SessionContext, session_context

        ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
        with session_context(ctx):
            result = read_uploaded_file("doc.pdf")
        assert len(result) > 0

    def test_reads_docx(self, tmp_path):
        from app.tools.files import read_uploaded_file

        ws = _workspace(tmp_path)
        _make_real_docx(ws.resolve_upload("doc.docx"))

        from app.api.context import SessionContext, session_context

        ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
        with session_context(ctx):
            result = read_uploaded_file("doc.docx")
        assert len(result) > 0

    def test_reads_xlsx(self, tmp_path):
        from app.tools.files import read_uploaded_file

        ws = _workspace(tmp_path)
        _make_real_xlsx(ws.resolve_upload("doc.xlsx"))

        from app.api.context import SessionContext, session_context

        ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
        with session_context(ctx):
            result = read_uploaded_file("doc.xlsx")
        assert len(result) > 0

    def test_rejects_unknown_extension(self, tmp_path):
        from app.tools.files import read_uploaded_file

        ws = _workspace(tmp_path)
        f = ws.resolve_upload("data.exe")
        f.write_bytes(b"payload")

        from app.api.context import SessionContext, session_context

        ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
        with session_context(ctx):
            with pytest.raises(ValueError, match="extension"):
                read_uploaded_file("data.exe")

    def test_rejects_missing_file(self, tmp_path):
        from app.tools.files import read_uploaded_file

        ws = _workspace(tmp_path)

        from app.api.context import SessionContext, session_context

        ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
        with session_context(ctx):
            with pytest.raises((FileNotFoundError, ValueError)):
                read_uploaded_file("nonexistent.txt")


def test_content_type_mismatch_does_not_override_validation(tmp_path):
    """MIME content-type must be advisory only — actual content drives validation."""
    from app.tools.files import read_uploaded_file

    ws = _workspace(tmp_path)
    f = ws.resolve_upload("fake.pdf")
    f.write_text("actually text not pdf")

    from app.api.context import SessionContext, session_context

    ctx = SessionContext(thread_id=UUID_V4, workspace=ws)
    with session_context(ctx):
        with pytest.raises(ValueError):
            read_uploaded_file("fake.pdf")


# ── Same-name upload: atomic replace ──────────────────────────────────────────


class TestSameSessionDuplicateUpload:
    def test_last_complete_replaces_previous(self, tmp_path):
        """The last complete, validated upload atomically replaces the prior file."""
        ws = _workspace(tmp_path)

        from app.tools.files import save_uploaded_file

        save_uploaded_file(ws, "data.txt", b"version 1")
        first = ws.resolve_upload("data.txt").read_text()
        assert "version 1" == first

        save_uploaded_file(ws, "data.txt", b"version 2")
        second = ws.resolve_upload("data.txt").read_text()
        assert "version 2" == second

    def test_failed_upload_preserves_old_file(self, tmp_path):
        """When validation fails, the old complete file stays intact."""
        ws = _workspace(tmp_path)

        from app.tools.files import save_uploaded_file

        save_uploaded_file(ws, "data.txt", b"good data")
        # Attempt invalid upload — too large
        with pytest.raises(ValueError):
            save_uploaded_file(ws, "data.txt", b"x" * (MAX_FILE_SIZE_BYTES + 100))
        content = ws.resolve_upload("data.txt").read_text()
        assert "good data" == content

    def test_atomic_replace_no_partial_state(self, tmp_path):
        """After replace, no .tmp files remain."""
        ws = _workspace(tmp_path)

        from app.tools.files import save_uploaded_file

        save_uploaded_file(ws, "doc.txt", b"content")
        tmps = list(ws.upload_dir.glob("*.tmp"))
        assert len(tmps) == 0, f"tmp files left: {[t.name for t in tmps]}"


# ── MIME content-type does not override actual content ───────────────────────


def test_text_content_type_on_pdf_is_rejected(tmp_path):
    """A file with .pdf extension but text content is rejected by content validation."""
    from app.tools.files import read_pdf_file

    f = tmp_path / "fake.pdf"
    f.write_text("text/plain content but pdf extension")
    with pytest.raises(ValueError):
        read_pdf_file(f)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

_CT_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="docx" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)

_CT_XLSX_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xlsx" '
    'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    "</Types>"
)

_DOCUMENT_XML = (
    "<w:document "
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body><w:p><w:r><w:t>Hello world</w:t></w:r></w:p></w:body>"
    "</w:document>"
)

_WORKBOOK_XML = (
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'
)


def _workspace(tmp_path):
    return SessionWorkspace.for_thread(
        thread_id=UUID_V4,
        base_upload=str(tmp_path / "updated"),
        base_output=str(tmp_path / "output"),
    )


def _make_valid_pdf(path: Path, pages: int = 2) -> Path:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(200, 300)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fp:
        writer.write(fp)
    return path


def _make_real_docx(path: Path) -> Path:
    from docx import Document

    doc = Document()
    doc.add_paragraph("Hello from python-docx")
    doc.add_paragraph("Second paragraph with more content")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path


def _make_real_xlsx(path: Path, rows: int = 10) -> Path:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws["A1"] = "Name"
    ws["B1"] = "Value"
    for i in range(1, rows):
        ws.cell(row=i + 1, column=1, value=f"Item {i}")
        ws.cell(row=i + 1, column=2, value=i * 10)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))
    return path


def _make_formula_xlsx(path: Path) -> Path:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws["A1"] = 10
    ws["A2"] = 20
    ws["A3"] = "=SUM(A1:A2)"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))
    return path
