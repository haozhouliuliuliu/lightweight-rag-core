"""Document add/remove operations for the local knowledge base."""

from __future__ import annotations

import hashlib
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from .catalog import CatalogError, DocumentCatalog
from .parser import DocumentParseError, SUPPORTED_EXTENSIONS, parse_document


class DocumentManagerError(RuntimeError):
    """Raised when document management cannot complete safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class DocumentManager:
    def __init__(self, docs_dir: str | Path, project_root: str | Path):
        self.docs_dir = Path(docs_dir)
        self.project_root = Path(project_root)
        self.manifest_path = self.docs_dir / "manifest.json"
        self.catalog = DocumentCatalog(self.manifest_path, self.project_root)

    def list(self) -> list[dict[str, Any]]:
        return list(self.catalog.entries)

    def add(
        self,
        source: str | Path,
        *,
        doc_id: str | None = None,
        title: str | None = None,
        category: str = "imported",
        version: str = "V1.0",
    ) -> dict[str, Any]:
        src = Path(source)
        if src.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise DocumentManagerError(f"unsupported format: {src.suffix}")
        try:
            parse_document(src)  # validate before copying
        except DocumentParseError as exc:
            raise DocumentManagerError(f"cannot import {src.name}: {exc.error_type}: {exc.reason}") from exc

        digest = _sha256(src)
        chosen_id = doc_id or f"IMP-{digest[:8]}"
        if self.catalog.by_id(chosen_id) is not None:
            raise DocumentManagerError(f"document id already exists: {chosen_id}")

        target = self.docs_dir / category / f"{chosen_id}-{src.name}"
        if target.exists():
            raise DocumentManagerError(f"target file already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        entry: dict[str, Any] = {
            "id": chosen_id,
            "path": target.relative_to(self.project_root).as_posix(),
            "format": src.suffix.lower().lstrip("."),
            "title": title or src.stem,
            "code": "",
            "version": version,
            "date": date.today().isoformat(),
            "status": "导入",
            "category": category,
            "scope": "用户导入",
            "summary": "通过 DocumentManager 导入的文档",
            "obsolete": False,
            "bytes": src.stat().st_size,
            "sha256": digest,
            "source_project": "user-import",
        }
        try:
            shutil.copy2(src, target)
            self.catalog.add(entry)
        except Exception as exc:
            if target.exists():
                target.unlink()
            raise DocumentManagerError(f"failed to import {src}: {exc}") from exc
        return entry

    def remove(self, doc_id: str, *, delete_file: bool = True) -> dict[str, Any]:
        entry = self.catalog.by_id(doc_id)
        if entry is None:
            raise DocumentManagerError(f"document id not found: {doc_id}")
        path = self.project_root / str(entry["path"])
        self.catalog.remove(doc_id)
        if delete_file and path.exists():
            path.unlink()
        return entry
