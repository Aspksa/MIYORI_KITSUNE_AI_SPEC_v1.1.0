import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync("templates/index.html", "utf8");
const ts = readFileSync("frontend/nexus/proactive.ts", "utf8");
const js = readFileSync("static/js/nexus/proactive.js", "utf8");
const client = readFileSync("static/js/nexus/client.js", "utf8");
const surfaces = readFileSync("frontend/nexus/surfaces.ts", "utf8");
const shell = readFileSync("frontend/nexus/shell.ts", "utf8");
const css = readFileSync("static/css/nexus.css", "utf8");

assert.ok(
  html.includes('id="nexusProactiveHost"') &&
    html.includes('aria-label="Ненавязчивые предложения Miyori"'),
  "Proactive inbox host is missing",
);
assert.ok(
  !html.match(/id="nexusProactiveHost"[^>]+aria-live=/),
  "Proactive inbox must not announce itself as an interrupting live region",
);
assert.ok(
  client.includes("fetchNexusProactive") &&
    client.includes("dismissNexusProactive") &&
    client.includes("snoozeNexusProactive"),
  "typed proactive client controls are missing",
);
assert.ok(
  ts.includes("auto_execute_allowed === false") &&
    ts.includes("write_tools_allowed === false") &&
    ts.includes("chat_interruption_allowed === false") &&
    ts.includes("creates_chat_message === false") &&
    ts.includes("requires_explicit_user_action === true"),
  "Proactive renderer must reject unsafe signal policy",
);
assert.ok(
  ts.includes("Позже") &&
    ts.includes("Скрыть") &&
    ts.includes("Отложить на 1 час"),
  "Proactive inbox must expose explicit snooze and dismiss controls",
);
assert.ok(
  !ts.includes("addMessage(") &&
    !js.includes("addMessage(") &&
    !ts.includes(".innerHTML") &&
    !js.includes(".innerHTML"),
  "Proactive Miyori must not inject chat messages or arbitrary HTML",
);
assert.ok(
  !ts.includes("Math.random") &&
    !js.includes("Math.random") &&
    !ts.includes("setInterval") &&
    !js.includes("setInterval"),
  "Proactive Miyori must be state/event-driven, not timer/random driven",
);
assert.ok(
  surfaces.includes("nexusProactiveVisible") &&
    surfaces.includes("miyori:proactive-visibility"),
  "Generative UI must suppress duplicate chat surfaces while proactive inbox is visible",
);
assert.ok(
  shell.includes("last_event_id") &&
    shell.includes("state.events.at(-1)?.id"),
  "Proactive refresh must be able to fingerprint real event changes",
);
assert.ok(
  css.includes("/* N10 — Proactive Miyori.") &&
    !css.includes("@keyframes"),
  "Proactive visual layer must remain quiet and animation-free",
);

console.log("NEXUS Proactive Miyori contract OK.");
