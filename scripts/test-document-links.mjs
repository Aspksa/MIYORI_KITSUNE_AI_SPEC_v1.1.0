import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const api=readFileSync("app.py","utf8");
const ui=readFileSync("static/js/drive.js","utf8");
const finder=readFileSync("miyori/document_links.py","utf8");
const css=readFileSync("static/css/drive.css","utf8");
assert.ok(api.includes('@app.get("/api/projects/{project_id}/documents/{document_id}/related")'));
assert.ok(api.includes("related_documents(project_id,document_id,limit=limit)"));
assert.ok(ui.includes('id="driveRelatedDocuments"') &&
  ui.includes("relatedPanel.addEventListener(\"toggle\",async()=>{") &&
  ui.includes("if(!relatedPanel.open || relatedLoaded)return"),
  "Related links must load on-demand only when the existing details opens");
assert.ok(ui.includes("document.createElement(\"article\")") &&
  ui.includes("info.textContent=match.kind") &&
  !ui.includes("driveRelatedOverlay"),
  "No new popup and no HTML injection from document text");
assert.ok(finder.includes("d.deleted_at IS NULL") &&
  finder.includes("d.project_id=?") &&
  finder.includes('"verified_relationship":False') &&
  finder.includes('"scan_truncated":truncated'));
assert.ok(css.includes("drive-related-documents") && css.includes("var(--ui-border)"));
console.log("On-demand, project-scoped candidate document link UI OK");
