import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {JSDOM} from "jsdom";
import vm from "node:vm";

const client=readFileSync("static/js/chat-extras.js","utf8");
const core=readFileSync("static/js/core.js","utf8");
const apiSource=readFileSync("app.py","utf8");
assert.ok(core.includes('["correct", "Исправить"]') &&
  core.includes("options.bookmarked"));
assert.ok(apiSource.includes("conversation_feedback_create") &&
  apiSource.includes("relevant_owner_corrections") &&
  apiSource.includes('feedback_context=user_corrections or None'));
const begin=client.indexOf('  function showCorrectionEditor(row) {');
const end=client.indexOf('  $("messages")?.addEventListener(',begin);
assert.ok(begin>0 && end>begin,"Correction editor missing");
const dom=new JSDOM('<article class="message assistant" data-message-id="10">'+
 '<div class="bubble"></div></article>');
const row=dom.window.document.querySelector("article");
const calls=[];const errors=[];
const state={projectId:7,conversationId:11,busy:false};
const context=vm.createContext({
 document:dom.window.document,
 state,
 showError:message=>errors.push(message),
 api:async(url,opts)=>{calls.push({url,body:JSON.parse(opts.body)});return {ok:true};}
});
vm.runInContext(client.slice(begin,end),context);
context.row=row;
vm.runInContext("showCorrectionEditor(row)",context);
const form=row.querySelector("form");
assert.ok(form && !form.hidden,"Editor must open inline");
assert.equal(dom.window.document.querySelectorAll("[role=dialog]").length,0);
form.querySelector("textarea").value="Правильная сумма 150 рублей <img src=x>";
form.dispatchEvent(new dom.window.Event("submit",{cancelable:true,bubbles:true}));
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(calls.length,1);
assert.equal(calls[0].url,
  "/api/projects/7/conversations/11/messages/10/feedback");
assert.equal(calls[0].body.verdict,"corrected");
assert.match(row.textContent,/Поправка сохранена/);
assert.equal(row.querySelector("img"),null,"Text must not inject HTML");
assert.equal(errors.length,0);
vm.runInContext("showCorrectionEditor(row)",context);
assert.equal(form.hidden,false);
state.projectId=8;
form.querySelector("textarea").value="Не тот проект";
form.dispatchEvent(new dom.window.Event("submit",{cancelable:true,bubbles:true}));
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(calls.length,1,"Never save correction in the wrong project");
assert.ok(errors.length>0);
console.log("Inline correction form, project isolation and safe text OK");
