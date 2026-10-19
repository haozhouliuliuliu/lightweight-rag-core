from pathlib import Path

import pytest

from lightrag.parser import (
    DocumentParseError,
    find_supported_documents,
    parse_document,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA = REPO_ROOT / "data" / "docs"
DOCX = DATA / "product" / "STARLAN-X100-product-manual-v1.2.docx"
PDF = DATA / "quality" / "STARLAN-QS-001-inspection-spec-v2.0.pdf"


def test_parse_docx() -> None:
    document = parse_document(DOCX)
    assert document.file_type == "docx"
    assert document.source_file == "data/docs/product/STARLAN-X100-product-manual-v1.2.docx"
    assert document.blocks
    assert all(block.source_file == document.source_file for block in document.blocks)
    assert any(block.kind == "table" for block in document.blocks)
    assert "X-100" in document.text


def test_parse_pdf_with_pages() -> None:
    document = parse_document(PDF)
    assert document.file_type == "pdf"
    assert document.blocks
    assert all(block.page is not None and block.page >= 1 for block in document.blocks)
    assert document.blocks[0].page == 1
    assert "1500 VAC" in document.text
    assert document.metadata["page_count"] >= 1


def test_parse_txt(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("第一段：星澜虚构资料。\n\n第二段：用于 M1 解析测试。", encoding="utf-8")
    document = parse_document(path)
    assert document.file_type == "txt"
    assert len(document.blocks) == 2
    assert document.blocks[0].page is None
    assert "第一段" in document.text


def test_empty_file_is_structured_error(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")
    with pytest.raises(DocumentParseError) as exc_info:
        parse_document(path)
    error = exc_info.value
    assert error.error_type == "empty_document"
    assert error.file_name == "empty.txt"
    assert error.reason
    assert error.to_dict()["file"] == "empty.txt"


def test_corrupted_pdf_is_structured_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4\nthis is definitely not a valid PDF\n")
    with pytest.raises(DocumentParseError) as exc_info:
        parse_document(path)
    error = exc_info.value
    assert error.error_type == "corrupted_file"
    assert error.file_name == "broken.pdf"
    assert "PDF" in error.reason


def test_corrupted_docx_is_structured_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a zip package")
    with pytest.raises(DocumentParseError) as exc_info:
        parse_document(path)
    assert exc_info.value.error_type == "corrupted_file"


def test_unsupported_format_is_structured_error(tmp_path: Path) -> None:
    path = tmp_path / "notes.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(DocumentParseError) as exc_info:
        parse_document(path)
    error = exc_info.value
    assert error.error_type == "unsupported_format"
    assert "csv" in error.reason
    assert error.file_name == "notes.csv"


def test_missing_file_is_structured_error(tmp_path: Path) -> None:
    with pytest.raises(DocumentParseError) as exc_info:
        parse_document(tmp_path / "not-there.pdf")
    assert exc_info.value.error_type == "file_not_found"


def test_all_project_documents_parse() -> None:
    paths = find_supported_documents(DATA)
    assert len(paths) == 22
    failures = []
    for path in paths:
        try:
            document = parse_document(path)
        except DocumentParseError as exc:
            failures.append((path.as_posix(), exc.to_dict()))
            continue
        assert document.blocks, path
        assert document.text.strip(), path
    assert failures == []
