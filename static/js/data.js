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
  if (toolName === "project_document_read") {
    const documentId = prompt("ID документа:");
    if (!documentId || !Number(documentId)) return null;
    return {document_id: Number(documentId), start: 0, limit: 12};
  }
  if (toolName === "drive_folder_create") {
    const name = prompt("Название новой папки:");
    if (!name || !name.trim()) return null;
    const parent = prompt("ID родительской папки (оставьте пустым для корня):");
    return {name: name.trim(), parent_id: parent && Number(parent) ? Number(parent) : null};
  }
  if (toolName === "drive_document_move") {
    const documentId = prompt("ID документа:");
    if (!documentId || !Number(documentId)) return null;
    const folderId = prompt("ID целевой папки (оставьте пустым для корня):");
    return {document_id: Number(documentId), folder_id: folderId && Number(folderId) ? Number(folderId) : null};
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
    project_document_catalog: "Каталог Drive",
    project_document_read: "Прочитать документ",
    drive_folder_create: "Создать папку Drive",
    drive_document_move: "Переместить документ",
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
  if (args.name) lines.push("Папка: " + args.name);
  if (args.document_id) lines.push("Документ ID: " + args.document_id);
  if (Object.prototype.hasOwnProperty.call(args, "folder_id")) {
    lines.push("Целевая папка ID: " + (args.folder_id ?? "корень"));
  }
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
  } else if (toolName === "project_document_catalog") {
    const docs = result.documents || [];
    const folders = result.folders || [];
    body.innerHTML = '<div class="result-title">Документы: ' + docs.length + ' · Папки: ' + folders.length + '</div>';
    for (const item of docs.slice(0, 25)) {
      const row = document.createElement("div");
      row.className = "result-row";
      row.innerHTML = '<div><strong>#' + item.id + ' ' + escapeHtml(item.filename) + '</strong><small>' +
        Number(item.chunk_count || 0) + ' фрагм.</small></div>';
      body.appendChild(row);
    }
  } else if (toolName === "project_document_read") {
    const doc = result.document || {};
    body.innerHTML = '<div class="result-title">' + escapeHtml(doc.filename || "Документ") + '</div>';
    for (const item of (result.chunks || []).slice(0, 12)) {
      const source = document.createElement("div");
      source.className = "source-card";
      source.innerHTML = '<strong>Фрагмент ' + (Number(item.chunk_index || 0) + 1) + '</strong><p>' +
        escapeHtml((item.content || "").slice(0, 700)) + '</p>';
      body.appendChild(source);
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
        escapeHtml(fact.statement) + '</span><small>' +
        escapeHtml((fact.memory_scope || "project") + " · " + (fact.memory_kind || "fact")) + '</small>';
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
