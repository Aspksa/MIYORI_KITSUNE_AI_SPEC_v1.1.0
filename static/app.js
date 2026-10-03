const state = { projectId: null, conversationId: null, busy: false };

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
const toolList = el("toolList");
const taskList = el("taskList");
const developmentStats = el("developmentStats");
const agentTrace = el("agentTrace");
const agentBudget = el("agentBudget");
const permissionList = el("permissionList");

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function showError(text) {
  errorBox.textContent = text || "";
  errorBox.hidden = !text;
}

function setBusy(value) {
  state.busy = value;
  sendButton.disabled = value;
  input.disabled = value;
  projectSelect.disabled = value;
  sendButton.textContent = value ? "Думаю…" : "Отправить";
}

function addMessage(role, text) {
  const article = document.createElement("article");
  article.className = "message " + role;
  article.innerHTML =
    '<div class="avatar">' + (role === "assistant" ? "狐" : "Вы") + '</div>' +
    '<div class="bubble"><strong>' + (role === "assistant" ? "Миёри" : "Господин") +
    '</strong><p>' + escapeHtml(text).replace(/\n/g, "<br>") + '</p></div>';
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
}

function showWelcome() {
  messages.innerHTML = "";
  addMessage("assistant", "Здравствуйте, Господин. Я готова. Выберите разговор или начните новый.");
  conversationTitle.textContent = "Новый разговор";
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    const detail = data?.detail?.message || data?.detail || "Ошибка запроса.";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

async function loadStatus() {
  try {
    const data = await api("/api/status");
    versionText.textContent = data.version;
    if (data.provider_configured) {
      statusDot.className = "dot ready";
      statusText.textContent = "Cloud.ru настроен";
      modelText.textContent = data.model_id;
    } else {
      statusDot.className = "dot warn";
      statusText.textContent = "Нужна настройка";
      modelText.textContent = "Заполните .env";
    }
  } catch {
    statusDot.className = "dot error-dot";
    statusText.textContent = "Сервер недоступен";
  }
}

async function loadProjects() {
  const data = await api("/api/projects");
  projectSelect.innerHTML = "";
  for (const project of data.projects) {
    const option = document.createElement("option");
    option.value = project.id;
    option.textContent = project.name;
    projectSelect.appendChild(option);
  }
  if (!state.projectId && data.projects.length) state.projectId = data.projects[0].id;
  projectSelect.value = String(state.projectId);
  updateProjectLabel();
  await Promise.all([
    loadConversations(), loadMemory(), loadDocuments(),
    loadTools(), loadPermissions(), loadTasks(), loadDevelopment()
  ]);
}

function updateProjectLabel() {
  const option = projectSelect.selectedOptions[0];
  projectLabel.textContent = option ? "Проект: " + option.textContent : "Проект";
}

async function loadDocuments() {
  if (!state.projectId) return;
  try {
    const data = await api("/api/projects/" + state.projectId + "/documents");
    documentList.innerHTML = "";
    if (!data.documents.length) {
      documentList.innerHTML = '<div class="conversation-empty">Документов пока нет</div>';
      return;
    }
    for (const item of data.documents) {
      const row = document.createElement("div");
      row.className = "document-item";
      row.innerHTML =
        '<span>' + escapeHtml(item.filename) + '</span>' +
        '<small>' + item.chunk_count + ' фрагм. · ' + Math.max(1, Math.round(item.size_bytes / 1024)) + ' КБ</small>';
      documentList.appendChild(row);
    }
  } catch (error) {
    documentList.innerHTML = '<div class="conversation-empty">' + escapeHtml(error.message) + '</div>';
  }
}

async function searchDocuments() {
  if (!state.projectId) return;
  const query = documentSearch.value.trim();
  documentSearchResults.innerHTML = "";
  if (!query) return;

  try {
    const data = await api(
      "/api/projects/" + state.projectId + "/documents/search?q=" + encodeURIComponent(query)
    );
    if (!data.chunks.length) {
      documentSearchResults.innerHTML = '<div class="conversation-empty">Совпадений нет</div>';
      return;
    }
    for (const item of data.chunks) {
      const card = document.createElement("div");
      card.className = "document-result";
      const preview = item.content.length > 260 ? item.content.slice(0, 257) + "..." : item.content;
      card.innerHTML =
        '<strong>' + escapeHtml(item.filename) + ' · фрагмент ' + item.chunk_index + '</strong>' +
        '<p>' + escapeHtml(preview) + '</p>';
      documentSearchResults.appendChild(card);
    }
  } catch (error) {
    showError(error.message);
  }
}

async function uploadDocument(file) {
  if (!file || !state.projectId) return;
  const formData = new FormData();
  formData.append("file", file);
  showError("");
  try {
    const response = await fetch(
      "/api/projects/" + state.projectId + "/documents",
      {method: "POST", body: formData}
    );
    const data = await response.json();
    if (!response.ok) {
      const detail = data?.detail || "Ошибка загрузки документа.";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    await loadDocuments();
  } catch (error) {
    showError(error.message);
  } finally {
    documentInput.value = "";
  }
}

async function loadTools() {
  try {
    const data = await api("/api/tools");
    toolList.innerHTML = "";
    for (const tool of data.tools) {
      const row = document.createElement("div");
      row.className = "tool-item";
      row.innerHTML = "<strong>" + escapeHtml(tool.name) + "</strong><small>" +
        escapeHtml(tool.description) + "</small>";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "mini-button";
      button.textContent = "Запустить";
      button.onclick = async () => {
        let argumentsPayload = {};
        if (tool.name === "project_memory_search" || tool.name === "project_document_search") {
          const query = prompt("Что искать?");
          if (!query || !query.trim()) return;
          argumentsPayload = {query: query.trim()};
        } else if (tool.name === "workspace_read") {
          const path = prompt("Путь к файлу в workspace:");
          if (!path || !path.trim()) return;
          argumentsPayload = {path: path.trim()};
        } else if (tool.name === "workspace_create" || tool.name === "workspace_modify") {
          const path = prompt("Путь к файлу в workspace:");
          if (!path || !path.trim()) return;
          const content = prompt("Содержимое файла:");
          if (content === null) return;
          argumentsPayload = {path: path.trim(), content};
        }
        try {
          const result = await api("/api/projects/" + state.projectId + "/tools/execute", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({name: tool.name, arguments: argumentsPayload})
          });
          const output = document.createElement("pre");
          output.className = "tool-output";
          if (result.status === "approval_required") {
            output.textContent = "Требуется подтверждение пользователя.";
            await loadPermissions();
          } else {
            output.textContent = JSON.stringify(result.result, null, 2);
          }
          row.appendChild(output);
        } catch (error) {
          showError(error.message);
        }
      };
      row.appendChild(button);
      toolList.appendChild(row);
    }
  } catch (error) {
    toolList.innerHTML = '<div class="conversation-empty">' + escapeHtml(error.message) + '</div>';
  }
}

async function decidePermission(requestId, approved) {
  try {
    await api("/api/projects/" + state.projectId + "/permissions/" + requestId + "/decision", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({approved})
    });
    await Promise.all([loadPermissions(), loadTools()]);
  } catch (error) {
    showError(error.message);
  }
}

async function loadPermissions() {
  if (!state.projectId) return;
  try {
    const data = await api("/api/projects/" + state.projectId + "/permissions");
    permissionList.innerHTML = "";
    if (!data.requests.length) {
      permissionList.innerHTML = '<div class="conversation-empty">Запросов нет</div>';
      return;
    }

    for (const req of data.requests.slice(0, 12)) {
      const row = document.createElement("div");
      row.className = "permission-item status-" + req.status;
      row.innerHTML =
        "<div><strong>#" + req.id + " " + escapeHtml(req.tool_name) + "</strong>" +
        "<small>" + escapeHtml(req.status) + "</small></div>";

      if (req.status === "pending") {
        const actions = document.createElement("div");
        actions.className = "permission-actions";
        const allow = document.createElement("button");
        allow.type = "button";
        allow.textContent = "Разрешить";
        allow.onclick = () => decidePermission(req.id, true);
        const deny = document.createElement("button");
        deny.type = "button";
        deny.textContent = "Отклонить";
        deny.onclick = () => decidePermission(req.id, false);
        actions.append(allow, deny);
        row.appendChild(actions);
      }

      permissionList.appendChild(row);
    }
  } catch (error) {
    permissionList.innerHTML = '<div class="conversation-empty">' + escapeHtml(error.message) + "</div>";
  }
}

async function createBackgroundTask(taskType) {
  if (!state.projectId) return;
  try {
    await api("/api/projects/" + state.projectId + "/tasks", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({task_type: taskType, payload: {}})
    });
    await loadTasks();
  } catch (error) {
    showError(error.message);
  }
}

async function cancelTask(taskId) {
  try {
    await api("/api/projects/" + state.projectId + "/tasks/" + taskId + "/cancel", {
      method: "POST"
    });
    await loadTasks();
  } catch (error) {
    showError(error.message);
  }
}

async function loadTasks() {
  if (!state.projectId) return;
  try {
    const data = await api("/api/projects/" + state.projectId + "/tasks");
    taskList.innerHTML = "";
    if (!data.tasks.length) {
      taskList.innerHTML = '<div class="conversation-empty">Задач пока нет</div>';
      return;
    }
    for (const task of data.tasks.slice(0, 10)) {
      const row = document.createElement("div");
      row.className = "task-item status-" + task.status;
      row.innerHTML =
        "<div><strong>#" + task.id + " " + escapeHtml(task.task_type) + "</strong>" +
        "<small>" + escapeHtml(task.status) + "</small></div>";
      if (task.status === "queued" || task.status === "running") {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = "Отмена";
        button.onclick = () => cancelTask(task.id);
        row.appendChild(button);
      }
      taskList.appendChild(row);
    }
  } catch (error) {
    taskList.innerHTML = '<div class="conversation-empty">' + escapeHtml(error.message) + '</div>';
  }
}

async function loadDevelopment() {
  if (!state.projectId) return;
  try {
    const data = await api("/api/projects/" + state.projectId + "/development");
    const s = data.snapshot;
    developmentStats.innerHTML =
      "Факты: <b>" + s.verified_facts + "</b> · Документы: <b>" + s.documents +
      "</b> · Задачи OK: <b>" + s.completed_tasks + "</b> · Ошибки: <b>" +
      s.failed_tasks + "</b> · Проверки: <b>" + s.checks_passed + "/" + s.checks_total + "</b>";
  } catch (error) {
    developmentStats.textContent = error.message;
  }
}

async function runDevelopmentCheck() {
  if (!state.projectId) return;
  try {
    await api("/api/projects/" + state.projectId + "/development/check", {method: "POST"});
    await loadDevelopment();
  } catch (error) {
    showError(error.message);
  }
}

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
    if (item.role === "user" || item.role === "assistant") addMessage(item.role, item.content);
  }
  conversationTitle.textContent = title || "Разговор с Миёри";
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
        '<span>' + escapeHtml(fact.source_kind || "source") + '</span></div>' +
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
  loadConversations();
  input.focus();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.busy || !state.projectId) return;
  const text = input.value.trim();
  if (!text) return;

  showError("");
  addMessage("user", text);
  input.value = "";
  input.style.height = "auto";
  setBusy(true);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        message: text,
        project_id: state.projectId,
        conversation_id: state.conversationId
      })
    });
    const data = await response.json();
    if (!response.ok) {
      if (data?.detail?.conversation_id) state.conversationId = data.detail.conversation_id;
      const detail = data?.detail?.message || data?.detail || "Ошибка запроса.";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }

    state.conversationId = data.conversation_id;
    addMessage("assistant", data.answer);
    if (data.brain) {
      brainState.textContent = "ready";
      brainPlan.innerHTML = data.brain.plan.map(
        (item, index) => "<div>" + (index + 1) + ". " + escapeHtml(item) + "</div>"
      ).join("");
    }
    if (data.agent) {
      agentBudget.textContent = data.agent.steps_used + "/" + data.agent.max_steps;
      agentTrace.innerHTML = data.agent.actions.map((action) => {
        const tool = action.tool_name ? escapeHtml(action.tool_name) : "без инструмента";
        return '<div class="agent-step"><strong>Шаг ' + action.step_index + ' · ' + tool +
          '</strong><span>' + escapeHtml(action.reason) + '</span><small>' +
          escapeHtml(action.status) + '</small></div>';
      }).join("");
    }
    await Promise.all([
      loadConversations(), loadMemory(), loadDocuments(),
      loadTools(), loadPermissions(), loadTasks(), loadDevelopment()
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
    loadTools(), loadPermissions(), loadTasks(), loadDevelopment()
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
  } catch (error) {
    showError(error.message);
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 180) + "px";
});
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
memorySearch.addEventListener("input", loadMemory);
documentSearch.addEventListener("input", searchDocuments);
documentInput.addEventListener("change", () => uploadDocument(documentInput.files[0]));
el("refreshMemory").addEventListener("click", loadMemory);
el("refreshTools").addEventListener("click", loadTools);
el("refreshPermissions").addEventListener("click", loadPermissions);
el("refreshTasks").addEventListener("click", loadTasks);
el("runSelfCheckTask").addEventListener("click", () => createBackgroundTask("self_check"));
el("runMemoryTask").addEventListener("click", () => createBackgroundTask("memory_consolidation"));
el("runDevelopmentCheck").addEventListener("click", runDevelopmentCheck);
el("newChat").addEventListener("click", startNewChat);
el("newChatSide").addEventListener("click", startNewChat);

async function boot() {
  showWelcome();
  await loadStatus();
  try { await loadProjects(); } catch (error) { showError(error.message); }
  input.focus();
}
boot();
