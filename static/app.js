const state = {
  projectId: null,
  conversationId: null,
  busy: false,
};

const messages = document.getElementById("messages");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const errorBox = document.getElementById("errorBox");
const newChat = document.getElementById("newChat");
const newChatSide = document.getElementById("newChatSide");
const projectSelect = document.getElementById("projectSelect");
const addProject = document.getElementById("addProject");
const conversationList = document.getElementById("conversationList");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const modelText = document.getElementById("modelText");
const versionText = document.getElementById("versionText");
const projectLabel = document.getElementById("projectLabel");
const conversationTitle = document.getElementById("conversationTitle");

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

function clearMessages() {
  messages.innerHTML = "";
}

function addMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;

  const name = role === "assistant" ? "Миёри" : "Господин";
  const avatar = role === "assistant" ? "狐" : "Вы";

  article.innerHTML = `
    <div class="avatar">${avatar}</div>
    <div class="bubble">
      <strong>${name}</strong>
      <p>${escapeHtml(text).replace(/\n/g, "<br>")}</p>
    </div>
  `;
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
}

function showWelcome() {
  clearMessages();
  addMessage("assistant", "Здравствуйте, Господин. Я готова. Выберите старый разговор или начните новый.");
  conversationTitle.textContent = "Новый разговор";
}

function showError(text) {
  errorBox.textContent = text;
  errorBox.hidden = !text;
}

function setBusy(value) {
  state.busy = value;
  sendButton.disabled = value;
  input.disabled = value;
  projectSelect.disabled = value;
  sendButton.textContent = value ? "Думаю…" : "Отправить";
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

  if (!state.projectId && data.projects.length) {
    state.projectId = data.projects[0].id;
  }

  projectSelect.value = String(state.projectId);
  updateProjectLabel();
  await loadConversations();
}

function updateProjectLabel() {
  const option = projectSelect.selectedOptions[0];
  projectLabel.textContent = option ? `Проект: ${option.textContent}` : "Проект";
}

async function loadConversations() {
  if (!state.projectId) return;
  const data = await api(`/api/projects/${state.projectId}/conversations`);
  conversationList.innerHTML = "";

  if (!data.conversations.length) {
    const empty = document.createElement("div");
    empty.className = "conversation-empty";
    empty.textContent = "Пока нет разговоров";
    conversationList.appendChild(empty);
    return;
  }

  for (const item of data.conversations) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "conversation-item";
    if (item.id === state.conversationId) button.classList.add("active");
    button.dataset.id = item.id;
    button.innerHTML = `
      <span>${escapeHtml(item.title)}</span>
      <small>${item.message_count} сообщ.</small>
    `;
    button.addEventListener("click", () => openConversation(item.id, item.title));
    conversationList.appendChild(button);
  }
}

async function openConversation(id, title) {
  showError("");
  const data = await api(`/api/projects/${state.projectId}/conversations/${id}`);
  state.conversationId = id;
  clearMessages();

  for (const message of data.messages) {
    if (message.role === "user" || message.role === "assistant") {
      addMessage(message.role, message.content);
    }
  }

  conversationTitle.textContent = title || "Разговор с Миёри";
  await loadConversations();
  input.focus();
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
        conversation_id: state.conversationId,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      if (data?.detail?.conversation_id) {
        state.conversationId = data.detail.conversation_id;
      }
      const message = data?.detail?.message || data?.detail || "Ошибка запроса.";
      throw new Error(typeof message === "string" ? message : JSON.stringify(message));
    }

    state.conversationId = data.conversation_id;
    addMessage("assistant", data.answer);
    await loadConversations();

    const active = conversationList.querySelector(`[data-id="${state.conversationId}"] span`);
    if (active) conversationTitle.textContent = active.textContent;
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
  await loadConversations();
});

addProject.addEventListener("click", async () => {
  const name = prompt("Название нового проекта:");
  if (!name || !name.trim()) return;

  try {
    const data = await api("/api/projects", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({name: name.trim()}),
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

newChat.addEventListener("click", startNewChat);
newChatSide.addEventListener("click", startNewChat);

async function boot() {
  showWelcome();
  await loadStatus();
  try {
    await loadProjects();
  } catch (error) {
    showError(error.message);
  }
  input.focus();
}

boot();
