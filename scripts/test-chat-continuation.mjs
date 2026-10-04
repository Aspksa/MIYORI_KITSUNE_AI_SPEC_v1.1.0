import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {JSDOM} from "jsdom";
import vm from "node:vm";

const html=readFileSync("templates/index.html","utf8");
const source=readFileSync("static/js/chat-continuation.js","utf8");
const boot=readFileSync("static/js/boot.js","utf8");
const chat=readFileSync("static/js/chat.js","utf8");
const active=readFileSync("static/js/chat-extras.js","utf8");
assert.ok(html.includes('id="chatContinuationDetails"'));
assert.ok(source.includes('"/nexus/actions?limit=80"'));
assert.ok(!source.includes("/workflows/") &&
          !source.includes("/permissions/") &&
          !source.includes('method:"POST"'),
          "A passive chat summary must never resume workflows or approve permissions");
assert.ok(boot.includes("miyoriChatContinuation?.refresh()"));
assert.ok(chat.includes("miyoriChatContinuation?.refresh()"));
assert.ok(active.includes("miyoriChatContinuation?.refresh()"));

const dom=new JSDOM('<section id="chatActivity" hidden>'+
  '<details id="chatContinuationDetails" hidden><summary>'+
  '<strong id="chatContinuationLabel"></strong></summary>'+
  '<div id="chatContinuationItems"></div>'+
  '<button id="chatContinuationOpen"></button></details>'+
  '<div id="chatActivityEvents"></div></section>'+
  '<button id="nexusNavActions">Actions</button>');
const document=dom.window.document;
let clicks=0;let calls=0;let rows=[];
document.getElementById("nexusNavActions").onclick=()=>clicks++;
const state={projectId:7,busy:false};
const context=vm.createContext({
  document,window:dom.window,state,
  api:async(url)=>{
    calls++;assert.equal(url,"/api/projects/7/nexus/actions?limit=80");
    return {actions:rows};
  }
});
vm.runInContext(source,context);
const $=id=>document.getElementById(id);
rows=[
 {project_id:7,state:"waiting_permission",title:"Оплатить контракт",id:"workflow:7"},
 {project_id:7,state:"completed",title:"Завершено",id:"workflow:8"},
 {project_id:8,state:"recovery",title:"Другой проект",id:"workflow:9"},
];
await dom.window.miyoriChatContinuation.refresh();
assert.equal(calls,1);
assert.equal($("chatActivity").hidden,false);
assert.equal($("chatContinuationDetails").hidden,false);
assert.equal($("chatContinuationItems").childElementCount,1);
assert.equal(clicks,0,"Never run tools on initial load");
assert.equal($("chatContinuationDetails").open,false,"Keep compact by default");
$("chatContinuationOpen").click();
assert.equal(clicks,1,"Explicit click opens authoritative Actions");
rows=[];
await dom.window.miyoriChatContinuation.refresh();
assert.equal($("chatContinuationDetails").hidden,true);
assert.equal($("chatActivity").hidden,true);
assert.equal(clicks,1);
console.log("Real-state-only, project-isolated passive chat continuation OK.");
