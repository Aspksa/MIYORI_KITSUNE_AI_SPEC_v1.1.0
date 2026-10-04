import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync("templates/index.html", "utf8");
const core = readFileSync("static/js/core.js", "utf8");
const ts = readFileSync("frontend/nexus/presence.ts", "utf8");
const js = readFileSync("static/js/nexus/presence.js", "utf8");
const client = readFileSync("static/js/nexus/client.js", "utf8");
const css = readFileSync("static/css/nexus.css", "utf8");

assert.ok(
  html.includes('id="nexusPresenceHost"') &&
    html.includes('aria-label="Текущее состояние Miyori"'),
  "Living Presence host is missing",
);
assert.ok(
  client.includes("fetchNexusPresence"),
  "typed Living Presence client is missing",
);
assert.ok(
  core.includes('new CustomEvent("miyori:interaction-state"') &&
    core.includes('state: value ? "thinking" : "idle"'),
  "Chat must publish real request activity instead of simulated liveness",
);
assert.ok(
  ts.includes('window.addEventListener("miyori:nexus-snapshot"') &&
    ts.includes('window.addEventListener("miyori:interaction-state"'),
  "Presence must derive from real snapshot and interaction events",
);
assert.ok(
  ts.includes('presence.mode === "ready"') &&
    ts.includes("host.hidden = true"),
  "idle Presence must remain visually quiet",
);
assert.ok(
  !ts.includes("Math.random") &&
    !js.includes("Math.random") &&
    !ts.includes("setInterval") &&
    !js.includes("setInterval"),
  "Living Presence must not simulate random or timer-driven life",
);
assert.ok(
  css.includes("/* N9 — Living Presence.") &&
    [...css.matchAll(/@keyframes\s+([a-zA-Z0-9_-]+)/g)].every((match) => ["nexus-rig-active", "nexus-rig-recover", "nexus-rig-speak"].includes(match[1])),
  "Presence styling must remain event-driven and animation-free",
);

console.log("NEXUS Living Presence contract OK.");
