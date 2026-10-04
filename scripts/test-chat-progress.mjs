import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const app=readFileSync("app.py","utf8");
const progress=readFileSync("miyori/chat_progress.py","utf8");
const chat=readFileSync("static/js/chat.js","utf8");
const extras=readFileSync("static/js/chat-extras.js","utf8");

for (const stage of ["accepted","agent","retrieving","generating","verifying","completed","error"]) {
  assert.ok(progress.includes('"'+stage+'"'), "missing real stage "+stage);
}
assert.ok(app.includes('/chat/progress/{request_id}') &&
  app.includes('set_chat_progress('));
assert.ok(chat.includes("miyoriChatActivity?.begin(requestId)"));
assert.ok(extras.includes("/chat/progress/") &&
  extras.includes("miyori:chat-progress") &&
  extras.includes("progressLabels"));
assert.ok(!extras.includes("Math.random") &&
  !extras.includes("fakeProgress"));

console.log("Real chat request progress contract OK.");
