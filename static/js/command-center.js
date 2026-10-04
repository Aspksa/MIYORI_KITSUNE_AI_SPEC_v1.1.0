(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  let activeIndex = 0;
  let results = [];
  let searchTimer = null;
  let requestGeneration = 0;
  let cache = {projectId:null, at:0, documents:[], actions:[]};

  const staticCommands = [
    {id:"new-chat", label:"Новый разговор", hint:"Создать чистый чат", keys:"новый чат разговор", run:()=>startNewChat()},
    {id:"chat", label:"Чат", hint:"Вернуться к переписке", keys:"чат диалог", run:()=>showChatWorkspace()},
    {id:"actions", label:"Действия", hint:"Задачи, разрешения и workflow", keys:"действия задачи агент разрешения", run:()=>renderNexusActionsWorkspace()},
    {id:"knowledge", label:"Знания", hint:"Документы, память и знания проекта", keys:"знания память rag", run:()=>nexusNavKnowledge?.click()},
    {id:"documents", label:"Документы", hint:"Открыть Miyori Drive", keys:"документы файлы договор счета pdf", run:()=>menuDocumentsHub?.click()},
    {id:"home", label:"Дом", hint:"Домашние устройства и проекты", keys:"дом устройства", run:()=>nexusNavHome?.click()},
    {id:"settings", label:"Настройки", hint:"Настройки Миёри", keys:"настройки параметры", run:()=>menuSettings?.click()},
    {id:"status", label:"Состояние системы", hint:"Cloud.ru, память, RAG и база", keys:"состояние статус система cloud", run:()=>$("openSystemStatus")?.click()},
    {id:"update", label:"Обновление проекта", hint:"Проверить версию и обновления", keys:"обновление версия github", run:()=>menuProjectUpdate?.click()},
  ];

  function normalize(value) {
    return String(value || "").toLocaleLowerCase("ru-RU").replace(/ё/g,"е").trim();
  }

  function score(text, query) {
    const hay = normalize(text);
    const q = normalize(query);
    if (!q) return 1;
    if (hay === q) return 100;
    if (hay.startsWith(q)) return 70;
    if (hay.includes(q)) return 45;
    const tokens = q.split(/\s+/).filter(Boolean);
    return tokens.reduce((sum, token) => sum + (hay.includes(token) ? 10 : 0), 0);
  }

  function createUi() {
    if ($("commandCenterOverlay")) return;
    const trigger = document.createElement("button");
    trigger.id = "commandCenterButton";
    trigger.type = "button";
    trigger.className = "chat-top-button command-center-trigger";
    trigger.title = "Командный центр · Ctrl+K";
    trigger.setAttribute("aria-label","Открыть командный центр");
    trigger.textContent = "⌘K";
    $("chatFindButton")?.before(trigger);

    const overlay = document.createElement("div");
    overlay.id = "commandCenterOverlay";
    overlay.className = "command-center-overlay";
    overlay.hidden = true;
    overlay.innerHTML =
      '<section class="command-center" role="dialog" aria-modal="true" aria-labelledby="commandCenterTitle">' +
        '<header><div><span class="section-caption">MIYORI</span>' +
          '<h3 id="commandCenterTitle">Командный центр</h3></div>' +
          '<kbd>Esc</kbd></header>' +
        '<label class="command-center-search"><span aria-hidden="true">⌕</span>' +
          '<input id="commandCenterInput" type="search" autocomplete="off" ' +
          'placeholder="Разговор, документ, задача, проект или команда…" ' +
          'aria-label="Поиск по Миёри" aria-controls="commandCenterResults"/></label>' +
        '<div id="commandCenterResults" class="command-center-results" role="listbox" aria-label="Результаты"></div>' +
        '<footer><span>↑↓ выбрать</span><span>Enter открыть</span><span>Ctrl+K закрыть</span></footer>' +
      '</section>';
    document.body.appendChild(overlay);

    trigger.onclick = open;
    overlay.addEventListener("mousedown", event => {
      if (event.target === overlay) close();
    });
    $("commandCenterInput").addEventListener("input", scheduleSearch);
    $("commandCenterInput").addEventListener("keydown", onInputKeydown);
  }

  function open() {
    const overlay = $("commandCenterOverlay");
    if (!overlay) return;
    overlay.hidden = false;
    activeIndex = 0;
    $("commandCenterInput").value = "";
    void render("");
    requestAnimationFrame(()=>$("commandCenterInput")?.focus());
  }

  function close() {
    const overlay = $("commandCenterOverlay");
    if (overlay) overlay.hidden = true;
  }

  async function fetchProjectData() {
    const pid = Number(state.projectId);
    if (!pid) return {documents:[],actions:[]};
    if (cache.projectId === pid && Date.now() - cache.at < 10000) return cache;
    const [documents, actions] = await Promise.allSettled([
      api("/api/projects/" + pid + "/documents"),
      api("/api/projects/" + pid + "/nexus/actions?limit=80")
    ]);
    cache = {
      projectId:pid,
      at:Date.now(),
      documents:documents.status === "fulfilled" ? documents.value.documents || [] : [],
      actions:actions.status === "fulfilled" ? actions.value.actions || [] : []
    };
    return cache;
  }

  function staticResults(query) {
    return staticCommands
      .map(item=>({...item,kind:"command",score:score(item.label+" "+item.keys,query)}))
      .filter(item=>item.score>0)
      .sort((a,b)=>b.score-a.score);
  }

  function projectResults(query) {
    return [...($("projectSelect")?.options || [])].map(option=>({
      kind:"project",
      id:Number(option.value),
      label:"Проект · " + option.textContent,
      hint:"Переключить текущий проект",
      score:score(option.textContent,query)
    })).filter(item=>item.id && item.score>0);
  }

  async function dynamicResults(query, generation) {
    const q = query.trim();
    if (q.length < 2 || !state.projectId) return [];
    const project = await fetchProjectData();
    const [conversations, unified] = await Promise.allSettled([
      api("/api/projects/" + state.projectId + "/conversations?q=" + encodeURIComponent(q)),
      api("/api/projects/" + state.projectId + "/chat/search?q=" +
          encodeURIComponent(q) + "&scope=project")
    ]);
    if (generation !== requestGeneration) return [];

    const found = [];
    for (const doc of project.documents) {
      const value = score((doc.filename || "")+" "+(doc.title || ""),q);
      if (value>0) found.push({
        kind:"document", id:Number(doc.id),
        label:doc.filename || ("Документ #"+doc.id),
        hint:"Документ · " + Number(doc.chunk_count || 0) + " фрагм.",
        score:value + (Number(doc.id)||0)*0.0001
      });
    }
    for (const action of project.actions) {
      const value=score((action.title||"")+" "+(action.summary||"")+" "+(action.state_label||""),q);
      if(value>0) found.push({
        kind:"action",id:action.id,label:action.title||"Действие",
        hint:"Действие · "+(action.state_label||action.state||""),
        score:value
      });
    }
    if(conversations.status==="fulfilled"){
      for(const item of conversations.value.conversations||[]){
        const value=score((item.title||"")+" "+(item.preview||""),q);
        found.push({
          kind:"conversation",id:Number(item.id),messageId:null,
          label:item.title||"Разговор",hint:"Разговор · "+String(item.preview||"").slice(0,100),
          score:Math.max(value,15)
        });
      }
    }
    if(unified.status==="fulfilled"){
      for(const item of unified.value.matches||[]){
        if(item.kind==="chat"){
          found.push({
            kind:"conversation",id:Number(item.conversation_id),
            messageId:Number(item.message_id),label:item.title||"Разговор",
            hint:"Сообщение · "+String(item.preview||"").slice(0,110),score:35
          });
        } else if(item.kind==="document" && item.metadata?.document_id){
          found.push({
            kind:"document",id:Number(item.metadata.document_id),
            label:item.title||"Документ",hint:String(item.preview||"").slice(0,110),score:34
          });
        } else {
          found.push({
            kind:"knowledge",label:item.title||"Знание",
            hint:String(item.preview||"").slice(0,110),score:25
          });
        }
      }
    }
    const unique=new Map();
    for(const item of found){
      const key=item.kind+":"+(item.id??item.label)+":"+(item.messageId??"");
      if(!unique.has(key)||unique.get(key).score<item.score) unique.set(key,item);
    }
    return [...unique.values()].sort((a,b)=>b.score-a.score).slice(0,24);
  }

  async function render(query) {
    const generation=++requestGeneration;
    const base=[...staticResults(query),...projectResults(query)];
    results=base.slice(0,12);
    paint();
    if(query.trim().length<2) return;
    try {
      const dynamic=await dynamicResults(query,generation);
      if(generation!==requestGeneration)return;
      results=[...base,...dynamic].sort((a,b)=>b.score-a.score).slice(0,30);
      activeIndex=Math.min(activeIndex,Math.max(0,results.length-1));
      paint();
    } catch (_) {}
  }

  function paint() {
    const host=$("commandCenterResults");
    if(!host)return;
    host.replaceChildren();
    if(!results.length){
      const empty=document.createElement("div");
      empty.className="command-center-empty";
      empty.textContent="Ничего не найдено";
      host.appendChild(empty);
      return;
    }
    results.forEach((item,index)=>{
      const row=document.createElement("button");
      row.type="button";
      row.className="command-center-row"+(index===activeIndex?" active":"");
      row.setAttribute("role","option");
      row.setAttribute("aria-selected",String(index===activeIndex));
      row.innerHTML="<span><strong>"+escapeHtml(item.label)+"</strong><small>"+
        escapeHtml(item.hint||"")+"</small></span><em>"+escapeHtml({
          command:"Команда",project:"Проект",conversation:"Чат",
          document:"Документ",action:"Действие",knowledge:"Знание"
        }[item.kind]||item.kind)+"</em>";
      row.onmousemove=()=>{activeIndex=index;paint();};
      row.onclick=()=>void execute(item);
      host.appendChild(row);
    });
    host.querySelector(".active")?.scrollIntoView({block:"nearest"});
  }

  async function execute(item) {
    close();
    if(item.kind==="command") return await item.run();
    if(item.kind==="project"){
      const select=$("projectSelect");
      if(select){
        select.value=String(item.id);
        select.dispatchEvent(new Event("change",{bubbles:true}));
      }
      return;
    }
    if(item.kind==="conversation") return await openConversation(item.id,item.messageId||null);
    if(item.kind==="document") return await window.miyoriOpenDocument?.(item.id);
    if(item.kind==="action") return await window.miyoriOpenNexusAction?.(item.id);
    if(item.kind==="knowledge") return nexusNavKnowledge?.click();
  }

  function scheduleSearch(event) {
    clearTimeout(searchTimer);
    const value=event.target.value;
    searchTimer=setTimeout(()=>void render(value),140);
  }

  function onInputKeydown(event) {
    if(event.key==="ArrowDown"){
      event.preventDefault(); activeIndex=Math.min(results.length-1,activeIndex+1); paint();
    } else if(event.key==="ArrowUp"){
      event.preventDefault(); activeIndex=Math.max(0,activeIndex-1); paint();
    } else if(event.key==="Enter"){
      event.preventDefault(); if(results[activeIndex]) void execute(results[activeIndex]);
    } else if(event.key==="Escape"){
      event.preventDefault(); close();
    }
  }

  document.addEventListener("keydown",event=>{
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="k"){
      event.preventDefault();
      if($("commandCenterOverlay")?.hidden===false) close(); else open();
      return;
    }
    if(event.key==="Escape"&&$("commandCenterOverlay")?.hidden===false){
      event.preventDefault(); close();
    }
  });

  createUi();
  window.miyoriCommandCenter={open,close};
})();
