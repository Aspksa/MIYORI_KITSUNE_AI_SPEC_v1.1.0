/* 00.00.61 — user-facing conversation capabilities.
 * All persistence is backed by project-scoped APIs; drafts remain local to this tab.
 */
(() => {
  const $ = id => document.getElementById(id);
  const make = (tag, className = "", text = "") => {
    const node = document.createElement(tag);
    node.className = className;
    node.textContent = text;
    return node;
  };
  const staged = [];
  const maxFiles = 5;
  const allowed = /\.(pdf|docx|xlsx|pptx|txt|md|markdown|json)$/i;
  const attachmentsHost = $("chatAttachments");
  const inputFile = document.createElement("input");
  inputFile.type = "file";
  inputFile.multiple = true;
  inputFile.accept = ".pdf,.docx,.xlsx,.pptx,.txt,.md,.markdown,.json";
  inputFile.hidden = true;
  inputFile.id = "composerFileInput";
  document.body.appendChild(inputFile);

  function report(message) {
    const region = $("composerUploadStatus");
    if (region) region.textContent = message;
  }

  function attachmentsRender() {
    if (!attachmentsHost) return;
    attachmentsHost.replaceChildren();
    attachmentsHost.hidden = staged.filter(item => !item.removed).length === 0;
    for (const entry of staged.filter(item => !item.removed)) {
      const chip = make("div", "chat-attachment-chip");
      const extension = (entry.filename.split(".").pop() || "FILE").toUpperCase();
      const fileSize = entry.size ? " · " + Math.max(1, Math.ceil(entry.size / 1024)) + " КБ" : "";
      const icon = make("span", "chat-file-icon", "▤");
      const detail = make("span", "chat-file-detail");
      detail.append(
        make("strong", "", entry.filename),
        make("small", "", extension + fileSize + " · " + (entry.error
          ? "Ошибка: " + entry.error
          : entry.pending
            ? "Загружается…"
            : entry.readable
              ? "В этом вопросе"
              : "Нет извлекаемого текста — нужен OCR"))
      );
      const remove = make("button", "chat-remove-file", "×");
      remove.type = "button";
      remove.title = "Убрать из сообщения";
      remove.setAttribute("aria-label", "Убрать " + entry.filename);
      remove.onclick = () => {
        entry.removed = true;
        attachmentsRender();
      };
      chip.append(icon, detail, remove);
      attachmentsHost.appendChild(chip);
    }
  }

  function queueFiles(files) {
    if (!state.projectId) {
      showError("Сначала выберите пространство проекта.");
      return;
    }
    for (const file of Array.from(files || [])) {
      if (!file || !allowed.test(file.name) || file.size > 25 * 1024 * 1024) {
        showError("Файл не поддерживается или превышает 25 МБ: " + (file?.name || ""));
        continue;
      }
      if (staged.filter(item => !item.removed).length >= maxFiles) {
        showError("Для одного сообщения можно выбрать не более пяти документов.");
        break;
      }
      const projectAtStart = Number(state.projectId);
      const entry = {
        filename: file.name, size: file.size, projectId: projectAtStart,
        id: null, readable: false, pending: true, error: null, removed: false,
        promise: null
      };
      staged.push(entry);
      const form = new FormData();
      form.append("file", file);
      entry.promise = fetch("/api/projects/" + projectAtStart + "/documents", {
        method: "POST", body: form
      })
        .then(async response => {
          const data = await response.json();
          if (!response.ok) {
            throw new Error(typeof data.detail === "string"
              ? data.detail : "Не удалось загрузить документ.");
          }
          entry.id = Number(data.document.id);
          entry.readable = Number(data.chunk_count || 0) > 0;
          entry.pending = false;
          if (projectAtStart === Number(state.projectId)) {
            void loadDocuments();
          }
          return entry;
        })
        .catch(error => {
          entry.pending = false;
          entry.error = error.message || "Ошибка загрузки";
          return entry;
        })
        .finally(attachmentsRender);
    }
    attachmentsRender();
  }

  inputFile.addEventListener("change", () => {
    queueFiles(inputFile.files);
    inputFile.value = "";
  });
  $("composerAttach")?.addEventListener("click", () => inputFile.click());

  const composer = $("chatForm");
  const overlay = $("chatDropOverlay");
  if (composer && overlay) {
    const validDrag = event => Array.from(event.dataTransfer?.types || []).includes("Files");
    composer.addEventListener("dragover", event => {
      if (!validDrag(event)) return;
      event.preventDefault();
      overlay.hidden = false;
    });
    composer.addEventListener("dragleave", event => {
      if (!composer.contains(event.relatedTarget)) overlay.hidden = true;
    });
    composer.addEventListener("drop", event => {
      if (!validDrag(event)) return;
      event.preventDefault();
      overlay.hidden = true;
      queueFiles(event.dataTransfer.files);
    });
    composer.addEventListener("paste", event => {
      const files = event.clipboardData?.files;
      if (!files?.length) return;
      event.preventDefault();
      queueFiles(files);
    });
  }

  window.miyoriChatAttachments = {
    queueFiles,
    render: attachmentsRender,
    clear() {
      staged.length = 0;
      attachmentsRender();
      report("");
    },
    useExisting(list) {
      staged.length = 0;
      for (const raw of (list || []).slice(0, maxFiles)) {
        const id = typeof raw === "object" ? raw.id : raw;
        if (!Number.isInteger(Number(id)) || Number(id) <= 0) continue;
        staged.push({
          id: Number(id), filename: raw.filename || ("Документ #" + id),
          pending: false, readable: true, projectId: Number(state.projectId),
          removed: false, error: null, promise: Promise.resolve()
        });
      }
      attachmentsRender();
    },
    async ready() {
      await Promise.all(staged.filter(e => !e.removed).map(e => e.promise));
      const current = staged.filter(e => !e.removed);
      if (current.some(e => e.projectId !== Number(state.projectId))) {
        throw new Error("Проект изменился во время загрузки вложения.");
      }
      const failed = current.find(e => e.error || !Number.isInteger(e.id));
      if (failed) throw new Error(failed.error || "Вложение не загружено.");
      return current;
    }
  };

  const draftKey = () =>
    "miyori:draft:" + state.projectId + ":" + (state.conversationId || "new");
  window.miyoriDrafts = {
    save() {
      try { sessionStorage.setItem(draftKey(), $("messageInput")?.value || ""); }
      catch (_) { /* Private browsing may disable storage. */ }
    },
    restore() {
      try { $("messageInput").value = sessionStorage.getItem(draftKey()) || ""; }
      catch (_) { $("messageInput").value = ""; }
      $("messageInput")?.dispatchEvent(new Event("input", {bubbles:true}));
    }
  };
  $("messageInput")?.addEventListener("input", () => window.miyoriDrafts.save());

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(String(text));
    } catch {
      const target = document.createElement("textarea");
      target.value = String(text);
      document.body.appendChild(target);
      target.select();
      document.execCommand("copy");
      target.remove();
    }
  }

  async function changeBookmark(row, button) {
    const id = Number(row.dataset.messageId);
    if (!state.conversationId || !id) return;
    const bookmarked = button.getAttribute("aria-pressed") !== "true";
    try {
      const result = await api(
        "/api/projects/" + state.projectId + "/conversations/" +
        state.conversationId + "/messages/" + id + "/bookmark",
        {method:"PUT", headers:{"Content-Type":"application/json"},
         body:JSON.stringify({bookmarked})}
      );
      button.setAttribute("aria-pressed", String(result.bookmarked));
      button.textContent = result.bookmarked ? "Сохранено" : "Сохранить";
    } catch (error) {
      showError(error.message);
    }
  }

  async function forkMessage(row, isEdit) {
    const id = Number(row.dataset.messageId);
    if (!id || !state.conversationId || state.busy) {
      showError("Дождитесь сохранения сообщения, прежде чем изменять его.");
      return;
    }
    let text = row._miyoriText;
    if (isEdit) {
      const changed = window.prompt("Изменить вопрос — исходный вариант сохранится:", text);
      if (changed === null) return;
      text = changed.trim();
      if (!text) return;
    }
    try {
      const fork = await api(
        "/api/projects/" + state.projectId + "/conversations/" +
        state.conversationId + "/messages/" + id + "/fork",
        {method:"POST"}
      );
      window.miyoriDrafts.save();
      state.conversationId = Number(fork.conversation_id);
      showWelcome();
      window.miyoriChatAttachments.useExisting(fork.attachments || []);
      $("messageInput").value = isEdit ? text : fork.message;
      $("messageInput").dispatchEvent(new Event("input", {bubbles:true}));
      form.requestSubmit();
    } catch (error) {
      showError(error.message);
    }
  }

  $("messages")?.addEventListener("click", async event => {
    const button = event.target.closest("[data-chat-action]");
    if (!button) return;
    const action = button.dataset.chatAction;
    const row = button.closest(".message");
    if (action === "copy-code") {
      const pre = button.closest("pre");
      const code = pre?.querySelector("code")?.textContent || "";
      await copy(code);
      button.textContent = "Скопировано";
      return;
    }
    if (!row) return;
    if (action === "copy") {
      await copy(row._miyoriText || "");
      button.textContent = "Скопировано";
    } else if (action === "save") {
      await changeBookmark(row, button);
    } else if (action === "edit") {
      await forkMessage(row, true);
    } else if (action === "retry") {
      await forkMessage(row, false);
    }
  });

  let searchDelay = null;
  const searchInput = $("conversationSearch");
  searchInput?.addEventListener("input", () => {
    if (searchDelay) clearTimeout(searchDelay);
    searchDelay = setTimeout(() => void loadConversations(), 170);
  });
  const savedAnswersButton = $("savedAnswersButton");
  let showingSaved = false;
  savedAnswersButton?.addEventListener("click", async () => {
    if (!state.projectId) return;
    showingSaved = !showingSaved;
    savedAnswersButton.textContent = showingSaved ? "Все разговоры" : "Сохранённые ответы";
    if (!showingSaved) {
      await loadConversations();
      return;
    }
    try {
      const data = await api("/api/projects/" + state.projectId + "/bookmarks");
      const list = $("conversationList");
      list.replaceChildren();
      if (!data.bookmarks?.length) {
        list.appendChild(make("p", "conversation-empty", "Сохранённых ответов пока нет"));
      }
      for (const item of data.bookmarks || []) {
        const button = make("button", "saved-answer-row", item.conversation_title + " · " + item.preview);
        button.type = "button";
        button.onclick = () => openConversation(item.conversation_id, item.id);
        list.appendChild(button);
      }
    } catch (error) {
      showError(error.message);
    }
  });

  const list = $("conversationList");
  list?.addEventListener("click", async event => {
    const pin = event.target.closest("[data-conversation-pin]");
    const rename = event.target.closest("[data-conversation-rename]");
    if (!pin && !rename) return;
    const id = Number((pin || rename).dataset.conversationPin || rename?.dataset.conversationRename);
    let change;
    if (pin) {
      change = {pinned: pin.dataset.pinned !== "1"};
    } else {
      const title = window.prompt("Название разговора:", rename.dataset.title);
      if (title === null) return;
      change = {title: title.trim()};
      if (!change.title) return;
    }
    try {
      await api("/api/projects/" + state.projectId + "/conversations/" + id, {
        method:"PATCH", headers:{"Content-Type":"application/json"},
        body:JSON.stringify(change)
      });
      await loadConversations();
    } catch (error) {
      showError(error.message);
    }
  });

  const searchPanel = $("chatSearchPanel");
  const searchText = $("chatSearchInput");
  const searchResults = $("chatSearchResult");
  $("chatFindButton")?.addEventListener("click", () => {
    searchPanel.hidden = !searchPanel.hidden;
    if (!searchPanel.hidden) {
      searchText.focus();
      searchText.dispatchEvent(new Event("input"));
    }
  });
  $("chatSearchClose")?.addEventListener("click", () => {
    searchPanel.hidden = true;
    searchResults.replaceChildren();
  });
  document.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      $("chatFindButton")?.click();
    }
    if (event.key === "Escape") searchPanel.hidden = true;
  });
  let searchGeneration = 0;
  searchText?.addEventListener("input", async () => {
    const generation = ++searchGeneration;
    const q = searchText.value.trim();
    searchResults.replaceChildren();
    if (!q || !state.conversationId) return;
    try {
      const data = await api(
        "/api/projects/" + state.projectId + "/conversations/" +
        state.conversationId + "/search?q=" + encodeURIComponent(q)
      );
      if (generation !== searchGeneration) return;
      if (!data.matches.length) {
        searchResults.appendChild(make("small", "", "Ничего не найдено"));
      }
      for (const match of data.matches.slice(0, 25)) {
        const button = make("button", "chat-search-match", match.preview);
        button.type = "button";
        button.onclick = async () => {
          searchPanel.hidden = true;
          await openConversation(state.conversationId, match.id);
        };
        searchResults.appendChild(button);
      }
    } catch (error) {
      if (generation === searchGeneration) showError(error.message);
    }
  });

  // Actual, persisted NEXUS events only. No invented progress or idle animation.
  let activityTimer = null;
  let activeProject = null;
  let activityCursor = null;
  let activityGeneration = 0;
  let requestSince = null;
  async function checkEvents(initial = false, generation = activityGeneration) {
    if (!state.busy || generation !== activityGeneration || !activeProject) return;
    try {
      const query = activityCursor
        ? "?after=" + encodeURIComponent(activityCursor) + "&limit=15"
        : "?tail=true&limit=10";
      const data = await api(
        "/api/projects/" + activeProject + "/nexus/events" + query
      );
      if (generation !== activityGeneration || !state.busy) return;
      activityCursor = data.next_cursor;
      if (initial) return; // Existing events establish baseline only.
      for (const event of data.events || []) {
        if (event.created_at < requestSince) continue;
        const list = $("chatActivityEvents");
        if (!list || list.childElementCount >= 30) continue;
        const row = make("div", "chat-activity-event");
        row.append(
          make("time", "", new Date(event.created_at).toLocaleTimeString("ru-RU")),
          make("span", "", event.summary || event.event_type)
        );
        list.appendChild(row);
        $("chatActivitySummary").textContent = "Есть подтверждённые события";
      }
    } catch {
      $("chatActivitySummary").textContent = "Журнал событий временно недоступен";
    }
  }

  window.miyoriChatActivity = {
    begin() {
      if (activityTimer) clearInterval(activityTimer);
      activityGeneration++;
      const generation = activityGeneration;
      activeProject = Number(state.projectId);
      activityCursor = null;
      requestSince = new Date().toISOString().slice(0,19);
      $("chatActivity").hidden = false;
      $("chatActivitySummary").textContent = "Ожидаю подтверждённых событий";
      $("chatActivityEvents").replaceChildren();
      $("chatActivityDetails").open = false;
      // Record cursor before poll begins. No prior event is reported as new.
      void checkEvents(true, generation).finally(() => {
        if (generation === activityGeneration) {
          activityTimer = setInterval(() => {
            if (document.visibilityState === "visible") void checkEvents(false, generation);
          }, 2500);
        }
      });
    },
    complete() {
      if (activityTimer) clearInterval(activityTimer);
      activityTimer = null;
      activityGeneration++;
      if (!$("chatActivityEvents").childElementCount) {
        $("chatActivitySummary").textContent = "Новых событий в журнале нет";
      }
    }
  };
  window.addEventListener("miyori:chat-response", event => {
    const data = event.detail || {};
    const events = $("chatActivityEvents");
    if (!events) return;
    for (const action of data.agent?.actions || []) {
      if (events.childElementCount >= 30) break;
      const row = make("div", "chat-activity-event");
      row.append(
        make("strong", "", action.tool_name || action.tool || "Шаг агента"),
        make("span", "", action.status || "")
      );
      events.appendChild(row);
    }
    if (events.childElementCount) {
      $("chatActivitySummary").textContent = "Выполнение записано в журнал";
    }
  });
})();
