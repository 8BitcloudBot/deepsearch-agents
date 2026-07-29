"""Safe workspace paths and file readers."""

import os
import re
import zipfile
from pathlib import Path

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".pdf", ".docx", ".xlsx"})
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MiB
MAX_TEXT_CHARS = 100_000
TRUNCATION_SUFFIX = "\n\n[TRUNCATED — exceeds maximum allowed characters]\n"


class SessionWorkspace:
    def __init__(self, thread_id: str, base_upload: str, base_output: str):
        self._thread_id = thread_id
        self.upload_dir = Path(base_upload) / f"session_{thread_id}"
        self.output_dir = Path(base_output) / f"session_{thread_id}"

    @classmethod
    def for_thread(cls, *, thread_id: str, base_upload: str, base_output: str):
        if not UUID_RE.fullmatch(thread_id):
            raise ValueError(f"thread_id must be a UUID: {thread_id!r}")
        ws = cls(thread_id, base_upload, base_output)
        ws.upload_dir.mkdir(parents=True, exist_ok=True)
        ws.output_dir.mkdir(parents=True, exist_ok=True)
        return ws

    def _safe_resolve(self, base: Path, name: str) -> Path:
        if not name or not name.strip():
            raise ValueError("Empty filename not allowed")
        if os.path.isabs(name) or name.startswith("/"):
            raise ValueError(f"Absolute path not allowed: {name!r}")
        # Sanitize to basename only
        clean = Path(name).name
        if not clean or clean in (".", ".."):
            raise ValueError(f"Invalid filename: {name!r}")
        candidate = (base / clean).resolve()
        base_resolved = base.resolve()
        if not str(candidate).startswith(str(base_resolved) + os.sep):
            raise ValueError(f"Path escape attempt: {name!r}")
        # Symlink check
        try:
            real = candidate.resolve(strict=False)
            if not str(real).startswith(str(base_resolved) + os.sep):
                raise ValueError(f"Symlink escape: {name!r}")
        except (OSError, RuntimeError):
            raise ValueError(f"Cannot resolve path: {name!r}")
        return candidate

    def resolve_upload(self, name: str) -> Path:
        return self._safe_resolve(self.upload_dir, name)

    def resolve_output(self, name: str) -> Path:
        return self._safe_resolve(self.output_dir, name)


def validate_upload_file(path: Path) -> None:
    """Validate a single uploaded file for size and extension."""
    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension: {ext!r}. "
            f"Allowed: {sorted(ALLOWED_EXTENSIONS)}"
        )
    if path.stat().st_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File too large: {path.stat().st_size} bytes (max {MAX_FILE_SIZE_BYTES})"
        )


def read_text_file(path: Path, max_chars: int = MAX_TEXT_CHARS) -> str:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"File is not valid UTF-8: {path}") from exc
    if len(raw) > max_chars:
        return raw[:max_chars] + TRUNCATION_SUFFIX
    return raw


def read_pdf_file(path: Path, max_pages: int = 200) -> str:
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise ValueError(f"Not a valid PDF (missing %PDF header): {path}")

    # Count pages by counting "/Type /Page" or "/Type/Page" occurrences
    import re as _re

    page_count = len(_re.findall(rb"/Type\s*/Page[^s]", data))
    if page_count > max_pages:
        raise ValueError(f"PDF exceeds max pages: {page_count} > {max_pages}")
    if page_count == 0:
        # Estimate from page tree
        page_count = max(1, data.count(b"stream") - data.count(b"endstream") + 1)
    return f"[PDF content: {page_count} pages, {len(data)} bytes]"


def read_docx_file(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if "[Content_Types].xml" not in names:
                raise ValueError("Missing [Content_Types].xml in DOCX")
            if "word/document.xml" not in names:
                raise ValueError("Missing word/document.xml in DOCX")
            # Basic read — extract text from document.xml
            doc_xml = zf.read("word/document.xml").decode("utf-8")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Not a valid ZIP (DOCX): {path}") from exc
    # Strip XML tags for plain text
    text = re.sub(r"<[^>]+>", " ", doc_xml)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + TRUNCATION_SUFFIX
    return text


def read_xlsx_file(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if "[Content_Types].xml" not in names:
                raise ValueError("Missing [Content_Types].xml in XLSX")
            if "xl/workbook.xml" not in names:
                raise ValueError("Missing xl/workbook.xml in XLSX")
            # Basic read
            if "xl/sharedStrings.xml" in names:
                ss = zf.read("xl/sharedStrings.xml").decode("utf-8")
            else:
                ss = ""
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Not a valid ZIP (XLSX): {path}") from exc
    text = re.sub(r"<[^>]+>", " ", ss)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + TRUNCATION_SUFFIX
    return text
