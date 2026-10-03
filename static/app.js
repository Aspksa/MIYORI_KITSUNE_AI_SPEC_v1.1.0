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

function setProcessingStage(stage, detail = null) {
  const order = ["accepted", "context", "work", "result"];
  const current = order.indexOf(stage);
  document.querySelectorAll(".processing-step").forEach((row) => {
    const index = order.indexOf(row.dataset.stage);
    row.classList.toggle("active", index === current);
    row.classList.toggle("completed", current >= 0 && index < current);
    if (index === current && detail) {
      const small = row.querySelector("small");
      if (small) small.textContent = detail;
    }
  });
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
  bubble.className = "bubble welcome-bubble clean-welcome";
  bubble.innerHTML =
    '<div class="quiet-welcome-top">' +
      '<div><strong>Миёри</strong><p>Здравствуйте, Господин. Чем займёмся?</p></div>' +
      '<div class="pulse-mini"><span class="pulse-dot"></span><span id="pulseText">готова</span></div>' +
    '</div>' +
    '<div id="nexusSuggestions" hidden></div>';

  article.append(avatar, bubble);
  messages.appendChild(article);
  conversationTitle.textContent = "Miyori Kitsune";
  messages.scrollTop = 0;
  setPulse("ready");
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
  if (!projectLabel) return;
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

    const truthJob = document.createElement("button");
    truthJob.type = "button";
    truthJob.className = "chat-action special";
    truthJob.innerHTML = '<span class="chat-action-icon">⌕</span><span><strong>Ревизия знаний</strong><small>фоновая задача</small></span>';
    truthJob.onclick = () => runChatBackgroundTask("epistemic_review", "Ревизия знаний");
    chatActionBar.appendChild(truthJob);
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
  conversationTitle.textContent = "Miyori Kitsune";
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
  setProcessingStage("accepted", "Ожидаю задачу");
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
  setProcessingStage("accepted", "Запрос получен");
  setProcessingStage("context", "RAG ищет релевантный контекст");
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
    setProcessingStage("work", "Анализирую и выполняю шаги");
    addMessage("assistant", data.answer);

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
      if (agentBudget) agentBudget.textContent = data.agent.steps_used + "/" + data.agent.max_steps;
      if (agentTrace) {
        agentTrace.innerHTML = (data.agent.actions || []).map((action) => {
          const tool = action.tool_name ? escapeHtml(action.tool_name) : "без инструмента";
          return '<div class="agent-step"><strong>Шаг ' + action.step_index + ' · ' + tool +
            '</strong><span>' + escapeHtml(action.reason) + '</span><small>' +
            escapeHtml(action.status) + '</small></div>';
        }).join("");
      }
    }

    setProcessingStage("result", "Результат готов");
    await Promise.all([
      loadConversations(), loadMemory(), loadDocuments(),
      loadTools(), loadPermissions(), loadTasks(), loadDevelopment(), loadNexus()
    ]);
  } catch (error) {
    setProcessingStage("result", "Нужно внимание");
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
if (el("newChat")) el("newChat").addEventListener("click", startNewChat);
if (el("newChatSide")) el("newChatSide").addEventListener("click", startNewChat);

function openSidebarSection(title, detail, tone = "neutral") {
  addActivityCard(title, detail, tone);
  messages.scrollTop = messages.scrollHeight;
}

const menuMiyoriAI = el("menuMiyoriAI");
const menuMobileApp = el("menuMobileApp");
const menuAccount = el("menuAccount");
const menuSettings = el("menuSettings");
const menuDocumentsHub = el("menuDocumentsHub");
const menuWorkProjects = el("menuWorkProjects");
const menuHomeProjects = el("menuHomeProjects");
const menuProjectUpdate = el("menuProjectUpdate");

const chatHeader = el("chatHeader");
const chatComposer = el("chatComposer");
const workspaceView = el("workspaceView");
const workspaceBody = el("workspaceBody");
const workspaceTitle = el("workspaceTitle");
const workspaceSubtitle = el("workspaceSubtitle");
const workspaceEyebrow = el("workspaceEyebrow");

const workspaceMenu = {
  ai: menuMiyoriAI,
  mobile: menuMobileApp,
  account: menuAccount,
  settings: menuSettings,
  documents: menuDocumentsHub,
  work: menuWorkProjects,
  home: menuHomeProjects,
  update: menuProjectUpdate,
};

function setWorkspaceMenuActive(name) {
  Object.entries(workspaceMenu).forEach(([key, button]) => {
    if (button) button.classList.toggle("active", key === name);
  });
}

function showChatWorkspace() {
  if (workspaceView) {
    workspaceView.hidden = true;
    workspaceView.style.display = "none";
  }
  if (chatHeader) chatHeader.hidden = false;
  if (messages) messages.hidden = false;
  if (chatComposer) chatComposer.hidden = false;
  if (messages) messages.scrollTop = messages.scrollHeight;
  setWorkspaceMenuActive("ai");
  input.focus();
}

function showWorkspaceShell(name, eyebrow, title, subtitle) {
  if (chatHeader) chatHeader.hidden = true;
  if (messages) messages.hidden = true;
  if (chatComposer) chatComposer.hidden = true;
  if (workspaceView) {
    workspaceView.hidden = false;
    workspaceView.style.display = "grid";
  }
  workspaceEyebrow.textContent = eyebrow;
  workspaceTitle.textContent = title;
  workspaceSubtitle.textContent = subtitle;
  workspaceBody.innerHTML = '<div class="workspace-loading">Загружаю раздел…</div>';
  setWorkspaceMenuActive(name);
}

function workspaceResult(message, tone = "neutral") {
  return '<div class="sheet-result ' + tone + '">' + escapeHtml(message) + '</div>';
}

function shortSha(value) {
  if (!value) return "—";
  const text = String(value).trim();
  return text.length > 10 ? text.slice(0, 10) : text;
}

async function renderAccountWorkspace() {
  showWorkspaceShell("account", "Личный кабинет", "Личный кабинет", "Профиль, Cloud.ru, устройства и сессии.");
  try {
    const [profileData, cloudData] = await Promise.all([
      api("/api/account/profile"),
      api("/api/account/cloudru")
    ]);
    const profile = profileData.profile || {};
    const cloud = cloudData.cloudru || {};
    let devices = profileData.devices || [];

    workspaceBody.innerHTML =
      '<section class="account-dashboard">' +
        '<div class="account-hero">' +
          '<div class="account-avatar-wrap">' +
            '<div id="accountAvatar" class="account-avatar">' +
              (profile.avatar_url
                ? '<img src="' + profile.avatar_url + '?v=' + Date.now() + '" alt="Аватар">'
                : '<span>' + escapeHtml((profile.owner_name || "A").slice(0,1).toUpperCase()) + '</span>') +
            '</div>' +
            '<label class="account-avatar-edit">Изменить<input id="accountAvatarInput" type="file" accept="image/png,image/jpeg,image/webp" hidden></label>' +
          '</div>' +
          '<div class="account-hero-copy"><span>Владелец Miyori Kitsune</span><h3 id="accountOwnerTitle">' +
            escapeHtml(profile.owner_name || "Не указано") + '</h3><p>Обращение: <strong>' +
            escapeHtml(profile.miyori_address || "Господин") + '</strong></p></div>' +
          '<div class="account-hero-status"><span class="soft-status ' + (cloud.configured ? 'ok' : 'warn') + '">' +
            (cloud.configured ? 'Cloud.ru подключён' : 'Cloud.ru не настроен') + '</span></div>' +
        '</div>' +
        '<div class="account-stat-grid">' +
          '<div><span>Основной профиль</span><strong>' + (profile.profile_kind === "work" ? "Рабочий" : "Личный") + '</strong></div>' +
          '<div><span>Язык</span><strong>' + escapeHtml(profile.language || "ru-RU") + '</strong></div>' +
          '<div><span>Часовой пояс</span><strong>' + escapeHtml(profile.timezone || "UTC") + '</strong></div>' +
          '<div><span>Устройства</span><strong id="accountDeviceCount">' + devices.length + '</strong></div>' +
        '</div>' +
        '<div class="account-tabs">' +
          '<button class="account-tab active" data-account-tab="profile" type="button">Профиль</button>' +
          '<button class="account-tab" data-account-tab="cloud" type="button">Cloud.ru</button>' +
          '<button class="account-tab" data-account-tab="devices" type="button">Устройства и сессии</button>' +
        '</div>' +
        '<div class="account-tab-panels">' +
          '<section class="account-tab-panel active" data-account-panel="profile">' +
            '<form id="accountProfileForm" class="account-form-grid">' +
              '<label><span>Имя владельца</span><input id="accountOwnerName" type="text" value="' + escapeHtml(profile.owner_name || "") + '" placeholder="Aspksa"></label>' +
              '<label><span>Как Миёри должна обращаться</span><input id="accountAddress" type="text" value="' + escapeHtml(profile.miyori_address || "Господин") + '"></label>' +
              '<label><span>Язык</span><select id="accountLanguage">' +
                '<option value="ru-RU"' + ((profile.language || "ru-RU") === "ru-RU" ? " selected" : "") + '>Русский</option>' +
                '<option value="en-US"' + (profile.language === "en-US" ? " selected" : "") + '>English</option>' +
              '</select></label>' +
              '<label><span>Часовой пояс</span><input id="accountTimezone" type="text" value="' + escapeHtml(profile.timezone || "UTC") + '" placeholder="Europe/Moscow"></label>' +
              '<label><span>Основной профиль</span><select id="accountProfileKind">' +
                '<option value="personal"' + (profile.profile_kind !== "work" ? " selected" : "") + '>Личный</option>' +
                '<option value="work"' + (profile.profile_kind === "work" ? " selected" : "") + '>Рабочий</option>' +
              '</select></label>' +
              '<div id="accountProfileResult" class="account-form-result"></div>' +
              '<div class="sheet-actions account-form-actions"><button class="primary-sheet-button" type="submit">Сохранить профиль</button></div>' +
            '</form>' +
          '</section>' +
          '<section class="account-tab-panel" data-account-panel="cloud">' +
            '<div class="account-cloud-summary">' +
              '<div><span>Состояние API</span><strong>' + (cloud.configured ? "Настроено" : "Не настроено") + '</strong></div>' +
              '<div><span>Основная модель</span><strong>' + escapeHtml(cloud.model_id || "Не выбрана") + '</strong></div>' +
              '<div><span>Предпочтительная</span><strong>DeepSeek V4 Flash</strong></div>' +
              '<div><span>Расход запросов / токенов</span><strong>API статистики не подключён</strong></div>' +
            '</div>' +
            '<form id="accountCloudForm" class="settings-form account-cloud-form">' +
              '<label><span>API-ключ Cloud.ru</span><input id="accountCloudKey" type="password" autocomplete="off" placeholder="Вставьте новый ключ"><small>' +
              (cloud.api_key_set ? 'Сохранён: ' + escapeHtml(cloud.api_key_masked) + ' · пустое поле сохранит текущий ключ' : 'Ключ не сохранён') + '</small></label>' +
              '<label><span>Модель</span><select id="accountCloudModel"><option value="">Загружаю список моделей…</option></select><small id="accountCloudModelState">DeepSeek V4 Flash используется как предпочтительная модель.</small></label>' +
              '<label><span>Base URL</span><input id="accountCloudBase" type="url" value="' + escapeHtml(cloud.base_url || "https://foundation-models.api.cloud.ru/v1") + '"></label>' +
              '<div id="accountCloudResult"></div>' +
              '<div class="sheet-actions"><button id="accountCloudRefresh" class="secondary-sheet-button" type="button">Обновить модели</button><button id="accountCloudTest" class="secondary-sheet-button" type="button">Проверить соединение</button><button class="primary-sheet-button" type="submit">Сохранить Cloud.ru</button></div>' +
            '</form>' +
          '</section>' +
          '<section class="account-tab-panel" data-account-panel="devices">' +
            '<div class="account-devices-head"><div><strong>Устройства и сессии</strong><small>Текущий компьютер и будущие клиенты Miyori</small></div><span class="soft-status ok">Локальный доступ</span></div>' +
            '<div id="accountDevicesList" class="account-device-list"></div>' +
            '<div class="account-mobile-placeholder"><span>▣</span><div><strong>Мобильный клиент</strong><small>Будет подключаться через отдельную привязку устройства.</small></div><span class="soft-status neutral">Позже</span></div>' +
          '</section>' +
        '</div>' +
      '</section>';

    const switchTab = (name) => {
      workspaceBody.querySelectorAll("[data-account-tab]").forEach(button => button.classList.toggle("active", button.dataset.accountTab === name));
      workspaceBody.querySelectorAll("[data-account-panel]").forEach(panel => panel.classList.toggle("active", panel.dataset.accountPanel === name));
    };
    workspaceBody.querySelectorAll("[data-account-tab]").forEach(button => {
      button.onclick = () => switchTab(button.dataset.accountTab);
    });

    const renderDevices = () => {
      const list = el("accountDevicesList");
      list.innerHTML = devices.length ? devices.map(device =>
        '<div class="account-device-row">' +
          '<span class="account-device-icon">' + (device.session_kind === "desktop" ? "▣" : "◉") + '</span>' +
          '<div><strong>' + escapeHtml(device.device_name) + '</strong><small>' +
          escapeHtml(device.platform) + ' · последняя активность ' + escapeHtml(device.last_seen_at || "—") + '</small></div>' +
          '<span class="soft-status ' + (device.status === "active" ? "ok" : "neutral") + '">' + (device.status === "active" ? "Активно" : "Отключено") + '</span>' +
          '<button class="secondary-sheet-button" type="button" data-device-disconnect="' + device.id + '"' + (device.status !== "active" ? " disabled" : "") + '>Отключить</button>' +
        '</div>'
      ).join("") : '<div class="workspace-empty">Нет активных устройств.</div>';
      list.querySelectorAll("[data-device-disconnect]").forEach(button => {
        button.onclick = async () => {
          try {
            const data = await api("/api/account/devices/" + button.dataset.deviceDisconnect + "/disconnect", {method:"POST"});
            devices = data.devices || [];
            el("accountDeviceCount").textContent = devices.length;
            renderDevices();
          } catch (error) {
            showError(error.message);
          }
        };
      });
    };
    renderDevices();

    el("accountProfileForm").onsubmit = async (event) => {
      event.preventDefault();
      const result = el("accountProfileResult");
      try {
        const saved = await api("/api/account/profile", {
          method:"PUT",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            owner_name: el("accountOwnerName").value.trim(),
            miyori_address: el("accountAddress").value.trim(),
            language: el("accountLanguage").value,
            timezone: el("accountTimezone").value.trim(),
            profile_kind: el("accountProfileKind").value
          })
        });
        el("accountOwnerTitle").textContent = saved.profile.owner_name || "Не указано";
        result.innerHTML = workspaceResult("Профиль сохранён.", "success");
      } catch (error) {
        result.innerHTML = workspaceResult(error.message, "error");
      }
    };

    el("accountAvatarInput").onchange = async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      const body = new FormData();
      body.append("file", file);
      try {
        const response = await fetch("/api/account/profile/avatar", {method:"POST", body});
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || "Не удалось сохранить аватар.");
        el("accountAvatar").innerHTML = '<img src="' + data.profile.avatar_url + '?v=' + Date.now() + '" alt="Аватар">';
      } catch (error) {
        showError(error.message);
      }
      event.target.value = "";
    };

    const cloudModel = el("accountCloudModel");
    const cloudState = el("accountCloudModelState");
    const cloudResult = el("accountCloudResult");
    const cloudKey = el("accountCloudKey");
    const cloudBase = el("accountCloudBase");

    const populateCloudModels = (catalog, preferred = null) => {
      const models = catalog.chat_models || [];
      cloudModel.innerHTML = '<option value="">Выберите чат-модель…</option>';
      models.forEach(item => {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = item.name && item.name !== item.id ? item.name + " — " + item.id : item.id;
        cloudModel.appendChild(option);
      });
      const deepseek = catalog.preferred_model_id || "deepseek-ai/DeepSeek-V4-Flash";
      const desired = preferred || cloud.model_id || deepseek;
      const exists = models.some(item => item.id === desired);
      const deepseekExists = models.some(item => item.id === deepseek);
      cloudModel.value = exists ? desired : (deepseekExists ? deepseek : "");
      cloudState.textContent = deepseekExists
        ? "DeepSeek V4 Flash доступна и является предпочтительной."
        : "Доступных чат-моделей: " + models.length + ".";
    };

    const loadCloudModels = async () => {
      cloudModel.disabled = true;
      try {
        const catalog = await api("/api/account/cloudru/models");
        if (catalog.reason === "key_required") {
          cloudModel.innerHTML = '<option value="">Сначала сохраните API-ключ</option>';
          cloudState.textContent = "После сохранения ключа Miyori загрузит доступные модели.";
          cloudResult.innerHTML = workspaceResult("Cloud.ru ожидает API-ключ.", "neutral");
          return;
        }
        populateCloudModels(catalog, cloud.model_id);
      } catch (error) {
        cloudResult.innerHTML = workspaceResult(error.message, "error");
      } finally {
        cloudModel.disabled = false;
      }
    };

    el("accountCloudRefresh").onclick = loadCloudModels;
    el("accountCloudTest").onclick = async () => {
      cloudResult.innerHTML = workspaceResult("Проверяю Cloud.ru и выбранную модель…", "working");
      try {
        const checked = await api("/api/account/cloudru/test", {
          method:"POST",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            api_key: cloudKey.value.trim() || null,
            model_id: cloudModel.value || null,
            base_url: cloudBase.value.trim() || null
          })
        });
        populateCloudModels(checked, checked.selected_model);
        cloudResult.innerHTML = workspaceResult(checked.message || "Проверка завершена.", checked.ok && checked.chat_ok ? "success" : "warning");
      } catch (error) {
        cloudResult.innerHTML = workspaceResult(error.message, "error");
      }
    };

    el("accountCloudForm").onsubmit = async (event) => {
      event.preventDefault();
      if (!cloudModel.value) {
        cloudResult.innerHTML = workspaceResult("Выберите модель Cloud.ru.", "warning");
        return;
      }
      try {
        const saved = await api("/api/account/cloudru", {
          method:"PUT",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            api_key: cloudKey.value.trim() || null,
            model_id: cloudModel.value,
            base_url: cloudBase.value.trim()
          })
        });
        cloud.model_id = saved.cloudru.model_id;
        cloudResult.innerHTML = workspaceResult("Cloud.ru сохранён. Модель: " + saved.cloudru.model_id, "success");
        cloudKey.value = "";
        await loadStatus();
      } catch (error) {
        cloudResult.innerHTML = workspaceResult(error.message, "error");
      }
    };

    await loadCloudModels();
  } catch (error) {
    workspaceBody.innerHTML = workspaceResult(error.message, "error");
  }
}

async function renderUpdateWorkspace(refresh = false) {
  const formatUpdateSha = (value) => {
    if (!value) return "—";
    const text = String(value).trim();
    return text.length > 10 ? text.slice(0, 10) : text;
  };
  showWorkspaceShell("update", "Система", "Обновление проекта", "Проверка GitHub и безопасное обновление локальной Miyori.");
  workspaceBody.innerHTML =
    '<section class="workspace-card workspace-card-wide">' +
      '<div class="repository-card"><strong>Aspksa/MIYORI_KITSUNE_AI_SPEC_v1.1.0</strong>' +
      '<small>github.com · main · Git fast-forward или Portable ZIP</small></div>' +
      '<div id="workspaceUpdateStatus" class="workspace-loading">Проверяю состояние…</div>' +
      '<div class="sheet-actions"><button id="workspaceUpdateCheck" class="secondary-sheet-button" type="button">Проверить GitHub</button>' +
      '<button id="workspaceUpdateApply" class="primary-sheet-button" type="button">Обновить сейчас</button></div>' +
    '</section>';

  const container = el("workspaceUpdateStatus");
  const applyButton = el("workspaceUpdateApply");

  const load = async (doRefresh) => {
    container.innerHTML = workspaceResult(doRefresh ? "Проверяю GitHub…" : "Загружаю состояние…", "working");
    try {
      const data = doRefresh
        ? await api("/api/update/check", {method: "POST"})
        : await api("/api/update/status");
      const u = data.update;
      const mode = u.install_mode === "portable" ? "Portable ZIP" : "Git";
      const worktree = u.install_mode === "portable"
        ? "Portable установка"
        : (!u.clean ? "Есть локальные изменения" : "Чистая");
      let tone = "neutral";
      let note = "Нажмите «Проверить GitHub».";
      if (u.last_error) { tone = "error"; note = u.last_error; }
      else if (u.restart_required) { tone = "warning"; note = "Обновление применено. Перезапустите Miyori."; }
      else if (u.update_available) { tone = "warning"; note = "На GitHub доступна более новая версия."; }
      else if (u.remote_sha) { tone = "success"; note = "Локальная версия синхронизирована с GitHub."; }

      container.innerHTML =
        '<div class="update-status-grid">' +
          '<div><span>Режим</span><strong>' + escapeHtml(mode) + '</strong></div>' +
          '<div><span>Локальная версия</span><strong>' +
          escapeHtml(u.local_sha ? formatUpdateSha(u.local_sha) : ("Miyori " + (versionText?.textContent || "—"))) +
          '</strong></div>' +
          '<div><span>GitHub версия</span><strong>' + escapeHtml(formatUpdateSha(u.remote_sha)) + '</strong></div>' +
          '<div><span>Рабочая копия</span><strong>' + escapeHtml(worktree) + '</strong></div>' +
          '<div><span>Автообновление</span><strong>' + (u.auto_update ? 'Включено' : 'Выключено') + '</strong></div>' +
          '<div><span>Проверка</span><strong>' + escapeHtml(u.last_checked_at || '—') + '</strong></div>' +
        '</div>' + workspaceResult(note, tone) +
        (u.backup_path ? '<div class="sheet-note">Резервная копия: <code>' + escapeHtml(u.backup_path) + '</code></div>' : '');

      applyButton.disabled = !u.update_available || !!u.last_error ||
        (u.install_mode !== "portable" && (!u.clean || !u.origin_ok || u.current_branch !== u.branch || u.ahead > 0));
    } catch (error) {
      container.innerHTML = workspaceResult(error.message, "error");
      applyButton.disabled = true;
    }
  };

  el("workspaceUpdateCheck").onclick = () => load(true);
  applyButton.onclick = async () => {
    container.innerHTML = workspaceResult("Скачиваю и применяю безопасное обновление…", "working");
    try {
      const data = await api("/api/update/apply", {method: "POST"});
      const u = data.update;
      container.innerHTML = workspaceResult(
        u.updated
          ? "Обновление применено до " + formatUpdateSha(u.to_sha) + ". Перезапустите Miyori."
          : (u.message || "Обновление не требуется."),
        u.updated ? "success" : "neutral"
      ) + (u.backup_path ? '<div class="sheet-note">Резервная копия: <code>' + escapeHtml(u.backup_path) + '</code></div>' : '');
      applyButton.disabled = true;
    } catch (error) {
      container.innerHTML = workspaceResult(error.message, "error");
    }
  };

  await load(refresh);
}

async function renderDocumentsWorkspace() {
  showWorkspaceShell("documents", "Miyori Drive", "Документы / Облако / Miyori", "Файловое пространство проекта.");
  workspaceBody.innerHTML =
    '<section class="miyori-drive">' +
      '<aside class="drive-sidebar">' +
        '<button id="driveUploadButton" class="drive-primary-action" type="button">＋ Загрузить</button>' +
        '<button id="driveNewFolderButton" class="drive-secondary-action" type="button">＋ Новая папка</button>' +
        '<nav class="drive-nav">' +
          '<button class="drive-nav-item active" data-drive-scope="files" type="button"><span>▤</span><strong>Мои файлы</strong></button>' +
          '<button class="drive-nav-item" data-drive-scope="recent" type="button"><span>◷</span><strong>Недавние</strong></button>' +
          '<button class="drive-nav-item" data-drive-scope="rag" type="button"><span>✦</span><strong>Знания Miyori</strong></button>' +
        '</nav>' +
        '<div class="drive-storage-card"><span>Хранилище проекта</span><strong id="driveStorageText">—</strong><small>Файлы используются в RAG Miyori</small></div>' +
      '</aside>' +
      '<main class="drive-main">' +
        '<div class="drive-toolbar">' +
          '<div id="driveBreadcrumb" class="drive-breadcrumb"></div>' +
          '<div class="drive-toolbar-actions">' +
            '<label class="drive-search"><span>⌕</span><input id="driveSearchInput" type="search" placeholder="Поиск по файлам"></label>' +
            '<button id="driveGridView" class="drive-view-button active" type="button" title="Плитка">▦</button>' +
            '<button id="driveListView" class="drive-view-button" type="button" title="Список">☷</button>' +
          '</div>' +
        '</div>' +
        '<section id="driveContent" class="drive-content">' +
          '<div id="driveFoldersSection" class="drive-section"><div class="drive-section-title"><strong>Папки</strong><span id="driveFolderCount"></span></div><div id="driveFolders" class="drive-folder-grid"></div></div>' +
          '<div id="driveFilesSection" class="drive-section"><div class="drive-section-title"><strong>Файлы</strong><span id="driveFileCount"></span></div><div id="driveFiles" class="drive-file-grid"></div></div>' +
          '<div id="driveKnowledgeSection" class="drive-section" hidden><div class="drive-section-title"><strong>Знания Miyori</strong></div><div id="driveKnowledge"></div></div>' +
          '<div id="driveResult"></div>' +
        '</section>' +
      '</main>' +
      '<input id="driveFileInput" type="file" accept=".txt,.md,.markdown,.json,.pdf,.docx,.xlsx,.pptx" multiple hidden>' +
    '</section>';

  let activeFolderId = null;
  let activeScope = "files";
  let viewMode = "grid";
  let folders = [];
  let documents = [];
  let ragStatus = null;

  const fileType = (name) => {
    const ext = String(name || "").split(".").pop().toLowerCase();
    if (ext === "pdf") return {icon: "PDF", cls: "pdf"};
    if (ext === "docx") return {icon: "W", cls: "word"};
    if (ext === "xlsx") return {icon: "X", cls: "excel"};
    if (ext === "pptx") return {icon: "P", cls: "powerpoint"};
    if (["md","markdown","txt"].includes(ext)) return {icon: "TXT", cls: "text"};
    if (ext === "json") return {icon: "{ }", cls: "json"};
    return {icon: "▤", cls: "file"};
  };

  const formatBytes = (bytes) => {
    const value = Number(bytes || 0);
    if (value < 1024) return value + " Б";
    if (value < 1024 * 1024) return (value / 1024).toFixed(1) + " КБ";
    return (value / (1024 * 1024)).toFixed(1) + " МБ";
  };

  const formatDate = (value) => {
    if (!value) return "";
    try {
      return new Date(value).toLocaleDateString("ru-RU", {day: "2-digit", month: "short", year: "numeric"});
    } catch (_) {
      return "";
    }
  };

  const folderPath = (folderId) => {
    const map = new Map(folders.map(folder => [folder.id, folder]));
    const path = [];
    let current = folderId ? map.get(folderId) : null;
    const guard = new Set();
    while (current && !guard.has(current.id)) {
      guard.add(current.id);
      path.unshift(current);
      current = current.parent_id ? map.get(current.parent_id) : null;
    }
    return path;
  };

  const renderBreadcrumb = () => {
    const parts = folderPath(activeFolderId);
    el("driveBreadcrumb").innerHTML =
      '<button type="button" data-drive-root="1">Мои файлы</button>' +
      parts.map(folder =>
        '<span>›</span><button type="button" data-drive-crumb="' + folder.id + '">' + escapeHtml(folder.name) + '</button>'
      ).join("");
    const root = workspaceBody.querySelector("[data-drive-root]");
    if (root) root.onclick = async () => { activeFolderId = null; activeScope = "files"; await renderDrive(); };
    workspaceBody.querySelectorAll("[data-drive-crumb]").forEach(button => {
      button.onclick = async () => { activeFolderId = Number(button.dataset.driveCrumb); activeScope = "files"; await renderDrive(); };
    });
  };

  const renderDrive = async () => {
    const resultNode = el("driveResult");
    try {
      const [docs, status] = await Promise.all([
        api("/api/projects/" + state.projectId + "/documents"),
        api("/api/status")
      ]);
      folders = docs.folders || [];
      documents = docs.documents || [];
      ragStatus = status.rag || {};

      const query = (el("driveSearchInput")?.value || "").trim().toLowerCase();
      const folderMap = new Map(folders.map(folder => [folder.id, folder]));
      const childFolders = folders.filter(folder =>
        activeFolderId === null ? folder.parent_id === null : folder.parent_id === activeFolderId
      );
      const currentDocs = documents.filter(document =>
        activeFolderId === null ? document.folder_id === null : document.folder_id === activeFolderId
      );

      let visibleFolders = childFolders;
      let visibleDocs = currentDocs;

      if (activeScope === "recent") {
        visibleFolders = [];
        visibleDocs = [...documents].sort((a,b) => String(b.created_at).localeCompare(String(a.created_at))).slice(0, 30);
      }

      if (query) {
        visibleFolders = folders.filter(folder => folder.name.toLowerCase().includes(query));
        visibleDocs = documents.filter(document => document.filename.toLowerCase().includes(query));
      }

      renderBreadcrumb();
      el("driveFolderCount").textContent = visibleFolders.length ? visibleFolders.length : "";
      el("driveFileCount").textContent = visibleDocs.length ? visibleDocs.length : "";

      const totalBytes = documents.reduce((sum, document) => sum + Number(document.size_bytes || 0), 0);
      el("driveStorageText").textContent = formatBytes(totalBytes) + " · " + documents.length + " файлов";

      const folderSection = el("driveFoldersSection");
      const filesSection = el("driveFilesSection");
      const knowledgeSection = el("driveKnowledgeSection");

      folderSection.hidden = activeScope === "rag" || !visibleFolders.length;
      filesSection.hidden = activeScope === "rag";
      knowledgeSection.hidden = activeScope !== "rag";

      el("driveFolders").innerHTML = visibleFolders.map(folder =>
        '<button class="drive-folder-tile" type="button" data-drive-folder="' + folder.id + '">' +
          '<span class="drive-folder-shape">▰</span>' +
          '<span class="drive-tile-copy"><strong>' + escapeHtml(folder.name) + '</strong><small>' +
          folder.document_count + ' файлов</small></span>' +
          '<span class="drive-more">•••</span>' +
        '</button>'
      ).join("");

      el("driveFiles").className = viewMode === "list" ? "drive-file-list" : "drive-file-grid";
      el("driveFiles").innerHTML = visibleDocs.length
        ? visibleDocs.map(document => {
            const type = fileType(document.filename);
            const folderName = document.folder_name || (document.folder_id ? (folderMap.get(document.folder_id)?.name || "") : "Мои файлы");
            return '<article class="drive-file-item ' + viewMode + '">' +
              '<div class="drive-file-preview ' + type.cls + '"><span>' + escapeHtml(type.icon) + '</span></div>' +
              '<div class="drive-file-copy"><strong title="' + escapeHtml(document.filename) + '">' + escapeHtml(document.filename) + '</strong>' +
              '<small>' + escapeHtml(folderName) + ' · ' + formatBytes(document.size_bytes) + ' · ' + formatDate(document.created_at) + '</small></div>' +
              '<button class="drive-file-menu" type="button" aria-label="Действия">•••</button>' +
            '</article>';
          }).join("")
        : '<div class="drive-empty"><span>☁</span><strong>Здесь пока пусто</strong><small>Загрузите файл или создайте папку.</small></div>';

      el("driveKnowledge").innerHTML =
        '<div class="drive-knowledge-card"><span>✦</span><div><strong>RAG Miyori</strong><small>' +
        (ragStatus.fts5 ? "Hybrid FTS5 + lexical" : "Lexical fallback") +
        ' · ' + (ragStatus.indexed_chunks || 0) + ' фрагментов проиндексировано</small></div></div>' +
        '<div class="drive-knowledge-card"><span>▤</span><div><strong>Документы проекта</strong><small>' +
        documents.length + ' файлов доступны для контекста Miyori</small></div></div>';

      workspaceBody.querySelectorAll("[data-drive-folder]").forEach(button => {
        button.onclick = async () => {
          activeFolderId = Number(button.dataset.driveFolder);
          activeScope = "files";
          await renderDrive();
        };
      });

      if (resultNode && !resultNode.dataset.persist) resultNode.innerHTML = "";
    } catch (error) {
      if (resultNode) resultNode.innerHTML = workspaceResult(error.message, "error");
    }
  };

  const uploadFiles = async (fileList) => {
    const resultNode = el("driveResult");
    const files = Array.from(fileList || []);
    if (!files.length) return;

    let completed = 0;
    for (const file of files) {
      resultNode.dataset.persist = "1";
      resultNode.innerHTML = workspaceResult("Загружаю «" + file.name + "»…", "working");
      const body = new FormData();
      body.append("file", file);
      if (activeFolderId !== null) body.append("folder_id", String(activeFolderId));
      try {
        const response = await fetch("/api/projects/" + state.projectId + "/documents", {method: "POST", body});
        const data = await response.json();
        if (!response.ok) {
          const detail = data?.detail || "Не удалось загрузить документ.";
          throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
        }
        completed += 1;
      } catch (error) {
        resultNode.innerHTML = workspaceResult(file.name + ": " + error.message, "error");
        return;
      }
    }

    resultNode.innerHTML = workspaceResult("Загружено файлов: " + completed + ". Документы добавлены в RAG.", "success");
    await renderDrive();
    delete resultNode.dataset.persist;
  };

  el("driveUploadButton").onclick = () => el("driveFileInput").click();
  el("driveFileInput").onchange = async (event) => {
    await uploadFiles(event.target.files);
    event.target.value = "";
  };

  el("driveNewFolderButton").onclick = async () => {
    const name = prompt("Название новой папки:");
    if (!name || !name.trim()) return;
    const resultNode = el("driveResult");
    try {
      await api("/api/projects/" + state.projectId + "/document-folders", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({name: name.trim(), parent_id: activeFolderId})
      });
      resultNode.innerHTML = workspaceResult("Папка создана.", "success");
      await renderDrive();
    } catch (error) {
      resultNode.innerHTML = workspaceResult(error.message, "error");
    }
  };

  workspaceBody.querySelectorAll("[data-drive-scope]").forEach(button => {
    button.onclick = async () => {
      activeScope = button.dataset.driveScope;
      workspaceBody.querySelectorAll("[data-drive-scope]").forEach(item => item.classList.toggle("active", item === button));
      await renderDrive();
    };
  });

  el("driveGridView").onclick = async () => {
    viewMode = "grid";
    el("driveGridView").classList.add("active");
    el("driveListView").classList.remove("active");
    await renderDrive();
  };
  el("driveListView").onclick = async () => {
    viewMode = "list";
    el("driveListView").classList.add("active");
    el("driveGridView").classList.remove("active");
    await renderDrive();
  };

  let searchTimer = null;
  el("driveSearchInput").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(renderDrive, 180);
  });

  await renderDrive();
}

async function renderPrimavtodorSubmodule(project, module) {
  showWorkspaceShell(
    "work",
    'АО "Примавтодор"',
    module.name,
    "Отдельный модуль рабочего проекта."
  );

  const descriptions = {
    timesheet: "Учёт табелей, смен, рабочего времени и связанных документов.",
    garage: "Учёт гаража, техники, транспорта и эксплуатационных материалов.",
    employees: "Сотрудники проекта, кадровые сведения и связанные документы."
  };

  workspaceBody.innerHTML =
    '<section class="workspace-card workspace-card-wide primavtodor-module-view">' +
      '<div class="workspace-hero-icon">' +
        (module.module_key === "timesheet" ? "▦" : module.module_key === "garage" ? "▰" : "◉") +
      '</div>' +
      '<strong>' + escapeHtml(module.name) + '</strong>' +
      '<p>' + escapeHtml(descriptions[module.module_key] || "Модуль проекта.") + '</p>' +
      '<div class="sheet-note">Модуль привязан к проекту АО «Примавтодор». Данные и документы остаются в контексте этого проекта.</div>' +
      '<div class="sheet-actions">' +
        '<button id="primavtodorModuleBack" class="secondary-sheet-button" type="button">← К проекту</button>' +
        '<button id="primavtodorModuleDocuments" class="primary-sheet-button" type="button">Документы проекта</button>' +
      '</div>' +
    '</section>';

  el("primavtodorModuleBack").onclick = () => renderProjectModule(project);
  el("primavtodorModuleDocuments").onclick = renderDocumentsWorkspace;
}

async function renderProjectModule(project) {
  state.projectId = Number(project.id);
  projectSelect.value = String(state.projectId);
  updateProjectLabel();
  showWorkspaceShell(
    project.kind === "work" ? "work" : "home",
    project.kind === "work" ? "Рабочий модуль" : "Домашний модуль",
    project.name,
    "Отдельное пространство проекта Miyori."
  );

  workspaceBody.innerHTML =
    '<div class="workspace-grid">' +
      '<section class="workspace-card"><strong>Документы</strong><small>Материалы проекта</small><div id="projectModuleDocs">Загружаю…</div></section>' +
      '<section class="workspace-card"><strong>Память</strong><small>Факты проекта</small><div id="projectModuleMemory">Загружаю…</div></section>' +
      '<section class="workspace-card"><strong>Задачи</strong><small>Фоновые процессы</small><div id="projectModuleTasks">Загружаю…</div></section>' +
      '<section id="projectSubmodulesCard" class="workspace-card workspace-card-wide" hidden>' +
        '<strong>Модули</strong><small>Разделы рабочего проекта</small>' +
        '<div id="projectSubmodules" class="workspace-project-grid"></div>' +
      '</section>' +
      '<section class="workspace-card workspace-card-wide"><div class="sheet-actions">' +
        '<button id="projectModuleDocuments" class="secondary-sheet-button" type="button">Документы проекта</button>' +
        '<button id="projectModuleChat" class="primary-sheet-button" type="button">Открыть чат проекта</button>' +
      '</div></section>' +
    '</div>';

  try {
    const [docs, memory, tasks, modules] = await Promise.all([
      api("/api/projects/" + project.id + "/documents"),
      api("/api/projects/" + project.id + "/memory"),
      api("/api/projects/" + project.id + "/tasks"),
      api("/api/projects/" + project.id + "/modules")
    ]);
    el("projectModuleDocs").innerHTML = workspaceResult(
      (docs.documents || []).length + " файл(ов) · " + (docs.folders || []).length + " папок",
      "neutral"
    );
    el("projectModuleMemory").innerHTML = workspaceResult(
      (memory.facts || []).length + " фактов",
      "neutral"
    );
    el("projectModuleTasks").innerHTML = workspaceResult(
      (tasks.tasks || []).length + " задач",
      "neutral"
    );

    const projectModules = modules.modules || [];
    if (projectModules.length) {
      el("projectSubmodulesCard").hidden = false;
      el("projectSubmodules").innerHTML = projectModules.map(module =>
        '<button class="workspace-project-card project-submodule-card" type="button" data-module-id="' + module.id + '">' +
          '<span class="workspace-project-icon">' +
            (module.module_key === "timesheet" ? "▦" : module.module_key === "garage" ? "▰" : "◉") +
          '</span>' +
          '<strong>' + escapeHtml(module.name) + '</strong>' +
          '<small>Модуль проекта</small>' +
        '</button>'
      ).join("");

      workspaceBody.querySelectorAll("[data-module-id]").forEach(button => {
        button.onclick = () => {
          const module = projectModules.find(item => item.id === Number(button.dataset.moduleId));
          if (module) renderPrimavtodorSubmodule(project, module);
        };
      });
    }
  } catch (error) {
    workspaceBody.insertAdjacentHTML("beforeend", workspaceResult(error.message, "error"));
  }

  el("projectModuleDocuments").onclick = renderDocumentsWorkspace;
  el("projectModuleChat").onclick = async () => {
    state.conversationId = null;
    showChatWorkspace();
    showWelcome();
    await Promise.all([loadConversations(), loadMemory(), loadDocuments(), loadNexus()]);
  };
}

async function renderProjectsWorkspace(kind) {
  const isWork = kind === "work";
  showWorkspaceShell(
    kind,
    "Проекты",
    isWork ? "Рабочие проекты" : "Домашние проекты",
    isWork ? "Рабочие пространства Miyori." : "Личные и домашние пространства Miyori."
  );
  try {
    const data = await api("/api/projects");
    const projects = (data.projects || []).filter(project => (project.kind || "home") === kind);
    workspaceBody.innerHTML =
      '<section class="workspace-card workspace-card-wide"><div class="workspace-project-grid">' +
      projects.map(project =>
        '<button class="workspace-project-card ' +
        (project.name === 'АО "Примавтодор"' ? 'primavtodor-project-card' : '') +
        '" type="button" data-project-id="' + project.id + '">' +
          '<span class="workspace-project-icon">' + (isWork ? '▰' : '⌂') + '</span>' +
          '<strong>' + escapeHtml(project.name) + '</strong>' +
          '<small>' + (project.name === 'АО "Примавтодор"' ? 'Отдельный рабочий модуль' : 'Проект #' + project.id) + '</small>' +
        '</button>'
      ).join("") +
      '</div>' +
      (!projects.length ? '<div class="workspace-empty">Проектов в этом разделе пока нет.</div>' : '') +
      '</section>';

    workspaceBody.querySelectorAll("[data-project-id]").forEach(button => {
      button.onclick = () => {
        const project = projects.find(item => item.id === Number(button.dataset.projectId));
        if (project) renderProjectModule(project);
      };
    });
  } catch (error) {
    workspaceBody.innerHTML = workspaceResult(error.message, "error");
  }
}

async function renderSettingsWorkspace() {
  showWorkspaceShell("settings", "Система", "Настройки", "Настройки Miyori и состояние локальных модулей.");
  try {
    const status = await api("/api/status");
    workspaceBody.innerHTML =
      '<div class="workspace-grid">' +
        '<section class="workspace-card"><strong>Cloud.ru</strong><small>AI-провайдер</small>' +
        workspaceResult(status.provider_configured ? "Подключён · " + (status.model_id || "") : "Не настроен", status.provider_configured ? "success" : "warning") + '</section>' +
        '<section class="workspace-card"><strong>RAG</strong><small>Поиск контекста</small>' +
        workspaceResult((status.rag?.fts5 ? "FTS5 + lexical" : "Lexical fallback") + " · chunks " + (status.rag?.indexed_chunks || 0), "neutral") + '</section>' +
        '<section class="workspace-card"><strong>Личность</strong><small>Persona Pack</small>' +
        workspaceResult("v" + (status.persona?.version || "—") + " · активна", "success") + '</section>' +
      '</div>';
  } catch (error) {
    workspaceBody.innerHTML = workspaceResult(error.message, "error");
  }
}

function renderMobileWorkspace() {
  showWorkspaceShell("mobile", "Клиенты", "Мобильное приложение", "Отдельная рабочая область будущего iOS / Android клиента.");
  workspaceBody.innerHTML =
    '<div class="workspace-grid">' +
      '<section class="workspace-card workspace-card-wide"><div class="workspace-hero-icon">▣</div>' +
      '<strong>Мобильная Miyori</strong><p>Этот раздел вынесен из чата. Здесь будут привязка устройства, QR-код, push-уведомления и синхронизация мобильного клиента.</p>' +
      workspaceResult("Мобильный клиент ещё не реализован.", "neutral") + '</section>' +
    '</div>';
}

if (menuMiyoriAI) menuMiyoriAI.onclick = showChatWorkspace;
if (el("workspaceBackToChat")) el("workspaceBackToChat").onclick = showChatWorkspace;
if (menuAccount) menuAccount.onclick = renderAccountWorkspace;
if (menuProjectUpdate) menuProjectUpdate.onclick = () => renderUpdateWorkspace(false);
if (menuSettings) menuSettings.onclick = renderSettingsWorkspace;
if (menuMobileApp) menuMobileApp.onclick = renderMobileWorkspace;
if (menuDocumentsHub) menuDocumentsHub.onclick = renderDocumentsWorkspace;
if (menuWorkProjects) menuWorkProjects.onclick = () => renderProjectsWorkspace("work");
if (menuHomeProjects) menuHomeProjects.onclick = () => renderProjectsWorkspace("home");

const systemStatusOverlay = el("systemStatusOverlay");
const openSystemStatus = el("openSystemStatus");
const closeSystemStatus = el("closeSystemStatus");

function openSystemStatusModal() {
  if (!systemStatusOverlay) return;
  systemStatusOverlay.hidden = false;
  document.body.classList.add("sheet-open");
  loadStatus();
  if (state.projectId) loadNexus();
}

function closeSystemStatusModal() {
  if (!systemStatusOverlay) return;
  systemStatusOverlay.hidden = true;
  document.body.classList.remove("sheet-open");
}

if (openSystemStatus) openSystemStatus.onclick = openSystemStatusModal;
if (closeSystemStatus) closeSystemStatus.onclick = closeSystemStatusModal;
if (systemStatusOverlay) {
  systemStatusOverlay.addEventListener("click", (event) => {
    if (event.target === systemStatusOverlay) closeSystemStatusModal();
  });
}

async function boot() {
  showWelcome();
  showChatWorkspace();
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
