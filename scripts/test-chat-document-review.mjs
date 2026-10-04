import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {JSDOM} from "jsdom";

const html=readFileSync("templates/index.html","utf8");
const core=readFileSync("static/js/core.js","utf8");
const css=readFileSync("static/css/chat-document-review.css","utf8");
const server=readFileSync("app.py","utf8");
const {window}=new JSDOM(html,{url:"http://127.0.0.1/",runScripts:"outside-only"});
const $=id=>window.document.getElementById(id);
assert.ok(server.includes("compare_project_documents("));
assert.ok(css.includes(".chat-review-field"));
assert.equal(window.document.querySelector(".brand .mark"),null);
assert.ok(!$("chatHeader").contains($("nexusBodyHost")));
window.eval(readFileSync("static/vendor/marked.umd.js","utf8"));
window.eval(readFileSync("static/vendor/purify.min.js","utf8"));
window.eval(core);

const called=[];
window.state.projectId=7;
window.api=async(url,opts)=>{called.push({url,opts});return {question:{id:1}};};
window.addMessage("assistant","Результат",[],{
  diagnostics:{
    plan:{mode:"deep"},
    evidence:{source_count:2,status:"partial_extraction"},
    model_usage:{},
    document_review_query:"Проверь по всем фрагментам",
    document_review:{
      documents:[
        {document_id:1,requires_ocr:false,stored_text_scanned:true},
        {document_id:2,requires_ocr:false,stored_text_scanned:true}
      ],
      potential_differences:[{
        field:"НДС",
        evidence:[
          {filename:"Договор <script>alert(1)</script>.txt",
           values:[{value:"20%",chunk_index:1}]},
          {filename:"Счёт.txt",values:[{value:"10%",chunk_index:0}]}
        ]
      }],
      difference_count:1
    }
  }
});
const detail=$("messages").querySelector(".chat-answer-insights");
assert.ok(detail&&!detail.open,"Comparison must not open another panel");
assert.match(detail.textContent,/НДС/);
assert.equal(detail.querySelector("script"),null,
  "Document names may be malicious; only text nodes are allowed.");
const button=detail.querySelector(".chat-full-review-button");
assert.ok(button);
assert.equal(called.length,0,"Full cloud review must never launch automatically");
button.click();
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(called.length,2,"Explicit click triggers two verified project docs");
assert.ok(called.every(r=>r.url.startsWith("/api/projects/7/documents/")));
assert.ok(called.every(r=>JSON.parse(r.opts.body).question==="Проверь по всем фрагментам"));
console.log("Grounded document comparison disclosure and explicit full-review control OK.");
