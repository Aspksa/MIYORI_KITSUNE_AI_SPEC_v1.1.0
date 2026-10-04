import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const html=readFileSync("templates/index.html","utf8");
const client=readFileSync("static/js/chat.js","utf8");
const extra=readFileSync("static/js/chat-extras.js","utf8");
const api=readFileSync("app.py","utf8");

assert.ok(!html.includes('<div class="mark"'),"Top sidebar fox icon must not return.");
assert.ok(!/<header class="chat-header"[\s\S]*?id="nexusBodyHost"/.test(
  html.match(/<header class="chat-header"[\s\S]*?<\/header>/)?.[0] || ""
),"No assistant avatar is allowed next to the Miyori title.");
assert.ok(
  extra.includes("window.miyoriForkReadOnly = true") &&
  extra.includes("state.pendingRequest = null") &&
  client.includes("read_only: readOnly") &&
  client.includes("window.miyoriForkReadOnly = false"),
  "An edited or regenerated turn must be explicitly read-only.",
);
assert.ok(
  client.includes("pending.conversationId === state.conversationId") &&
  client.includes("JSON.stringify(pending.attachment_ids)") &&
  client.includes("pending.projectId === state.projectId"),
  "Retry must never reuse an idempotency key for another project, conversation or files.",
);
assert.ok(
  client.includes("if (userRow) userRow.remove()") &&
  client.includes("input.value = text") &&
  client.includes("state.pendingRequest = null"),
  "Failed responses must retain the text and same-key recovery path.",
);
assert.ok(
  api.includes('read_only: bool = False') &&
  api.includes('use_tools=False') &&
  api.includes('safe_read_only_fork') &&
  api.includes('None if request.read_only') &&
  api.includes('(existing_message.get("metadata") or {}).get("read_only"'),
  "Server must enforce read-only regeneration independent of browser state.",
);
console.log("Fork action safety and idempotent recovery contract OK.");
