import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {JSDOM} from "jsdom";
import vm from "node:vm";

const html=readFileSync("templates/index.html","utf8");
const ts=readFileSync("frontend/nexus/shell.ts","utf8");
const shell=readFileSync("static/js/nexus/shell.js","utf8");
const css=readFileSync("static/css/menu-system.css","utf8");
const doc=new JSDOM(html).window.document;
const $=id=>doc.getElementById(id);
const rail=doc.querySelector(".left-rail");
const buttons=[...rail.querySelectorAll("button")];
assert.equal(buttons[0].id,"openSystemStatus");
assert.ok(!rail.querySelector("details.nexus-secondary-details"),
  "Additional cannot collapse or hide navigation");
assert.ok(rail.querySelector("#additionalMenuTitle") &&
  rail.querySelector("#menuMiyoriAI") &&
  rail.querySelector("#menuSettings") &&
  rail.querySelector("#menuProjectUpdate"));
assert.equal($("nexusRailStatus")?.closest("#systemStatusOverlay")?.id,
  "systemStatusOverlay");
assert.equal($("systemDocumentCount")?.textContent,"—");
assert.equal($("systemMemoryCount")?.textContent,"—");
assert.ok(!rail.contains($("nexusRailStatus")));
assert.ok(css.includes("html[data-theme=\"dark\"]"),"Dark theme missing");
for(const source of [ts,shell]){
  for(const term of [
    'setText("systemDocumentCount", String(Number(snapshot.counts.documents ?? 0)))',
    'setText("systemMemoryCount", String(Number(snapshot.counts.verified_memory ?? 0)))',
    'setText("systemMemoryCount", "—")',
  ])assert.ok(source.includes(term),"Missing runtime binding: "+term);
}
console.log("Permanent navigation and source-backed System metrics verified");
