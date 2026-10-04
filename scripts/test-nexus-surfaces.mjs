import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync("templates/index.html", "utf8");
const ts = readFileSync("frontend/nexus/surfaces.ts", "utf8");
const js = readFileSync("static/js/nexus/surfaces.js", "utf8");
const client = readFileSync("static/js/nexus/client.js", "utf8");
const shell = readFileSync("static/js/nexus/shell.js", "utf8");
const css = readFileSync("static/css/nexus.css", "utf8");

assert.ok(
  html.includes('id="nexusSurfaceHost"') &&
    html.includes('aria-label="Структурный контекст Miyori"'),
  "trusted Generative UI host is missing",
);
assert.ok(
  ts.includes("const SURFACE_REGISTRY") &&
    ts.includes("status_summary") &&
    ts.includes("action_card") &&
    ts.includes("progress_card") &&
    ts.includes("knowledge_attention") &&
    ts.includes("result_collection"),
  "surface registry must be closed and explicit",
);
assert.ok(
  !ts.includes(".innerHTML") && !js.includes(".innerHTML"),
  "surface renderer must never inject model/backend data through innerHTML",
);
assert.ok(
  ts.includes("textContent") &&
    ts.includes("trusted_component_only") &&
    ts.includes("model_html_allowed === false") &&
    ts.includes("script_allowed === false"),
  "surface renderer must validate trusted-component policy",
);
assert.ok(
  client.includes("fetchNexusSurfaces") &&
    client.includes("unknown_components_rejected"),
  "typed surface client contract is missing",
);
assert.ok(
  shell.includes('new CustomEvent("miyori:nexus-snapshot"'),
  "surface host must be driven by authoritative snapshot changes",
);
assert.ok(
  css.includes("/* N7 — trusted Generative UI.") &&
    [...css.matchAll(/@keyframes\s+([a-zA-Z0-9_-]+)/g)].every((match) => ["miyori-character-recover", "nexus-rig-active", "nexus-rig-recover", "nexus-rig-speak"].includes(match[1])),
  "Generative UI styling must remain quiet and animation-free",
);

console.log("NEXUS trusted Generative UI contract OK.");
