"""File readers for the personal knowledge base ingestion.

Uses real pypdf, python-docx, openpyxl — no regex-only page counting.
Macro and ZIP bomb defense included. (H5: T1-era session workspace helpers
removed — ingestion is tempfile-based via app.conversation.uploads.)
"""

import zipfile
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".pdf", ".docx", ".xlsx"})
DISALLOWED_EXTENSIONS = frozenset({".doc", ".xls", ".docm", ".xlsm"})
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MiB
MAX_TEXT_CHARS = 100_000
MAX_ZIP_ENTRIES = 500
MAX_UNCOMPRESSED_SIZE = 100 * 1024 * 1024  # 100 MiB
MAX_ZIP_RATIO = 200
MAX_XLSX_DATA_ROWS = 200  # 每个工作表入库的数据行上限（G5：20 行静默丢失实测不可用）
TRUNCATION_SUFFIX = "\n\n[内容已截断：超过最大允许字符数]\n"

MACRO_ENTRIES = frozenset(
    {
        "vbaProject.bin",
        "word/vbaProject.bin",
        "xl/vbaProject.bin",
        "word/vbaData.xml",
        "xl/vbaData.xml",
    }
)
MACRO_CONTENT_TYPES = frozenset(
    {
        "application/vnd.ms-word.document.macroEnabled.main+xml",
        "application/vnd.ms-excel.sheet.macroEnabled.main+xml",
    }
)


# ── Upload validation ────────────────────────────────────────────────────────
# （H5：T1 遗留的 SessionWorkspace/原子写助手已移除——个人知识库入库走
#   uploads.read_supported_file 的临时目录方案，不再使用会话工作区。）

# ── Upload helpers ────────────────────────────────────────────────────────────


def validate_upload_file(path: Path) -> None:
    """Validate a single uploaded file for size and extension."""
    ext = path.suffix.lower()
    if ext in DISALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件类型：{ext}")
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"不支持的文件类型：{ext}（支持：{', '.join(sorted(ALLOWED_EXTENSIONS))}）"
        )
    if path.stat().st_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"文件过大：{path.stat().st_size} 字节（上限 {MAX_FILE_SIZE_BYTES}）"
        )




# ── Text readers ──────────────────────────────────────────────────────────────


def read_text_file(path: Path, max_chars: int = MAX_TEXT_CHARS) -> str:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("文件不是有效的 UTF-8 编码，请另存为 UTF-8 后重试") from exc
    if len(raw) > max_chars:
        return raw[:max_chars] + TRUNCATION_SUFFIX
    return raw


# ── PDF reader (pypdf) ────────────────────────────────────────────────────────


def read_pdf_file(path: Path, max_pages: int = 200) -> str:
    """Read PDF using pypdf with real page counting and text extraction."""
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise ValueError("不是有效的 PDF 文件（缺少 %PDF 头）")

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf not installed. Run: uv sync --extra dev") from exc

    try:
        reader = PdfReader(path)
    except Exception:
        raise ValueError("PDF 文件损坏或无法读取")

    if reader.is_encrypted:
        raise ValueError("暂不支持加密 PDF")

    pages = len(reader.pages)
    if pages > max_pages:
        raise ValueError(f"PDF 页数超出上限：{pages} > {max_pages}")

    texts: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text()
            if t:
                texts.append(t)
        except Exception:
            pass

    combined = "\n".join(texts)
    if len(combined) > MAX_TEXT_CHARS:
        combined = combined[:MAX_TEXT_CHARS] + TRUNCATION_SUFFIX
    if not combined:
        combined = "[PDF 未包含可提取的文本]"
    return combined


# ── DOCX reader (python-docx) ─────────────────────────────────────────────────


def _validate_zip_safety(zf: zipfile.ZipFile) -> None:
    """Reject ZIP bombs and macro-enabled archives."""
    names = zf.namelist()
    if len(names) > MAX_ZIP_ENTRIES:
        raise ValueError(f"ZIP 条目数超出上限：{len(names)} > {MAX_ZIP_ENTRIES}")

    # Check for macro entries
    for name in names:
        base = name.split("/")[-1]
        if base in MACRO_ENTRIES or name in MACRO_ENTRIES:
            raise ValueError("已拒绝宏文档：检测到 vbaProject.bin")

    # Check uncompressed size to avoid ZIP bomb
    total_size = 0
    for info in zf.infolist():
        if info.file_size > 0:
            total_size += info.file_size
            # Check per-entry ratio
            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > MAX_ZIP_RATIO:
                    raise ValueError("检测到疑似 ZIP 炸弹：异常压缩比")
    if total_size > MAX_UNCOMPRESSED_SIZE:
        raise ValueError(
            f"ZIP 解压后大小超出上限：{total_size} > {MAX_UNCOMPRESSED_SIZE}"
        )


def _check_content_types_macros(names: list[str], raw_ct: bytes | None) -> None:
    """Reject macro content types in [Content_Types].xml."""
    if raw_ct:
        text = raw_ct.decode("utf-8", errors="replace").lower()
        for mt in MACRO_CONTENT_TYPES:
            if mt.lower() in text:
                raise ValueError("检测到宏启用内容类型")


def read_docx_file(path: Path) -> str:
    """Read DOCX using python-docx with macro and ZIP bomb defense."""
    try:
        import zipfile as _zf

        with _zf.ZipFile(path) as zf:
            names = zf.namelist()
            if "[Content_Types].xml" not in names:
                raise ValueError("DOCX 缺少 [Content_Types].xml")
            if "word/document.xml" not in names:
                raise ValueError("DOCX 缺少 word/document.xml")

            # Check content types for macros
            ct_data = zf.read("[Content_Types].xml")
            _check_content_types_macros(names, ct_data)

            # ZIP bomb defense
            _validate_zip_safety(zf)
    except zipfile.BadZipFile as exc:
        raise ValueError("不是有效的 DOCX 文件（ZIP 结构损坏）") from exc
    except ValueError:
        raise

    try:
        from docx import Document

        doc = Document(str(path))
    except ImportError as exc:
        raise RuntimeError(
            "python-docx not installed. Run: uv sync --extra dev"
        ) from exc
    except Exception:
        raise ValueError("无法解析 DOCX 文档")

    paragraphs = []
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text)

    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                paragraphs.append(" | ".join(cells))

    text = "\n".join(paragraphs)
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + TRUNCATION_SUFFIX
    return text


# ── XLSX reader (openpyxl) ────────────────────────────────────────────────────


def read_xlsx_file(path: Path) -> str:
    """Read XLSX using openpyxl with read_only, data_only, no macros."""
    try:
        import zipfile as _zf

        with _zf.ZipFile(path) as zf:
            names = zf.namelist()
            if "[Content_Types].xml" not in names:
                raise ValueError("XLSX 缺少 [Content_Types].xml")
            if "xl/workbook.xml" not in names:
                raise ValueError("XLSX 缺少 xl/workbook.xml")

            ct_data = zf.read("[Content_Types].xml")
            _check_content_types_macros(names, ct_data)
            _validate_zip_safety(zf)
    except zipfile.BadZipFile as exc:
        raise ValueError("不是有效的 XLSX 文件（ZIP 结构损坏）") from exc
    except ValueError:
        raise

    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl not installed. Run: uv sync --extra dev") from exc

    import itertools

    output_lines: list[str] = []
    try:
        # openpyxl rejects paths whose extension is not a supported format
        # (e.g. the ".tmp" of a validation temp file), so hand it a binary
        # file object: content parsing stays extension-independent, matching
        # the documented "parse content, not names" contract.
        with path.open("rb") as fh:
            wb = load_workbook(fh, read_only=True, data_only=True, keep_links=False)
            try:
                for sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                    # Bound: header + up to MAX_XLSX_DATA_ROWS data rows
                    all_rows = ws.iter_rows(values_only=True)
                    header_row = next(all_rows, None)
                    headers = (
                        [str(c) if c is not None else "" for c in header_row]
                        if header_row
                        else []
                    )
                    data_rows = list(itertools.islice(all_rows, MAX_XLSX_DATA_ROWS))
                    truncated = next(all_rows, None) is not None

                    col_count = ws.max_column or len(headers)
                    row_count = len(data_rows) + (1 if header_row else 0)

                    output_lines.append(f"## Sheet: {sheet_name}")
                    output_lines.append(
                        f"Rows (bounded): {row_count}, Columns: {col_count}"
                    )
                    if headers:
                        output_lines.append(f"Headers: {' | '.join(headers)}")
                    output_lines.append("")
                    for row in data_rows:
                        row_str = " | ".join(
                            str(c) if c is not None else "" for c in row
                        )
                        output_lines.append(row_str)
                    if truncated:
                        output_lines.append(
                            f"[数据已截断：仅入库每个工作表前 {MAX_XLSX_DATA_ROWS} 行]"
                        )
                    output_lines.append("")
            finally:
                wb.close()
    except Exception:
        raise ValueError("无法解析 XLSX 工作簿")
    text = "\n".join(output_lines)
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + TRUNCATION_SUFFIX
    return text
