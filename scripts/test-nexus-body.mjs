import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const body = readFileSync("frontend/nexus/body.ts", "utf8");
const contracts = readFileSync("frontend/nexus/contracts.ts", "utf8");
const client = readFileSync("frontend/nexus/client.ts", "utf8");
const css = readFileSync("static/css/nexus.css", "utf8");
const template = readFileSync("templates/index.html", "utf8");

assert.ok(
  template.includes('id="nexusBodyHost"') &&
    body.includes("installNexusDigitalBody"),
  "Digital Body mount/runtime is missing",
);

assert.ok(
  body.includes('window.addEventListener("miyori:voice-state"') &&
    body.includes('window.addEventListener("miyori:interaction-state"') &&
    body.includes('window.addEventListener("miyori:nexus-snapshot"'),
  "Digital Body must react only to authoritative/local runtime events",
);

assert.ok(
  body.includes("fetchNexusBody") &&
    client.includes("/nexus/body") &&
    client.includes("runtime truth contract"),
  "typed Digital Body API contract is missing",
);

assert.ok(
  contracts.includes("NEXUS_BODY_SCHEMA_VERSION") &&
    contracts.includes("NexusBodyLocalState") &&
    contracts.includes("appearance_unconfigured") &&
    contracts.includes("presence_plus_explicit_local_runtime"),
  "Digital Body types must preserve canon and runtime source",
);

assert.ok(
  client.includes("random_liveness_allowed !== false") &&
    client.includes("timer_idle_animation_allowed !== false") &&
    client.includes("sentiment_to_expression_allowed !== false") &&
    client.includes("model_authored_motion_allowed !== false"),
  "Digital Body client must fail closed on fake liveness policies",
);

assert.ok(
  body.includes("createElement") &&
    body.includes("textContent") &&
    !body.includes("innerHTML"),
  "Digital Body renderer must use trusted DOM construction",
);

assert.ok(
  body.includes("Оставлено на ваш выбор") &&
    body.includes("цвет волос, глаз, число хвостов или наряд"),
  "Digital Body must disclose unresolved owner appearance choices",
);

assert.ok(
  !body.includes("Math.random") &&
    !body.includes("setInterval") &&
    !body.includes("setTimeout"),
  "Digital Body must not synthesize idle liveness with timers/randomness",
);

assert.ok(
  css.includes("/* N12 — Digital Body Runtime.") &&
    css.includes("@keyframes nexus-rig-active") &&
    css.includes("@media (prefers-reduced-motion: reduce)"),
  "Digital Body motion must stay contract-driven and respect reduced motion",
);

assert.ok(
  css.includes('[data-pose="listen"]') &&
    css.includes('[data-gesture="speak"]') &&
    css.includes('[data-state="recovery"]'),
  "Digital Body must visibly distinguish meaningful runtime states",
);

console.log("NEXUS Digital Body contract OK.");
