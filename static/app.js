const state = {
  conversationId: null,
  busy: false,
};

const messages = document.getElementById("messages");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const errorBox = document.getElementById("errorBox");
const newChat = document.getElementById("newChat");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const modelText = document.getElementById("modelText");

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
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

function showError(text) {
  errorBox.textContent = text;
  errorBox.hidden = !text;
}

function setBusy(value) {
  state.busy = value;
  sendButton.disabled = value;
  input.disabled = value;
  sendButton.textContent = value ? "Думаю…" : "Отправить";
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    const data = await response.json();
    if (data.provider_configured) {
      statusDot.classList.add("ready");
      statusText.textContent = "Cloud.ru настроен";
      modelText.textContent = data.model_id;
    } else {
      statusDot.classList.add("warn");
      statusText.textContent = "Нужна настройка";
      modelText.textContent = "Заполните .env";
    }
  } catch {
    statusDot.classList.add("error-dot");
    statusText.textContent = "Сервер недоступен";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.busy) return;

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
  } catch (error) {
    showError(error.message || "Не удалось получить ответ.");
  } finally {
    setBusy(false);
    input.focus();
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

newChat.addEventListener("click", () => {
  state.conversationId = null;
  messages.innerHTML = "";
  addMessage("assistant", "Новый разговор начат, Господин. С чего начнём?");
  showError("");
  input.focus();
});

loadStatus();
input.focus();
