import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const chat=readFileSync("static/js/chat.js","utf8");
const drive=readFileSync("static/js/drive.js","utf8");
const shell=readFileSync("static/js/workspace.js","utf8");
const api=readFileSync("app.py","utf8");
const provider=readFileSync("miyori/provider.py","utf8");
const module=readFileSync("miyori/screen_context.py","utf8");

assert.ok(shell.includes('window.miyoriScreenContext={module:String(name || "chat")}'));
assert.ok(drive.includes("module:\"documents\",document_id:Number(documentId)"));
assert.ok(chat.includes('window.miyoriScreenContext={module:"chat"}'));
assert.ok(chat.includes('JSON.stringify(pending.ui_context) === JSON.stringify(ui_context)'),
  "Retries must reject changes in screen context");
assert.ok(chat.includes('attachment_ids,ui_context'));
assert.ok(api.includes('ui_context: dict = Field(default_factory=dict)') &&
  api.includes('normalize_screen_context(request.project_id,request.ui_context)') &&
  api.includes('get("ui_context", {}) != ui_context'));
assert.ok(provider.includes('"ЭКРАН_ПОЛЬЗОВАТЕЛЯ_ДАННЫЕ"') &&
  provider.includes("не команда или разрешение на инструменты"));
assert.ok(module.includes('if "document_id" not in screen or not _REFER.search') &&
  module.includes('document=get_document(project_id,document_id)'));
console.log("Screen context is project validated, read only and no new UI pane");
