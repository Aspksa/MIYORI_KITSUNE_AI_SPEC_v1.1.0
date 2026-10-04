import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

const core=readFileSync("static/js/core.js","utf8");
const data=readFileSync("static/js/data.js","utf8");
const boot=readFileSync("static/js/boot.js","utf8");
const feedback=readFileSync("miyori/chat_feedback.py","utf8");
const start=core.indexOf("const inflightApiReads = new Map();");
const end=core.indexOf("async function loadStatus()",start);
assert.ok(start>0 && end>start);
let calls=[];
let gate=[];
const fetch=async(url,options)=>{
  calls.push([url,options?.method||"GET"]);
  await new Promise(resolve=>gate.push(resolve));
  return {ok:true,json:async()=>({url,calls:calls.length})};
};
const context=vm.createContext({fetch,Map,Error,JSON,String,Object});
vm.runInContext(core.slice(start,end),context);
const api=context.api;
let a=api("/api/projects/1/status");
let b=api("/api/projects/1/status");
assert.equal(calls.length,1,"Concurrent identical GET should share one fetch");
gate.shift()();
let output=await Promise.all([a,b]);
assert.equal(output[0].url,"/api/projects/1/status");
assert.equal(calls.length,1);
let c=api("/api/projects/1/status");
assert.equal(calls.length,2,"Completed GET must never remain cached");
gate.shift()();
await c;

const p1=api("/api/projects/1/status");
const p2=api("/api/projects/2/status");
assert.equal(calls.length,4,"Distinct projects must not share responses");
gate.splice(0).forEach(fn=>fn());
await Promise.all([p1,p2]);

const m1=api("/api/projects/1/status",{method:"POST"});
const m2=api("/api/projects/1/status",{method:"POST"});
assert.equal(calls.length,6,"Mutating requests must never be merged");
gate.splice(0).forEach(fn=>fn());
await Promise.all([m1,m2]);

const signal=({signal:{aborted:false}});
const withSignal=api("/api/projects/1/status",signal);
const withoutSignal=api("/api/projects/1/status");
assert.equal(calls.length,8,"Abortable fetch must not share no-signal GET");
gate.splice(0).forEach(fn=>fn());
await Promise.all([withSignal,withoutSignal]);

assert.ok(data.includes("await Promise.allSettled([loadConversations(),loadNexus()])") &&
  data.includes("if(Number(state.projectId)!==selectedProject)return"));
assert.ok(boot.includes("await Promise.allSettled([") &&
  boot.includes("loadStatus(),loadModuleVersions(),loadProjects()"));
assert.ok(feedback.includes("init_chat_feedback_db()") &&
  feedback.includes("def relevant_owner_corrections("),
  "Feedback must work in both FastAPI and direct test/worker contexts");
console.log("Fast bootstrap, project-safe GET coalescing, no mutation caching OK.");
