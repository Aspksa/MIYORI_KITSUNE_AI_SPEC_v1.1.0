from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miyori.config import settings
from miyori.db import (
    add_document,
    create_document_folder,
    create_project,
    get_document_folder_parts,
    init_db,
    list_deleted_document_folders,
    list_deleted_documents,
    list_document_folders,
    list_documents,
    mark_document_deleted,
    mark_document_folder_deleted,
    restore_document_folder_record,
    restore_document_record,
)
from miyori.documents import (
    DRIVE_DIR_NAME,
    FILES_DIR_NAME,
    TRASH_DIR_NAME,
    ensure_drive_folder,
    move_document_to_trash,
    move_folder_to_trash,
    project_drive_dir,
    resolve_data_path,
    restore_document_from_trash,
    restore_folder_from_trash,
    save_original,
    sha256_bytes,
)
from miyori.rag import init_rag, rag_status


class MiyoriDrivePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        self.old_database_path = settings.database_path
        root = Path(self.tmp.name)
        object.__setattr__(settings, "data_dir", root / "data")
        object.__setattr__(settings, "database_path", root / "data" / "miyori.sqlite3")
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        self.project = create_project("Drive Test", kind="work")
        self.project_id = int(self.project["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_data_dir)
        object.__setattr__(settings, "database_path", self.old_database_path)
        self.tmp.cleanup()

    def test_project_drive_is_inside_project_workspace(self) -> None:
        root = project_drive_dir(self.project_id)
        expected = (
            settings.data_dir / "workspace" / str(self.project_id) / DRIVE_DIR_NAME
        )
        self.assertEqual(root, expected)
        self.assertTrue((root / FILES_DIR_NAME).is_dir())
        self.assertTrue((root / TRASH_DIR_NAME).is_dir())

    def test_browser_original_is_stored_in_logical_folder(self) -> None:
        folder = create_document_folder(self.project_id, "Договоры")
        parts = get_document_folder_parts(self.project_id, folder["id"])
        ensure_drive_folder(self.project_id, parts)

        data = b"original contract bytes"
        digest = sha256_bytes(data)
        stored = save_original(
            self.project_id,
            "contract.txt",
            data,
            digest,
            parts,
        )
        path = resolve_data_path(stored)

        self.assertTrue(path.is_file())
        self.assertEqual(path.read_bytes(), data)
        self.assertIn(DRIVE_DIR_NAME, str(path))
        self.assertIn("Договоры", str(path))

    def test_deleted_document_keeps_original_and_can_be_restored(self) -> None:
        data = "Тестовый рабочий документ".encode("utf-8")
        digest = sha256_bytes(data)
        stored = save_original(self.project_id, "work.txt", data, digest)
        document = add_document(
            self.project_id,
            "work.txt",
            stored,
            "text/plain",
            digest,
            len(data),
            ["Тестовый рабочий документ"],
        )

        trash_path = move_document_to_trash(
            self.project_id,
            stored,
            "work.txt",
            int(document["id"]),
        )
        deleted = mark_document_deleted(
            self.project_id,
            int(document["id"]),
            trash_path,
        )
        self.assertIsNotNone(deleted)
        self.assertEqual(list_documents(self.project_id), [])
        self.assertEqual(len(list_deleted_documents(self.project_id)), 1)
        self.assertEqual(resolve_data_path(trash_path).read_bytes(), data)

        restored_path = restore_document_from_trash(
            self.project_id,
            trash_path,
            "work.txt",
        )
        restored = restore_document_record(
            self.project_id,
            int(document["id"]),
            restored_path,
            None,
        )
        self.assertIsNotNone(restored)
        self.assertEqual(len(list_documents(self.project_id)), 1)
        self.assertEqual(resolve_data_path(restored_path).read_bytes(), data)

    def test_deleted_folder_is_soft_deleted_with_contents(self) -> None:
        folder = create_document_folder(self.project_id, "Архив договоров")
        parts = get_document_folder_parts(self.project_id, folder["id"])
        data = b"folder document"
        digest = sha256_bytes(data)
        stored = save_original(
            self.project_id,
            "inside.txt",
            data,
            digest,
            parts,
        )
        add_document(
            self.project_id,
            "inside.txt",
            stored,
            "text/plain",
            digest,
            len(data),
            ["folder document"],
            folder_id=folder["id"],
        )

        trash_path = move_folder_to_trash(
            self.project_id,
            parts,
            int(folder["id"]),
        )
        deleted = mark_document_folder_deleted(
            self.project_id,
            int(folder["id"]),
            trash_path,
        )
        self.assertIsNotNone(deleted)
        self.assertFalse(any(item["id"] == folder["id"] for item in list_document_folders(self.project_id)))
        self.assertEqual(list_documents(self.project_id), [])
        self.assertTrue(any(item["id"] == folder["id"] for item in list_deleted_document_folders(self.project_id)))

        _, restored_name = restore_folder_from_trash(
            self.project_id,
            trash_path,
            [],
            folder["name"],
        )
        restored = restore_document_folder_record(
            self.project_id,
            int(folder["id"]),
            restored_name=restored_name,
        )
        self.assertIsNotNone(restored)
        self.assertEqual(len(list_documents(self.project_id)), 1)

    def test_soft_deleted_document_is_removed_from_rag_index(self) -> None:
        data = b"rag source"
        digest = sha256_bytes(data)
        stored = save_original(self.project_id, "rag.txt", data, digest)
        document = add_document(
            self.project_id,
            "rag.txt",
            stored,
            "text/plain",
            digest,
            len(data),
            ["Уникальный индексируемый фрагмент Drive."],
        )
        before = init_rag()
        if before["fts5"]:
            self.assertEqual(rag_status()["indexed_chunks"], 1)

        trash_path = move_document_to_trash(
            self.project_id,
            stored,
            "rag.txt",
            int(document["id"]),
        )
        mark_document_deleted(
            self.project_id,
            int(document["id"]),
            trash_path,
        )
        after = init_rag()
        if after["fts5"]:
            self.assertEqual(rag_status()["indexed_chunks"], 0)


if __name__ == "__main__":
    unittest.main()
