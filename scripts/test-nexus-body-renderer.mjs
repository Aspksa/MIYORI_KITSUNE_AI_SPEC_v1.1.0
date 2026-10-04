import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const renderer = readFileSync("frontend/nexus/body_renderer.ts", "utf8");
const body = readFileSync("frontend/nexus/body.ts", "utf8");
const client = readFileSync("frontend/nexus/client.ts", "utf8");
const contracts = readFileSync("frontend/nexus/contracts.ts", "utf8");

assert.ok(
  contracts.includes('BODY_RENDERER_SCHEMA_VERSION = "1.0.0"') &&
    contracts.includes('"neutral_shell"') &&
    contracts.includes('"static_portrait"'),
  "trusted renderer registry types are missing",
);

assert.ok(
  client.includes("trusted_registry_only !== true") &&
    client.includes("arbitrary_renderer_module_allowed !== false") &&
    client.includes("asset_authored_javascript_allowed !== false") &&
    client.includes('unknown_adapter_fallback !== "neutral_shell"'),
  "Digital Body client must fail closed on untrusted renderer contracts",
);

assert.ok(
  renderer.includes("renderTrustedBodyVisual") &&
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
    !body.includes("function buildPortrait("),
  "Digital Body must delegate rendering to the trusted adapter registry",
);

assert.ok(
  !renderer.includes("import(") &&
    !renderer.includes("eval(") &&
    !renderer.includes("new Function") &&
    !renderer.includes("innerHTML") &&
    !renderer.includes("Math.random") &&
    !renderer.includes("setInterval") &&
    !renderer.includes("setTimeout"),
  "renderer registry must not execute asset code or synthesize liveness",
);

console.log("NEXUS Body Renderer Registry contract OK.");
