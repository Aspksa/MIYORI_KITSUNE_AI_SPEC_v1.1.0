let conversationLoadToken = 0;
let conversationListController = null;
let conversationOpenToken = 0;
let conversationOpenController = null;

async function loadConversations() {
  if (!state.projectId) return;
  const token = ++conversationLoadToken;
  conversationListController?.abort();
  const controller = new AbortController();
  conversationListController = controller;
  const search = el("conversationSearch")?.value?.trim() || "";
  const folder = window.miyoriConversationUX?.folderQuery?.() || "all";
  const params = new URLSearchParams();
  if (search) params.set("q", search);
  if (folder && folder !== "all") params.set("folder", folder);
  let data;
  try {
    data = await api(
      "/api/projects/" + state.projectId + "/conversations" +
      (params.size ? "?" + params.toString() : ""),
      {signal:controller.signal}
    );
  } catch (error) {
    if (controller.signal.aborted) return;
    throw error;
  }
  if (controller.signal.aborted || token !== conversationLoadToken) return;
  conversationList.replaceChildren();
  if (!data.conversations?.length) {
    const empty = document.createElement("div");
    empty.className = "conversation-empty";
    empty.textContent = search ? "Ничего не найдено" : "Пока нет разговоров";
    conversationList.appendChild(empty);
    return;
  }
  let group = "";
  for (const item of data.conversations) {
    const today = new Date();
    const updated = new Date(item.updated_at || item.created_at);
    const days = Math.floor(
      (new Date(today.getFullYear(), today.getMonth(), today.getDate()) -
       new Date(updated.getFullYear(), updated.getMonth(), updated.getDate())) / 86400000
    );
    const category = item.pinned ? "Закреплённые" :
      days <= 0 ? "Сегодня" : days === 1 ? "Вчера" : days <= 7 ? "Последние 7 дней" : "Ранее";
    if (category !== group) {
      group = category;
      const heading = document.createElement("div");
      heading.className = "conversation-date-heading";
      heading.textContent = group;
      conversationList.appendChild(heading);
    }
    const row = document.createElement("div");
    row.className = "conversation-history-row";
    row.dataset.conversationId = String(item.id);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "conversation-item" + (item.id === state.conversationId ? " active" : "");
    const name = document.createElement("span");
    name.textContent = item.title;
    const count = document.createElement("small");
    count.textContent = item.message_count + " сообщ.";
    button.append(name, count);
    button.onclick = () => openConversation(item.id);
    const pin = document.createElement("button");
    pin.type = "button";
    pin.className = "history-row-button";
    pin.dataset.conversationPin = String(item.id);
    pin.dataset.pinned = item.pinned ? "1" : "0";
    pin.textContent = item.pinned ? "★" : "☆";
    pin.title = item.pinned ? "Открепить" : "Закрепить";
    pin.setAttribute("aria-label", pin.title);
    const rename = document.createElement("button");
    rename.type = "button";
    rename.className = "history-row-button";
    rename.dataset.conversationRename = String(item.id);
    rename.dataset.title = item.title;
    rename.textContent = "✎";
    rename.title = "Переименовать";
    rename.setAttribute("aria-label", "Переименовать");
    row.append(button, pin, rename);
    conversationList.appendChild(row);
  }
}

const chatWindow = {hasMore: false, beforeId: null, loading: false};

function messageFromRecord(item) {
  const row = addMessage(item.role, item.content, item.metadata?.sources || [], {
    id: item.id,
    bookmarked: Boolean(item.bookmarked),
    diagnostics: item.metadata?.diagnostics,
    comparison_offer: item.metadata?.comparison_offer,
    task_goal: item.metadata?.task_goal,
    workflow: item.metadata?.workflow_id ? {
      id: item.metadata.workflow_id,
      status: item.metadata.workflow_status || ""
    } : null,
    attachments: (item.metadata?.attachments || []).map(id => ({id})),
    suppressEvent: true,
    suppressScroll: true
  });
  row._miyoriMeta = item.metadata || {};
  return row;
}

function renderOlderControl() {
  messages.querySelector(".older-messages-button")?.remove();
  if (!chatWindow.hasMore) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "older-messages-button";
  button.textContent = "↑ Показать предыдущие сообщения";
  button.onclick = loadOlderMessages;
  messages.prepend(button);
}

async function openConversation(id, targetId = null) {
  if (!state.projectId) return;
  const token = ++conversationOpenToken;
  const projectAtStart = Number(state.projectId);
  conversationOpenController?.abort();
  const controller = new AbortController();
  conversationOpenController = controller;
  showError("");
  const url = "/api/projects/" + state.projectId + "/conversations/" + id +
    (targetId ? "?before_id=" + (Number(targetId) + 1) + "&limit=80" : "?limit=80");
  let data;
  try {
    data = await api(url, {signal:controller.signal});
  } catch (error) {
    if (controller.signal.aborted) return;
    showError(error.message);
    return;
  }
  if (controller.signal.aborted || token !== conversationOpenToken || projectAtStart !== Number(state.projectId)) return;
  window.miyoriDrafts?.save();
  window.miyoriChatAttachments?.clear();
  state.conversationId = id;
  messages.replaceChildren();
  for (const item of data.messages) {
    if (item.role === "user" || item.role === "assistant") messageFromRecord(item);
  }
  chatWindow.hasMore = Boolean(data.has_more);
  chatWindow.beforeId = data.before_id;
  renderOlderControl();
  conversationTitle.textContent = "Миёри";
  await loadConversations();
  if (token !== conversationOpenToken) return;
  window.miyoriDrafts?.restore();
  if (targetId) {
    const found = messages.querySelector('[data-message-id="' + Number(targetId) + '"]');
    found?.scrollIntoView({block:"center"});
    found?.classList.add("search-hit");
  } else messages.scrollTop = messages.scrollHeight;
  await window.miyoriConversationUX?.afterConversationOpen?.(data);
  input.focus();
}

async function loadOlderMessages() {
  if (chatWindow.loading || !chatWindow.hasMore || !state.conversationId) return;
  chatWindow.loading = true;
  const before = chatWindow.beforeId;
  const conversationAtStart = state.conversationId;
  const top = messages.scrollTop;
  const height = messages.scrollHeight;
  try {
    const data = await api(
      "/api/projects/" + state.projectId + "/conversations/" +
      state.conversationId + "?before_id=" + before + "&limit=80"
    );
    if (state.conversationId !== conversationAtStart) return;
    const existing = messages.querySelector(".message");
    for (const item of data.messages) {
      if (item.role !== "user" && item.role !== "assistant") continue;
      const row = messageFromRecord(item);
      if (existing) messages.insertBefore(row, existing);
      else messages.appendChild(row);
    }
    chatWindow.hasMore = Boolean(data.has_more);
    chatWindow.beforeId = data.before_id;
    renderOlderControl();
    const rows = messages.querySelectorAll(".message:not(.welcome-message)");
    // 200 DOM rows at most. Older history remains in SQLite and is reloadable.
    if (rows.length > 200) {
      for (let i = 200; i < rows.length; i++) rows[i].remove();
      if (!messages.querySelector(".latest-messages-button")) {
        const latest = document.createElement("button");
        latest.className = "latest-messages-button";
        latest.type = "button";
        latest.textContent = "Вернуться к последним ↓";
        latest.onclick = () => openConversation(state.conversationId);
        messages.appendChild(latest);
      }
    }
    messages.scrollTop = top + messages.scrollHeight - height;
  } catch (error) {
    showError(error.message);
  } finally {
    chatWindow.loading = false;
  }
}

function memoryActions(fact, card) {
  const actions = document.createElement("div");
  actions.className = "memory-actions";

  const addAction = (label, handler) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.onclick = handler;
    actions.appendChild(button);
  };

  if (fact.status === "candidate") {
    addAction("Подтвердить", () => setFactStatus(fact.id, "verified"));
    addAction("Оспорить", () => setFactStatus(fact.id, "disputed"));
  }
  if (fact.status === "verified") {
    addAction("Заменить", () => replaceFact(fact));
    addAction("Устарело", () => setFactStatus(fact.id, "superseded"));
  }

  if (actions.children.length) card.appendChild(actions);
}

async function setFactStatus(id, status) {
  await api("/api/projects/" + state.projectId + "/memory/" + id, {
    method: "PATCH",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({status})
  });
  await loadMemory();
}

async function replaceFact(fact) {
  const statement = prompt("Новая версия факта:", fact.statement);
  if (!statement || !statement.trim() || statement.trim() === fact.statement) return;
  await api("/api/projects/" + state.projectId + "/memory/" + fact.id + "/replace", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({statement: statement.trim()})
  });
  await loadMemory();
}

async function loadMemory() {
  if (!state.projectId) return;
  try {
    const data = await api("/api/projects/" + state.projectId + "/memory");
    const query = memorySearch.value.trim().toLowerCase();
    memoryList.innerHTML = "";
    const facts = query
      ? data.facts.filter((f) => f.statement.toLowerCase().includes(query))
      : data.facts;

    if (!facts.length) {
      memoryList.innerHTML = '<div class="conversation-empty">Ничего не найдено</div>';
      return;
    }

    for (const fact of facts) {
      const card = document.createElement("div");
      card.className = "memory-item status-" + fact.status;
      const conflictNote = fact.possible_conflict_ids?.length
        ? '<div class="memory-conflict">Возможный конфликт: ' + fact.possible_conflict_ids.join(", ") + '</div>'
        : "";
      card.innerHTML =
        '<div class="memory-statement">' + escapeHtml(fact.statement) + '</div>' +
        '<div class="memory-meta"><span>#' + fact.id + '</span><span>' + escapeHtml(fact.status) + '</span>' +
        '<span>' + escapeHtml(fact.memory_scope || "project") + '</span>' +
        '<span>' + escapeHtml(fact.memory_kind || "fact") + '</span></div>' +
        conflictNote;
      memoryActions(fact, card);
      memoryList.appendChild(card);
    }
  } catch (error) {
    memoryList.innerHTML = '<div class="conversation-empty">' + escapeHtml(error.message) + '</div>';
  }
}

function startNewChat() {
  window.miyoriScreenContext={module:"chat"};
  window.miyoriForkReadOnly = false;
  state.pendingRequest = null;
  window.miyoriDrafts?.save();
  window.miyoriChatAttachments?.clear();
  window.miyoriConversationUX?.resetConversation?.();
  state.conversationId = null;
  showError("");
  showWelcome();
  window.miyoriDrafts?.restore();
  brainPlan.innerHTML = '<span class="empty-copy">План появится после запроса.</span>';
  agentTrace.innerHTML = '<span class="empty-copy">Действий ещё не было.</span>';
  agentBudget.textContent = "0/5";
  Promise.all([loadConversations(), loadTools(), loadNexus()]);
  void window.miyoriChatContinuation?.refresh();
  input.focus();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.busy || state.submissionPending || !state.projectId) return;
  const text = input.value.trim();
  if (!text) return;
  state.submissionPending = true;
  const attachmentStore = window.miyoriChatAttachments;
  let attachedFiles = [];
  try {
    attachedFiles = attachmentStore ? await attachmentStore.ready() : [];
  } catch (error) {
    state.submissionPending = false;
    showError(error.message || "Не удалось загрузить документ.");
    return;
  }
  if (attachedFiles.length && attachedFiles.some(file => file.failed)) {
    state.submissionPending = false;
    showError("Исправьте ошибки загрузки вложений перед отправкой.");
    return;
  }
  const attachment_ids = attachedFiles.map(file => Number(file.id));
  const ui_context=structuredClone(window.miyoriScreenContext ||
    {module:"chat"});
  const ux_context = window.miyoriConversationUX?.composerContext?.() || {};
  const readOnly = Boolean(window.miyoriForkReadOnly);
  showError("");
  const uploadStatus = el("composerUploadStatus");
  if (uploadStatus) uploadStatus.textContent = "";
  const userRow = addMessage("user", text, [], {
    attachments: attachedFiles,
    animate: true,
  });
  userRow._miyoriMeta = {...ux_context, attachments:attachment_ids};
  input.value = "";
  window.miyoriDrafts?.save();
  input.style.height = "auto";
  setBusy(true);
  state.submissionPending = false;

  const pending = state.pendingRequest;
  const reuse = pending &&
    pending.projectId === state.projectId &&
    pending.text === text &&
    pending.readOnly === readOnly &&
    pending.conversationId === state.conversationId &&
    JSON.stringify(pending.attachment_ids) === JSON.stringify(attachment_ids) &&
    JSON.stringify(pending.ui_context) === JSON.stringify(ui_context) &&
    JSON.stringify(pending.ux_context || {}) === JSON.stringify(ux_context);
  const requestId = reuse ? pending.requestId :
    (window.crypto?.randomUUID?.() ||
      (Date.now().toString(36) + "-" + Math.random().toString(36).slice(2)));
  state.pendingRequest = {
    requestId, projectId:state.projectId, conversationId:state.conversationId,
    text, readOnly, attachment_ids:[...attachment_ids],ui_context,
    ux_context:structuredClone(ux_context),
  };
  state.lastRequestId = requestId;
  window.miyoriChatActivity?.begin(requestId);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        message: text,
        project_id: state.projectId,
        conversation_id: state.conversationId,
        request_id: requestId,
        read_only: readOnly,
        attachment_ids,ui_context,
        reply_to_message_id: ux_context.reply_to_message_id ?? null,
        quoted_text: ux_context.quoted_text || "",
        topic_id: ux_context.topic_id ?? null,
        voice_note_id: ux_context.voice_note_id ?? null
      })
    });
    const data = await response.json();
    if (!response.ok) {
      if (data?.detail?.conversation_id) {
        state.conversationId = data.detail.conversation_id;
        if (state.pendingRequest)
          state.pendingRequest.conversationId = state.conversationId;
      }
      const detail = data?.detail?.message || data?.detail || "Ошибка запроса.";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }

    state.conversationId = data.conversation_id;
    if (data.user_message_id) userRow.dataset.messageId = String(data.user_message_id);
    const assistantRow = addMessage("assistant", data.answer, data.sources || [], {
      id:data.assistant_message_id, diagnostics:data.diagnostics,
      comparison_offer:data.comparison_offer,
      task_goal:data.task_goal,
      workflow:data.workflow,
      animate:true
    });
    assistantRow._miyoriMeta = {
      topic_id:data.topic_id ?? ux_context.topic_id ?? null,
      reply_context:data.reply_context || null,
    };
    attachmentStore?.clear();
    state.pendingRequest = null;
    window.miyoriForkReadOnly = false;
    window.dispatchEvent(new CustomEvent("miyori:chat-response", {detail: data}));
    await window.miyoriConversationUX?.afterSend?.(data, text);

    // Технические данные обновляются внутри системы, но не добавляются в пользовательский чат.
    if (data.brain) {
      if (brainState) brainState.textContent = "ready";
      if (brainPlan) {
        brainPlan.innerHTML = (data.brain.plan || []).map(
          (item, index) => "<div>" + (index + 1) + ". " + escapeHtml(item) + "</div>"
        ).join("");
      }
    }

    if (data.agent) {
      if (agentBudget) {
        agentBudget.textContent = data.agent.steps_used + "/" + data.agent.max_steps;
        agentBudget.title = data.agent.workflow_status
          ? "Workflow: " + data.agent.workflow_status
          : "";
      }
      if (agentTrace) {
        agentTrace.innerHTML = (data.agent.actions || []).map((action) => {
          const tool = action.tool_name ? escapeHtml(action.tool_name) : "без инструмента";
          return '<div class="agent-step"><strong>Шаг ' + action.step_index + ' · ' + tool +
            '</strong><span>' + escapeHtml(action.reason) + '</span><small>' +
            escapeHtml(action.status) + '</small></div>';
        }).join("");
      }

      for (const req of (data.agent.pending_permissions || [])) {
        addPermissionActivity(req);
      }
      if (data.agent.recovery_required && data.agent.workflow_id) {
        addActivityCard(
          "Workflow требует восстановления",
          "Состояние сохранено. Miyori не будет повторять изменение вслепую.",
          "warning",
          [{
            label: "Проверить и продолжить",
            primary: true,
            onClick: async () => resumeWorkflow(data.agent.workflow_id, true)
          }]
        );
      }
    }

    // The response is already persisted. Refresh only the material that
    // genuinely changed; a dashboard refresh may never undo the chat send.
    const operations=(data.agent?.actions||[]).some(
      action=>Boolean(action.tool_name) && action.status!=="skipped"
    );
    const permissions=Boolean(data.agent?.pending_permissions?.length);
    const memoryChanged=Boolean(data.memory?.captured) ||
      Boolean(data.epistemic?.captured_claim_ids?.length);
    const refresh=[loadConversations(),loadNexus()];
    if(operations||permissions){
      refresh.push(loadTools(),loadPermissions(),loadAudit(),loadTasks());
    }
    if(operations||memoryChanged){
      refresh.push(loadMemory(),loadDevelopment());
    }
    if(operations||attachment_ids.length){
      refresh.push(loadDocuments());
    }
    const refreshResults=await Promise.allSettled(refresh);
    if(refreshResults.some(item=>item.status==="rejected")) {
      const note=el("composerUploadStatus");
      if(note) note.textContent=
        "Ответ сохранён. Часть дополнительных статусов пока недоступна.";
    }
  } catch (error) {
    showError(error.message || "Не удалось получить ответ.");
    // Keep the stable request ID for safe retry of a persisted workflow.
    // Restore the draft and staged files instead of losing the user's work.
    if (userRow) userRow.remove();
    input.value = text;
    input.dispatchEvent(new Event("input", {bubbles:true}));
    await loadConversations();
  } finally {
    window.miyoriChatActivity?.complete();
    setBusy(false);
    input.focus();
  }
});

projectSelect.addEventListener("change", async () => {
  window.miyoriScreenContext={module:"chat"};
  window.miyoriForkReadOnly = false;
  state.pendingRequest = null;
  ++conversationOpenToken;
  conversationOpenController?.abort();
  window.miyoriDrafts?.save();
  window.miyoriChatAttachments?.clear();
  state.projectId = Number(projectSelect.value);
  state.conversationId = null;
  void window.miyoriChatContinuation?.refresh();
  updateProjectLabel();
  showWelcome();
  window.miyoriDrafts?.restore();
  await Promise.all([
    loadConversations(), loadMemory(), loadDocuments(),
    loadTools(), loadPermissions(), loadAudit(), loadTasks(), loadDevelopment(), loadNexus()
  ]);
  void window.miyoriChatContinuation?.refresh();
});

el("addProject").addEventListener("click", async () => {
  const name = prompt("Название нового проекта:");
  if (!name || !name.trim()) return;
  try {
    const data = await api("/api/projects", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({name: name.trim()})
    });
    state.projectId = data.project.id;
    state.conversationId = null;
    void window.miyoriChatContinuation?.refresh();
    await loadProjects();
    showWelcome();
    await loadTools();
  } catch (error) {
    showError(error.message);
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 180) + "px";
});
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing && !event.ctrlKey && !event.altKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
memorySearch.addEventListener("input", loadMemory);
documentSearch.addEventListener("input", searchDocuments);
documentInput.addEventListener("change", () => uploadDocument(documentInput.files[0]));
el("refreshMemory").addEventListener("click", loadMemory);
el("refreshPermissions").addEventListener("click", loadPermissions);
el("refreshTasks").addEventListener("click", loadTasks);
el("runSelfCheckTask").addEventListener("click", () => createBackgroundTask("self_check"));
el("runMemoryTask").addEventListener("click", () => createBackgroundTask("memory_consolidation"));
el("runDevelopmentCheck").addEventListener("click", runDevelopmentCheck);
if (el("newChat")) el("newChat").addEventListener("click", startNewChat);
if (el("newChatSide")) el("newChatSide").addEventListener("click", startNewChat);

const composerAttach = el("composerAttach");
if (composerAttach && documentInput) {
  composerAttach.addEventListener("click", () => documentInput.click());
}
const chatHistoryButton = el("chatHistoryButton");
conversationList?.addEventListener("click", (event) => {
  if (!event.target.closest(".conversation-item")) return;
  const drawer = document.querySelector(".workspace-details");
  if (!drawer) return;
  drawer.hidden = true;
  drawer.setAttribute("aria-hidden", "true");
  drawer.classList.remove("history-drawer-open");
  chatHistoryButton?.setAttribute("aria-expanded", "false");
});
if (chatHistoryButton) {
  chatHistoryButton.addEventListener("click", () => {
    const drawer = document.querySelector(".workspace-details");
    if (!drawer) return;
    const visible = drawer.hidden;
    drawer.hidden = !visible;
    drawer.setAttribute("aria-hidden", visible ? "false" : "true");
    drawer.classList.toggle("history-drawer-open", visible);
    chatHistoryButton.setAttribute("aria-expanded", String(visible));
  });
}
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    const drawer = document.querySelector(".workspace-details");
    if (drawer && !drawer.hidden) {
      drawer.hidden = true;
      drawer.setAttribute("aria-hidden", "true");
      drawer.classList.remove("history-drawer-open");
      chatHistoryButton?.setAttribute("aria-expanded", "false");
    }
  }
});
