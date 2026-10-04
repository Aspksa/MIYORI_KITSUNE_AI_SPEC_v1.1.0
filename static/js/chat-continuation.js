/* 00.00.65 — Read-only project continuation in the existing activity strip.
 * Uses the authoritative NEXUS action registry, never invents progress.
 * No timer, no automatic resume, no executing tools from chat.
 */
(() => {
  const $ = id => document.getElementById(id);
  const recoverable = new Set([
    "waiting_permission","recovery","error","planned","running","verifying"
  ]);
  const stateRank = {
    waiting_permission:0,recovery:1,error:2,verifying:3,running:4,planned:5,
  };
  const actionLabel = {
    waiting_permission:"Нужно разрешение",
    recovery:"Требуется проверка",
    error:"Ошибка",
    planned:"Запланировано",
    running:"Выполняется",
    verifying:"Проверяется",
  };
  let generation=0;
  let pending=null;
  function visible(projectId,items){
    const details=$("chatContinuationDetails");
    const host=$("chatActivity");
    const content=$("chatContinuationItems");
    if (!details||!host||!content)return;
    content.replaceChildren();
    const outstanding=items.filter(a=>recoverable.has(a.state));
    if(!outstanding.length){
      details.hidden=true;
      details.open=false;
      if(!state.busy &&
         !$("chatActivityEvents")?.childElementCount)
        host.hidden=true;
      return;
    }
    details.hidden=false;
    host.hidden=false;
    $("chatContinuationLabel").textContent=
      "Работа проекта: "+outstanding.length+" незавершённ"+(
        outstanding.length%10===1&&outstanding.length%100!==11?"ая":"ых"
      )+" задач";
    for (const item of outstanding.slice(0,5)){
      const line=document.createElement("div");
      line.className="chat-continuation-row";
      const label=document.createElement("strong");
      label.textContent=actionLabel[item.state]||"Статус неизвестен";
      const title=document.createElement("span");
      title.textContent=String(item.title||"Задача").slice(0,160);
      line.append(label,title);
      content.appendChild(line);
    }
    if(outstanding.length>5){
      const more=document.createElement("p");
      more.textContent="Остальные задачи — в разделе «Действия».";
      content.appendChild(more);
    }
    // This control opens the existing permission/recovery UI. It does NOT
    // authorize, resume or retry anything.
    $("chatContinuationOpen").onclick=()=>{
      const nav=$("nexusNavActions");
      if(nav)nav.click();
      else if(typeof renderNexusActionsWorkspace==="function")
        renderNexusActionsWorkspace();
    };
  }
  async function refresh(){
    const pid=Number(state.projectId||0);
    if(!pid)return;
    const token=++generation;
    try{
      const response=await api(
        "/api/projects/"+pid+"/nexus/actions?limit=80"
      );
      if(token!==generation ||
         Number(state.projectId||0)!==pid)return;
      const actions=Array.isArray(response.actions)?
        response.actions.filter(a=>a.project_id===pid):[];
      actions.sort((a,b)=>(stateRank[a.state]??99)-(stateRank[b.state]??99));
      visible(pid,actions);
    }catch(_){
      // A failed status fetch is not evidence of a healthy or idle project.
      // Keep the previous state rather than clearing a warning.
    }
  }
  window.miyoriChatContinuation={refresh};
})();
