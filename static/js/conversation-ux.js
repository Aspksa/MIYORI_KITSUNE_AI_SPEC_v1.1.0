(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const ux = {
    reply: null,
    topicId: null,
    voiceNote: null,
    snapshot: null,
    folder: sessionStorage.getItem("miyori.chat.folder") || "all",
    pendingScheduleId: null,
    pendingScheduleText: "",
    dueSeen: new Set(),
    recording: null,
    transcript: "",
  };

  function projectId() {
    const id = Number(state.projectId);
    return Number.isInteger(id) && id > 0 ? id : null;
  }

  function conversationId() {
    const id = Number(state.conversationId);
    return Number.isInteger(id) && id > 0 ? id : null;
  }

  function endpoint(messageId, tail) {
    return "/api/projects/" + projectId() + "/conversations/" +
      conversationId() + "/messages/" + Number(messageId) + "/" + tail;
  }

  function setStatus(text) {
    const node = $("conversationUxStatus");
    if (!node) return;
    node.textContent = text || "";
    node.hidden = !text;
  }

  function button(label, cls = "") {
    const node = document.createElement("button");
    node.type = "button";
    node.className = cls;
    node.textContent = label;
    return node;
  }

  function ensureChrome() {
    const header = $("chatHeader");
    if (header && !$("conversationUxBar")) {
      const bar = document.createElement("section");
      bar.id = "conversationUxBar";
      bar.className = "conversation-ux-bar";
      bar.setAttribute("aria-label", "Контекст разговора");

      const topic = document.createElement("select");
      topic.id = "conversationTopicSelect";
      topic.className = "conversation-ux-select";
      topic.setAttribute("aria-label", "Тема разговора");
      topic.addEventListener("change", onTopicChange);

      const pins = document.createElement("div");
      pins.id = "conversationPins";
      pins.className = "conversation-pins";
      pins.setAttribute("aria-label", "Закреплённый контекст");

      const status = document.createElement("small");
      status.id = "conversationUxStatus";
      status.className = "conversation-ux-status";
      status.hidden = true;

      bar.append(topic, pins, status);
      header.insertAdjacentElement("afterend", bar);
    }

    const composer = $("chatForm");
    if (composer && !$("conversationReplyBar")) {
      const reply = document.createElement("div");
      reply.id = "conversationReplyBar";
      reply.className = "conversation-reply-bar";
      reply.hidden = true;
      const copy = document.createElement("span");
      copy.id = "conversationReplyText";
      const close = button("×", "conversation-ux-close");
      close.setAttribute("aria-label", "Убрать цитату");
      close.onclick = clearReply;
      reply.append(copy, close);
      composer.prepend(reply);

      const rich = document.createElement("div");
      rich.id = "conversationRichToolbar";
      rich.className = "conversation-rich-toolbar";
      rich.setAttribute("aria-label", "Форматирование сообщения");
      const tools = [
        ["B", "**", "**", "Жирный"],
        ["I", "*", "*", "Курсив"],
        ["</>", "`", "`", "Код"],
        ["❝", "> ", "", "Цитата"],
        ["•", "- ", "", "Список"],
        ["☑", "- [ ] ", "", "Чек-лист"],
      ];
      for (const [label, before, after, title] of tools) {
        const item = button(label, "conversation-format-button");
        item.title = title;
        item.setAttribute("aria-label", title);
        item.onclick = () => wrapSelection(before, after);
        rich.appendChild(item);
      }
      const schedule = button("◷", "conversation-format-button");
      schedule.title = "Отложить запрос";
      schedule.setAttribute("aria-label", "Отложить запрос");
      schedule.onclick = openScheduleEditor;
      rich.appendChild(schedule);

      const voice = button("◉", "conversation-format-button");
      voice.id = "voiceNoteButton";
      voice.title = "Записать голосовое сообщение";
      voice.setAttribute("aria-label", "Записать голосовое сообщение");
      voice.onclick = toggleVoiceNote;
      rich.appendChild(voice);

      const textarea = $("messageInput");
      composer.insertBefore(rich, textarea);

      const voiceDraft = document.createElement("div");
      voiceDraft.id = "voiceNoteDraft";
      voiceDraft.className = "voice-note-draft";
      voiceDraft.hidden = true;
      composer.insertBefore(voiceDraft, $("chatAttachments"));

      const schedulePanel = document.createElement("div");
      schedulePanel.id = "chatSchedulePanel";
      schedulePanel.className = "chat-schedule-panel";
      schedulePanel.hidden = true;
      const dt = document.createElement("input");
      dt.id = "chatScheduleTime";
      dt.type = "datetime-local";
      dt.setAttribute("aria-label", "Дата и время");
      const repeat = document.createElement("select");
      repeat.id = "chatScheduleRepeat";
      repeat.setAttribute("aria-label", "Повтор");
      for (const [value, label] of [["none","Один раз"],["daily","Каждый день"],["weekly","Каждую неделю"]]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        repeat.appendChild(option);
      }
      const auto = document.createElement("label");
      auto.className = "chat-schedule-auto";
      const cb = document.createElement("input");
      cb.id = "chatScheduleAuto";
      cb.type = "checkbox";
      cb.checked = true;
      auto.append(cb, document.createTextNode("Отправить автоматически, когда приложение открыто"));
      const save = button("Запланировать", "conversation-primary-small");
      save.onclick = createSchedule;
      const cancel = button("Отмена", "conversation-secondary-small");
      cancel.onclick = () => { schedulePanel.hidden = true; };
      schedulePanel.append(dt, repeat, auto, save, cancel);
      composer.appendChild(schedulePanel);
    }

    const history = document.querySelector(".workspace-details");
    if (history && !$("conversationFolderBar")) {
      const bar = document.createElement("div");
      bar.id = "conversationFolderBar";
      bar.className = "conversation-folder-bar";
      const select = document.createElement("select");
      select.id = "conversationFolderSelect";
      select.className = "conversation-ux-select";
      select.setAttribute("aria-label", "Папка разговоров");
      select.onchange = () => {
        if (select.value === "__new__") {
          void createConversationFolder();
          return;
        }
        ux.folder = select.value || "all";
        sessionStorage.setItem("miyori.chat.folder", ux.folder);
        void loadConversations();
      };
      const assign = button("+ папка", "conversation-folder-assign");
      assign.title = "Добавить текущий разговор в папку";
      assign.onclick = assignCurrentConversationToFolder;
      bar.append(select, assign);
      const heading = history.querySelector(".rail-heading");
      heading?.insertAdjacentElement("afterend", bar);
    }

    const search = $("chatSearchPanel");
    if (search && !$("chatSearchScope")) {
      const select = document.createElement("select");
      select.id = "chatSearchScope";
      select.className = "chat-search-scope";
      select.setAttribute("aria-label", "Область поиска");
      for (const [value, label] of [
        ["conversation", "Этот чат"],
        ["project", "Весь проект"],
        ["saved", "Сохранённые"],
      ]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        select.appendChild(option);
      }
      select.onchange = () => $("chatSearchInput")?.dispatchEvent(new Event("input"));
      search.prepend(select);
    }

    if (!$("scheduledDueShelf")) {
      const shelf = document.createElement("section");
      shelf.id = "scheduledDueShelf";
      shelf.className = "scheduled-due-shelf";
      shelf.hidden = true;
      shelf.setAttribute("aria-label", "Отложенные запросы");
      $("conversationUxBar")?.insertAdjacentElement("afterend", shelf);
    }
  }

  function wrapSelection(before, after) {
    const field = $("messageInput");
    if (!field) return;
    const start = field.selectionStart ?? field.value.length;
    const end = field.selectionEnd ?? start;
    const selected = field.value.slice(start, end);
    const prefix = start === 0 || field.value[start - 1] === "\n" ? "" : "";
    field.setRangeText(prefix + before + selected + after, start, end, "end");
    field.dispatchEvent(new Event("input", {bubbles:true}));
    field.focus();
  }

  function clearReply() {
    ux.reply = null;
    const bar = $("conversationReplyBar");
    if (bar) bar.hidden = true;
  }

  function setReply(row) {
    const messageId = Number(row?.dataset.messageId);
    if (!messageId) return;
    const selection = window.getSelection();
    let quote = "";
    if (selection && !selection.isCollapsed && row.contains(selection.anchorNode)) {
      quote = selection.toString().trim();
    }
    if (!quote) quote = String(row._miyoriText || row.querySelector(".message-body")?.textContent || "").trim();
    quote = quote.slice(0, 800);
    ux.reply = {reply_to_message_id:messageId, quoted_text:quote};
    const bar = $("conversationReplyBar");
    const text = $("conversationReplyText");
    if (bar && text) {
      text.textContent = "Ответ на #" + messageId + " · " + quote.slice(0, 160);
      bar.hidden = false;
    }
    $("messageInput")?.focus();
  }

  function composerContext() {
    return {
      reply_to_message_id: ux.reply?.reply_to_message_id ?? null,
      quoted_text: ux.reply?.quoted_text || "",
      topic_id: ux.topicId ?? null,
      voice_note_id: ux.voiceNote?.id ?? null,
    };
  }

  function resetConversation() {
    ux.topicId = null;
    ux.snapshot = null;
    clearReply();
    clearVoiceDraft();
    renderTopicOptions([]);
    renderPins([]);
    document.querySelectorAll(".unread-divider").forEach(node => node.remove());
  }

  function renderTopicOptions(topics) {
    const select = $("conversationTopicSelect");
    if (!select) return;
    const current = ux.topicId == null ? "" : String(ux.topicId);
    select.replaceChildren();
    const general = document.createElement("option");
    general.value = "";
    general.textContent = "Тема: Общее";
    select.appendChild(general);
    for (const topic of topics || []) {
      const option = document.createElement("option");
      option.value = String(topic.id);
      option.textContent = "Тема: " + topic.name;
      select.appendChild(option);
    }
    const create = document.createElement("option");
    create.value = "__new__";
    create.textContent = "+ Новая тема";
    select.appendChild(create);
    select.value = current;
  }

  async function onTopicChange(event) {
    const value = event.target.value;
    if (value === "__new__") {
      const name = window.prompt("Название темы:");
      if (!name?.trim() || !conversationId()) {
        renderTopicOptions(ux.snapshot?.topics || []);
        return;
      }
      try {
        const data = await api(
          "/api/projects/" + projectId() + "/conversations/" + conversationId() + "/topics",
          {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({name:name.trim()})}
        );
        ux.topicId = Number(data.topic.id);
        await refreshSnapshot();
      } catch (error) {
        showError(error.message);
      }
      return;
    }
    ux.topicId = value ? Number(value) : null;
    applyTopicFilter();
  }

  function applyTopicFilter() {
    const topicId = ux.topicId;
    const mapping = ux.snapshot?.message_topics || {};
    for (const row of messages.querySelectorAll(".message[data-message-id]")) {
      const ids = mapping[String(row.dataset.messageId)] || [];
      row.hidden = topicId != null && !ids.includes(topicId);
    }
  }

  function renderPins(pins) {
    const host = $("conversationPins");
    if (!host) return;
    host.replaceChildren();
    for (const item of (pins || []).slice(0, 4)) {
      const chip = button("📌 " + String(item.preview || "").slice(0, 56), "conversation-pin-chip");
      chip.title = String(item.preview || "");
      chip.onclick = () => {
        const row = messages.querySelector('[data-message-id="' + Number(item.message_id) + '"]');
        if (row) {
          row.hidden = false;
          row.scrollIntoView({block:"center", behavior:"smooth"});
          row.classList.add("search-hit");
          window.setTimeout(() => row.classList.remove("search-hit"), 1300);
        } else {
          void openConversation(conversationId(), Number(item.message_id));
        }
      };
      host.appendChild(chip);
    }
  }

  async function refreshSnapshot() {
    if (!projectId() || !conversationId()) return;
    try {
      ux.snapshot = await api(
        "/api/projects/" + projectId() + "/conversations/" + conversationId() + "/experience"
      );
      renderTopicOptions(ux.snapshot.topics || []);
      renderPins(ux.snapshot.pins || []);
      applyExperienceToMessages();
      applyUnreadDivider();
    } catch (error) {
      showError(error.message);
    }
  }

  async function afterConversationOpen() {
    clearReply();
    clearVoiceDraft();
    ux.topicId = null;
    await Promise.all([refreshSnapshot(), refreshFolders()]);
    applyTopicFilter();
    window.setTimeout(() => void markLatestRead(), 450);
  }

  async function afterSend(data, submittedText = "") {
    clearReply();
    clearVoiceDraft();
    await refreshSnapshot();
    if (
      ux.pendingScheduleId &&
      submittedText.trim() === String(ux.pendingScheduleText || "").trim()
    ) {
      const scheduleId = ux.pendingScheduleId;
      ux.pendingScheduleId = null;
      ux.pendingScheduleText = "";
      try {
        await api("/api/projects/" + projectId() + "/chat/schedules/" + scheduleId + "/complete", {
          method:"POST"
        });
      } catch (_) {}
    }
    void markLatestRead();
  }

  function applyExperienceToMessages() {
    const snapshot = ux.snapshot || {};
    for (const row of messages.querySelectorAll(".message[data-message-id]")) {
      decorateMessage(row);
      const id = String(row.dataset.messageId);
      renderTags(row, snapshot.tags?.[id] || []);
      renderReactions(row, snapshot.reactions?.[id] || []);
      renderChecklist(row, snapshot.checklists?.[id]?.items || null);
      renderTopicBadge(row, snapshot.message_topics?.[id] || []);
      renderMetadataContext(row);
    }
    applyTopicFilter();
  }

  function ensureMetaHost(row) {
    let host = row.querySelector(".conversation-message-meta");
    if (!host) {
      host = document.createElement("div");
      host.className = "conversation-message-meta";
      row.querySelector(".bubble")?.appendChild(host);
    }
    return host;
  }

  function renderTags(row, tags) {
    let host = row.querySelector(".conversation-tags");
    if (!tags?.length) {
      host?.remove();
      return;
    }
    if (!host) {
      host = document.createElement("div");
      host.className = "conversation-tags";
      ensureMetaHost(row).appendChild(host);
    }
    host.replaceChildren();
    for (const tag of tags) {
      const chip = document.createElement("span");
      chip.textContent = "#" + tag;
      host.appendChild(chip);
    }
  }

  const reactionLabels = {
    useful:"👍 Полезно",
    verify:"⚠ Проверить",
    pin:"📌",
    remember:"🧠",
  };

  function renderReactions(row, reactions) {
    let host = row.querySelector(".conversation-reactions");
    if (!host) {
      host = document.createElement("div");
      host.className = "conversation-reactions";
      ensureMetaHost(row).appendChild(host);
    }
    host.replaceChildren();
    for (const key of Object.keys(reactionLabels)) {
      const b = button(reactionLabels[key], "conversation-reaction");
      b.dataset.reaction = key;
      b.setAttribute("aria-pressed", reactions.includes(key) ? "true" : "false");
      if (reactions.includes(key)) b.classList.add("active");
      b.onclick = () => toggleReaction(row, key, !reactions.includes(key));
      host.appendChild(b);
    }
  }

  function renderChecklist(row, items) {
    let host = row.querySelector(".conversation-checklist");
    if (!items?.length) {
      host?.remove();
      return;
    }
    if (!host) {
      host = document.createElement("div");
      host.className = "conversation-checklist";
      ensureMetaHost(row).appendChild(host);
    }
    host.replaceChildren();
    const title = document.createElement("strong");
    title.textContent = "Чек-лист";
    host.appendChild(title);
    items.forEach((item, index) => {
      const label = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = Boolean(item.done);
      cb.onchange = async () => {
        const next = items.map((entry, i) => ({
          text:entry.text, done:i === index ? cb.checked : Boolean(entry.done)
        }));
        await saveChecklistFor(row, next);
      };
      label.append(cb, document.createTextNode(item.text));
      host.appendChild(label);
    });
  }

  function renderTopicBadge(row, topicIds) {
    row.querySelector(".conversation-topic-badge")?.remove();
    if (!topicIds?.length) return;
    const topic = (ux.snapshot?.topics || []).find(item => Number(item.id) === Number(topicIds[0]));
    if (!topic) return;
    const badge = document.createElement("span");
    badge.className = "conversation-topic-badge";
    badge.textContent = topic.name;
    ensureMetaHost(row).prepend(badge);
  }

  function renderMetadataContext(row) {
    const meta = row._miyoriMeta || {};
    row.querySelector(".conversation-reply-reference")?.remove();
    const replyId = Number(meta.reply_to_message_id || meta.reply_context?.message_id);
    if (replyId) {
      const ref = button(
        "↩ #" + replyId + " · " +
        String(meta.quoted_text || meta.reply_context?.quote || "").slice(0, 120),
        "conversation-reply-reference"
      );
      ref.onclick = () => {
        const target = messages.querySelector('[data-message-id="' + replyId + '"]');
        if (target) target.scrollIntoView({block:"center",behavior:"smooth"});
        else void openConversation(conversationId(), replyId);
      };
      row.querySelector(".bubble")?.insertBefore(ref, row.querySelector(".message-body"));
    }

    const noteId = Number(meta.voice_note_id);
    if (noteId && !row.querySelector("audio.voice-note-player")) {
      const audio = document.createElement("audio");
      audio.className = "voice-note-player";
      audio.controls = true;
      audio.preload = "metadata";
      audio.src = "/api/projects/" + projectId() + "/voice-notes/" + noteId;
      ensureMetaHost(row).appendChild(audio);
    }
  }

  function decorateMessage(row) {
    if (!row || row.dataset.conversationUx === "1" || !row.dataset.messageId) return;
    row.dataset.conversationUx = "1";
    const tools = row.querySelector(".message-tools");
    if (!tools) return;
    const actions = [
      ["reply","Ответить"],
      ["pin-message","Закрепить"],
      ["tags","Теги"],
      ["checklist","Чек-лист"],
      ["route","Отправить в…"],
    ];
    for (const [action, label] of actions) {
      const b = button(label);
      b.dataset.conversationAction = action;
      b.onclick = () => handleMessageAction(row, action);
      tools.appendChild(b);
    }
    renderReactions(row, ux.snapshot?.reactions?.[String(row.dataset.messageId)] || []);
  }

  async function handleMessageAction(row, action) {
    try {
      if (action === "reply") return setReply(row);
      if (action === "pin-message") return await togglePin(row);
      if (action === "tags") return await editTags(row);
      if (action === "checklist") return await createChecklist(row);
      if (action === "route") return await chooseRoute(row);
    } catch (error) {
      showError(error.message);
    }
  }

  async function togglePin(row) {
    const id = Number(row.dataset.messageId);
    const pinned = (ux.snapshot?.pins || []).some(item => Number(item.message_id) === id);
    await api(endpoint(id, "pin"), {
      method:"PUT", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({enabled:!pinned})
    });
    await refreshSnapshot();
  }

  async function editTags(row) {
    const id = Number(row.dataset.messageId);
    const current = ux.snapshot?.tags?.[String(id)] || [];
    const raw = window.prompt("Теги через запятую:", current.join(", "));
    if (raw === null) return;
    const tags = raw.split(",").map(value => value.trim()).filter(Boolean);
    await api(endpoint(id, "tags"), {
      method:"PUT", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({tags})
    });
    await refreshSnapshot();
  }

  function checklistItemsFromText(text) {
    const items = [];
    for (const line of String(text || "").split(/\r?\n/)) {
      const match = line.match(/^\s*(?:[-*]|\d+[.)])\s+(?:\[[ xX]\]\s*)?(.{2,240})$/);
      if (match) items.push({text:match[1].trim(),done:/\[[xX]\]/.test(line)});
    }
    return items.slice(0, 30);
  }

  async function createChecklist(row) {
    let items = checklistItemsFromText(row._miyoriText || row.querySelector(".message-body")?.textContent);
    if (!items.length) {
      const raw = window.prompt("Пункты чек-листа через ;");
      if (!raw) return;
      items = raw.split(";").map(text => ({text:text.trim(),done:false})).filter(item => item.text);
    }
    await saveChecklistFor(row, items);
  }

  async function saveChecklistFor(row, items) {
    const id = Number(row.dataset.messageId);
    const data = await api(endpoint(id, "checklist"), {
      method:"PUT", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({items})
    });
    ux.snapshot = ux.snapshot || {};
    ux.snapshot.checklists = ux.snapshot.checklists || {};
    ux.snapshot.checklists[String(id)] = {items:data.items};
    renderChecklist(row, data.items);
  }

  async function toggleReaction(row, reaction, enabled) {
    const id = Number(row.dataset.messageId);
    if (reaction === "pin") {
      await togglePin(row);
    }
    if (reaction === "remember" && enabled) {
      const base = String(row._miyoriText || row.querySelector(".message-body")?.textContent || "").trim().slice(0,1000);
      const statement = window.prompt(
        "Что сохранить как кандидат в Memory? Проверьте формулировку перед сохранением.",
        base
      );
      if (statement === null || !statement.trim()) return;
      await api(endpoint(id, "remember"), {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({statement:statement.trim()})
      });
      setStatus("Кандидат сохранён в Knowledge; он ещё не подтверждён как факт.");
    }
    const data = await api(endpoint(id, "reaction"), {
      method:"PUT", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({reaction,enabled})
    });
    ux.snapshot = ux.snapshot || {};
    ux.snapshot.reactions = ux.snapshot.reactions || {};
    ux.snapshot.reactions[String(id)] = data.reactions || [];
    renderReactions(row, data.reactions || []);
  }

  async function chooseRoute(row) {
    const raw = window.prompt(
      "Куда отправить? new_chat / saved / knowledge / documents / tasks / agent",
      "new_chat"
    );
    if (!raw) return;
    const destination = raw.trim().toLowerCase();
    const id = Number(row.dataset.messageId);
    const text = String(row._miyoriText || row.querySelector(".message-body")?.textContent || "").trim();
    await api(endpoint(id, "route"), {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({destination,detail:{source:"chat_message"}})
    });
    if (destination === "new_chat") {
      startNewChat();
      input.value = "Продолжи работу с этим сообщением:\n\n> " + text.replace(/\n/g, "\n> ");
      input.dispatchEvent(new Event("input",{bubbles:true}));
      input.focus();
    } else if (destination === "saved") {
      await api(endpoint(id, "bookmark"), {
        method:"PUT", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({bookmarked:true})
      });
    } else if (destination === "knowledge") {
      if (typeof renderNexusKnowledgeWorkspace === "function") await renderNexusKnowledgeWorkspace();
    } else if (destination === "documents") {
      $("menuDocumentsHub")?.click();
    } else if (destination === "tasks" || destination === "agent") {
      if (typeof openAgentWorkspaceFromChat === "function") {
        await openAgentWorkspaceFromChat(text);
      }
    }
  }

  async function refreshFolders() {
    if (!projectId()) return;
    try {
      const data = await api("/api/projects/" + projectId() + "/conversation-folders");
      const select = $("conversationFolderSelect");
      if (!select) return;
      const current = ux.folder;
      select.replaceChildren();
      const labels = {
        all:"Все",
        pinned:"Закреплённые",
        saved:"С сохранённым",
        tasks:"С задачами",
        unread:"Непрочитанные",
      };
      for (const key of Object.keys(labels)) {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = labels[key] + (data.system?.[key] != null ? " · " + data.system[key] : "");
        select.appendChild(option);
      }
      for (const folder of data.custom || []) {
        const option = document.createElement("option");
        option.value = "custom:" + folder.id;
        option.textContent = folder.name + " · " + folder.conversation_count;
        select.appendChild(option);
      }
      const create = document.createElement("option");
      create.value = "__new__";
      create.textContent = "+ Новая папка";
      select.appendChild(create);
      select.value = [...select.options].some(item => item.value === current) ? current : "all";
      ux.folder = select.value;
    } catch (_) {}
  }

  async function createConversationFolder() {
    const name = window.prompt("Название папки разговоров:");
    if (!name?.trim()) {
      await refreshFolders();
      return;
    }
    try {
      const data = await api("/api/projects/" + projectId() + "/conversation-folders", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({name:name.trim()})
      });
      ux.folder = "custom:" + data.folder.id;
      sessionStorage.setItem("miyori.chat.folder", ux.folder);
      await refreshFolders();
      await loadConversations();
    } catch (error) {
      showError(error.message);
    }
  }

  async function assignCurrentConversationToFolder() {
    if (!conversationId()) return;
    let id = null;
    if (ux.folder.startsWith("custom:")) id = Number(ux.folder.split(":")[1]);
    if (!id) {
      const data = await api("/api/projects/" + projectId() + "/conversation-folders");
      const names = (data.custom || []).map(item => item.id + ":" + item.name).join(", ");
      const raw = window.prompt("ID папки. Доступно: " + (names || "сначала создайте папку"));
      if (!raw) return;
      id = Number(raw.split(":")[0]);
    }
    if (!id) return;
    await api("/api/projects/" + projectId() + "/conversations/" + conversationId() + "/folder", {
      method:"PUT", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({folder_id:id,enabled:true})
    });
    setStatus("Разговор добавлен в папку.");
    await refreshFolders();
  }

  function folderQuery() {
    return ux.folder || "all";
  }

  function applyUnreadDivider() {
    document.querySelectorAll(".unread-divider").forEach(node => node.remove());
    const lastRead = Number(ux.snapshot?.read_state?.last_read_message_id || 0);
    if (!lastRead) return;
    const rows = [...messages.querySelectorAll(".message[data-message-id]")];
    const firstUnread = rows.find(row => Number(row.dataset.messageId) > lastRead);
    if (!firstUnread) return;
    const divider = document.createElement("div");
    divider.className = "unread-divider";
    divider.textContent = "Новые сообщения";
    firstUnread.before(divider);
  }

  async function markLatestRead() {
    if (!projectId() || !conversationId() || !chatNearBottom()) return;
    const rows = [...messages.querySelectorAll(".message[data-message-id]")];
    const last = rows.at(-1);
    const id = Number(last?.dataset.messageId);
    if (!id) return;
    try {
      await api("/api/projects/" + projectId() + "/conversations/" + conversationId() + "/read", {
        method:"PUT", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({last_read_message_id:id})
      });
      document.querySelectorAll(".unread-divider").forEach(node => node.remove());
    } catch (_) {}
  }

  let readTimer = null;
  messages?.addEventListener("scroll", () => {
    if (readTimer) clearTimeout(readTimer);
    readTimer = setTimeout(() => void markLatestRead(), 400);
  }, {passive:true});

  function searchRequest(q) {
    const scope = $("chatSearchScope")?.value || "conversation";
    if (scope === "conversation") return null;
    const params = new URLSearchParams({q,scope});
    if (conversationId()) params.set("conversation_id", String(conversationId()));
    return api("/api/projects/" + projectId() + "/chat/search?" + params.toString());
  }

  async function renderUnifiedSearch(data, host, panel) {
    host.replaceChildren();
    const note = document.createElement("small");
    note.className = "chat-search-mode-note";
    note.textContent = data.semantic_embeddings
      ? "Семантический поиск"
      : "Умный поиск · " + (data.mode || "ranked");
    host.appendChild(note);
    if (!data.matches?.length) {
      const empty = document.createElement("small");
      empty.textContent = "Ничего не найдено";
      host.appendChild(empty);
      return;
    }
    for (const match of data.matches.slice(0, 30)) {
      const b = button(
        (match.kind === "chat" ? (match.title + " · ") : (match.title ? match.title + " · " : "")) +
        String(match.preview || "").slice(0, 240),
        "chat-search-match"
      );
      if (match.kind === "chat") {
        b.onclick = async () => {
          panel.hidden = true;
          await openConversation(Number(match.conversation_id), Number(match.message_id));
        };
      } else {
        b.onclick = () => {
          panel.hidden = true;
          $("menuDocumentsHub")?.click();
        };
      }
      host.appendChild(b);
    }
  }

  function openScheduleEditor() {
    const panel = $("chatSchedulePanel");
    if (!panel) return;
    panel.hidden = !panel.hidden;
    if (!panel.hidden) {
      const dt = $("chatScheduleTime");
      if (dt && !dt.value) {
        const future = new Date(Date.now() + 3600000);
        const local = new Date(future.getTime() - future.getTimezoneOffset() * 60000)
          .toISOString().slice(0,16);
        dt.value = local;
      }
    }
  }

  async function createSchedule() {
    const text = input.value.trim();
    const value = $("chatScheduleTime")?.value;
    if (!text || !value) {
      setStatus("Введите текст и время отложенного запроса.");
      return;
    }
    const payload = {
      text,
      scheduled_for:new Date(value).toISOString(),
      repeat_mode:$("chatScheduleRepeat")?.value || "none",
      auto_send:Boolean($("chatScheduleAuto")?.checked),
      conversation_id:conversationId(),
    };
    try {
      await api("/api/projects/" + projectId() + "/chat/schedules", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify(payload)
      });
      input.value = "";
      input.dispatchEvent(new Event("input",{bubbles:true}));
      $("chatSchedulePanel").hidden = true;
      setStatus("Отложенный запрос сохранён.");
    } catch (error) {
      showError(error.message);
    }
  }

  async function pollSchedules() {
    if (!projectId() || state.busy) return;
    try {
      const data = await api("/api/projects/" + projectId() + "/chat/schedules/due");
      const schedules = data.schedules || [];
      const shelf = $("scheduledDueShelf");
      if (!shelf) return;
      shelf.replaceChildren();
      shelf.hidden = schedules.length === 0;
      for (const item of schedules) {
        const composerFree = !input.value.trim() && !ux.reply && !ux.voiceNote;
        if (item.auto_send && !ux.dueSeen.has(item.id) && !state.busy && composerFree) {
          ux.dueSeen.add(item.id);
          if (item.conversation_id && Number(item.conversation_id) !== conversationId()) {
            await openConversation(Number(item.conversation_id));
          }
          input.value = item.text;
          input.dispatchEvent(new Event("input",{bubbles:true}));
          ux.pendingScheduleId = Number(item.id);
          ux.pendingScheduleText = item.text;
          form.requestSubmit();
          break;
        }
        const card = document.createElement("div");
        card.className = "scheduled-due-card";
        const copy = document.createElement("span");
        copy.textContent = item.text.slice(0,180);
        const send = button("Отправить", "conversation-primary-small");
        send.onclick = async () => {
          if (item.conversation_id && Number(item.conversation_id) !== conversationId()) {
            await openConversation(Number(item.conversation_id));
          }
          input.value = item.text;
          input.dispatchEvent(new Event("input",{bubbles:true}));
          ux.pendingScheduleId = Number(item.id);
          ux.pendingScheduleText = item.text;
          form.requestSubmit();
        };
        card.append(copy,send);
        shelf.appendChild(card);
      }
    } catch (_) {}
  }

  async function toggleVoiceNote() {
    if (ux.recording) {
      ux.recording.recorder.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setStatus("Браузер не поддерживает запись voice-note.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio:true});
      const recorder = new MediaRecorder(stream);
      const chunks = [];
      const startedAt = performance.now();
      ux.transcript = "";
      let recognition = null;
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (Recognition) {
        recognition = new Recognition();
        recognition.lang = document.documentElement.lang || "ru-RU";
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.onresult = event => {
          let text = "";
          for (let i=0;i<event.results.length;i++) text += event.results[i][0]?.transcript || "";
          ux.transcript = text.trim();
          setStatus(ux.transcript ? "Распознаю: " + ux.transcript.slice(-90) : "Записываю голосовое…");
        };
        try { recognition.start(); } catch (_) {}
      }
      recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());
        try { recognition?.stop(); } catch (_) {}
        ux.recording = null;
        $("voiceNoteButton")?.classList.remove("recording");
        const blob = new Blob(chunks,{type:recorder.mimeType || "audio/webm"});
        const formData = new FormData();
        formData.append("file",blob,"voice-note.webm");
        formData.append("duration_ms",String(Math.round(performance.now()-startedAt)));
        try {
          const response = await fetch("/api/projects/" + projectId() + "/voice-notes", {
            method:"POST",body:formData
          });
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || "Не удалось сохранить voice-note.");
          ux.voiceNote = data.voice_note;
          if (!input.value.trim() && ux.transcript) {
            input.value = ux.transcript;
            input.dispatchEvent(new Event("input",{bubbles:true}));
          } else if (!input.value.trim()) {
            input.value = "Голосовое сообщение (аудио сохранено без автоматической транскрипции).";
            input.dispatchEvent(new Event("input",{bubbles:true}));
          }
          renderVoiceDraft();
          setStatus("Голосовое сохранено. Текст можно проверить перед отправкой.");
        } catch (error) {
          showError(error.message);
        }
      };
      recorder.start();
      ux.recording = {recorder,stream,recognition,startedAt};
      $("voiceNoteButton")?.classList.add("recording");
      setStatus("Записываю голосовое… Нажмите ещё раз, чтобы остановить.");
    } catch (error) {
      setStatus(error?.name === "NotAllowedError" ? "Доступ к микрофону не разрешён." : "Не удалось открыть микрофон.");
    }
  }

  function renderVoiceDraft() {
    const host = $("voiceNoteDraft");
    if (!host) return;
    host.replaceChildren();
    if (!ux.voiceNote) {
      host.hidden = true;
      return;
    }
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.preload = "metadata";
    audio.src = ux.voiceNote.url;
    const label = document.createElement("span");
    label.textContent = "Voice note" + (ux.transcript ? " · транскрипция готова" : " · без транскрипции");
    const remove = button("×", "conversation-ux-close");
    remove.setAttribute("aria-label","Удалить voice-note из сообщения");
    remove.onclick = clearVoiceDraft;
    host.append(audio,label,remove);
    host.hidden = false;
  }

  function clearVoiceDraft() {
    ux.voiceNote = null;
    ux.transcript = "";
    renderVoiceDraft();
  }

  const observer = new MutationObserver(records => {
    for (const record of records) {
      for (const node of record.addedNodes) {
        if (!(node instanceof HTMLElement)) continue;
        if (node.matches?.(".message[data-message-id]")) decorateMessage(node);
        node.querySelectorAll?.(".message[data-message-id]").forEach(decorateMessage);
      }
    }
  });

  ensureChrome();
  observer.observe(messages,{childList:true,subtree:true});
  messages.querySelectorAll(".message[data-message-id]").forEach(decorateMessage);
  void refreshFolders();
  window.setInterval(() => {
    if (document.visibilityState === "visible") void pollSchedules();
  }, 30000);
  window.addEventListener("focus", () => void pollSchedules());
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") void pollSchedules();
  });

  window.miyoriConversationUX = {
    composerContext,
    resetConversation,
    afterConversationOpen,
    afterSend,
    folderQuery,
    refreshFolders,
    refreshSnapshot,
    searchRequest,
    renderUnifiedSearch,
  };

  void pollSchedules();
})();
