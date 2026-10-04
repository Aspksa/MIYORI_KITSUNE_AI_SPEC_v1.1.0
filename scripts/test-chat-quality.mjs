import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const core=readFileSync("static/js/core.js","utf8");
const api=readFileSync("app.py","utf8");
const metrics=readFileSync("miyori/chat_metrics.py","utf8");

assert.ok(api.includes('/api/projects/{project_id}/chat/quality') &&
  api.includes("chat_quality_summary"));
assert.ok(metrics.includes('"quality_accuracy_measured": False') &&
  metrics.includes("numeric_claims_missing_source") &&
  metrics.includes("responses_with_sources"));
assert.ok(core.includes("Качество чата за 30 дней") &&
  core.includes("/chat/quality?days=30") &&
  core.includes("Это измерения, не процент точности."));
assert.ok(!metrics.includes('"accuracy_percent"') &&
  !core.includes("accuracy_percent"));

console.log("Measured chat quality contract OK.");
