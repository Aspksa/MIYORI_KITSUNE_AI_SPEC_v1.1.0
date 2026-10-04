import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const api=readFileSync("app.py","utf8");
const ui=readFileSync("static/js/core.js","utf8");
const verifier=readFileSync("miyori/answer_check.py","utf8");
assert.ok(api.includes("check_numeric_support(") &&
  api.includes('"numeric_check":numeric_check'));
assert.ok(ui.includes('const crosscheck=diagnostics.numeric_check || {}') &&
  ui.includes('line("Сверка чисел"') &&
  ui.includes('crosscheck.missing_source > 0'));
assert.ok(ui.includes('const box=document.createElement("details")') &&
  !ui.includes('id="numericCheckOverlay"'),
  "Diagnostics must stay inside the existing disclosure without a new pane");
assert.ok(verifier.includes('"semantic_fact_verification":False') &&
  verifier.includes('"missing_source":claims-matching'));
console.log("Source-backed numeric check and quiet UI contract OK.");
