import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {JSDOM} from "jsdom";

const html=readFileSync("templates/index.html","utf8");
const core=readFileSync("static/js/core.js","utf8");
const chat=readFileSync("static/js/chat.js","utf8");
const css=readFileSync("static/css/chat-insights.css","utf8");
const app=readFileSync("app.py","utf8");
const {window}=new JSDOM(html,{runScripts:"outside-only",url:"http://127.0.0.1/"});
const $=(id)=>window.document.getElementById(id);
assert.equal(window.document.querySelector(".brand .mark"),null);
assert.ok(!$("chatHeader").contains($("nexusBodyHost")));
assert.ok(css.includes(".chat-answer-insights"));
assert.ok(core.includes("sources_available_not_fact_checked"));
assert.ok(chat.includes("diagnostics: item.metadata?.diagnostics"));
assert.ok(chat.includes("diagnostics:data.diagnostics"));
assert.ok(app.includes("plan_chat_query("));
assert.ok(app.includes("store_model_usage("));

window.eval(readFileSync("static/vendor/marked.umd.js","utf8"));
window.eval(readFileSync("static/vendor/purify.min.js","utf8"));
window.eval(core);
window.addMessage("assistant","**Ответ**",[],{
  diagnostics:{
    plan:{mode:"deep"},
    evidence:{status:"sources_available_not_fact_checked",source_count:2},
    retrieval_ms:11,
    model_usage:{latency_ms:320,total_tokens:120}
  }
});
const details=$("messages").querySelector("details.chat-answer-insights");
assert.ok(details && !details.open,"Diagnostics should be closed by default");
assert.match(details.textContent,/не гарантированы/);
assert.match(details.textContent,/320/);
assert.ok(!$("messages").querySelectorAll(".chat-answer-insights").length===false);
console.log("Chat Intelligence minimal diagnostics UI contract OK.");
