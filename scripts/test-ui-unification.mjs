import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync("templates/index.html", "utf8");
const workspace = readFileSync("static/js/workspace.js", "utf8");
const settings = readFileSync("static/js/settings.js", "utf8");
const foundation = readFileSync("static/css/foundation.css", "utf8");
const unified = readFileSync("static/css/unified.css", "utf8");

assert.ok(
  html.indexOf("/static/css/unified.css") > html.indexOf("/static/css/nexus.css"),
  "unified UI foundation must load after all legacy module styles",
);

assert.ok(
  html.includes('id="menuSettings"') &&
    html.includes('id="nexusNavSystem"') &&
    html.includes('data-nexus-view="system" type="button" hidden aria-hidden="true" tabindex="-1"'),
  "settings must be visible only inside Дополнительно",
);

assert.ok(
  !html.includes("Проект и разговоры") &&
    html.includes('<div class="workspace-details" hidden aria-hidden="true" role="region" aria-label="История переписки">') &&
    html.includes('id="projectSelect"') &&
    html.includes('id="conversationList"'),
  "legacy project/conversation controls must stay available to runtime but hidden from the UI",
);

assert.ok(
  !workspace.includes("NEXUS · Agents & Actions") &&
    !workspace.includes("NEXUS · Home") &&
    !workspace.includes("NEXUS · Knowledge") &&
    workspace.includes('showWorkspaceShell("actions", "", "Действия", "")') &&
    workspace.includes('showWorkspaceShell("home", "", "Дом", "")'),
  "workspace headers must not expose duplicate technical NEXUS labels",
);

assert.ok(
  settings.includes('showWorkspaceShell("settings", "", "Настройки", "")') &&
    !settings.includes("Общие параметры, система, автоматизация и диагностика."),
  "settings header must not repeat System/Settings labels or generic subtitle",
);

assert.ok(
  foundation.includes("color-scheme: light") &&
    foundation.includes("--bg: #f4f2f7") &&
    unified.includes("width: min(1500px, 100vw)") &&
    unified.includes("grid-template-columns: 292px minmax(0, 1fr)") &&
    unified.includes("max-width: 900px") &&
    unified.includes('html[data-theme="dark"]'),
  "global theme, application width and readable chat width contract are missing",
);

assert.ok(
  unified.includes(".workspace-page-body") &&
    unified.includes("width: min(1100px, 100%)") &&
    unified.includes(".settings-section-card") &&
    unified.includes(".nexus-action-group") &&
    unified.includes(".nexus-home-section"),
  "major modules must share the unified surface system",
);

console.log("Miyori unified UI contract OK.");
