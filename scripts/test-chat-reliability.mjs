import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {JSDOM} from "jsdom";

const html=readFileSync("templates/index.html","utf8");
const core=readFileSync("static/js/core.js","utf8");
const chat=readFileSync("static/js/chat.js","utf8");
const source=readFileSync("static/js/chat-continuation.js","utf8");
const css=readFileSync("static/css/chat-insights.css","utf8");

assert.ok(chat.includes("const refresh=[loadConversations(),loadNexus()]"),
 "Simple requests must not reload all heavy modules.");
assert.ok(chat.includes("Promise.allSettled(refresh)"),
 "A failed status fetch must not report a persisted answer as failed.");
assert.ok(chat.includes("Ответ сохранён."),
 "Refresh failure should show truth without touching send state.");
assert.ok(core.includes("window.miyoriChatContinuation?.refresh()"),
 "Persisted comparisons must trigger status refresh, not background writes.");
assert.ok(!source.includes('method:"POST"'),"Status component may not write.");
assert.ok(css.includes(".chat-usage-details-button"));
assert.equal((html.match(/id="chatActivity"/g)||[]).length,1,
 "Only one activity panel should exist.");
assert.equal((html.match(/id="chatContinuationDetails"/g)||[]).length,1);
const {window}=new JSDOM(html,{url:"http://127.0.0.1/",runScripts:"outside-only"});
window.eval(readFileSync("static/vendor/marked.umd.js","utf8"));
window.eval(readFileSync("static/vendor/purify.min.js","utf8"));
window.eval(core+"\nwindow.__metricsTest={setProject(id){state.projectId=id},setApi(fn){api=fn}};");
window.__metricsTest.setProject(7);
const requests=[];
window.__metricsTest.setApi(async(url)=>{requests.push(url);return {
 requests:10,measured_requests:9,total_tokens:2000,
 estimated_cost_rub:null
};});
window.addMessage("assistant","Готово",[],{
 diagnostics:{
  plan:{mode:"deep"},evidence:{source_count:2,status:"sources_available_not_fact_checked"},
  model_usage:{total_tokens:50,latency_ms:210}
 }
});
const details=window.document.querySelector(".chat-answer-insights");
assert.ok(details && !details.open);
const button=details.querySelector(".chat-usage-details-button");
assert.ok(button);
assert.equal(requests.length,0,"Never fetch diagnostics without user click.");
button.click();
await new Promise(resolve=>setTimeout(resolve,0));
assert.deepEqual(requests,["/api/projects/7/chat/metrics?days=30"]);
assert.match(details.textContent,/стоимость неизвестна/);
assert.match(details.textContent,/2000/);
assert.equal(window.document.querySelector(".brand .mark"),null,
 "Removed top fox logo must stay absent.");
assert.ok(!window.document.getElementById("chatHeader")
 .contains(window.document.getElementById("nexusBodyHost")));
console.log("Chat reliability, real status and opt-in metrics UI OK.");
