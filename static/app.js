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
const miyoriConsole = el("miyoriConsole");
const consoleHeader = el("consoleHeader");
const toggleConsole = el("toggleConsole");

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
  sendButton.disabled = value;
  input.disabled = value;
  projectSelect.disabled = value;
  sendButton.textContent = value ? "Думаю…" : "Отправить";
  setPulse(value ? "thinking" : "ready");
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

  const article = document.createElement("article");
  article.className = "message assistant welcome-message";

  const avatar = document.createElement("div");
  avatar.className = "avatar nexus-avatar";
  avatar.textContent = "狐";

  const bubble = document.createElement("div");
  bubble.className = "bubble welcome-bubble quiet-welcome";
  bubble.innerHTML =
    '<div class="quiet-welcome-top">' +
      '<div><strong>Миёри</strong><p>Здравствуйте, Господин. Чем займёмся?</p></div>' +
      '<div class="pulse-mini"><span class="pulse-dot"></span><span id="pulseText">готова</span></div>' +
    '</div>' +
    '<div id="nexusSuggestions" class="quiet-suggestions">' +
      '<div class="nexus-loading">Подбираю следующий шаг…</div>' +
    '</div>' +
    '<button id="openInnerWorld" class="inner-world-link" type="button">◎ Состояние и детали проекта</button>';

  article.append(avatar, bubble);
  messages.appendChild(article);
  conversationTitle.textContent = "Новый разговор";
  messages.scrollTop = 0;
  setPulse("ready");

  const openInnerWorld = el("openInnerWorld");
  if (openInnerWorld) {
    openInnerWorld.addEventListener("click", () => openConsole("context"));
  }
}


async function loadNexus() {
  if (!state.projectId) return;
  const suggestions = el("nexusSuggestions");
  if (!suggestions) return;

  try {
    const data = await api("/api/projects/" + state.projectId + "/nexus");
    suggestions.innerHTML = "";

    for (const suggestion of data.suggestions) {
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

    const c = data.counts;
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


function addContextOrbit(brain, agent) {
  const actions = agent?.actions?.filter((item) => item.status === "completed") || [];
  const sources = brain?.sources || [];
  const memoryCount = brain?.memory_items || 0;
  const plan = brain?.plan || [];

  if (!memoryCount && !sources.length && !actions.length && !plan.length) return;

  const drawer = document.createElement("section");
  drawer.className = "response-context collapsed";

  const summaryBits = [];
  if (sources.length) summaryBits.push(sources.length + " источн.");
  if (memoryCount) summaryBits.push(memoryCount + " память");
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
        '<strong>' + escapeHtml(source.filename || "Документ") +
        ' · ' + source.chunk_index + '</strong>' +
        '<p>' + escapeHtml(source.content || "") + '</p>';
      section.appendChild(item);
    }
    body.appendChild(section);
  }

  if (memoryCount) {
    const section = document.createElement("div");
    section.className = "context-section compact";
    section.innerHTML =
      '<h4>Память</h4><div class="context-stat">Использовано подтверждённых фактов: <strong>' +
      memoryCount + '</strong></div>';
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
    loadTools(), loadPermissions(), loadTasks(), loadDevelopment(), loadNexus()
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

function addActivityCard(title, details, tone = "neutral", actions = []) {
  const article = document.createElement("article");
  article.className = "message activity";
  const card = document.createElement("div");
  card.className = "activity-card tone-" + tone;

  const head = document.createElement("div");
  head.className = "activity-head";
  head.innerHTML = '<span class="activity-icon">✋</span><div><strong>' +
    escapeHtml(title) + '</strong><small>Действие Миёри</small></div>';
  card.appendChild(head);

  if (details) {
    const body = document.createElement("div");
    body.className = "activity-body";
    if (typeof details === "string") {
      body.textContent = details;
    } else {
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(details, null, 2);
      body.appendChild(pre);
    }
    card.appendChild(body);
  }

  if (actions.length) {
    const actionRow = document.createElement("div");
    actionRow.className = "activity-actions";
    for (const item of actions) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = item.label;
      if (item.primary) button.classList.add("primary");
      button.onclick = item.onClick;
      actionRow.appendChild(button);
    }
    card.appendChild(actionRow);
  }

  article.appendChild(card);
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
  return card;
}

function askToolArguments(toolName) {
  if (toolName === "project_memory_search" || toolName === "project_document_search") {
    const query = prompt("Что искать?");
    if (!query || !query.trim()) return null;
    return {query: query.trim()};
  }
  if (toolName === "workspace_read") {
    const path = prompt("Путь к файлу в workspace:");
    if (!path || !path.trim()) return null;
    return {path: path.trim()};
  }
  if (toolName === "workspace_create" || toolName === "workspace_modify") {
    const path = prompt("Путь к файлу в workspace:");
    if (!path || !path.trim()) return null;
    const content = prompt("Содержимое файла:");
    if (content === null) return null;
    return {path: path.trim(), content};
  }
  return {};
}

function toolLabel(name) {
  const labels = {
    project_memory_search: "Память",
    project_document_search: "Документы",
    project_status: "Статус",
    workspace_list: "Файлы",
    workspace_read: "Прочитать",
    workspace_create: "Создать файл",
    workspace_modify: "Изменить файл"
  };
  return labels[name] || name;
}

function permissionPreview(request) {
  const args = request.arguments || {};
  const lines = [];
  if (args.path) lines.push("Файл: " + args.path);
  if (typeof args.content === "string") {
    const preview = args.content.length > 500 ? args.content.slice(0, 500) + "…" : args.content;
    lines.push("Содержимое:\n" + preview);
  }
  if (request.reason) lines.push("Причина: " + request.reason);
  return lines.join("\n\n") || "Это действие изменит workspace проекта.";
}

function addToolResultCard(toolName, result) {
  const card = addActivityCard("Готово · " + toolLabel(toolName), null, "success");
  const body = document.createElement("div");
  body.className = "activity-body structured-result";

  if (toolName === "workspace_list") {
    const files = result.files || [];
    if (!files.length) {
      body.textContent = "Workspace пока пуст.";
    } else {
      for (const file of files.slice(0, 40)) {
        const row = document.createElement("div");
        row.className = "result-row";
        row.innerHTML = '<div><strong>' + escapeHtml(file.path) + '</strong><small>' +
          file.size_bytes + ' байт</small></div>';
        const read = document.createElement("button");
        read.type = "button";
        read.textContent = "Прочитать";
        read.onclick = () => runChatTool(state.tools.workspace_read, {path: file.path});
        row.appendChild(read);
        body.appendChild(row);
      }
    }
  } else if (toolName === "workspace_read") {
    body.innerHTML = '<div class="result-title">' + escapeHtml(result.path || "Файл") + '</div>';
    const pre = document.createElement("pre");
    pre.textContent = result.content || "";
    body.appendChild(pre);
    if (result.truncated) {
      const note = document.createElement("div");
      note.className = "result-note";
      note.textContent = "Показана только часть файла.";
      body.appendChild(note);
    }
  } else if (toolName === "project_document_search") {
    const chunks = result.chunks || [];
    if (!chunks.length) body.textContent = "Подходящих фрагментов не найдено.";
    for (const item of chunks.slice(0, 8)) {
      const source = document.createElement("div");
      source.className = "source-card";
      source.innerHTML =
        '<strong>' + escapeHtml(item.filename) + ' · фрагмент ' + item.chunk_index + '</strong>' +
        '<p>' + escapeHtml((item.content || "").slice(0, 360)) + '</p>';
      const ask = document.createElement("button");
      ask.type = "button";
      ask.textContent = "Спросить об этом";
      ask.onclick = () => {
        input.value = "По источнику " + item.filename + ", фрагмент " + item.chunk_index + ": ";
        input.focus();
      };
      source.appendChild(ask);
      body.appendChild(source);
    }
  } else if (toolName === "project_memory_search") {
    const facts = result.facts || [];
    if (!facts.length) body.textContent = "Подтверждённых совпадений в памяти нет.";
    for (const fact of facts.slice(0, 10)) {
      const row = document.createElement("div");
      row.className = "fact-result";
      row.innerHTML = '<strong>#' + fact.id + '</strong><span>' +
        escapeHtml(fact.statement) + '</span><small>' + escapeHtml(fact.status || "") + '</small>';
      body.appendChild(row);
    }
  } else if (toolName === "project_status") {
    const project = result.project || {};
    body.innerHTML =
      '<div class="status-grid"><span>Проект</span><strong>' + escapeHtml(project.name || "—") +
      '</strong><span>Состояние</span><strong>' + escapeHtml(result.status || "—") + '</strong></div>';
  } else {
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(result, null, 2);
    body.appendChild(pre);
  }

  card.appendChild(body);
  messages.scrollTop = messages.scrollHeight;
}

async function runChatTool(tool, providedArgs = null) {
  if (!tool) return;
  const args = providedArgs || askToolArguments(tool.name);
  setPulse(tool.permission === "read" ? "reading" : "acting");
  if (args === null) return;

  addActivityCard(toolLabel(tool.name), "Запускаю действие…", "working");

  try {
    const result = await api("/api/projects/" + state.projectId + "/tools/execute", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({name: tool.name, arguments: args})
    });

    if (result.status === "approval_required") {
      const req = result.permission_request;
      addActivityCard(
        "Нужно подтверждение · " + toolLabel(tool.name),
        permissionPreview(req),
        "warning",
        [
          {
            label: "Разрешить",
            primary: true,
            onClick: async () => {
              await decidePermission(req.id, true, true);
            }
          },
          {
            label: "Отклонить",
            onClick: async () => {
              await decidePermission(req.id, false, true);
            }
          }
        ]
      );
      setPulse("waiting");
      await loadPermissions();
      return;
    }

    addToolResultCard(tool.name, result.result);
    setPulse("ready");
  } catch (error) {
    addActivityCard(
      "Ошибка · " + toolLabel(tool.name),
      error.message,
      "error"
    );
    setPulse("ready");
  }
}

async function loadTools() {
  try {
    const data = await api("/api/tools");
    state.tools = Object.fromEntries(data.tools.map((tool) => [tool.name, tool]));
    const chatActionBar = el("chatActionBar");
    if (!chatActionBar) return;
    chatActionBar.innerHTML = "";
    for (const tool of data.tools) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chat-action";
      button.innerHTML =
        '<span class="chat-action-icon">' +
        (tool.permission === "read" ? "↗" : "✎") +
        '</span><span><strong>' + escapeHtml(toolLabel(tool.name)) +
        '</strong><small>' + (tool.permission === "read" ? "авто" : "подтверждение") +
        "</small></span>";
      button.onclick = () => runChatTool(tool);
      chatActionBar.appendChild(button);
    }

    const selfCheck = document.createElement("button");
    selfCheck.type = "button";
    selfCheck.className = "chat-action special";
    selfCheck.innerHTML = '<span class="chat-action-icon">✓</span><span><strong>Самопроверка</strong><small>фоновая задача</small></span>';
    selfCheck.onclick = () => runChatBackgroundTask("self_check", "Самопроверка");
    chatActionBar.appendChild(selfCheck);

    const memoryJob = document.createElement("button");
    memoryJob.type = "button";
    memoryJob.className = "chat-action special";
    memoryJob.innerHTML = '<span class="chat-action-icon">✦</span><span><strong>Консолидация</strong><small>фоновая задача</small></span>';
    memoryJob.onclick = () => runChatBackgroundTask("memory_consolidation", "Консолидация памяти");
    chatActionBar.appendChild(memoryJob);
  } catch (error) {
    chatActionBar.innerHTML = '<div class="conversation-empty">' + escapeHtml(error.message) + "</div>";
  }
}

async function decidePermission(requestId, approved, fromChat = false) {
  try {
    const result = await api("/api/projects/" + state.projectId + "/permissions/" + requestId + "/decision", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({approved})
    });
    if (fromChat) {
      if (approved) {
        addActivityCard(
          "Разрешение выполнено",
          result.execution?.result || "Действие выполнено.",
          "success"
        );
      } else {
        addActivityCard("Действие отклонено", "Изменений не внесено.", "neutral");
      }
    }
    setPulse("ready");
    await Promise.all([loadPermissions(), loadTools(), loadNexus()]);
  } catch (error) {
    if (fromChat) addActivityCard("Ошибка разрешения", error.message, "error");
    else showError(error.message);
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

async function refreshChatTask(taskId, label) {
  try {
    const data = await api("/api/projects/" + state.projectId + "/tasks");
    const task = data.tasks.find((item) => item.id === taskId);
    if (!task) {
      addActivityCard(label, "Задача не найдена.", "error");
      return;
    }
    const tone = task.status === "completed" ? "success" :
      task.status === "failed" ? "error" :
      task.status === "cancelled" ? "neutral" : "working";
    addActivityCard(
      label + " · " + task.status,
      task.result || ("Задача #" + task.id),
      tone,
      (task.status === "queued" || task.status === "running")
        ? [{label: "Отменить", onClick: () => cancelTask(task.id, true)}]
        : []
    );
  } catch (error) {
    addActivityCard(label, error.message, "error");
  }
}

async function runChatBackgroundTask(taskType, label) {
  if (!state.projectId) return;
  try {
    const data = await api("/api/projects/" + state.projectId + "/tasks", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({task_type: taskType, payload: {}})
    });
    const task = data.task;
    addActivityCard(
      label + " · запущена",
      "Задача #" + task.id + " добавлена в очередь.",
      "working",
      [{label: "Обновить статус", primary: true, onClick: () => refreshChatTask(task.id, label)},
       {label: "Отменить", onClick: () => cancelTask(task.id, true)}]
    );
    await loadTasks();
  } catch (error) {
    addActivityCard(label, error.message, "error");
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

async function cancelTask(taskId, fromChat = false) {
  try {
    await api("/api/projects/" + state.projectId + "/tasks/" + taskId + "/cancel", {
      method: "POST"
    });
    if (fromChat) addActivityCard("Задача отменена", "Задача #" + taskId, "neutral");
    await loadTasks();
  } catch (error) {
    if (fromChat) addActivityCard("Ошибка отмены задачи", error.message, "error");
    else showError(error.message);
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
  brainPlan.innerHTML = '<span class="empty-copy">План появится после запроса.</span>';
  agentTrace.innerHTML = '<span class="empty-copy">Действий ещё не было.</span>';
  agentBudget.textContent = "0/3";
  Promise.all([loadConversations(), loadTools(), loadNexus()]);
  input.focus();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.busy || !state.projectId) return;
  const text = input.value.trim();
  if (!text) return;

  showError("");
  addMessage("user", text);
  const livingIntent = createLivingIntent(text);
  updateLivingIntent(livingIntent, "context");
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
    updateLivingIntent(livingIntent, "actions");
    addMessage("assistant", data.answer);
    if (data.brain) {
      brainState.textContent = "ready";
      brainPlan.innerHTML = data.brain.plan.map(
        (item, index) => "<div>" + (index + 1) + ". " + escapeHtml(item) + "</div>"
      ).join("");

      if (data.brain.plan?.length) {
        const planCard = addActivityCard("План Brain", null, "neutral");
        const planBody = document.createElement("div");
        planBody.className = "activity-body plan-result";
        data.brain.plan.forEach((item, index) => {
          const row = document.createElement("div");
          row.className = "plan-row";
          row.innerHTML = '<span>' + (index + 1) + '</span><div>' + escapeHtml(item) + '</div>';
          planBody.appendChild(row);
        });
        planCard.appendChild(planBody);
      }

      if (data.brain.sources?.length) {
        const sourceCard = addActivityCard("Источники ответа", null, "neutral");
        const sourceBody = document.createElement("div");
        sourceBody.className = "activity-body source-list";
        data.brain.sources.forEach((source) => {
          const item = document.createElement("div");
          item.className = "source-card";
          item.innerHTML =
            '<strong>' + escapeHtml(source.filename || "Документ") +
            ' · фрагмент ' + source.chunk_index + '</strong>' +
            '<p>' + escapeHtml(source.content || "") + '</p>';
          const ask = document.createElement("button");
          ask.type = "button";
          ask.textContent = "Спросить по источнику";
          ask.onclick = () => {
            input.value = "По источнику " + (source.filename || "документ") +
              ", фрагмент " + source.chunk_index + ": ";
            input.focus();
          };
          item.appendChild(ask);
          sourceBody.appendChild(item);
        });
        sourceCard.appendChild(sourceBody);
      }
    }
    if (data.agent) {
      agentBudget.textContent = data.agent.steps_used + "/" + data.agent.max_steps;
      agentTrace.innerHTML = data.agent.actions.map((action) => {
        const tool = action.tool_name ? escapeHtml(action.tool_name) : "без инструмента";
        return '<div class="agent-step"><strong>Шаг ' + action.step_index + ' · ' + tool +
          '</strong><span>' + escapeHtml(action.reason) + '</span><small>' +
          escapeHtml(action.status) + '</small></div>';
      }).join("");

      const completedActions = data.agent.actions.filter((action) => action.status === "completed");
      if (completedActions.length) {
        addActivityCard(
          "Agent Core · действия",
          completedActions.map((action) => ({
            step: action.step_index,
            tool: action.tool_name || "без инструмента",
            status: action.status
          })),
          "neutral"
        );
      }
    }
    addContextOrbit(data.brain, data.agent);
    updateLivingIntent(
      livingIntent,
      "done",
      "готово",
      "Готово · " +
        (data.brain?.document_items || 0) + " источн. · " +
        (data.brain?.memory_items || 0) + " память · " +
        ((data.agent?.actions || []).filter((item) => item.status === "completed").length) + " действ."
    );
    await Promise.all([
      loadConversations(), loadMemory(), loadDocuments(),
      loadTools(), loadPermissions(), loadTasks(), loadDevelopment(), loadNexus()
    ]);
  } catch (error) {
    updateLivingIntent(livingIntent, "error", "нужно внимание", error.message || "Не удалось завершить задачу.");
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
    loadTools(), loadPermissions(), loadTasks(), loadDevelopment(), loadNexus()
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
  if (event.key === "Enter" && !event.shiftKey) {
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
el("newChat").addEventListener("click", startNewChat);
el("newChatSide").addEventListener("click", startNewChat);

async function boot() {
  showWelcome();
  await loadStatus();
  try { await loadProjects(); } catch (error) { showError(error.message); }
  input.focus();
}
boot();


function activateInspectorTab(name) {
  document.querySelectorAll(".inspector-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });
  document.querySelectorAll(".inspector-page").forEach((page) => {
    page.classList.toggle("active", page.dataset.page === name);
  });
}

document.querySelectorAll(".inspector-tab").forEach((button) => {
  button.addEventListener("click", () => activateInspectorTab(button.dataset.tab));
});

if (consoleHeader) {
  consoleHeader.addEventListener("click", toggleConsoleState);
}
if (toggleConsole) {
  toggleConsole.addEventListener("click", () => {
    toggleConsoleState();
    input.focus();
  });
}


