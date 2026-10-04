async function loadConversations() {
  if (!state.projectId) return;
  const data = await api("/api/projects/" + state.projectId + "/conversations");
  conversationList.innerHTML = "";
  if (!data.conversations.length) {
    conversationList.innerHTML = '<div class="conversation-empty">Пока нет разговоров</div>';
    return;
  }
  for (const item of data.conversations) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "conversation-item" + (item.id === state.conversationId ? " active" : "");
    button.innerHTML = "<span>" + escapeHtml(item.title) + "</span><small>" + item.message_count + " сообщ.</small>";
    button.onclick = () => openConversation(item.id, item.title);
    conversationList.appendChild(button);
  }
}

async function openConversation(id, title) {
  showError("");
  const data = await api("/api/projects/" + state.projectId + "/conversations/" + id);
  state.conversationId = id;
  messages.innerHTML = "";
  for (const item of data.messages) {
    if (item.role === "user" || item.role === "assistant") {
      addMessage(item.role, item.content, item.metadata?.sources || []);
    }
  }
  conversationTitle.textContent = "Миёри";
  await loadConversations();
  input.focus();
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
  state.conversationId = null;
  showError("");
  showWelcome();
  brainPlan.innerHTML = '<span class="empty-copy">План появится после запроса.</span>';
  agentTrace.innerHTML = '<span class="empty-copy">Действий ещё не было.</span>';
  agentBudget.textContent = "0/5";
  Promise.all([loadConversations(), loadTools(), loadNexus()]);
  input.focus();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.busy || !state.projectId) return;
  const text = input.value.trim();
  if (!text) return;

  showError("");
  const uploadStatus = el("composerUploadStatus");
  if (uploadStatus) uploadStatus.textContent = "";
  addMessage("user", text);
  input.value = "";
  input.style.height = "auto";
  setBusy(true);

  const requestId = (window.crypto?.randomUUID?.() || (
    Date.now().toString(36) + "-" + Math.random().toString(36).slice(2)
  ));
  state.lastRequestId = requestId;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        message: text,
        project_id: state.projectId,
        conversation_id: state.conversationId,
        request_id: requestId
      })
    });
    const data = await response.json();
    if (!response.ok) {
      if (data?.detail?.conversation_id) state.conversationId = data.detail.conversation_id;
      const detail = data?.detail?.message || data?.detail || "Ошибка запроса.";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }

    state.conversationId = data.conversation_id;
    addMessage("assistant", data.answer, data.sources || []);

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

    await Promise.all([
      loadConversations(), loadMemory(), loadDocuments(),
      loadTools(), loadPermissions(), loadAudit(), loadTasks(), loadDevelopment(), loadNexus()
    ]);
  } catch (error) {
    showError(error.message || "Не удалось получить ответ.");
    await loadConversations();
  } finally {
    setBusy(false);
    input.focus();
  }
});

projectSelect.addEventListener("change", async () => {
  state.projectId = Number(projectSelect.value);
  state.conversationId = null;
  updateProjectLabel();
  showWelcome();
  await Promise.all([
    loadConversations(), loadMemory(), loadDocuments(),
    loadTools(), loadPermissions(), loadAudit(), loadTasks(), loadDevelopment(), loadNexus()
  ]);
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
