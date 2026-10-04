import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const backend=readFileSync("miyori/document_vision.py","utf8");
const app=readFileSync("app.py","utf8");
const drive=readFileSync("static/js/drive.js","utf8");
const docs=readFileSync("miyori/documents.py","utf8");
const req=readFileSync("requirements.txt","utf8");

assert.ok(
  req.includes("PyMuPDF") && req.includes("Pillow"),
  "Vision OCR must use explicit bounded PDF/image raster dependencies.",
);
assert.ok(
  backend.includes("deepseek-ai/DeepSeek-OCR-2") &&
  backend.includes("moonshotai/Kimi-K2.6") &&
  backend.includes("MAX_VISUAL_ITEMS") &&
  backend.includes("MAX_RENDER_EDGE") &&
  backend.includes('"bbox_verified": False'),
  "OCR/Vision must be bounded and must not invent trusted bounding boxes.",
);
assert.ok(
  backend.includes("pdf:page:") &&
  backend.includes("image:page:1") &&
  backend.includes("_chunks_with_locators") &&
  backend.includes("replace_document_chunks"),
  "OCR results must retain source locators and enter the existing RAG index.",
);
assert.ok(
  app.includes('/documents/{document_id}/vision') &&
  app.includes('"document_vision"') &&
  drive.includes("driveVisionStart") &&
  drive.includes("Распознать страницы и изображения"),
  "Vision OCR must run explicitly through the existing background task and Drive UI.",
);
assert.ok(
  docs.includes('".png"') && docs.includes('".webp"') &&
  drive.includes(".png,.jpg,.jpeg,.webp"),
  "Image originals must be accepted as OCR-ready documents.",
);
assert.ok(
  !backend.includes("bbox_verified=True") &&
  !drive.includes("точные координаты"),
  "UI must not claim unverified page coordinates.",
);

console.log("Document Vision OCR contract OK.");
