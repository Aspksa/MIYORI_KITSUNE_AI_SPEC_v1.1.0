async function renderDocumentsWorkspace(initialFolderId = null) {
  showWorkspaceShell(
    "documents",
    "Miyori Drive",
    "Документы / Облако / Miyori",
    "Рабочая документация проекта, оригиналы и знания Miyori."
  );

  workspaceBody.innerHTML =
    '<section class="miyori-drive">' +
      '<aside class="drive-sidebar">' +
        '<div class="drive-sidebar-title"><strong>Miyori Drive</strong><small>Файлы и знания проекта</small></div>' +
        '<button id="driveUploadButton" class="drive-primary-action" type="button">＋ Загрузить документы</button>' +
        '<button id="driveNewFolderButton" class="drive-secondary-action" type="button">＋ Новая папка</button>' +
        '<nav class="drive-nav">' +
          '<button class="drive-nav-item active" data-drive-scope="files" type="button"><span>▤</span><strong>Мои файлы</strong></button>' +
          '<button class="drive-nav-item" data-drive-scope="recent" type="button"><span>◷</span><strong>Недавние</strong></button>' +
          '<button class="drive-nav-item" data-drive-scope="rag" type="button"><span>✦</span><strong>Знания Miyori</strong></button>' +
          '<button class="drive-nav-item" data-drive-scope="trash" type="button"><span>⌫</span><strong>Корзина</strong><em id="driveTrashBadge"></em></button>' +
        '</nav>' +
        '<div class="drive-storage-card">' +
          '<span>Хранилище проекта</span>' +
          '<strong id="driveStorageText">—</strong>' +
          '<small id="driveStoragePath">Оригиналы сохраняются локально</small>' +
        '</div>' +
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
          '<div><span>Знания</span><strong id="driveStatRag">0</strong></div>' +
        '</div>' +
        '<button id="driveDropzone" class="drive-dropzone" type="button">' +
          '<span class="drive-drop-icon">⇧</span><div><strong>Перетащите рабочие документы сюда</strong>' +
          '<small>Любые рабочие файлы до 25 МБ · PDF/Office/TXT/Markdown/JSON индексируются в знания</small></div>' +
        '</button>' +
        '<section id="driveContent" class="drive-content">' +
          '<div id="driveFoldersSection" class="drive-section"><div class="drive-section-title"><strong>Папки</strong><span id="driveFolderCount"></span></div><div id="driveFolders" class="drive-folder-grid"></div></div>' +
          '<div id="driveFilesSection" class="drive-section"><div class="drive-section-title"><strong id="driveFilesTitle">Файлы</strong><span id="driveFileCount"></span></div><div id="driveFiles" class="drive-file-grid"></div></div>' +
          '<div id="driveKnowledgeSection" class="drive-section" hidden><div class="drive-section-title"><strong>Знания Miyori</strong><span>поиск по содержимому</span></div><div id="driveKnowledge"></div></div>' +
          '<div id="driveTrashSection" class="drive-section" hidden><div class="drive-section-title"><strong>Корзина</strong><span>оригиналы не удаляются автоматически</span></div><div id="driveTrash"></div></div>' +
          '<div id="driveResult"></div>' +
        '</section>' +
      '</main>' +
      '<input id="driveFileInput" type="file" multiple hidden>' +
    '</section>';

  let activeFolderId = initialFolderId ? Number(initialFolderId) : null;
  let activeScope = "files";
  let viewMode = "grid";
  let folders = [];
  let documents = [];
  let ragStatus = {};
  let storageRoot = "";
  let documentQuestionPoll = null;

  const fileType = (name) => {
    const ext = String(name || "").split(".").pop().toLowerCase();
    if (ext === "pdf") return {icon: "PDF", cls: "pdf"};
    if (ext === "docx") return {icon: "W", cls: "word"};
    if (ext === "xlsx") return {icon: "X", cls: "excel"};
    if (ext === "pptx") return {icon: "P", cls: "powerpoint"};
    if (["md", "markdown", "txt"].includes(ext)) return {icon: "TXT", cls: "text"};
    if (ext === "json") return {icon: "{ }", cls: "json"};
    return {icon: "▤", cls: "file"};
  };

  const formatBytes = (bytes) => {
    const value = Number(bytes || 0);
    if (value < 1024) return value + " Б";
    if (value < 1024 * 1024) return (value / 1024).toFixed(1) + " КБ";
    if (value < 1024 * 1024 * 1024) return (value / (1024 * 1024)).toFixed(1) + " МБ";
    return (value / (1024 * 1024 * 1024)).toFixed(1) + " ГБ";
  };

  const formatDate = (value) => {
    if (!value) return "";
    try {
      return new Date(value).toLocaleString("ru-RU", {
        day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"
      });
    } catch (_) {
      return "";
    }
  };

  const folderPath = (folderId) => {
    const map = new Map(folders.map(folder => [Number(folder.id), folder]));
    const path = [];
    let current = folderId ? map.get(Number(folderId)) : null;
    const guard = new Set();
    while (current && !guard.has(Number(current.id))) {
      guard.add(Number(current.id));
      path.unshift(current);
      current = current.parent_id ? map.get(Number(current.parent_id)) : null;
    }
    return path;
  };

  const renderBreadcrumb = () => {
    const parts = folderPath(activeFolderId);
    if (activeScope === "rag") {
      el("driveBreadcrumb").innerHTML = '<span class="drive-breadcrumb-label">✦ Знания Miyori</span>';
      return;
    }
    if (activeScope === "trash") {
      el("driveBreadcrumb").innerHTML = '<span class="drive-breadcrumb-label">⌫ Корзина</span>';
      return;
    }
    if (activeScope === "recent") {
      el("driveBreadcrumb").innerHTML = '<span class="drive-breadcrumb-label">◷ Недавние</span>';
      return;
    }

    el("driveBreadcrumb").innerHTML =
      '<button type="button" data-drive-root="1">Мои файлы</button>' +
      parts.map(folder =>
        '<span>›</span><button type="button" data-drive-crumb="' + folder.id + '">' +
        escapeHtml(folder.name) + '</button>'
      ).join("");

    const root = workspaceBody.querySelector("[data-drive-root]");
    if (root) root.onclick = async () => {
      activeFolderId = null;
      activeScope = "files";
      await renderDrive();
    };
    workspaceBody.querySelectorAll("[data-drive-crumb]").forEach(button => {
      button.onclick = async () => {
        activeFolderId = Number(button.dataset.driveCrumb);
        activeScope = "files";
        await renderDrive();
      };
    });
  };

  const setScopeUi = () => {
    workspaceBody.querySelectorAll("[data-drive-scope]").forEach(button => {
      button.classList.toggle("active", button.dataset.driveScope === activeScope);
    });

    const search = el("driveSearchInput");
    search.placeholder = activeScope === "rag"
      ? "Поиск по содержимому документов"
      : activeScope === "trash"
        ? "Поиск в корзине"
        : "Поиск по файлам";

    const fileControlsVisible = !["rag", "trash"].includes(activeScope);
    el("driveGridView").hidden = !fileControlsVisible;
    el("driveListView").hidden = !fileControlsVisible;
    el("driveDropzone").hidden = activeScope === "trash";
    el("driveUploadButton").disabled = activeScope === "trash";
    el("driveNewFolderButton").disabled = activeScope === "trash";
  };

  const renderFileItem = (document) => {
    const type = fileType(document.filename);
    const folderMap = new Map(folders.map(folder => [Number(folder.id), folder]));
    const folderName = document.folder_name ||
      (document.folder_id ? (folderMap.get(Number(document.folder_id))?.name || "") : "Мои файлы");
    return '<article class="drive-file-item ' + viewMode + '">' +
      '<div class="drive-file-preview ' + type.cls + '"><span>' + escapeHtml(type.icon) + '</span></div>' +
      '<div class="drive-file-copy"><strong title="' + escapeHtml(document.filename) + '">' +
        escapeHtml(document.filename) + '</strong>' +
        '<small>' + escapeHtml(folderName) + ' · ' + formatBytes(document.size_bytes) +
        ' · ' + formatDate(document.created_at) + '</small>' +
        '<span class="drive-file-knowledge">✦ ' + Number(document.chunk_count || 0) + ' фрагментов</span>' +
      '</div>' +
      '<div class="drive-file-actions">' +
        '<button type="button" data-drive-understand="' + document.id + '" title="Понимание документа">◎</button>' +
        '<button type="button" data-drive-download="' + document.id + '" title="Скачать оригинал">↓</button>' +
        '<button type="button" data-drive-delete="' + document.id + '" class="danger" title="В корзину">⌫</button>' +
      '</div>' +
    '</article>';
  };

  const intelligenceStatusLabel = (status) => ({
    indexed: "Структура готова",
    queued: "В очереди",
    analyzing: "Анализируется",
    complete: "Понято полностью",
    partial: "Понято частично",
    needs_ocr: "Нужен OCR",
    unsupported: "Только оригинал",
    failed: "Ошибка анализа"
  }[status] || status || "Не построено");

  const renderIntelligencePanel = async (documentId) => {
    const resultNode = el("driveResult");
    resultNode.innerHTML = workspaceResult("Загружаю карту документа…", "working");

    try {
      clearTimeout(documentQuestionPoll);
      const [data, questionData] = await Promise.all([
        api(
          "/api/projects/" + state.projectId + "/documents/" +
          documentId + "/intelligence"
        ),
        api(
          "/api/projects/" + state.projectId + "/documents/" +
          documentId + "/questions?limit=12"
        )
      ]);
      const profile = data.intelligence || {};
      const questions = questionData.questions || [];
      const coverage = Math.max(0, Math.min(100, Math.round(
        Number(profile.coverage_ratio || 0) * 100
      )));
      const extractionCoverage = Math.max(0, Math.min(100, Math.round(
        Number(profile.extraction_coverage || 0) * 100
      )));
      const extractionStatus = profile.extraction_status || "unknown";
      const extractionWarnings = Array.isArray(profile.extraction_warnings)
        ? profile.extraction_warnings
        : [];
      const outline = profile.outline || [];
      const analysis = profile.analysis || {};
      const keyPoints = analysis.key_points || [];
      const risks = analysis.risks || [];
      const entities = analysis.entities || [];
      const dates = analysis.dates || [];
      const amounts = analysis.amounts || [];
      const status = profile.status || "indexed";

      resultNode.innerHTML =
        '<section class="drive-intelligence-panel">' +
          '<header class="drive-intelligence-head">' +
            '<div><span class="section-caption">Document Intelligence</span>' +
              '<h3>' + escapeHtml(profile.title || "Документ") + '</h3>' +
              '<p>' + escapeHtml(intelligenceStatusLabel(status)) + '</p></div>' +
            '<button id="driveIntelligenceClose" class="sheet-close" type="button">×</button>' +
          '</header>' +
          '<div class="drive-intelligence-metrics">' +
            '<div><span>Слов</span><strong>' + Number(profile.word_count || 0).toLocaleString("ru-RU") + '</strong></div>' +
            '<div><span>Страниц</span><strong>' + Number(profile.page_count || 0) + '</strong></div>' +
            '<div><span>Разделов</span><strong>' + Number(profile.section_count || 0) + '</strong></div>' +
            '<div><span>Структурных узлов</span><strong>' + Number(profile.node_count || 0) + '</strong></div>' +
          '</div>' +
          '<div class="drive-intelligence-coverage extraction-coverage">' +
            '<div><strong>Извлечение из оригинала</strong><span>' + extractionCoverage + '%</span></div>' +
            '<div class="drive-intelligence-progress"><i style="width:' + extractionCoverage + '%"></i></div>' +
            '<small>Статус: ' + escapeHtml(extractionStatus) +
              (extractionStatus === "complete"
                ? " · текстовые данные оригинала извлечены полностью в рамках поддерживаемого parser-а."
                : extractionStatus === "text_only"
                  ? " · текст извлечён, но изображения/диаграммы пока не интерпретируются визуально."
                  : extractionStatus === "partial"
                    ? " · часть страниц/слайдов не содержит доступного текстового слоя."
                    : extractionStatus === "needs_ocr"
                      ? " · для полного чтения нужен OCR."
                      : "") +
            '</small>' +
          '</div>' +
          (extractionWarnings.length
            ? '<div class="drive-extraction-warnings">' +
              extractionWarnings.slice(0, 20).map(item =>
                '<div><span>!</span><p>' + escapeHtml(item) + '</p></div>'
              ).join("") +
              '</div>'
            : '') +
          '<div class="drive-intelligence-coverage">' +
            '<div><strong>AI-анализ извлечённого текста</strong><span>' + coverage + '%</span></div>' +
            '<div class="drive-intelligence-progress"><i style="width:' + coverage + '%"></i></div>' +
            '<small>' +
              (status === "complete"
                ? "Miyori прошла весь доступный извлечённый текст и построила итоговый синтез."
                : status === "analyzing" || status === "queued"
                  ? "Анализ выполняется последовательно, окно за окном."
                  : status === "needs_ocr"
                    ? "AI-анализ невозможен до появления извлекаемого текста."
                    : "Локальная структура готова. Полный AI-анализ можно запустить отдельно.") +
            '</small>' +
          '</div>' +
          (profile.summary_long || profile.summary_short
            ? '<section class="drive-intelligence-section"><h4>Целостная сводка</h4><p>' +
              escapeHtml(profile.summary_long || profile.summary_short) + '</p></section>'
            : '') +
          '<details id="driveRelatedDocuments" class="drive-intelligence-section drive-related-documents">' +
            '<summary>Возможные связи с другими документами</summary>' +
            '<p class="drive-intelligence-help">Сопоставляются только явно указанные номера документов, VIN и госномера. Результат не считается подтверждённой связью.</p>' +
            '<div id="driveRelatedResults">Нажмите, чтобы найти совпадения.</div>' +
          '</details>' +
          '<section class="drive-intelligence-section drive-exhaustive-question">' +
            '<h4>Спросить по всему документу</h4>' +
            '<p class="drive-intelligence-help">Этот режим проверяет весь извлечённый текст от начала до конца, а не только найденные RAG-фрагменты.</p>' +
            '<div class="drive-exhaustive-form">' +
              '<input id="driveExhaustiveQuestion" type="text" maxlength="5000" placeholder="Например: перечисли все сроки и условия расторжения">' +
              '<button id="driveExhaustiveAsk" class="primary-sheet-button" type="button"' +
                (status === "needs_ocr" || status === "unsupported" ? " disabled" : "") +
                '>Проверить весь документ</button>' +
            '</div>' +
            '<div class="drive-exhaustive-history">' +
              (questions.length
                ? questions.slice(0, 8).map(item => {
                    const qCoverage = Math.max(0, Math.min(100, Math.round(Number(item.coverage_ratio || 0) * 100)));
                    const qExtraction = Math.max(0, Math.min(100, Math.round(Number(item.extraction_coverage || 0) * 100)));
                    const qOverall = Math.max(0, Math.min(100, Math.round(Number(item.overall_coverage_ratio || 0) * 100)));
                    const answer = item.answer || {};
                    const evidence = Array.isArray(answer.evidence) ? answer.evidence : [];
                    const stateLabel = ({
                      queued: "в очереди",
                      analyzing: "проверяется",
                      complete: "готово",
                      partial: "частично",
                      cancelled: "отменено",
                      failed: "ошибка"
                    }[item.status] || item.status || "");
                    return '<article class="drive-exhaustive-run status-' + escapeHtml(item.status || "") + '">' +
                      '<header><div><strong>' + escapeHtml(item.question || "") + '</strong>' +
                      '<small>' + escapeHtml(stateLabel) +
                      ' · scan ' + qCoverage + '% · original ' + qExtraction +
                      '% · overall ' + qOverall + '%</small></div>' +
                      (answer.confidence ? '<span>' + escapeHtml(String(answer.confidence)) + '</span>' : '') +
                      '</header>' +
                      (answer.answer
                        ? '<p>' + escapeHtml(answer.answer) + '</p>'
                        : item.last_error
                          ? '<p class="error-copy">' + escapeHtml(item.last_error) + '</p>'
                          : '<p>Полная проверка ещё выполняется.</p>') +
                      (evidence.length
                        ? '<div class="drive-exhaustive-evidence">' +
                          evidence.slice(0, 16).map(ev =>
                            '<div><strong>' + escapeHtml(ev.text || "") + '</strong>' +
                            '<small>' + escapeHtml(ev.locator || "") + '</small></div>'
                          ).join("") + '</div>'
                        : '') +
                    '</article>';
                  }).join("")
                : '<div class="workspace-empty">Полных вопросов по этому документу ещё не было.</div>') +
            '</div>' +
          '</section>' +
          '<section class="drive-intelligence-section"><h4>Структура документа</h4>' +
            (outline.length
              ? '<div class="drive-intelligence-outline">' +
                outline.slice(0, 100).map(item =>
                  '<div style="--outline-level:' + Math.max(0, Number(item.level || 0)) + '">' +
                    '<span>' + escapeHtml(item.locator || "") + '</span>' +
                    '<strong>' + escapeHtml(item.title || "Раздел") + '</strong>' +
                  '</div>'
                ).join("") +
                (outline.length > 100
                  ? '<small>Показаны первые 100 из ' + outline.length +
                    ' структурных элементов. Полная карта доступна Miyori через Agent Core.</small>'
                  : '') +
                '</div>'
              : '<div class="workspace-empty">Структурные заголовки не обнаружены.</div>') +
          '</section>' +
          (keyPoints.length
            ? '<section class="drive-intelligence-section"><h4>Ключевые пункты</h4><div class="drive-intelligence-list">' +
              keyPoints.slice(0, 30).map(item =>
                '<article><strong>' + escapeHtml(item.text || String(item)) + '</strong>' +
                (item.locator ? '<small>' + escapeHtml(item.locator) + '</small>' : '') +
                '</article>'
              ).join("") + '</div></section>'
            : '') +
          (risks.length
            ? '<section class="drive-intelligence-section"><h4>Риски и важные места</h4><div class="drive-intelligence-list">' +
              risks.slice(0, 20).map(item =>
                '<article><strong>' + escapeHtml(item.text || String(item)) + '</strong>' +
                '<small>' + escapeHtml(item.locator || item.basis || "") + '</small></article>'
              ).join("") + '</div></section>'
            : '') +
          ((entities.length || dates.length || amounts.length)
            ? '<section class="drive-intelligence-section"><h4>Извлечённые сущности</h4><div class="drive-intelligence-tags">' +
              entities.slice(0, 30).map(item =>
                '<span>' + escapeHtml(item.name || String(item)) + '</span>'
              ).join("") +
              dates.slice(0, 15).map(item =>
                '<span>' + escapeHtml(item.value || String(item)) + '</span>'
              ).join("") +
              amounts.slice(0, 15).map(item =>
                '<span>' + escapeHtml(
                  (item.value || "") + (item.currency ? " " + item.currency : "")
                ) + '</span>'
              ).join("") +
              '</div></section>'
            : '') +
          (profile.last_error
            ? '<div class="sheet-note warning">' + escapeHtml(profile.last_error) + '</div>'
            : '') +
          '<div class="sheet-actions drive-intelligence-actions">' +
            '<button id="driveIntelligenceRefresh" class="secondary-sheet-button" type="button">Обновить статус</button>' +
            '<button id="driveIntelligenceRebuild" class="secondary-sheet-button" type="button">Перестроить структуру</button>' +
            '<button id="driveIntelligenceAnalyze" class="primary-sheet-button" type="button"' +
              (status === "needs_ocr" || status === "unsupported" ? " disabled" : "") +
              '>' + (status === "complete" ? "Проанализировать заново" : "Понять документ полностью") + '</button>' +
          '</div>' +
        '</section>';

      const relatedPanel=el("driveRelatedDocuments");
      if (relatedPanel) {
        let relatedLoaded=false;
        relatedPanel.addEventListener("toggle",async()=>{
          if(!relatedPanel.open || relatedLoaded)return;
          relatedLoaded=true;
          const project=Number(state.projectId);
          const host=el("driveRelatedResults");
          if(!host)return;
          host.textContent="Ищу совпадения по извлечённым реквизитам…";
          try{
            const response=await api(
              "/api/projects/"+project+"/documents/"+documentId+"/related?limit=8"
            );
            if(Number(state.projectId)!==project || !host.isConnected)return;
            host.replaceChildren();
            if(response.scan_truncated){
              const warning=document.createElement("p");
              warning.className="drive-related-warning";
              warning.textContent="Поиск ограничен первыми доступными фрагментами; список может быть неполным.";
              host.append(warning);
            }
            if(!response.candidates?.length){
              const empty=document.createElement("p");
              empty.textContent="Точных совпадений пока нет.";
              host.append(empty);
            }
            for(const item of response.candidates||[]){
              const row=document.createElement("article");
              row.className="drive-related-item";
              const open=document.createElement("button");
              open.type="button";
              open.className="drive-related-open";
              open.textContent=item.filename;
              open.title="Открыть структуру этого документа";
              open.addEventListener("click",()=>renderIntelligencePanel(item.document_id));
              row.append(open);
              for(const match of (item.matches||[]).slice(0,4)){
                const info=document.createElement("p");
                info.textContent=match.kind+": "+match.identifier+
                  " · источник: "+(match.source?.locator||"не указано")+
                  " · здесь: "+(match.target?.locator||"не указано");
                row.append(info);
              }
              host.append(row);
            }
          }catch(error){
            relatedLoaded=false;
            if(host.isConnected)host.textContent=
              "Не удалось найти связи: "+String(error.message||error);
          }
        });
      }
      el("driveIntelligenceClose").onclick = () => {
        clearTimeout(documentQuestionPoll);
        resultNode.innerHTML = "";
      };
      const askExhaustive = async () => {
        const input = el("driveExhaustiveQuestion");
        const question = (input?.value || "").trim();
        if (!question) return;
        const button = el("driveExhaustiveAsk");
        if (button) {
          button.disabled = true;
          button.textContent = "Запускаю…";
        }
        try {
          const queued = await api(
            "/api/projects/" + state.projectId + "/documents/" +
            documentId + "/questions",
            {
              method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({question, force: false})
            }
          );
          resultNode.insertAdjacentHTML(
            "afterbegin",
            workspaceResult(
              queued.question?.existing
                ? "Такой полный вопрос уже есть — открываю сохранённый результат/прогресс."
                : "Miyori проверит весь документ по этому вопросу. Задача выполняется в фоне.",
              "success"
            )
          );
          if (typeof loadTasks === "function") loadTasks();
          await renderIntelligencePanel(documentId);
        } catch (error) {
          resultNode.insertAdjacentHTML("afterbegin", workspaceResult(error.message, "error"));
          if (button) {
            button.disabled = false;
            button.textContent = "Проверить весь документ";
          }
        }
      };
      if (el("driveExhaustiveAsk")) el("driveExhaustiveAsk").onclick = askExhaustive;
      if (el("driveExhaustiveQuestion")) {
        el("driveExhaustiveQuestion").onkeydown = event => {
          if (event.key === "Enter") {
            event.preventDefault();
            askExhaustive();
          }
        };
      }

      el("driveIntelligenceRefresh").onclick = () => renderIntelligencePanel(documentId);
      el("driveIntelligenceRebuild").onclick = async () => {
        resultNode.innerHTML = workspaceResult("Перестраиваю локальную карту документа…", "working");
        try {
          await api(
            "/api/projects/" + state.projectId + "/documents/" +
            documentId + "/intelligence/rebuild",
            {method: "POST"}
          );
          await renderIntelligencePanel(documentId);
        } catch (error) {
          resultNode.innerHTML = workspaceResult(error.message, "error");
        }
      };
      el("driveIntelligenceAnalyze").onclick = async () => {
        const force = status === "complete";
        resultNode.innerHTML = workspaceResult(
          "Полный анализ поставлен в очередь. Miyori пройдёт документ от начала до конца.",
          "working"
        );
        try {
          const queued = await api(
            "/api/projects/" + state.projectId + "/documents/" +
            documentId + "/intelligence/analyze",
            {
              method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({force})
            }
          );
          const taskId = queued.task?.id;
          resultNode.innerHTML =
            workspaceResult(
              "Document Intelligence запущен" +
              (taskId ? " · задача #" + taskId : "") +
              ". Можно продолжать работать: анализ выполняется в фоне.",
              "success"
            ) +
            '<div class="sheet-actions"><button id="driveIntelligenceReturn" class="primary-sheet-button" type="button">Открыть статус документа</button></div>';
          el("driveIntelligenceReturn").onclick = () => renderIntelligencePanel(documentId);
          if (typeof loadTasks === "function") loadTasks();
        } catch (error) {
          resultNode.innerHTML = workspaceResult(error.message, "error");
        }
      };

      if (questions.some(item => ["queued", "analyzing"].includes(item.status))) {
        documentQuestionPoll = setTimeout(() => {
          if (document.body.contains(resultNode)) {
            renderIntelligencePanel(documentId);
          }
        }, 2500);
      }
    } catch (error) {
      resultNode.innerHTML = workspaceResult(error.message, "error");
    }
  };

  const bindActiveActions = () => {
    workspaceBody.querySelectorAll("[data-drive-folder-open]").forEach(button => {
      button.onclick = async () => {
        activeFolderId = Number(button.dataset.driveFolderOpen);
        activeScope = "files";
        el("driveSearchInput").value = "";
        await renderDrive();
      };
    });

    workspaceBody.querySelectorAll("[data-drive-folder-delete]").forEach(button => {
      button.onclick = async () => {
        const folderId = Number(button.dataset.driveFolderDelete);
        const folder = folders.find(item => Number(item.id) === folderId);
        if (!folder) return;
        if (!confirm("Переместить папку «" + folder.name + "» в корзину? Оригиналы файлов сохранятся.")) return;
        try {
          await api("/api/projects/" + state.projectId + "/document-folders/" + folderId, {method: "DELETE"});
          el("driveResult").innerHTML = workspaceResult("Папка перемещена в корзину. Оригиналы сохранены.", "success");
          if (activeFolderId === folderId) activeFolderId = null;
          await renderDrive();
        } catch (error) {
          el("driveResult").innerHTML = workspaceResult(error.message, "error");
        }
      };
    });

    workspaceBody.querySelectorAll("[data-drive-understand]").forEach(button => {
      button.onclick = async () => {
        await renderIntelligencePanel(Number(button.dataset.driveUnderstand));
      };
    });

    workspaceBody.querySelectorAll("[data-drive-download]").forEach(button => {
      button.onclick = () => {
        const documentId = Number(button.dataset.driveDownload);
        window.location.href = "/api/projects/" + state.projectId + "/documents/" + documentId + "/download";
      };
    });

    workspaceBody.querySelectorAll("[data-drive-delete]").forEach(button => {
      button.onclick = async () => {
        const documentId = Number(button.dataset.driveDelete);
        const document = documents.find(item => Number(item.id) === documentId);
        if (!document) return;
        if (!confirm("Переместить «" + document.filename + "» в корзину? Оригинал останется на диске.")) return;
        try {
          await api("/api/projects/" + state.projectId + "/documents/" + documentId, {method: "DELETE"});
          el("driveResult").innerHTML = workspaceResult("Документ перемещён в корзину. Оригинал сохранён.", "success");
          await renderDrive();
        } catch (error) {
          el("driveResult").innerHTML = workspaceResult(error.message, "error");
        }
      };
    });
  };

  const renderTrash = async (query) => {
    const trash = await api("/api/projects/" + state.projectId + "/documents/trash");
    const needle = query.toLowerCase();
    const trashFolders = (trash.folders || []).filter(item =>
      !needle || String(item.name || "").toLowerCase().includes(needle)
    );
    const trashDocuments = (trash.documents || []).filter(item =>
      !needle || String(item.filename || "").toLowerCase().includes(needle)
    );

    el("driveTrash").innerHTML =
      '<div class="drive-trash-note"><span>⌫</span><div><strong>Безопасное удаление</strong>' +
      '<small>Файлы и папки не стираются автоматически. Они остаются в локальной корзине проекта до отдельной очистки.</small></div></div>' +
      '<div class="drive-trash-list">' +
        trashFolders.map(folder =>
          '<article class="drive-trash-row"><span class="drive-trash-icon">▰</span><div><strong>' +
          escapeHtml(folder.name) + '</strong><small>Папка · удалена ' + formatDate(folder.deleted_at) +
          '</small></div><button type="button" data-drive-restore-folder="' + folder.id + '">Восстановить</button></article>'
        ).join("") +
        trashDocuments.map(document =>
          '<article class="drive-trash-row"><span class="drive-trash-icon">▤</span><div><strong>' +
          escapeHtml(document.filename) + '</strong><small>' + formatBytes(document.size_bytes) +
          ' · удалён ' + formatDate(document.deleted_at) +
          '</small></div><button type="button" data-drive-restore-document="' + document.id + '">Восстановить</button></article>'
        ).join("") +
        (!trashFolders.length && !trashDocuments.length
          ? '<div class="drive-empty"><span>✓</span><strong>Корзина пуста</strong><small>Удалённые оригиналы появятся здесь.</small></div>'
          : '') +
      '</div>';

    workspaceBody.querySelectorAll("[data-drive-restore-document]").forEach(button => {
      button.onclick = async () => {
        try {
          await api(
            "/api/projects/" + state.projectId + "/documents/" +
            Number(button.dataset.driveRestoreDocument) + "/restore",
            {method: "POST"}
          );
          el("driveResult").innerHTML = workspaceResult("Документ восстановлен.", "success");
          await renderDrive();
        } catch (error) {
          el("driveResult").innerHTML = workspaceResult(error.message, "error");
        }
      };
    });

    workspaceBody.querySelectorAll("[data-drive-restore-folder]").forEach(button => {
      button.onclick = async () => {
        try {
          await api(
            "/api/projects/" + state.projectId + "/document-folders/" +
            Number(button.dataset.driveRestoreFolder) + "/restore",
            {method: "POST"}
          );
          el("driveResult").innerHTML = workspaceResult("Папка и её документы восстановлены.", "success");
          await renderDrive();
        } catch (error) {
          el("driveResult").innerHTML = workspaceResult(error.message, "error");
        }
      };
    });
  };

  const renderKnowledge = async (query) => {
    const indexed = documents.reduce(
      (sum, document) => sum + Number(document.chunk_count || 0),
      0
    );
    const mode = ragStatus.fts5 ? "Hybrid FTS5 + lexical" : "Lexical fallback";
    let results = [];

    if (query) {
      const found = await api(
        "/api/projects/" + state.projectId + "/documents/search?q=" + encodeURIComponent(query)
      );
      results = found.chunks || [];
    }

    el("driveKnowledge").innerHTML =
      '<div class="drive-knowledge-summary">' +
        '<div><span>✦</span><div><strong>База знаний готова</strong><small>' +
        documents.length + ' документов · ' + indexed + ' фрагментов · ' + escapeHtml(mode) +
        '</small></div></div>' +
        '<p>Оригиналы хранятся в Miyori Drive. В поиск и ответы Miyori попадает только активная документация; файлы из корзины исключены.</p>' +
      '</div>' +
      (query
        ? '<div class="drive-content-results"><div class="drive-section-title"><strong>Найдено по содержимому</strong><span>' +
          results.length + '</span></div>' +
          (results.length
            ? results.map(item =>
                '<article class="drive-search-hit"><strong>' + escapeHtml(item.filename || "Документ") +
                '</strong><small>Фрагмент ' + (Number(item.chunk_index || 0) + 1) + '</small><p>' +
                escapeHtml(String(item.content || "").slice(0, 520)) + '</p></article>'
              ).join("")
            : '<div class="drive-empty"><span>⌕</span><strong>Совпадений нет</strong><small>Попробуйте другой запрос.</small></div>') +
          '</div>'
        : '<div class="drive-knowledge-docs">' +
          documents.map(document =>
            '<article><span>✓</span><div><strong>' + escapeHtml(document.filename) +
            '</strong><small>' + Number(document.chunk_count || 0) +
            ' фрагментов · используется Miyori</small></div></article>'
          ).join("") +
          (!documents.length
            ? '<div class="drive-empty"><span>✦</span><strong>База знаний пуста</strong><small>Загрузите рабочие документы.</small></div>'
            : '') +
          '</div>');
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
      storageRoot = docs.storage_root || "";

      setScopeUi();
      renderBreadcrumb();

      const query = (el("driveSearchInput")?.value || "").trim();
      const lowerQuery = query.toLowerCase();
      const folderMap = new Map(folders.map(folder => [Number(folder.id), folder]));
      let visibleFolders = folders.filter(folder =>
        activeFolderId === null ? folder.parent_id === null : Number(folder.parent_id) === activeFolderId
      );
      let visibleDocs = documents.filter(document =>
        activeFolderId === null ? document.folder_id === null : Number(document.folder_id) === activeFolderId
      );

      if (activeScope === "recent") {
        visibleFolders = [];
        visibleDocs = [...documents]
          .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
          .slice(0, 40);
      }

      if (lowerQuery && !["rag", "trash"].includes(activeScope)) {
        visibleFolders = folders.filter(folder => String(folder.name).toLowerCase().includes(lowerQuery));
        visibleDocs = documents.filter(document => String(document.filename).toLowerCase().includes(lowerQuery));
      }

      const totalBytes = documents.reduce((sum, document) => sum + Number(document.size_bytes || 0), 0);
      el("driveStorageText").textContent = formatBytes(totalBytes) + " · " + documents.length + " файлов";
      el("driveStoragePath").textContent = storageRoot || "Локальное хранилище проекта";
      el("driveStatFiles").textContent = String(documents.length);
      el("driveStatFolders").textContent = String(folders.length);
      el("driveStatStorage").textContent = formatBytes(totalBytes);
      const projectChunks = documents.reduce(
        (sum, document) => sum + Number(document.chunk_count || 0),
        0
      );
      el("driveStatRag").textContent = String(projectChunks);
      el("driveTrashBadge").textContent = docs.trash_count ? String(docs.trash_count) : "";

      const folderSection = el("driveFoldersSection");
      const filesSection = el("driveFilesSection");
      const knowledgeSection = el("driveKnowledgeSection");
      const trashSection = el("driveTrashSection");

      folderSection.hidden = ["rag", "trash", "recent"].includes(activeScope) || !visibleFolders.length;
      filesSection.hidden = ["rag", "trash"].includes(activeScope);
      knowledgeSection.hidden = activeScope !== "rag";
      trashSection.hidden = activeScope !== "trash";

      if (activeScope === "rag") {
        await renderKnowledge(query);
        return;
      }
      if (activeScope === "trash") {
        await renderTrash(query);
        return;
      }

      el("driveFolderCount").textContent = visibleFolders.length ? String(visibleFolders.length) : "";
      el("driveFileCount").textContent = visibleDocs.length ? String(visibleDocs.length) : "";
      el("driveFilesTitle").textContent = activeScope === "recent" ? "Недавние документы" : "Файлы";

      el("driveFolders").innerHTML = visibleFolders.map(folder =>
        '<article class="drive-folder-tile">' +
          '<button class="drive-folder-open" type="button" data-drive-folder-open="' + folder.id + '">' +
            '<span class="drive-folder-shape">▰</span>' +
            '<span class="drive-tile-copy"><strong>' + escapeHtml(folder.name) + '</strong><small>' +
            folder.document_count + ' файлов</small></span>' +
          '</button>' +
          '<button class="drive-folder-delete" type="button" data-drive-folder-delete="' + folder.id + '" title="В корзину">⌫</button>' +
        '</article>'
      ).join("");

      el("driveFiles").className = viewMode === "list" ? "drive-file-list" : "drive-file-grid";
      el("driveFiles").innerHTML = visibleDocs.length
        ? visibleDocs.map(renderFileItem).join("")
        : '<div class="drive-empty"><span>☁</span><strong>Здесь пока пусто</strong><small>Загрузите файл или создайте папку.</small></div>';

      bindActiveActions();
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
    let duplicates = 0;
    let unindexed = 0;
    for (const file of files) {
      resultNode.dataset.persist = "1";
      resultNode.innerHTML = workspaceResult("Сохраняю оригинал «" + file.name + "»…", "working");
      const body = new FormData();
      body.append("file", file);
      if (activeFolderId !== null) body.append("folder_id", String(activeFolderId));
      try {
        const response = await fetch("/api/projects/" + state.projectId + "/documents", {
          method: "POST",
          body
        });
        const data = await response.json();
        if (!response.ok) {
          const detail = data?.detail || "Не удалось загрузить документ.";
          throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
        }
        if (data.duplicate) duplicates += 1;
        else {
          completed += 1;
          if (data.indexed === false) unindexed += 1;
        }
      } catch (error) {
        resultNode.innerHTML = workspaceResult(file.name + ": " + error.message, "error");
        delete resultNode.dataset.persist;
        return;
      }
    }

    const duplicateText = duplicates ? " · уже хранилось: " + duplicates : "";
    const unindexedText = unindexed ? " · без индекса знаний: " + unindexed : "";
    resultNode.innerHTML = workspaceResult(
      "Сохранено новых оригиналов: " + completed + duplicateText + unindexedText + ".",
      "success"
    );
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
      if (activeScope === "trash") return;
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
    if (activeScope !== "trash") await uploadFiles(event.dataTransfer?.files || []);
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
      resultNode.innerHTML = workspaceResult("Папка создана и сохранена в папке проекта.", "success");
      await renderDrive();
    } catch (error) {
      resultNode.innerHTML = workspaceResult(error.message, "error");
    }
  };

  workspaceBody.querySelectorAll("[data-drive-scope]").forEach(button => {
    button.onclick = async () => {
      activeScope = button.dataset.driveScope;
      if (activeScope !== "files") activeFolderId = null;
      el("driveSearchInput").value = "";
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
    searchTimer = setTimeout(renderDrive, 220);
  });

  await renderDrive();
}
