function formatSystemBytes(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) return value + " Б";
  if (value < 1024 * 1024) return (value / 1024).toFixed(1) + " КБ";
  if (value < 1024 * 1024 * 1024) return (value / (1024 * 1024)).toFixed(1) + " МБ";
  return (value / (1024 * 1024 * 1024)).toFixed(1) + " ГБ";
}

function applyInterfaceSettings(general) {
  const theme = general?.theme || "system";
  const density = general?.density || "normal";
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.density = density;
  document.documentElement.lang = general?.interface_language === "en-US" ? "en" : "ru";
}

async function renderSettingsWorkspace() {
  showWorkspaceShell("settings", "", "Настройки", "");
  try {
    const data = await api("/api/settings");
    const cfg = data.settings || {};
    const general = cfg.general || {};
    const automation = cfg.automation || {};
    const sys = data.system || {};
    const worker = data.worker || {};
    const update = data.update || {};
    const modules = data.modules?.modules || [];
    const settingsVersion = modules.find(item => item.key === "settings")?.version || "—";

    workspaceBody.innerHTML =
      '<section class="system-settings-shell">' +
        '<div class="settings-tabs">' +
          '<button class="settings-tab active" data-settings-tab="general" type="button">Общие</button>' +
          '<button class="settings-tab" data-settings-tab="system" type="button">Система</button>' +
          '<button class="settings-tab" data-settings-tab="automation" type="button">Автоматизация</button>' +
          '<button class="settings-tab" data-settings-tab="diagnostics" type="button">Диагностика</button>' +
          '<span class="settings-module-version">Настройки v' + escapeHtml(settingsVersion) + '</span>' +
        '</div>' +

        '<div class="settings-panel active" data-settings-panel="general">' +
          '<form id="generalSettingsForm" class="system-settings-form">' +
            '<section class="settings-section-card"><strong>Запуск и интерфейс</strong><small>Параметры локального приложения Miyori.</small>' +
              '<label class="settings-switch-row"><span><strong>Запускать вместе с Windows</strong><small>Создаёт MiyoriKitsune.cmd в пользовательской папке Startup</small></span><input id="settingAutostart" type="checkbox"></label>' +
              '<label class="settings-switch-row"><span><strong>Автоматически открывать браузер</strong><small>Открывать локальный интерфейс после запуска сервера</small></span><input id="settingOpenBrowser" type="checkbox"></label>' +
              '<div class="settings-field-grid">' +
                '<label><span>Язык интерфейса</span><select id="settingLanguage"><option value="ru-RU">Русский</option><option value="en-US">English</option></select></label>' +
                '<label><span>Тема</span><select id="settingTheme"><option value="system">Системная</option><option value="light">Светлая</option><option value="dark">Тёмная</option></select></label>' +
                '<label><span>Интерфейс</span><select id="settingDensity"><option value="normal">Обычный</option><option value="compact">Компактный</option></select></label>' +
                '<label><span>Экран при старте</span><select id="settingStartupScreen"><option value="chat">Чат</option><option value="ai">Miyori Kitsune AI</option><option value="account">Личный кабинет</option><option value="drive">Miyori Drive</option><option value="settings">Настройки</option></select></label>' +
              '</div>' +
            '</section>' +
            '<div id="generalSettingsResult"></div>' +
            '<div class="sheet-actions"><button class="primary-sheet-button" type="submit">Сохранить общие</button></div>' +
          '</form>' +
        '</div>' +

        '<div class="settings-panel" data-settings-panel="system">' +
          '<div class="system-info-grid">' +
            '<article><span>Версия Miyori</span><strong>' + escapeHtml(data.modules?.project_version || "—") + '</strong></article>' +
            '<article><span>Режим установки</span><strong>' + escapeHtml(sys.install_mode || "—") + '</strong></article>' +
            '<article><span>Python</span><strong>' + escapeHtml(sys.python_version || "—") + '</strong></article>' +
            '<article><span>SQLite</span><strong>' + (sys.sqlite?.ok ? "Готова" : "Нет базы") + '</strong></article>' +
            '<article><span>Фоновый worker</span><strong>' + (worker.monitor_running ? "Активен" : "Остановлен") + '</strong></article>' +
            '<article><span>Свободное место</span><strong>' + formatSystemBytes(sys.disk?.free_bytes) + '</strong></article>' +
          '</div>' +
          '<section class="settings-section-card system-path-card"><strong>Пути</strong>' +
            '<div><span>Установка</span><code>' + escapeHtml(sys.root_dir || "—") + '</code></div>' +
            '<div><span>Data</span><code>' + escapeHtml(sys.data_dir || "—") + '</code></div>' +
            '<div><span>SQLite</span><code>' + escapeHtml(sys.sqlite?.path || "—") + '</code></div>' +
            '<div class="sheet-actions"><button id="settingsOpenData" class="secondary-sheet-button" type="button">Открыть папку data</button></div>' +
          '</section>' +
          '<div id="systemSettingsResult"></div>' +
        '</div>' +

        '<div class="settings-panel" data-settings-panel="automation">' +
          '<form id="automationSettingsForm" class="system-settings-form">' +
            '<section class="settings-section-card"><strong>Фоновые задачи</strong><small>Очередь задач Miyori и периодический worker.</small>' +
              '<label class="settings-switch-row"><span><strong>Фоновые задачи</strong><small>Периодически проверять очередь и запускать задачи</small></span><input id="settingBackgroundTasks" type="checkbox"></label>' +
              '<label class="settings-number-row"><span>Интервал worker</span><input id="settingWorkerInterval" type="number" min="5" max="3600" step="5"><small>секунд</small></label>' +
            '</section>' +
            '<section class="settings-section-card"><strong>Обновления проекта</strong><small>Политика автоматического обновления GitHub.</small>' +
              '<label class="settings-switch-row"><span><strong>Автообновление</strong><small>Проверять GitHub и применять безопасные обновления</small></span><input id="settingAutoUpdate" type="checkbox"></label>' +
              '<label class="settings-number-row"><span>Интервал проверки GitHub</span><input id="settingUpdateInterval" type="number" min="5" max="1440" step="5"><small>минут</small></label>' +
              '<label class="settings-switch-row"><span><strong>Разрешить Portable Update</strong><small>Обновлять ZIP-установку без .git</small></span><input id="settingPortableUpdate" type="checkbox"></label>' +
              '<label class="settings-switch-row"><span><strong>Резервная копия перед обновлением</strong><small>Сохранять заменяемые файлы в data/update_backups</small></span><input id="settingUpdateBackup" type="checkbox"></label>' +
            '</section>' +
            '<div class="settings-restart-note">Изменение интервалов и политики updater полностью применяется после перезапуска Miyori.</div>' +
            '<div id="automationSettingsResult"></div>' +
            '<div class="sheet-actions"><button class="primary-sheet-button" type="submit">Сохранить автоматизацию</button></div>' +
          '</form>' +
        '</div>' +

        '<div class="settings-panel" data-settings-panel="diagnostics">' +
          '<div class="diagnostic-actions">' +
            '<button id="settingsRunDiagnostics" class="primary-sheet-button" type="button">Запустить self-check</button>' +
            '<button id="settingsExportDiagnostics" class="secondary-sheet-button" type="button">Экспорт JSON</button>' +
            '<button id="settingsCleanupRuntime" class="secondary-sheet-button danger-soft" type="button">Очистить runtime / logs</button>' +
          '</div>' +
          '<div id="diagnosticSummary" class="diagnostic-summary">' +
            '<div class="workspace-loading">Диагностика ещё не запускалась.</div>' +
          '</div>' +
          '<section class="settings-section-card"><strong>Модули</strong><small>Состояние и текущие версии.</small><div id="diagnosticModules" class="diagnostic-module-grid"></div></section>' +
        '</div>' +
      '</section>';

    const switchTab = (name) => {
      workspaceBody.querySelectorAll("[data-settings-tab]").forEach(button => button.classList.toggle("active", button.dataset.settingsTab === name));
      workspaceBody.querySelectorAll("[data-settings-panel]").forEach(panel => panel.classList.toggle("active", panel.dataset.settingsPanel === name));
    };
    workspaceBody.querySelectorAll("[data-settings-tab]").forEach(button => button.onclick = () => switchTab(button.dataset.settingsTab));

    el("settingAutostart").checked = !!general.windows_autostart;
    el("settingOpenBrowser").checked = !!general.open_browser;
    el("settingLanguage").value = general.interface_language || "ru-RU";
    el("settingTheme").value = general.theme || "system";
    el("settingDensity").value = general.density || "normal";
    el("settingStartupScreen").value = general.startup_screen || "chat";
    el("settingBackgroundTasks").checked = !!automation.background_tasks;
    el("settingWorkerInterval").value = automation.worker_interval_seconds || 15;
    el("settingAutoUpdate").checked = !!automation.auto_update;
    el("settingUpdateInterval").value = automation.update_interval_minutes || 15;
    el("settingPortableUpdate").checked = !!automation.allow_portable_update;
    el("settingUpdateBackup").checked = !!automation.backup_before_update;

    const collectGeneral = () => ({
      windows_autostart: el("settingAutostart").checked,
      open_browser: el("settingOpenBrowser").checked,
      interface_language: el("settingLanguage").value,
      theme: el("settingTheme").value,
      density: el("settingDensity").value,
      startup_screen: el("settingStartupScreen").value
    });
    const collectAutomation = () => ({
      background_tasks: el("settingBackgroundTasks").checked,
      worker_interval_seconds: Number(el("settingWorkerInterval").value || 15),
      auto_update: el("settingAutoUpdate").checked,
      update_interval_minutes: Number(el("settingUpdateInterval").value || 15),
      allow_portable_update: el("settingPortableUpdate").checked,
      backup_before_update: el("settingUpdateBackup").checked
    });

    el("settingTheme").onchange = () => applyInterfaceSettings({...general, theme: el("settingTheme").value, density: el("settingDensity").value});
    el("settingDensity").onchange = () => applyInterfaceSettings({...general, theme: el("settingTheme").value, density: el("settingDensity").value});

    const saveSettings = async (resultNode) => {
      try {
        const saved = await api("/api/settings", {
          method:"PUT",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify({general: collectGeneral(), automation: collectAutomation()})
        });
        Object.assign(general, saved.settings.general || {});
        Object.assign(automation, saved.settings.automation || {});
        applyInterfaceSettings(general);
        resultNode.innerHTML = workspaceResult(saved.message || "Настройки сохранены.", "success");
      } catch (error) {
        resultNode.innerHTML = workspaceResult(error.message, "error");
      }
    };
    el("generalSettingsForm").onsubmit = async event => { event.preventDefault(); await saveSettings(el("generalSettingsResult")); };
    el("automationSettingsForm").onsubmit = async event => { event.preventDefault(); await saveSettings(el("automationSettingsResult")); };

    el("settingsOpenData").onclick = async () => {
      try {
        await api("/api/settings/open-data", {method:"POST"});
        el("systemSettingsResult").innerHTML = workspaceResult("Папка data открыта.", "success");
      } catch (error) {
        el("systemSettingsResult").innerHTML = workspaceResult(error.message, "error");
      }
    };

    el("diagnosticModules").innerHTML = modules.map(module =>
      '<article><div><strong>' + escapeHtml(module.name) + '</strong><small>' + escapeHtml(module.description) + '</small></div><span>v' +
      escapeHtml(module.version) + '</span></article>'
    ).join("");

    let lastDiagnostic = null;
    const runDiagnostics = async () => {
      const node = el("diagnosticSummary");
      node.innerHTML = workspaceResult("Выполняю self-check…", "working");
      try {
        lastDiagnostic = await api("/api/settings/diagnostics?project_id=" + state.projectId);
        const checks = lastDiagnostic.self_check || [];
        const passed = checks.filter(item => item.passed).length;
        node.innerHTML =
          '<div class="diagnostic-score ' + (passed === checks.length ? 'ok' : 'warn') + '"><strong>' + passed + '/' + checks.length + '</strong><span>проверок пройдено</span></div>' +
          '<div class="diagnostic-check-list">' + checks.map(item =>
            '<div class="' + (item.passed ? 'passed' : 'failed') + '"><span>' + (item.passed ? '✓' : '!') + '</span><div><strong>' +
            escapeHtml(item.name) + '</strong><small>' + escapeHtml(item.details) + '</small></div></div>'
          ).join("") + '</div>' +
          ((lastDiagnostic.last_errors || []).length ? '<div class="sheet-result error">' + escapeHtml(lastDiagnostic.last_errors.join("\n")) + '</div>' : '');
      } catch (error) {
        node.innerHTML = workspaceResult(error.message, "error");
      }
    };

    el("settingsRunDiagnostics").onclick = runDiagnostics;
    el("settingsExportDiagnostics").onclick = async () => {
      if (!lastDiagnostic) await runDiagnostics();
      if (!lastDiagnostic) return;
      const blob = new Blob([JSON.stringify(lastDiagnostic, null, 2)], {type:"application/json"});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "miyori-diagnostics-" + new Date().toISOString().replace(/[:.]/g, "-") + ".json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    };
    el("settingsCleanupRuntime").onclick = async () => {
      if (!confirm("Очистить содержимое runtime/ и logs/? Пользовательские data и .env не затрагиваются.")) return;
      try {
        const result = await api("/api/settings/cleanup-runtime", {method:"POST"});
        el("diagnosticSummary").innerHTML = workspaceResult("Удалено файлов: " + result.removed_files + " · " + formatSystemBytes(result.removed_bytes), "success");
      } catch (error) {
        el("diagnosticSummary").innerHTML = workspaceResult(error.message, "error");
      }
    };
  } catch (error) {
    workspaceBody.innerHTML = workspaceResult(error.message, "error");
  }
}
