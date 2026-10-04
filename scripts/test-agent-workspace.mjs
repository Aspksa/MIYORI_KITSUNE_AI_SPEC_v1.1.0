import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const workspace = readFileSync("static/js/workspace.js", "utf8");
const css = readFileSync("static/css/nexus.css", "utf8");
const client = readFileSync("frontend/nexus/client.ts", "utf8");
const contracts = readFileSync("frontend/nexus/contracts.ts", "utf8");

assert.ok(
  workspace.includes("async function renderNexusAgentWorkspace()"),
  "Agent Workspace renderer is missing",
);
assert.ok(
  workspace.includes("/agent-workspaces") &&
    workspace.includes("data-agent-workspace-run") &&
    workspace.includes("data-agent-workspace-cancel"),
  "Agent Workspace lifecycle controls are missing",
);
assert.ok(
  workspace.includes("два read-only агента параллельно") &&
    workspace.includes("dependency graph") &&
    workspace.includes("step_budget") &&
    workspace.includes("read-only") &&
    workspace.includes("write через разрешение"),
  "Agent Workspace must expose delegation, dependencies and budgets",
);
assert.ok(
  workspace.includes("renderNexusAgentWorkspace") &&
    workspace.includes("Agent Workspace"),
  "Actions must link to the separate Agent Workspace surface",
);
assert.ok(
  client.includes("createNexusAgentWorkspace") &&
    client.includes("runNexusAgentWorkspace") &&
    client.includes("cancelNexusAgentWorkspace"),
  "typed Agent Workspace client is missing",
);
assert.ok(
  contracts.includes("NEXUS_AGENT_WORKSPACE_SCHEMA_VERSION") &&
    contracts.includes("NexusAgentWorkspaceNodeStatus") &&
    contracts.includes('capability: "read_only" | "standard"') &&
    contracts.includes("NexusAgentWorkspaceSummary"),
  "Agent Workspace typed contract is missing",
);
assert.ok(
  !workspace.includes('addMessage("agent"') &&
    !workspace.includes("agent-avatar"),
  "Agent Workspace must not pollute Chat or simulate agents with avatars",
);
assert.ok(
  css.includes("/* N8 — Agent Workspace.") &&
    [...css.matchAll(/@keyframes\s+([a-zA-Z0-9_-]+)/g)].every((match) => ["nexus-rig-active", "nexus-rig-recover", "nexus-rig-speak"].includes(match[1])),
  "Agent Workspace visual layer must stay state-driven and animation-free",
);

console.log("NEXUS Agent Workspace contract OK.");
