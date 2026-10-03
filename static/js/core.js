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
