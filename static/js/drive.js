async function renderDocumentsWorkspace(initialFolderId = null) {
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
        '<div class="drive-overview">' +
          '<div><span>Файлы</span><strong id="driveStatFiles">0</strong></div>' +
          '<div><span>Папки</span><strong id="driveStatFolders">0</strong></div>' +
          '<div><span>Объём</span><strong id="driveStatStorage">0 Б</strong></div>' +
          '<div><span>RAG</span><strong id="driveStatRag">0</strong></div>' +
        '</div>' +
        '<button id="driveDropzone" class="drive-dropzone" type="button">' +
          '<span class="drive-drop-icon">⇧</span><div><strong>Перетащите файлы сюда</strong><small>PDF, Word, Excel, PowerPoint, TXT, Markdown, JSON · до 25 МБ</small></div>' +
        '</button>' +
        '<section id="driveContent" class="drive-content">' +
          '<div id="driveFoldersSection" class="drive-section"><div class="drive-section-title"><strong>Папки</strong><span id="driveFolderCount"></span></div><div id="driveFolders" class="drive-folder-grid"></div></div>' +
          '<div id="driveFilesSection" class="drive-section"><div class="drive-section-title"><strong>Файлы</strong><span id="driveFileCount"></span></div><div id="driveFiles" class="drive-file-grid"></div></div>' +
          '<div id="driveKnowledgeSection" class="drive-section" hidden><div class="drive-section-title"><strong>Знания Miyori</strong></div><div id="driveKnowledge"></div></div>' +
          '<div id="driveResult"></div>' +
        '</section>' +
      '</main>' +
      '<input id="driveFileInput" type="file" accept=".txt,.md,.markdown,.json,.pdf,.docx,.xlsx,.pptx" multiple hidden>' +
    '</section>';

  let activeFolderId = initialFolderId ? Number(initialFolderId) : null;
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
      el("driveStatFiles").textContent = String(documents.length);
      el("driveStatFolders").textContent = String(folders.length);
      el("driveStatStorage").textContent = formatBytes(totalBytes);
      el("driveStatRag").textContent = String(ragStatus.indexed_chunks || 0);

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

  const dropzone = el("driveDropzone");
  dropzone.onclick = () => el("driveFileInput").click();
  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragging");
    });
  });
  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragging");
    });
  });
  dropzone.addEventListener("drop", async (event) => {
    await uploadFiles(event.dataTransfer?.files || []);
  });

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
