from pathlib import Path

import pytest

from lightrag.documents import DocumentManager, DocumentManagerError


def test_add_and_remove_document(tmp_path: Path) -> None:
    root = tmp_path
    docs = root / "data" / "docs"
    docs.mkdir(parents=True)
    source = tmp_path / "sample.txt"
    source.write_text("第一段。\n\n第二段。", encoding="utf-8")

    manager = DocumentManager(docs, root)
    entry = manager.add(source, doc_id="IMP-TEST", title="导入测试")
    assert entry["id"] == "IMP-TEST"
    target = root / entry["path"]
    assert target.exists()
    assert manager.catalog.by_id("IMP-TEST")["title"] == "导入测试"

    with pytest.raises(DocumentManagerError):
        manager.add(source, doc_id="IMP-TEST")

    manager.remove("IMP-TEST")
    assert not target.exists()
    assert manager.list() == []


def test_unsupported_and_empty_rejected(tmp_path: Path) -> None:
    docs = tmp_path / "data" / "docs"
    docs.mkdir(parents=True)
    manager = DocumentManager(docs, tmp_path)

    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("a,b\n", encoding="utf-8")
    with pytest.raises(DocumentManagerError, match="unsupported"):
        manager.add(csv_file)

    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(DocumentManagerError):
        manager.add(empty)


def test_manifest_is_valid_after_remove(tmp_path: Path) -> None:
    docs = tmp_path / "data" / "docs"
    docs.mkdir(parents=True)
    source = tmp_path / "a.txt"
    source.write_text("资料", encoding="utf-8")
    manager = DocumentManager(docs, tmp_path)
    manager.add(source, doc_id="A")
    manager.remove("A")
    text = (docs / "manifest.json").read_text(encoding="utf-8")
    assert '"A"' not in text
