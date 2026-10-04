const state = { projectId: null, conversationId: null, busy: false, tools: {}, pulse: "ready" };

const el = (id) => document.getElementById(id);
const messages = el("messages");
const form = el("chatForm");
const input = el("messageInput");
const sendButton = el("sendButton");
const errorBox = el("errorBox");
const projectSelect = el("projectSelect");
const conversationList = el("conversationList");
const memoryList = el("memoryList");
const documentInput = el("documentInput");
const documentSearch = el("documentSearch");
const documentList = el("documentList");
const documentSearchResults = el("documentSearchResults");
const memorySearch = el("memorySearch");
const statusDot = el("statusDot");
const statusText = el("statusText");
const modelText = el("modelText");
const versionText = el("versionText");
const projectLabel = el("projectLabel");
const conversationTitle = el("conversationTitle");
const brainPlan = el("brainPlan");
const brainState = el("brainState");
const taskList = el("taskList");
const developmentStats = el("developmentStats");
const agentTrace = el("agentTrace");
const agentBudget = el("agentBudget");
const permissionList = el("permissionList");
const auditList = el("auditList");
const miyoriConsole = el("miyoriConsole");
const consoleHeader = el("consoleHeader");
const toggleConsole = el("toggleConsole");
const aiStatusChip = el("aiStatusChip");
const personaStatusChip = el("personaStatusChip");
const personaStatusText = el("personaStatusText");
const truthStatusChip = el("truthStatusChip");
const truthStatusText = el("truthStatusText");
const ragStatusChip = el("ragStatusChip");
const ragStatusText = el("ragStatusText");
const memoryStatusChip = el("memoryStatusChip");
const dbStatusChip = el("dbStatusChip");
const docsStatusChip = el("docsStatusChip");
const docsStatusText = el("docsStatusText");

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function showError(text) {
  errorBox.textContent = text || "";
  errorBox.hidden = !text;
}

function setPulse(mode, label) {
  state.pulse = mode;
  document.querySelectorAll("[data-pulse]").forEach((item) => {
    item.classList.toggle("active", item.dataset.pulse === mode);
  });
  const text = el("pulseText");
  const resolvedLabel = label || ({
    ready: "готова",
    thinking: "думаю",
    reading: "читаю",
    acting: "действую",
    waiting: "жду решения"
  }[mode] || mode);
  if (text) text.textContent = resolvedLabel;
  const consoleSummary = el("consoleSummary");
  if (consoleSummary) consoleSummary.textContent = resolvedLabel;
}

function setBusy(value) {
  state.busy = value;
  sendButton.disabled = false;
  input.disabled = value;
  projectSelect.disabled = value;
  if (messages) messages.setAttribute("aria-busy", value ? "true" : "false");
  sendButton.classList.toggle("stop-generation", Boolean(value));
  sendButton.title = value ? "Остановить ответ" : "Отправить сообщение";
  sendButton.setAttribute("aria-label", value ? "Остановить ответ" : "Отправить сообщение");
  setPulse(value ? "thinking" : "ready");
  window.dispatchEvent(
    new CustomEvent("miyori:interaction-state", {
      detail: {state: value ? "thinking" : "idle"}
    })
  );
}

function renderMessageMarkdown(container, value) {
  const content = String(value ?? "");
  if (!window.marked?.parse || !window.DOMPurify?.sanitize) {
    container.innerHTML = escapeHtml(content).replace(/\n/g, "<br>");
    return;
  }
  try {
    const html = window.marked.parse(content, {gfm: true, breaks: true});
    container.innerHTML = window.DOMPurify.sanitize(html, {
      ALLOWED_TAGS: [
        "p", "br", "strong", "b", "em", "i", "ul", "ol", "li",
        "h1", "h2", "h3", "h4", "blockquote", "pre", "code",
        "hr", "a", "table", "thead", "tbody", "tr", "th", "td", "del"
      ],
      ALLOWED_ATTR: ["href", "title"],
      FORBID_TAGS: ["img", "svg", "iframe", "video", "audio", "style", "script", "form", "input"]
    });
    container.querySelectorAll("a[href]").forEach(link => {
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    });
  } catch (_) {
    container.innerHTML = escapeHtml(content).replace(/\n/g, "<br>");
  }
}

function chatNearBottom() {
  if (!messages) return true;
  return messages.scrollHeight - messages.scrollTop - messages.clientHeight <= 96;
}

messages?.addEventListener("scroll", () => {
  if (chatNearBottom()) delete messages.dataset.unreadReply;
}, {passive:true});

function addMessage(role, text, sources = [], options = {}) {
  const followLatest = !options.suppressScroll &&
    (role === "user" || chatNearBottom());
  if (role === "user") messages.querySelector(".welcome-message")?.remove();
  const article = document.createElement("article");
  article.className = "message " + role;
  if (options.id != null) article.dataset.messageId = String(options.id);
  article._miyoriText = String(text ?? "");
  article._miyoriAttachments = Array.isArray(options.attachments) ? options.attachments : [];
  article._miyoriTaskGoal = String(options.task_goal || "").trim();
  article._miyoriWorkflow = options.workflow || null;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "assistant" ? "狐" : "●";

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  const author = document.createElement("strong");
  author.textContent = role === "assistant" ? "Миёри" : "Вы";

  const body = document.createElement("div");
  body.className = "message-body";
  if (role === "assistant") renderMessageMarkdown(body, text);
  else body.textContent = String(text ?? "");
  bubble.append(author, body);

  if (role === "assistant" && Array.isArray(sources) && sources.length) {
    const sourceBox = document.createElement("div");
    sourceBox.className = "message-sources";

    const label = document.createElement("span");
    label.className = "message-sources-label";
    label.textContent = "Источники";
    sourceBox.appendChild(label);

    for (const source of sources) {
      const title = source?.title || "Документ";
      const indexes = Array.isArray(source?.chunk_indexes)
        ? source.chunk_indexes.map((value) => Number(value) + 1).filter(Number.isFinite)
        : [];
      const past = (source?.source_type === "chat_history" ||
        source?.source_type === "owner_feedback") &&
        Number.isSafeInteger(Number(source.conversation_id)) &&
        Number.isSafeInteger(Number(source.message_id));
      const chip = document.createElement(past ? "button" :
        (source?.download_url ? "a" : "span"));
      chip.className = "message-source-chip";
      if (past) {
        chip.type = "button";
        chip.classList.add("message-history-source");
        chip.title = "Открыть прежнее сообщение; сведения не проверены";
        chip.addEventListener("click", () => {
          if (typeof openConversation === "function")
            void openConversation(Number(source.conversation_id),
                                  Number(source.message_id));
        });
      }
      chip.textContent = past ? title + " · прежнее сообщение"
        : source?.readable === false
        ? title + " · нужен OCR"
        : indexes.length
          ? title + " · фрагм. " + indexes.join(", ") + (source?.truncated ? " · часть текста" : "")
          : title;

      if (source?.download_url && String(source.download_url).startsWith("/api/projects/")) {
        chip.href = source.download_url;
        chip.title = "Скачать оригинал";
      }
      sourceBox.appendChild(chip);
    }
    bubble.appendChild(sourceBox);
  }

  if (role === "assistant" && options.diagnostics) {
    const diagnostics=options.diagnostics;
    const evidence=diagnostics.evidence || {};
    const plan=diagnostics.plan || {};
    const usage=diagnostics.model_usage || {};
    if (plan.mode!=="fast" || Number(evidence.source_count)>0) {
      const box=document.createElement("details");
      box.className="chat-answer-insights";
      const summary=document.createElement("summary");
      summary.textContent="Проверка и обработка";
      const content=document.createElement("div");
      content.className="chat-answer-insight-body";
      function line(label,value) {
        const row=document.createElement("p");
        const head=document.createElement("strong");
        head.textContent=label+": ";
        row.append(head,document.createTextNode(String(value)));
        content.appendChild(row);
      }
      const names={
        missing_extraction:"Некоторые файлы не прочитаны: нужен OCR",
        partial_extraction:"Изучена только часть текста",
        insufficient_sources:"Источников недостаточно",
        sources_available_not_fact_checked:"Источники найдены; выводы модели не гарантированы",
        not_required:"Проверка источников не запрашивалась",
      };
      line("Режим",plan.mode==="deep"?"углублённый":"обычный");
      line("Источники",Number(evidence.source_count)||0);
      const crosscheck=diagnostics.numeric_check || {};
      if (crosscheck.status==="checked_numbers") {
        line("Сверка чисел",crosscheck.matching_source+"/"+
          crosscheck.claims_seen+" имеют совпадения в источниках");
        if (crosscheck.missing_source > 0) {
          const warning=document.createElement("p");
          warning.className="chat-source-warning";
          warning.textContent="Найдены значения без подтверждающего фрагмента: "+
            crosscheck.missing_source+". Проверьте документы.";
          content.appendChild(warning);
        }
      }
      if (Number(diagnostics.owner_feedback_count)>0)
        line("Уточнения владельца",
          diagnostics.owner_feedback_count+" (не являются проверенными фактами)");
      const history=diagnostics.historical_chat || {};
      if (history.requested) {
        line("Ранние разговоры",(history.matches||0)+
          " совпадений; сообщения не являются проверенными фактами");
      }
      line("Покрытие",names[evidence.status]||"не определено");
      if (Number.isFinite(diagnostics.retrieval_ms))
        line("Поиск",diagnostics.retrieval_ms+" мс");
      if (Number.isFinite(usage.latency_ms))
        line("Ответ модели",usage.latency_ms+" мс");
      if (Number.isFinite(usage.total_tokens))
        line("Токены Cloud.ru",usage.total_tokens);
      if (Number.isFinite(usage.estimated_cost_rub))
        line("Расчётная стоимость",usage.estimated_cost_rub+" ₽ (не счёт)");
      const totalsButton=document.createElement("button");
      totalsButton.type="button";
      totalsButton.className="chat-usage-details-button";
      totalsButton.textContent="Расход токенов за 30 дней";
      const totalsOutput=document.createElement("p");
      totalsOutput.className="chat-usage-monthly";
      totalsButton.addEventListener("click",async()=>{
        const project=Number(state.projectId);
        if(!project || totalsButton.disabled)return;
        totalsButton.disabled=true;
        try {
          const metrics=await api(
            "/api/projects/"+project+"/chat/metrics?days=30"
          );
          if(Number(state.projectId)!==project)return;
          totalsOutput.textContent=
            "Запросов: "+Number(metrics.requests||0)+
            " · с измерениями: "+Number(metrics.measured_requests||0)+
            " · токены API: "+Number(metrics.total_tokens||0)+
            (metrics.estimated_cost_rub==null?
              " · стоимость неизвестна":
              " · расчёт: "+Number(metrics.estimated_cost_rub)+" ₽ (не счёт)");
        } catch(error) {
          totalsOutput.textContent="Статистика недоступна: "+
            String(error.message||error);
          totalsButton.disabled=false;
        }
      });
      content.append(totalsButton,totalsOutput);
      const qualityButton=document.createElement("button");
      qualityButton.type="button";
      qualityButton.className="chat-quality-details-button";
      qualityButton.textContent="Качество чата за 30 дней";
      const qualityOutput=document.createElement("p");
      qualityOutput.className="chat-quality-monthly";
      qualityButton.addEventListener("click",async()=>{
        const project=Number(state.projectId);
        if(!project || qualityButton.disabled)return;
        qualityButton.disabled=true;
        try {
          const report=await api(
            "/api/projects/"+project+"/chat/quality?days=30"
          );
          if(Number(state.projectId)!==project)return;
          const feedback=report.feedback||{};
          qualityOutput.textContent=
            "Ответов: "+Number(report.assistant_responses||0)+
            " · с источниками: "+Number(report.responses_with_sources||0)+
            " · исправлений: "+Number(feedback.corrected||0)+
            " · чисел без найденного фрагмента: "+
              Number(report.numeric_claims_missing_source||0)+
            (report.average_latency_ms==null?"":" · средняя latency: "+
              Number(report.average_latency_ms)+" мс")+
            ". Это измерения, не процент точности.";
        } catch(error) {
          qualityOutput.textContent="Метрики качества недоступны: "+
            String(error.message||error);
          qualityButton.disabled=false;
        }
      });
      content.append(qualityButton,qualityOutput);
      const offer=options.comparison_offer;
      if(Array.isArray(offer?.document_ids) &&
         offer.document_ids.length>=2 &&
         typeof offer.question==="string") {
        const button=document.createElement("button");
        button.type="button";
        button.className="chat-compare-button";
        button.textContent="Проверить все страницы " + offer.document_ids.length + " документов";
        const results=document.createElement("div");
        results.className="chat-compare-results";
        results.setAttribute("role","status");
        const render=async(comparisonId)=>{
          const reply=await api(
            "/api/projects/"+state.projectId+"/document-comparisons/"+comparisonId
          );
          const report=reply.comparison;
          results.replaceChildren();
          const status=document.createElement("p");
          status.textContent=report.finished ?
            "Проверка завершена. Сопоставьте найденные факты и источники." :
            "Проверка выполняется в фоновых задачах. Результаты сохраняются.";
          results.appendChild(status);
          for(const doc of report.documents||[]){
            const details=document.createElement("details");
            const title=document.createElement("summary");
            title.textContent=(doc.filename||"Документ")+" · "+doc.status+
              (doc.coverage_ratio!=null?
                " · покрытие ~"+Math.round(doc.coverage_ratio*100)+"%":"");
            details.appendChild(title);
            if(doc.answer){
              const text=document.createElement("p");
              text.textContent=doc.answer;
              details.appendChild(text);
            }
            for(const item of (doc.evidence||[]).slice(0,18)){
              const row=document.createElement("p");
              row.textContent=(item.locator||"Источник не определён")+
                ": "+(item.text||"");
              details.appendChild(row);
            }
            if(doc.error){
              const error=document.createElement("p");
              error.textContent=doc.error;
              details.appendChild(error);
            }
            results.appendChild(details);
          }
          return report.finished;
        };
        button.addEventListener("click",async()=>{
          if(button.disabled)return;
          button.disabled=true;
          try{
            const data=await api(
              "/api/projects/"+state.projectId+"/document-comparisons",{
                method:"POST",headers:{"Content-Type":"application/json"},
                body:JSON.stringify({
                  document_ids:offer.document_ids,
                  question:offer.question,
                  conversation_id:state.conversationId,
                })
              }
            );
            const id=data.comparison.id;
            window.miyoriChatContinuation?.refresh();
            button.textContent="Обновить результаты проверки";
            await render(id);
            button.onclick=async()=>{
              try{await render(id);}catch(error){results.textContent=error.message;}
            };
          } catch(error){
            results.textContent=error.message;
          } finally{button.disabled=false;}
        },{once:true});
        content.append(button,results);
      }
      box.append(summary,content);
      bubble.appendChild(box);
    }
  }

  if (role === "assistant") {
    body.querySelectorAll("pre").forEach(pre => {
      const copy = document.createElement("button");
      copy.type = "button";
      copy.className = "code-copy";
      copy.dataset.chatAction = "copy-code";
      copy.textContent = "Копировать код";
      pre.classList.add("code-container");
      pre.appendChild(copy);
    });
  }
  if (Array.isArray(options.attachments) && options.attachments.length && role === "user") {
    const attachments = document.createElement("div");
    attachments.className = "message-attachment-labels";
    options.attachments.forEach(item => {
      const chip = document.createElement("span");
      chip.textContent = "📄 " + String(item.filename || item.title || ("Документ #" + (item.id || item)));
      attachments.appendChild(chip);
    });
    bubble.appendChild(attachments);
  }
  const controls = document.createElement("div");
  controls.className = "message-tools";
  controls.setAttribute("aria-label", "Действия с сообщением");
  const commands = role === "user"
    ? [["copy", "Копировать"], ["edit", "Изменить"]]
    : [["copy", "Копировать"], ["retry", "Повторить"],
       ["save", options.bookmarked ? "Сохранено" : "Сохранить"],
       ["correct", "Исправить"]];
  if (role === "assistant" && article._miyoriTaskGoal) {
    commands.push(["tasks", "В задачи"]);
  }
  if (role === "assistant" && Number(article._miyoriWorkflow?.id) > 0 &&
      ["waiting_permission", "recovering", "running"].includes(
        String(article._miyoriWorkflow?.status || "")
      )) {
    commands.push(["actions", "Действия"]);
  }
  commands.forEach(([action, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.chatAction = action;
    button.textContent = label;
    if (action === "save") button.setAttribute("aria-pressed", options.bookmarked ? "true" : "false");
    controls.appendChild(button);
  });
  bubble.appendChild(controls);
  article.append(avatar, bubble);
  messages.appendChild(article);

  if (options.animate) {
    article.classList.add("message-arriving");
    if (role === "assistant") {
      [...body.children].slice(0, 12).forEach((node, index) => {
        node.style.setProperty(
          "--chat-reveal-delay",
          Math.min(index * 28, 196) + "ms"
        );
      });
    }
    window.setTimeout(() => article.classList.remove("message-arriving"), 520);
  }

  if (!options.suppressScroll && followLatest) {
    messages.scrollTop = messages.scrollHeight;
    delete messages.dataset.unreadReply;
  } else if (!options.suppressScroll && role === "assistant") {
    messages.dataset.unreadReply = "true";
    const summary = el("chatActivitySummary");
    if (summary) summary.textContent = "Новый ответ ниже";
  }

  if (role === "assistant" && !options.suppressEvent) {
    window.dispatchEvent(
      new CustomEvent("miyori:assistant-message", {
        detail: {text: String(text || "")}
      })
    );
  }
  return article;
}

function showWelcome() {
  messages.innerHTML = "";

  const article = document.createElement("article");
  article.className = "message assistant welcome-message";
  const bubble = document.createElement("div");
  bubble.className = "bubble welcome-bubble clean-welcome";
  const title = document.createElement("h3");
  title.textContent = "С чего начнём, Господин?";
  const subtitle = document.createElement("p");
  subtitle.textContent = "Миёри готова помочь с документами, проектами и вопросами.";
  const suggestions = document.createElement("div");
  suggestions.id = "nexusSuggestions";
  suggestions.hidden = true;
  const examples = [
    ["Изучить документ", "Изучи прикреплённый документ и выдели главное."],
    ["Проверить ошибки", "Проверь недавние материалы проекта на ошибки и противоречия."],
    ["Мои задачи", "Покажи текущие задачи, ожидающие моего решения."],
    ["Продолжить работу", "Помоги продолжить последнюю задачу с подтверждённого состояния."]
  ];
  for (const [label, prompt] of examples) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "suggestion-chip";
    chip.textContent = label;
    chip.onclick = () => {
      input.value = prompt;
      input.dispatchEvent(new Event("input", {bubbles:true}));
      input.focus();
    };
    suggestions.appendChild(chip);
  }
  suggestions.hidden = false;
  bubble.append(title, subtitle, suggestions);
  article.appendChild(bubble);
  messages.appendChild(article);
  conversationTitle.textContent = "Миёри";
  messages.scrollTop = 0;
  setPulse("ready");
}


async function loadNexus() {
  if (!state.projectId) return;
  const suggestions = el("nexusSuggestions");
  if (!suggestions) return;

  try {
    const data = await api("/api/projects/" + state.projectId + "/nexus");
    // Keep the four owner's quick prompts; server hints are additional,
    // scoped suggestions and never replace the user's choices.
    if (data.suggestions && data.suggestions.length) {
      for (const suggestion of data.suggestions.slice(0, 2)) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "quiet-suggestion";
      button.innerHTML =
        '<span class="quiet-suggestion-icon">↗</span><span><strong>' +
        escapeHtml(suggestion.label) + '</strong><small>' +
        escapeHtml(suggestion.detail) + '</small></span>';

      button.onclick = () => {
        if (suggestion.kind === "documents") {
          input.value = "Проанализируй материалы текущего проекта и скажи, что важно.";
        } else if (suggestion.kind === "permission") {
          openConsole("data");
        } else if (suggestion.kind === "tasks" || suggestion.kind === "failed_tasks") {
          openConsole("system");
        } else {
          input.value = "";
        }
        input.focus();
      };
      suggestions.appendChild(button);
      }
    }

    const c = data.counts;
    const truth = data.epistemic || {};
    const truthClaims = truth.claims || {};
    const verifiedTruth = (truthClaims.verified || 0) + (truthClaims.supported || 0);
    const disputedTruth = (truthClaims.disputed || 0) + (truthClaims.rejected || 0);
    if (truthStatusChip) {
      truthStatusChip.textContent = disputedTruth ? "Есть споры" : (verifiedTruth ? "Проверено" : "Наблюдаю");
      truthStatusChip.className = disputedTruth ? "soft-status warn" : (verifiedTruth ? "soft-status ok" : "soft-status neutral");
    }
    if (truthStatusText) {
      truthStatusText.textContent =
        "проверено " + verifiedTruth +
        " · спорно " + disputedTruth +
        " · источников " + (truth.sources || 0);
    }
    if (memoryStatusChip) {
      memoryStatusChip.textContent = "Доступна";
      memoryStatusChip.className = "soft-status ok";
    }
    if (docsStatusChip) {
      docsStatusChip.textContent = c.documents ? "Готовы" : "Пусто";
      docsStatusChip.className = c.documents ? "soft-status ok" : "soft-status neutral";
    }
    if (docsStatusText) {
      docsStatusText.textContent = c.documents ? ("Документов: " + c.documents) : "Нет документов";
    }
    const consoleSummary = el("consoleSummary");
    if (consoleSummary) {
      const parts = [];
      if (c.verified_memory) parts.push("память " + c.verified_memory);
      if (c.documents) parts.push("документы " + c.documents);
      if (c.active_tasks) parts.push("задачи " + c.active_tasks);
      if (c.pending_permissions) parts.push("решения " + c.pending_permissions);
      consoleSummary.textContent = parts.length ? parts.join(" · ") : "готова";
    }
  } catch (error) {
    suggestions.innerHTML = '<div class="nexus-loading">' + escapeHtml(error.message) + '</div>';
  }
}


function addContextOrbit(brain, agent, epistemic, rag) {
  const actions = agent?.actions?.filter((item) => item.status === "completed") || [];
  const ragItems = rag?.items || [];
  const sources = ragItems.filter((item) => item.source_type === "document");
  const memoryItems = ragItems.filter((item) => item.source_type === "memory");
  const knowledge = ragItems.filter((item) => item.source_type === "knowledge");
  const memoryCount = memoryItems.length;
  const plan = brain?.plan || [];

  if (!memoryCount && !sources.length && !actions.length && !plan.length && !knowledge.length) return;

  const drawer = document.createElement("section");
  drawer.className = "response-context collapsed";

  const summaryBits = [];
  if (sources.length) summaryBits.push(sources.length + " докум.");
  if (memoryCount) summaryBits.push(memoryCount + " память");
  if (knowledge.length) summaryBits.push(knowledge.length + " знан.");
  if (actions.length) summaryBits.push(actions.length + " действ.");
  if (plan.length) summaryBits.push(plan.length + " шага");

  drawer.innerHTML =
    '<button class="response-context-head" type="button">' +
      '<span class="response-context-icon">◎</span>' +
      '<span class="response-context-copy"><strong>Контекст ответа</strong><small>' +
        escapeHtml(summaryBits.join(" · ")) +
      '</small></span>' +
      '<span class="response-context-chevron">⌄</span>' +
    '</button>' +
    '<div class="response-context-body"></div>';

  const body = drawer.querySelector(".response-context-body");

  if (sources.length) {
    const section = document.createElement("div");
    section.className = "context-section";
    section.innerHTML = '<h4>Источники</h4>';
    for (const source of sources) {
      const item = document.createElement("div");
      item.className = "context-item";
      item.innerHTML =
        '<strong>' + escapeHtml(source.title || "Документ") +
        ' · ' + escapeHtml(source.locator || "") + '</strong>' +
        '<p>' + escapeHtml(source.content || "") + '</p>';
      section.appendChild(item);
    }
    body.appendChild(section);
  }

  if (memoryItems.length) {
    const section = document.createElement("div");
    section.className = "context-section";
    section.innerHTML = '<h4>Память</h4>';
    for (const memory of memoryItems) {
      const item = document.createElement("div");
      item.className = "context-item";
      item.innerHTML =
        '<strong>' + escapeHtml(memory.locator || "memory") + '</strong>' +
        '<p>' + escapeHtml(memory.content || "") + '</p>';
      section.appendChild(item);
    }
    body.appendChild(section);
  }

  if (knowledge.length) {
    const section = document.createElement("div");
    section.className = "context-section";
    section.innerHTML = '<h4>Проверенные знания</h4>';
    for (const claim of knowledge) {
      const item = document.createElement("div");
      item.className = "context-item";
      const confidence = typeof claim.metadata?.confidence === "number"
        ? Math.round(claim.metadata.confidence * 100) + "%"
        : "—";
      item.innerHTML =
        '<strong>' + escapeHtml(claim.metadata?.status || "knowledge") +
        ' · ' + confidence + '</strong>' +
        '<p>' + escapeHtml(claim.content || "") + '</p>';
      section.appendChild(item);
    }
    body.appendChild(section);
  }

  if (plan.length) {
    const section = document.createElement("div");
    section.className = "context-section";
    section.innerHTML = '<h4>План</h4>';
    plan.forEach((step, index) => {
      const item = document.createElement("div");
      item.className = "context-plan-step";
      item.innerHTML = '<span>' + (index + 1) + '</span><div>' + escapeHtml(step) + '</div>';
      section.appendChild(item);
    });
    body.appendChild(section);
  }

  if (actions.length) {
    const section = document.createElement("div");
    section.className = "context-section";
    section.innerHTML = '<h4>Действия</h4>';
    for (const action of actions) {
      const item = document.createElement("div");
      item.className = "context-action";
      item.innerHTML =
        '<span>✋</span><div><strong>' +
        escapeHtml(action.tool_name || "действие") +
        '</strong><small>' + escapeHtml(action.reason || "выполнено") + '</small></div>';
      section.appendChild(item);
    }
    body.appendChild(section);
  }

  const developer = document.createElement("button");
  developer.type = "button";
  developer.className = "developer-link";
  developer.textContent = "Технические детали";
  developer.onclick = () => openConsole("context");
  body.appendChild(developer);

  drawer.querySelector(".response-context-head").addEventListener("click", () => {
    drawer.classList.toggle("collapsed");
  });

  messages.appendChild(drawer);
  messages.scrollTop = messages.scrollHeight;
}

function openConsole(tab = null) {
  if (!miyoriConsole) return;
  miyoriConsole.classList.remove("collapsed");
  document.body.classList.add("developer-open");
  if (tab) activateInspectorTab(tab);
}

function toggleConsoleState() {
  if (!miyoriConsole) return;
  const willClose = !miyoriConsole.classList.contains("collapsed");
  miyoriConsole.classList.toggle("collapsed");
  document.body.classList.toggle("developer-open", !willClose);
}

function createLivingIntent(goal) {
  const article = document.createElement("article");
  article.className = "message intent-message";

  const card = document.createElement("section");
  card.className = "living-intent";
  card.innerHTML =
    '<button class="intent-head" type="button">' +
      '<span class="intent-orb">◉</span>' +
      '<span class="intent-title"><small>Текущая задача</small><strong>' +
        escapeHtml(goal.length > 96 ? goal.slice(0, 93) + "…" : goal) +
      '</strong></span>' +
      '<span class="intent-state">принято</span>' +
      '<span class="intent-chevron">⌄</span>' +
    '</button>' +
    '<div class="intent-body">' +
      '<div class="intent-thread">' +
        '<div class="thread-step active" data-intent-step="accepted"><i></i><span>Цель</span></div>' +
        '<div class="thread-line"></div>' +
        '<div class="thread-step" data-intent-step="context"><i></i><span>Контекст</span></div>' +
        '<div class="thread-line"></div>' +
        '<div class="thread-step" data-intent-step="actions"><i></i><span>Работа</span></div>' +
        '<div class="thread-line"></div>' +
        '<div class="thread-step" data-intent-step="done"><i></i><span>Результат</span></div>' +
      '</div>' +
      '<div class="intent-detail" data-intent-detail>Миёри приняла задачу.</div>' +
      '<div class="intent-recovery" data-intent-recovery></div>' +
    '</div>';

  card.querySelector(".intent-head").addEventListener("click", () => {
    card.classList.toggle("collapsed");
  });

  article.appendChild(card);
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
  return card;
}

function updateLivingIntent(card, phase, label = null, detail = null) {
  if (!card) return;
  const order = ["accepted", "context", "actions", "done"];
  const current = order.indexOf(phase);

  card.querySelectorAll("[data-intent-step]").forEach((step) => {
    const index = order.indexOf(step.dataset.intentStep);
    step.classList.toggle("active", index === current);
    step.classList.toggle("completed", index < current || phase === "done");
  });

  const state = card.querySelector(".intent-state");
  if (state) {
    state.textContent = label || ({
      accepted: "принято",
      context: "собираю контекст",
      actions: "работаю",
      done: "готово",
      error: "нужно внимание"
    }[phase] || phase);
  }

  const detailNode = card.querySelector("[data-intent-detail]");
  if (detailNode) {
    detailNode.textContent = detail || ({
      accepted: "Миёри приняла задачу.",
      context: "Собираю память, документы и доступные действия.",
      actions: "Использую доступный контекст и выполняю необходимые шаги.",
      done: "Результат готов. Детали и использованный контекст находятся ниже.",
      error: "Не удалось завершить задачу автоматически."
    }[phase] || "");
  }

  const recovery = card.querySelector("[data-intent-recovery]");
  if (recovery) {
    recovery.innerHTML = "";
    if (phase === "error") {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.textContent = "Попробовать иначе";
      retry.onclick = () => {
        input.value = "Попробуй выполнить эту задачу другим способом: " +
          card.querySelector(".intent-title strong").textContent;
        input.focus();
      };

      const inspect = document.createElement("button");
      inspect.type = "button";
      inspect.textContent = "Посмотреть состояние";
      inspect.onclick = () => openConsole("context");

      recovery.append(retry, inspect);
    }
  }

  card.classList.toggle("complete", phase === "done");
  card.classList.toggle("error", phase === "error");
}

/* Only collapse simultaneous identical stateless reads. Never cache settled
 * values and never share requests with an AbortSignal / mutation options. */
const inflightApiReads = new Map();
async function api(url, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const singleflight = method === "GET" && Object.keys(options).length === 0 &&
    typeof url === "string" && url.startsWith("/api/");
  if (singleflight && inflightApiReads.has(url))
    return inflightApiReads.get(url);
  const run = async () => {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) {
      const detail = data?.detail?.message || data?.detail || "Ошибка запроса.";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  };
  if (!singleflight) return run();
  const promise = run();
  inflightApiReads.set(url,promise);
  try {return await promise;}
  finally {if(inflightApiReads.get(url) === promise) inflightApiReads.delete(url);}
}

async function loadStatus() {
  try {
    const data = await api("/api/status");
    versionText.textContent = data.version;
    if (dbStatusChip) {
      dbStatusChip.textContent = "Готова";
      dbStatusChip.className = "soft-status ok";
    }
    if (ragStatusChip && data.rag) {
      ragStatusChip.textContent = data.rag.fts5 ? "Hybrid" : "Fallback";
      ragStatusChip.className = data.rag.fts5 ? "soft-status ok" : "soft-status warn";
      ragStatusText.textContent =
        (data.rag.fts5 ? "FTS5 + lexical" : "lexical") +
        " · chunks " + (data.rag.indexed_chunks || 0);
    }
    if (personaStatusChip && data.persona) {
      personaStatusChip.textContent = "Активна";
      personaStatusChip.className = "soft-status ok";
      personaStatusText.textContent =
        "v" + data.persona.version + " · " +
        data.persona.phrases + " фраз · " +
        data.persona.dialogues + " диалогов";
    }
    if (data.provider_configured) {
      statusDot.className = "dot ready";
      statusText.textContent = "Подключён";
      modelText.textContent = data.model_id;
      if (aiStatusChip) {
        aiStatusChip.textContent = "Подключён";
        aiStatusChip.className = "soft-status ok";
      }
    } else {
      statusDot.className = "dot warn";
      statusText.textContent = "Нужна настройка";
      modelText.textContent = "Заполните .env";
      if (aiStatusChip) {
        aiStatusChip.textContent = "Настройка";
        aiStatusChip.className = "soft-status warn";
      }
    }
  } catch {
    statusDot.className = "dot error-dot";
    statusText.textContent = "Сервер недоступен";
    if (aiStatusChip) {
      aiStatusChip.textContent = "Недоступен";
      aiStatusChip.className = "soft-status error";
    }
    if (personaStatusChip) {
      personaStatusChip.textContent = "Ошибка";
      personaStatusChip.className = "soft-status error";
    }
    if (ragStatusChip) {
      ragStatusChip.textContent = "Ошибка";
      ragStatusChip.className = "soft-status error";
    }
    if (dbStatusChip) {
      dbStatusChip.textContent = "Недоступна";
      dbStatusChip.className = "soft-status error";
    }
  }
}
