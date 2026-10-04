import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {JSDOM} from "jsdom";

const html = readFileSync("templates/index.html", "utf8");
const core = readFileSync("static/js/core.js", "utf8");
const chat = readFileSync("static/js/chat.js", "utf8");
const css = readFileSync("static/css/chat-polish.css", "utf8");
const body = readFileSync("frontend/nexus/body.ts", "utf8");
const actions = readFileSync("static/js/workspace.js", "utf8");
const extras = readFileSync("static/js/chat-extras.js", "utf8");

const dom = new JSDOM(html, {url:"http://127.0.0.1/", runScripts:"outside-only"});
const {window} = dom;
const $ = (id) => window.document.getElementById(id);

assert.ok($("messageInput")?.closest("#chatForm"), "input must belong to chat composer");
assert.ok($("composerAttach") && $("voiceButton") && $("sendButton"), "composer must have attachment, voice and send");
assert.ok($("composerAttach").type === "button" && $("sendButton").type === "submit", "composer actions must be operational, not duplicate submit controls");
assert.ok(!$("chatHeader").contains($("nexusBodyHost")), "Owner explicitly removed the header avatar.");
assert.equal(window.document.querySelector(".brand .mark"), null, "Fox logo must be removed beside Miyori.");
assert.ok(window.document.querySelector(".app-shell > #nexusBodyHost"), "Owner's Appearance editor must remain accessible separately.");
assert.ok($("menuSettings")?.closest(".nexus-secondary-details"), "Settings must be in Additional menu");
assert.ok($("menuAppearance")?.closest(".nexus-secondary-details"), "Appearance must have separate menu entry");
assert.ok($("nexusNavSystem")?.hidden, "old Settings primary navigation must be visually hidden");
assert.ok(css.includes(".composer-toolbar") && css.includes(".message-body pre"), "composing and formatted response styles must exist");
assert.ok(body.includes('canon.open = host.dataset.appearanceOpen === "true"'), "appearance must open only by explicit user request");
assert.ok(actions.includes("Сейчас всё спокойно") && !actions.includes("Permission внутри workflow"), "Actions must explain statuses in plain Russian");
assert.ok($("documentInput").accept.includes(".pdf") && $("documentInput").accept.includes(".docx"), "attachment must preserve supported document types");

window.eval(readFileSync("static/vendor/marked.umd.js","utf8"));
window.eval(readFileSync("static/vendor/purify.min.js","utf8"));
assert.equal(typeof window.marked?.parse, "function", "Marked must work offline as a global");
assert.equal(typeof window.DOMPurify?.sanitize, "function", "DOMPurify must work offline as a global");
window.eval(core);

window.addMessage("assistant", "# Заголовок\n\n- **Первое**\n- Второе\n\n\`\`\`python\nprint(1)\n\`\`\`\n\n<script>alert(1)</script>\n\n![remote](https://invalid.test/leak.png)\n\n[bad](javascript:alert(1))");
const message = $("messages").querySelector(".message.assistant .message-body");
assert.ok(message.querySelector("h1") && message.querySelector("ul") && message.querySelector("pre"), "Markdown blocks not rendered");
assert.equal(message.querySelectorAll("script,img,iframe,svg,style").length,0,"unsafe embedded content must be stripped");
assert.ok(!message.querySelector('a[href^="javascript:"]'),"script URL must be stripped");
window.addMessage("user", "<img src=x onerror=alert(1)>");
const userBody = $("messages").querySelector(".message.user .message-body");
assert.equal(userBody.querySelector("img"),null,"user text must remain text");
assert.ok(userBody.textContent.includes("<img"),"user text must remain visible, not execute");

assert.ok(!chat.includes('sendButton.textContent = "Думаю…"'), "icon should never be replaced by busy label");
assert.ok(
  core.includes('commands.push(["tasks", "В задачи"])') &&
    actions.includes("async function openAgentWorkspaceFromChat(goal)") &&
    extras.includes('action === "tasks"') &&
    !extras.includes('"/agent-workspaces"'),
  "chat delegation must prefill the existing Agent Workspace without auto-creating or running it",
);

console.log("Chat composition, offline Markdown and DOMPurify safety OK.");
