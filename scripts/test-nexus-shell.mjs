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
const secondaryDetailsIndex = html.indexOf('<details class="nexus-secondary-details">');
const secondarySummaryIndex = html.indexOf(
  "<summary>Дополнительно</summary>",
  secondaryDetailsIndex,
);
assert.ok(
  secondaryDetailsIndex >= 0 && secondarySummaryIndex > secondaryDetailsIndex,
  "legacy secondary navigation must stay inside progressive disclosure",
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
  workspace.includes("Preview изменений") &&
    workspace.includes("Evidence") &&
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
  !shell.includes('state === "processing" ? "в работе" : "готово"'),
  "Chat badge must not report ready for degraded/error/not_connected states",
);
assert.ok(
  shell.includes('document.documentElement.dataset.nexusView || "chat"'),
  "shell must preserve a startup view already selected by legacy startup preferences",
);
assert.ok(!css.includes("@keyframes"), "NEXUS shell must not add decorative keyframe animation");

console.log("NEXUS shell contract OK.");
