"""Manifest-backed document catalog shared by indexing, retrieval and eval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CatalogError(RuntimeError):
    """Raised when the manifest is missing, malformed or inconsistent."""


class DocumentCatalog:
    def __init__(self, manifest_path: str | Path, root: str | Path):
        self.manifest_path = Path(manifest_path)
        self.root = Path(root)
        self.entries: list[dict[str, Any]] = []
        self.load()

    def load(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            self.entries = []
            return self.entries
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CatalogError(f"invalid manifest JSON: {exc}") from exc
        if not isinstance(data, list):
            raise CatalogError("manifest root must be an array")
        seen: set[str] = set()
        for item in data:
            if not isinstance(item, dict):
                raise CatalogError("manifest entries must be objects")
            doc_id = str(item.get("id", "")).strip()
            path = str(item.get("path", "")).strip()
            if not doc_id or not path:
                raise CatalogError("manifest entry requires id and path")
            if doc_id in seen:
                raise CatalogError(f"duplicate manifest id: {doc_id}")
            seen.add(doc_id)
        self.entries = data
        return data

    def save_atomic(self) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.manifest_path.with_suffix(self.manifest_path.suffix + ".tmp")
        temp.write_text(
            json.dumps(self.entries, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.manifest_path)

    def by_id(self, doc_id: str) -> dict[str, Any] | None:
        return next((item for item in self.entries if item.get("id") == doc_id), None)

    def by_source_file(self, source_file: str) -> dict[str, Any] | None:
        target = Path(source_file).as_posix()
        return next(
            (item for item in self.entries if Path(str(item.get("path", ""))).as_posix() == target),
            None,
        )

    def add(self, entry: dict[str, Any]) -> dict[str, Any]:
        if self.by_id(str(entry.get("id"))) is not None:
            raise CatalogError(f"document id already exists: {entry.get('id')}")
        self.entries.append(entry)
        self.save_atomic()
        return entry

    def remove(self, doc_id: str) -> dict[str, Any]:
        entry = self.by_id(doc_id)
        if entry is None:
            raise CatalogError(f"document id not found: {doc_id}")
        self.entries = [item for item in self.entries if item.get("id") != doc_id]
        self.save_atomic()
        return entry

    def paths(self) -> list[Path]:
        return [self.root / str(item["path"]) for item in self.entries]
