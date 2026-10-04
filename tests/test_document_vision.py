from __future__ import annotations

import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image, ImageDraw

from miyori.config import settings
from miyori.db import (
    add_document,
    create_project,
    init_db,
    search_document_chunks,
)
from miyori.document_intelligence import (
    get_document_intelligence,
    init_document_intelligence_db,
)
from miyori.document_vision import (
    _visual_items,
    document_vision_status,
    init_document_vision_db,
    run_document_vision,
)


class DocumentVisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_dir = settings.data_dir
        self.old_db = settings.database_path
        root = Path(self.tmp.name)
        data = root / "data"
        data.mkdir(parents=True, exist_ok=True)
        object.__setattr__(settings, "data_dir", data)
        object.__setattr__(
            settings,
            "database_path",
            data / "vision.sqlite3",
        )
        init_db()
        init_document_intelligence_db()
        init_document_vision_db()
        self.project = int(create_project("Vision")["id"])
        self.other = int(create_project("Other")["id"])

    def tearDown(self) -> None:
        object.__setattr__(settings, "data_dir", self.old_dir)
        object.__setattr__(settings, "database_path", self.old_db)
        self.tmp.cleanup()

    def image_bytes(self) -> bytes:
        image = Image.new("RGB", (900, 500), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((60, 60, 840, 440), outline="black", width=3)
        draw.text((90, 100), "INVOICE 42 TOTAL 1500", fill="black")
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    def add_image_document(self) -> int:
        raw = self.image_bytes()
        relative = "workspace/vision.png"
        path = settings.data_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        item = add_document(
            project_id=self.project,
            filename="scan.png",
            stored_path=relative,
            mime_type="image/png",
            sha256="vision-sha",
            size_bytes=len(raw),
            chunks=[],
        )
        return int(item["id"])

    def test_image_visual_item_has_page_locator(self) -> None:
        items, pages = _visual_items(
            "scan.png",
            self.image_bytes(),
            include_text_pages=False,
        )
        self.assertEqual(pages, 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].locator, "image:page:1")
        self.assertEqual(items[0].page_number, 1)
        self.assertLessEqual(
            max(Image.open(io.BytesIO(items[0].image)).size),
            1800,
        )

    def test_pipeline_reindexes_with_provenance_without_fake_bbox(self) -> None:
        document_id = self.add_image_document()

        async def fake_analyze(*args, **kwargs):
            return {
                "text": "Счет 42. Итого 1500 рублей.",
                "visual_summary": "Скан счета с таблицей итогов.",
                "elements": [
                    {"kind": "table", "description": "Таблица итоговой суммы."}
                ],
            }

        with (
            patch(
                "miyori.document_vision._resolve_models",
                new=AsyncMock(
                    return_value=(
                        "deepseek-ai/DeepSeek-OCR-2",
                        "moonshotai/Kimi-K2.6",
                    )
                ),
            ),
            patch(
                "miyori.document_vision._analyze_item",
                new=AsyncMock(side_effect=fake_analyze),
            ),
        ):
            result = asyncio.run(
                run_document_vision(
                    self.project,
                    document_id,
                    max_items=2,
                )
            )

        self.assertEqual(result["state"]["status"], "complete")
        self.assertFalse(result["bbox_verified"])
        self.assertEqual(result["items"][0]["locator"], "image:page:1")

        chunks = search_document_chunks(
            self.project,
            "1500",
            limit=5,
        )
        self.assertTrue(chunks)
        self.assertIn("[image:page:1]", chunks[0]["content"])

        profile = get_document_intelligence(
            self.project,
            document_id,
        )
        self.assertEqual(
            profile["extraction_status"],
            "vision_augmented",
        )
        nodes = profile["node_count"]
        self.assertGreater(nodes, 0)

    def test_status_is_project_scoped(self) -> None:
        document_id = self.add_image_document()
        with self.assertRaises(LookupError):
            document_vision_status(self.other, document_id)


if __name__ == "__main__":
    unittest.main()
