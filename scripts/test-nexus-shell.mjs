import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync("templates/index.html", "utf8");
const workspace = readFileSync("static/js/workspace.js", "utf8");
const shell = readFileSync("static/js/nexus/shell.js", "utf8");
const css = readFileSync("static/css/nexus.css", "utf8");

const views = [...html.matchAll(/data-nexus-view="([^"]+)"/g)].map((match) => match[1]);
assert.deepEqual(
  views,
  ["chat", "actions", "knowledge", "home", "system"],
  "NEXUS primary navigation must stay limited to five stable sections",
);
assert.match(
  html,
  /id="nexusPrimaryNav"[^>]+aria-label="Основные разделы MIYORI NEXUS"/,
);
assert.match(html, /id="nexusNavChat"[^>]+aria-current="page"/);
assert.match(html, /id="nexusRailStatus"[^>]+role="status"[^>]+aria-live="polite"/);
assert.match(html, /id="nexusHeaderStatus"[^>]+aria-label="Состояние проекта"/);
assert.ok(
  !/id="nexusHeaderStatus"[^>]+aria-live=/.test(html),
  "duplicate live regions must not announce the same state twice",
);
assert.match(
  html,
  /<details class="nexus-secondary-details">[sS]*?<summary>Дополнительно</summary>/,
);
assert.ok(!html.includes("\\n"), "template must not contain literal escaped newlines");

assert.ok(
  workspace.includes("async function renderNexusActionsWorkspace()"),
  "Actions workspace renderer is missing",
);
assert.ok(
  workspace.includes('new CustomEvent("miyori:nexus-view"'),
  "legacy workspace must announce NEXUS view changes",
);
assert.ok(
  shell.includes('["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End"]'),
  "keyboard navigation contract is missing",
);
assert.ok(
  shell.includes("new NexusStore"),
  "shell must be driven by the authoritative NEXUS store",
);
assert.ok(!css.includes("@keyframes"), "NEXUS shell must not add decorative keyframe animation");

console.log("NEXUS shell contract OK.");
