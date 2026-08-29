"""G5 文档入库治理：xlsx 行数上限与截断标记、编码与错误文案。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.knowledge.readers import (
    MAX_XLSX_DATA_ROWS,
    TRUNCATION_SUFFIX,
    read_text_file,
    read_xlsx_file,
)


def _write_xlsx(path: Path, data_rows: int, *, sheets: int = 1) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet_index in range(sheets):
        sheet = workbook.create_sheet(title=f"Sheet{sheet_index + 1}")
        sheet.append(["名称", "数值"])
        for row_index in range(data_rows):
            sheet.append([f"item-{row_index}", row_index])
    workbook.save(path)


def test_xlsx_within_limit_has_no_truncation_marker(tmp_path: Path) -> None:
    target = tmp_path / "small.xlsx"
    _write_xlsx(target, data_rows=10)
    text = read_xlsx_file(target)
    assert "item-9" in text
    assert "item-10" not in text
    assert "数据已截断" not in text


def test_xlsx_beyond_limit_is_truncated_with_marker(tmp_path: Path) -> None:
    target = tmp_path / "big.xlsx"
    _write_xlsx(target, data_rows=MAX_XLSX_DATA_ROWS + 50)
    text = read_xlsx_file(target)
    last = f"item-{MAX_XLSX_DATA_ROWS - 1}"
    dropped = f"item-{MAX_XLSX_DATA_ROWS + 10}"
    assert last in text
    assert dropped not in text
    assert f"[数据已截断：仅入库每个工作表前 {MAX_XLSX_DATA_ROWS} 行]" in text


def test_xlsx_truncation_marker_applies_per_sheet(tmp_path: Path) -> None:
    target = tmp_path / "twosheets.xlsx"
    _write_xlsx(target, data_rows=MAX_XLSX_DATA_ROWS + 5, sheets=2)
    text = read_xlsx_file(target)
    assert text.count("数据已截断") == 2


def test_text_file_rejects_non_utf8_with_actionable_message(
    tmp_path: Path,
) -> None:
    target = tmp_path / "gbk.txt"
    target.write_bytes("中文内容".encode("gbk"))
    with pytest.raises(ValueError) as excinfo:
        read_text_file(target)
    assert "UTF-8" in str(excinfo.value)


def test_oversized_text_file_appends_chinese_marker(tmp_path: Path) -> None:
    target = tmp_path / "long.txt"
    target.write_text("字" * 150_000, encoding="utf-8")
    text = read_text_file(target)
    assert text.startswith("字")
    assert TRUNCATION_SUFFIX in text
