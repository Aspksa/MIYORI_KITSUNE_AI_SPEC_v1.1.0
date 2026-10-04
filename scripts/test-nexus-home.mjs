import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const workspace = readFileSync("static/js/workspace.js", "utf8");
const css = readFileSync("static/css/nexus.css", "utf8");
const client = readFileSync("frontend/nexus/client.ts", "utf8");
const contracts = readFileSync("frontend/nexus/contracts.ts", "utf8");
const shell = readFileSync("frontend/nexus/shell.ts", "utf8");

assert.ok(
  workspace.includes("async function renderNexusHomeWorkspace()") &&
    workspace.includes("/nexus/home"),
  "NEXUS Home workspace is missing",
);
assert.ok(
  workspace.includes("authenticated heartbeat") &&
    workspace.includes("Legacy status") &&
    workspace.includes("Heartbeat TTL"),
  "Home UI must explain evidence semantics",
);
assert.ok(
  workspace.includes("showNexusHomeCredential") &&
    workspace.includes("code.textContent = credential") &&
    !workspace.includes("innerHTML = credential"),
  "one-time Home credential must never be injected as HTML",
);
assert.ok(
  workspace.includes("ready_for_device_agent") &&
    workspace.includes("Binding не означает OS-level enforcement"),
  "parental binding must not claim enforcement",
);
assert.ok(
  workspace.includes("nexusNavHome.onclick = renderNexusHomeWorkspace"),
  "primary Home navigation must open NEXUS Home",
);
assert.ok(
  client.includes("fetchNexusHome") &&
    client.includes('connectivity_source !== "authenticated_heartbeat"') &&
    client.includes("legacy_status_is_connectivity_source !== false") &&
    client.includes("parental_rules_applied_by_server !== false"),
  "typed Home evidence contract is missing",
);
assert.ok(
  contracts.includes("NEXUS_HOME_SCHEMA_VERSION") &&
    contracts.includes("NexusHomeConnectivityState") &&
    contracts.includes("parental_rules_require_explicit_binding: true"),
  "Home types must preserve evidence and binding semantics",
);
assert.ok(
  shell.includes("snapshot.counts.home_linked") &&
    shell.includes("snapshot.counts.home_online"),
  "Home nav must be driven by server connectivity counts",
);
assert.ok(
  !workspace.includes('addMessage("home"') &&
    !workspace.includes("home-waveform") &&
    !workspace.includes("Math.random"),
  "Home must not pollute Chat or simulate device activity",
);
assert.ok(
  css.includes("/* N11 — Home Runtime.") &&
    [...css.matchAll(/@keyframes\\s+([a-zA-Z0-9_-]+)/g)].every((match) => ["nexus-rig-active", "nexus-rig-recover", "nexus-rig-speak"].includes(match[1])),
  "Home UI must remain state-driven and animation-free",
);

console.log("NEXUS Home contract OK.");
