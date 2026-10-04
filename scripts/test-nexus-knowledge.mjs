import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const workspace = readFileSync("static/js/workspace.js", "utf8");
const css = readFileSync("static/css/nexus.css", "utf8");
const client = readFileSync("static/js/nexus/client.js", "utf8");
const contracts = readFileSync("static/js/nexus/contracts.js", "utf8");

assert.ok(
  workspace.includes("async function renderNexusKnowledgeWorkspace()"),
  "N4 Knowledge workspace renderer is missing",
);
assert.ok(
  workspace.includes("/nexus/knowledge?"),
  "Knowledge workspace must read the grouped server contract",
);
assert.ok(
  workspace.includes('role="tablist"') &&
    workspace.includes('role="tab"') &&
    workspace.includes('role="tabpanel"'),
  "Knowledge navigation must expose the WAI-ARIA tabs structure",
);
assert.ok(
  workspace.includes("Память, документы и проверяемые утверждения — рядом, но не смешаны."),
  "Knowledge UI must explain that source domains stay distinct",
);
assert.ok(
  workspace.includes("Происхождение и состояние") &&
    workspace.includes("Evidence и источники") &&
    workspace.includes("Coverage, provenance и exhaustive verification"),
  "Knowledge details must expose provenance, evidence and coverage through disclosure",
);
assert.ok(
  workspace.includes("nexusNavKnowledge.onclick = renderNexusKnowledgeWorkspace"),
  "Primary Knowledge navigation must open N4, not the legacy Drive directly",
);
assert.ok(
  workspace.includes('el("knowledgeOpenDrive").onclick = () => renderDocumentsWorkspace()'),
  "Legacy Drive must remain reachable from Knowledge",
);
assert.ok(
  client.includes("fetchNexusKnowledge") &&
    contracts.includes("NEXUS_KNOWLEDGE_SCHEMA_VERSION"),
  "Typed Knowledge client artifacts are missing",
);
assert.ok(
  css.includes("/* N4 — Knowledge.") &&
    [...css.matchAll(/@keyframes\\s+([a-zA-Z0-9_-]+)/g)].every((match) => ["nexus-rig-active", "nexus-rig-recover", "nexus-rig-speak"].includes(match[1])),
  "Knowledge visual layer must stay semantic and animation-free",
);

console.log("NEXUS Knowledge contract OK.");
