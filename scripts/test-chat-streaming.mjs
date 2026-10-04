import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const provider=readFileSync("miyori/provider.py","utf8");
const app=readFileSync("app.py","utf8");
const chat=readFileSync("static/js/chat.js","utf8");
const core=readFileSync("static/js/core.js","utf8");
const progress=readFileSync("miyori/chat_progress.py","utf8");

assert.ok(
  provider.includes('"stream": True') &&
  provider.includes('"stream_options": {"include_usage": True}') &&
  provider.includes("aiter_lines()") &&
  provider.includes("await stream_sink(piece)"),
  "Cloud.ru streaming must forward real provider chunks instead of fake timers.",
);
assert.ok(
  app.includes('@app.post("/api/chat/stream")') &&
  app.includes("StreamingResponse") &&
  app.includes('media_type="application/x-ndjson"') &&
  app.includes('"partial": True') &&
  app.includes('"stopped_by_user": True'),
  "Streaming endpoint must persist stopped partial output and preserve JSON endpoint compatibility.",
);
assert.ok(
  chat.includes('fetch("/api/chat/stream"') &&
  chat.includes("response.body.getReader()") &&
  chat.includes("new TextDecoder()") &&
  chat.includes("new AbortController()") &&
  chat.includes("state.streamController.abort()"),
  "Chat UI must consume real NDJSON chunks and support Stop generation.",
);
assert.ok(
  core.includes('"Остановить ответ"') &&
  progress.includes('"cancelled"'),
  "Busy UI and request progress must expose explicit cancellation.",
);
assert.ok(
  !chat.includes("setInterval(() => stream") &&
  !chat.includes("fakeStreaming"),
  "Streaming must not simulate token arrival.",
);

console.log("Real Cloud.ru streaming contract OK.");
