import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const client=readFileSync("static/js/command-center.js","utf8");
const css=readFileSync("static/css/command-center.css","utf8");
const drive=readFileSync("static/js/drive.js","utf8");
const workspace=readFileSync("static/js/workspace.js","utf8");
const html=readFileSync("templates/index.html","utf8");

assert.ok(
  html.includes("command-center.css") && html.includes("command-center.js"),
  "Command Center assets must load.",
);
for (const token of [
  'event.key.toLowerCase()==="k"',
  "commandCenterResults",
  'role="dialog"',
  'role="listbox"',
  "ArrowDown",
  "ArrowUp",
  "openConversation",
  "miyoriOpenDocument",
  "miyoriOpenNexusAction",
  "/nexus/actions?limit=80",
  "/chat/search?q=",
]) assert.ok(client.includes(token), "missing Command Center contract: "+token);

assert.ok(
  drive.includes("window.miyoriOpenDocument") &&
  workspace.includes("window.miyoriOpenNexusAction"),
  "Command Center must reuse existing Documents and Actions workspaces.",
);
assert.ok(
  !client.includes("/tools/execute") &&
  !client.includes("permission/approve"),
  "Command Center navigation must never bypass tool permissions.",
);
assert.ok(
  css.includes("prefers-reduced-motion"),
  "Command Center must honor reduced-motion preferences.",
);

console.log("Ctrl+K Command Center contract OK.");
