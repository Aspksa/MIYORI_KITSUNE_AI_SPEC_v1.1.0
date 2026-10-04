import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {JSDOM} from "jsdom";

const html = readFileSync("templates/index.html","utf8");
const core = readFileSync("static/js/core.js","utf8");
const js = readFileSync("static/js/chat-extras.js","utf8");
const chat = readFileSync("static/js/chat.js","utf8");
const css = readFileSync("static/css/chat-extras.css","utf8");
const api = readFileSync("app.py","utf8");

const {window} = new JSDOM(html,{url:"http://127.0.0.1/",runScripts:"outside-only"});
const doc = window.document;
const $ = id => doc.getElementById(id);
assert.equal(doc.querySelector(".brand .mark"),null,"The unwanted fox logo must be entirely removed.");
assert.ok(!$("chatHeader").contains($("nexusBodyHost")), "No header avatar beside Miyori.");
assert.ok($("nexusBodyHost") && doc.querySelector(".app-shell > #nexusBodyHost"),
  "Appearance runtime must remain available outside the visible chat header.");
assert.ok($("chatAttachments") && $("chatSearchPanel") && $("chatActivity"));
assert.ok($("conversationSearch") && $("savedAnswersButton"));

window.state = {projectId:42,conversationId:null,busy:false};
window.showError = msg => {window.lastError = msg};
window.loadDocuments = async () => {};
window.loadConversations = async () => {};
window.showWelcome = () => {};
window.openConversation = async () => {};
window.api = async () => ({});
window.fetch = async () => ({
  ok: true,
  json: async () => ({document:{id:35},chunk_count:2,indexed:true})
});
window.eval(js);
assert.ok($("composerFileInput").multiple, "Composer must allow multiple files.");
assert.ok(window.miyoriChatAttachments, "Staged per-message upload is unavailable.");
const file = new window.File(["Hello"],"contract.docx",{type:"application/vnd.openxmlformats-officedocument.wordprocessingml.document"});
window.miyoriChatAttachments.queueFiles([file]);
const ready = await window.miyoriChatAttachments.ready();
assert.deepEqual(Array.from(ready,x=>Number(x.id)),[35]);
assert.equal($("chatAttachments").hidden,false);
assert.match($("chatAttachments").textContent,/contract.docx/);
assert.match($("chatAttachments").textContent,/Прикреплено/);
window.miyoriChatAttachments.clear();
assert.equal($("chatAttachments").hidden,true);
window.miyoriChatAttachments.useExisting([{id:35,filename:"existing.docx"}]);
assert.deepEqual(Array.from(await window.miyoriChatAttachments.ready(),x=>Number(x.id)),[35]);
window.state.projectId=43;
await assert.rejects(() => window.miyoriChatAttachments.ready(), /Проект изменился/);
window.state.projectId=42;
window.miyoriChatAttachments.clear();

$("messageInput").value="Мой черновик";
window.miyoriDrafts.save();
$("messageInput").value="";
window.miyoriDrafts.restore();
assert.equal($("messageInput").value,"Мой черновик");

assert.ok(core.includes("dataChatAction") || core.includes("data.chatAction") || core.includes("dataset.chatAction"),
  "Each message must have accessible action toolbar.");
for(const command of ["edit","retry","save","copy-code","copy"]){
  assert.ok(core.includes('"' + command + '"'), "Missing message action: " + command);
}
assert.ok(chat.includes("before_id=") && chat.includes("chatWindow"),
  "History must use bounded server-side pagination.");
assert.ok(chat.includes("attachment_ids"),
  "Attachments must reach the chat endpoint, not just global project storage.");
assert.ok(css.includes("search-hit") && css.includes("older-messages-button"),
  "Search and pagination styling missing.");
assert.ok(api.includes("init_conversation_ui_db()") &&
          api.includes('attachment_ids: list[int]') &&
          api.includes("attached_document_context"),
 "API must validate per-question files and keep project scope.");

console.log("00.00.61 chat capabilities and owner-requested logo removal OK.");
