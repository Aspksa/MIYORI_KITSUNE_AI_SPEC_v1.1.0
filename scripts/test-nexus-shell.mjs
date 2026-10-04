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
assert.match(html, /id="nexusHeaderStatus"[^>]+role="status"[^>]+aria-live="polite"/);
const additionalIndex = html.indexOf('<section class="nexus-secondary-details" aria-labelledby="additionalMenuTitle">');
const additionalHeadingIndex = html.indexOf(
  '<h2 id="additionalMenuTitle" class="nexus-secondary-heading">Дополнительно</h2>',
  additionalIndex,
);
assert.ok(
  additionalIndex >= 0 && additionalHeadingIndex > additionalIndex &&
  !html.includes('<summary>Дополнительно</summary>'),
  "Additional must be a permanently visible navigation group, not a disclosure",
);
assert.ok(
  html.indexOf('id="openSystemStatus"') < html.indexOf('id="nexusPrimaryNav"'),
  "System Status must be the first menu action",
);
assert.ok(
  html.indexOf('id="nexusRailStatus"') > html.indexOf('id="systemStatusOverlay"') &&
  html.indexOf('id="systemDocumentCount"') > html.indexOf('id="systemStatusOverlay"') &&
  html.indexOf('id="systemMemoryCount"') > html.indexOf('id="systemStatusOverlay"'),
  "Persistent project health, document and memory counts must live in System Status",
);
assert.ok(!html.includes("\\n"), "template must not contain literal escaped newlines");

assert.ok(
  workspace.includes("async function renderNexusActionsWorkspace()"),
  "Actions workspace renderer is missing",
);
assert.ok(
  workspace.includes("/nexus/actions?limit=80"),
  "Actions workspace must consume the unified authoritative action contract",
);
assert.ok(
  workspace.includes("Что изменится") &&
    workspace.includes("Источники проверки") &&
    workspace.includes("История"),
  "Actions workspace must expose preview, evidence and execution history",
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
assert.ok(
  shell.includes("snapshot.counts.active_actions"),
  "Actions badge must use deduplicated server action counts",
);
assert.ok(
  shell.includes("snapshot.counts.knowledge_attention"),
  "Knowledge badge must use server-derived attention instead of client heuristics",
);
assert.ok(
  !shell.includes('state === "processing" ? "в работе" : "готово"'),
  "Chat badge must not report ready for degraded/error/not_connected states",
);
assert.ok(
  shell.includes('document.documentElement.dataset.nexusView || "chat"'),
  "shell must preserve a startup view already selected by legacy startup preferences",
);
const keyframes = [...css.matchAll(/@keyframes\s+([a-zA-Z0-9_-]+)/g)]
  .map((match) => match[1])
  .sort();
assert.deepEqual(
  keyframes,
  ["miyori-character-recover", "nexus-rig-active", "nexus-rig-recover", "nexus-rig-speak"].sort(),
  "NEXUS shell may only contain the explicit N12.3 state-driven rig keyframes",
);
assert.ok(
  css.includes("@media (prefers-reduced-motion: reduce)"),
  "all N12.3 rig motion must be disabled for reduced-motion users",
);

console.log("NEXUS shell contract OK.");
