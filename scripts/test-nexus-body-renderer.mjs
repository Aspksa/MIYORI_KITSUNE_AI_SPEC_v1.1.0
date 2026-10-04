import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const renderer = readFileSync("frontend/nexus/body_renderer.ts", "utf8");
const body = readFileSync("frontend/nexus/body.ts", "utf8");
const client = readFileSync("frontend/nexus/client.ts", "utf8");
const contracts = readFileSync("frontend/nexus/contracts.ts", "utf8");
const css = readFileSync("static/css/nexus.css", "utf8");

assert.ok(
  contracts.includes('BODY_RENDERER_SCHEMA_VERSION = "1.1.0"') &&
    contracts.includes('"neutral_shell"') &&
    contracts.includes('"static_portrait"') &&
    contracts.includes('"trusted_vector_rig"'),
  "trusted renderer registry types are missing",
);

assert.ok(
  client.includes("trusted_registry_only !== true") &&
    client.includes("arbitrary_renderer_module_allowed !== false") &&
    client.includes("asset_authored_javascript_allowed !== false") &&
    client.includes('unknown_adapter_fallback !== "neutral_shell"') &&
    client.includes('adapter_id !== "trusted_vector_rig"'),
  "Digital Body client must validate the installed trusted dynamic renderer",
);

assert.ok(
  renderer.includes("renderTrustedBodyVisual") &&
    renderer.includes("renderTrustedVectorRig") &&
    renderer.includes('case "trusted_vector_rig"') &&
    renderer.includes('case "static_portrait"') &&
    renderer.includes('case "neutral_shell"') &&
    renderer.includes("renderNeutralShell"),
  "frontend trusted renderer registry is incomplete",
);

assert.ok(
  renderer.includes('asset.kind !== "static_portrait" || !asset.url') &&
    renderer.includes("return renderNeutralShell"),
  "static portrait adapter must fall back to neutral shell on missing asset",
);

assert.ok(
  body.includes('import { renderTrustedBodyVisual } from "./body_renderer.js"') &&
    body.includes("renderTrustedBodyVisual(body, presentation, effectiveState)") &&
    body.includes("Динамическое тело активно") &&
    !body.includes("function buildPortrait("),
  "Digital Body must delegate rendering to the trusted dynamic adapter registry",
);

assert.ok(
  css.includes(".nexus-body-vector-rig") &&
    css.includes('data-gesture="speak"') &&
    css.includes("@media (prefers-reduced-motion: reduce)"),
  "trusted vector rig motion CSS is missing or does not respect reduced motion",
);

assert.ok(
  !renderer.includes("import(") &&
    !renderer.includes("eval(") &&
    !renderer.includes("new Function") &&
    !renderer.includes("innerHTML") &&
    !renderer.includes("Math.random") &&
    !renderer.includes("setInterval") &&
    !renderer.includes("setTimeout"),
  "renderer registry must not execute asset code or synthesize timer-driven liveness",
);

console.log("NEXUS Real Dynamic Renderer contract OK.");
