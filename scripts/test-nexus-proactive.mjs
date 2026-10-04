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
    client.includes("snoozeNexusProactive") &&
    client.includes("/nexus/proactive/decision") &&
    client.includes("signal_key") &&
    client.includes("fingerprint") &&
    !client.includes("/nexus/proactive/${encodeURIComponent(signalId)}/dismiss") &&
    !client.includes("/nexus/proactive/${encodeURIComponent(signalId)}/snooze"),
  "typed proactive client must use the canonical fingerprint decision endpoint",
);
assert.ok(
  ts.includes("page.display.chat_shelf_ids") &&
    ts.includes('signal.channel_owner === "attention_shelf"') &&
    ts.includes("signal.safety?.executes_action === false") &&
    ts.includes("signal.safety?.changes_domain_state === false") &&
    ts.includes("signal.safety?.requires_existing_permission_flow === true"),
  "Proactive renderer must show only budgeted advisory signals with safe policy",
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
    !js.includes("setInterval") &&
    ts.includes("next_wakeup_at") &&
    ts.includes("window.setTimeout"),
  "Proactive Miyori may only schedule a one-shot snooze wakeup, never simulated liveness",
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
    [...css.matchAll(/@keyframes\s+([a-zA-Z0-9_-]+)/g)].every((match) => ["miyori-character-recover", "nexus-rig-active", "nexus-rig-recover", "nexus-rig-speak"].includes(match[1])),
  "Proactive visual layer must remain quiet and animation-free",
);

console.log("NEXUS Proactive Miyori contract OK.");
