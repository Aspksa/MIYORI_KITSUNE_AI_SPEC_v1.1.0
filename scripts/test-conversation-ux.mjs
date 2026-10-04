import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const html=readFileSync("templates/index.html","utf8");
const client=readFileSync("static/js/conversation-ux.js","utf8");
const css=readFileSync("static/css/conversation-ux.css","utf8");
const app=readFileSync("app.py","utf8");
const backend=readFileSync("miyori/conversation_experience.py","utf8");
const chat=readFileSync("static/js/chat.js","utf8");
const extras=readFileSync("static/js/chat-extras.js","utf8");

assert.ok(html.includes("conversation-ux.css") &&
  html.includes("conversation-ux.js"), "Conversation UX assets must load.");

for (const token of [
  "setReply(row)",
  "create_topic",
  "conversationTopicSelect",
  "conversation-pins",
  "conversationFolderSelect",
  "conversation-reaction",
  "conversation-checklist",
  "conversation-rich-toolbar",
  "MediaRecorder",
  "chatSearchScope",
  "unread-divider",
  "chooseRoute(row)",
  "chatSchedulePanel",
  "remember_message_candidate",
]) {
  assert.ok(
    client.includes(token) || backend.includes(token) || css.includes(token),
    "missing conversation UX contract: "+token
  );
}

assert.ok(
  backend.includes('"semantic_embeddings": False') &&
  backend.includes("chat_ranked_lexical") &&
  backend.includes("rag_retrieve"),
  "Search must disclose lexical fallback and reuse existing RAG instead of claiming fake semantics.",
);
assert.ok(
  client.includes("Проверьте формулировку перед сохранением") &&
  app.includes("/messages/{message_id}/remember") &&
  backend.includes('status="candidate"'),
  "Remember reaction must require preview and create only a candidate memory.",
);
assert.ok(
  backend.includes("chat_message_routes") &&
  backend.includes("_ALLOWED_ROUTES") &&
  client.includes('["new_chat", "saved", "knowledge", "documents", "tasks", "agent"]') === false,
  "Message routing must use a backend allowlist rather than executable model-authored actions.",
);
assert.ok(
  backend.includes("chat_scheduled_messages") &&
  client.includes("composerFree") &&
  client.includes("auto_send"),
  "Scheduled requests must not overwrite an active draft.",
);
assert.ok(
  backend.includes("chat_voice_notes") &&
  client.includes("MediaRecorder") &&
  client.includes("SpeechRecognition"),
  "Voice notes must persist real audio and only use browser STT when available.",
);
assert.ok(
  chat.includes("reply_to_message_id") &&
  chat.includes("voice_note_id") &&
  app.includes("reply_context(") &&
  app.includes("validate_topic("),
  "Reply/topic/voice context must be part of server-validated chat idempotency.",
);
assert.ok(
  extras.includes("miyoriConversationUX?.searchRequest") &&
  client.includes("renderUnifiedSearch"),
  "Existing chat search must integrate the scoped project search without a second search shell.",
);
assert.ok(
  css.includes("@media(prefers-reduced-motion:reduce)") ||
  css.includes("@media (prefers-reduced-motion: reduce)"),
  "Conversation UX must respect reduced motion.",
);

console.log("Conversation UX 14-feature contract OK.");
