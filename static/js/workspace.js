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

async function renderMiyoriAiWorkspace() {
  showWorkspaceShell("ai", "Miyori Kitsune", "Miyori Kitsune AI", "Личность, поведение, память и автономность.");
  try {
    const [prefsData, status, modules] = await Promise.all([
      api("/api/ai/preferences"),
      api("/api/status"),
      api("/api/modules")
    ]);
    const p = prefsData.preferences || {};
    const aiVersion = (modules.modules || []).find(item => item.key === "miyori_ai")?.version || "—";

    workspaceBody.innerHTML =
      '<section class="ai-center">' +
        '<div class="ai-center-hero">' +
          '<div class="ai-center-orb">狐</div>' +
          '<div><span>Персональный AI</span><h3>Miyori Kitsune</h3><p>Версия модуля <strong>v' + escapeHtml(aiVersion) + '</strong> · Persona ' +
          escapeHtml(status.persona?.version || "—") + '</p></div>' +
          '<button id="aiOpenChat" class="primary-sheet-button" type="button">Открыть чат</button>' +
        '</div>' +
        '<form id="aiPreferencesForm" class="ai-settings-grid">' +
          '<section class="ai-settings-card"><strong>Личность и стиль</strong><small>Как Miyori общается и оформляет ответы.</small>' +
            '<label><span>Стиль общения</span><select id="aiCommunicationStyle">' +
              '<option value="balanced">Сбалансированный</option><option value="warm">Тёплый</option><option value="business">Деловой</option><option value="minimal">Минималистичный</option>' +
            '</select></label>' +
            '<label><span>Подробность</span><select id="aiDetailLevel"><option value="short">Кратко</option><option value="normal">Обычно</option><option value="detailed">Подробно</option></select></label>' +
            '<label><span>Инициативность</span><select id="aiInitiativeLevel"><option value="low">Низкая</option><option value="medium">Средняя</option><option value="high">Высокая</option></select></label>' +
          '</section>' +
          '<section class="ai-settings-card"><strong>Режим работы</strong><small>Основной контекст поведения Miyori.</small>' +
            '<label><span>Режим</span><select id="aiOperatingMode"><option value="personal">Личный помощник</option><option value="work">Рабочий помощник</option><option value="analyst">Аналитик</option><option value="research">Исследователь</option><option value="developer">Разработчик</option></select></label>' +
            '<label><span>Приоритет</span><select id="aiPriorityMode"><option value="accuracy">Точность</option><option value="balanced">Баланс</option><option value="speed">Скорость</option></select></label>' +
          '</section>' +
          '<section class="ai-settings-card ai-switch-card"><strong>Контекст и память</strong><small>Какие источники Miyori использует автоматически.</small>' +
            '<label class="ai-switch"><span><strong>RAG</strong><small>Документы и знания проекта</small></span><input id="aiUseRag" type="checkbox"></label>' +
            '<label class="ai-switch"><span><strong>Подтверждённая память</strong><small>Verified memory проекта</small></span><input id="aiUseMemory" type="checkbox"></label>' +
            '<label class="ai-switch"><span><strong>Показывать неопределённость</strong><small>Не скрывать границы знания</small></span><input id="aiShowUncertainty" type="checkbox"></label>' +
          '</section>' +
          '<section class="ai-settings-card ai-switch-card"><strong>Автономность</strong><small>Насколько активно Miyori продолжает работу сама.</small>' +
            '<label class="ai-switch"><span><strong>Предлагать следующие шаги</strong><small>После выполненной задачи</small></span><input id="aiSuggestNext" type="checkbox"></label>' +
            '<label class="ai-switch"><span><strong>Спрашивать перед предположением</strong><small>Если контекста недостаточно</small></span><input id="aiAskBeforeAssuming" type="checkbox"></label>' +
          '</section>' +
          '<div id="aiPreferencesResult" class="ai-settings-result"></div>' +
          '<div class="sheet-actions ai-settings-actions"><button class="primary-sheet-button" type="submit">Сохранить настройки AI</button></div>' +
        '</form>' +
      '</section>';

    el("aiCommunicationStyle").value = p.communication_style || "balanced";
    el("aiDetailLevel").value = p.detail_level || "normal";
    el("aiInitiativeLevel").value = p.initiative_level || "medium";
    el("aiOperatingMode").value = p.operating_mode || "personal";
    el("aiPriorityMode").value = p.priority_mode || "accuracy";
    el("aiUseRag").checked = !!p.use_rag;
    el("aiUseMemory").checked = !!p.use_verified_memory;
    el("aiShowUncertainty").checked = !!p.show_uncertainty;
    el("aiSuggestNext").checked = !!p.suggest_next_steps;
    el("aiAskBeforeAssuming").checked = !!p.ask_before_assuming;

    el("aiOpenChat").onclick = showChatWorkspace;
    el("aiPreferencesForm").onsubmit = async (event) => {
      event.preventDefault();
      const result = el("aiPreferencesResult");
      try {
        await api("/api/ai/preferences", {
          method: "PUT",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            communication_style: el("aiCommunicationStyle").value,
            detail_level: el("aiDetailLevel").value,
            initiative_level: el("aiInitiativeLevel").value,
            operating_mode: el("aiOperatingMode").value,
            priority_mode: el("aiPriorityMode").value,
            use_rag: el("aiUseRag").checked,
            use_verified_memory: el("aiUseMemory").checked,
            show_uncertainty: el("aiShowUncertainty").checked,
            suggest_next_steps: el("aiSuggestNext").checked,
            ask_before_assuming: el("aiAskBeforeAssuming").checked
          })
        });
        result.innerHTML = workspaceResult("Настройки Miyori AI сохранены и применяются к новым ответам.", "success");
      } catch (error) {
        result.innerHTML = workspaceResult(error.message, "error");
      }
    };
  } catch (error) {
    workspaceBody.innerHTML = workspaceResult(error.message, "error");
  }
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
    '</section>' +
    '<section class="workspace-card workspace-card-wide update-release-card">' +
      '<div class="workspace-card-head"><div><strong>Версии модулей</strong><small>Видно, какие части Miyori развиваются и в каком они состоянии</small></div></div>' +
      '<div id="workspaceModuleVersions" class="module-version-grid"><div class="workspace-loading">Загружаю версии…</div></div>' +
    '</section>' +
    '<section class="workspace-card workspace-card-wide update-release-card">' +
      '<div class="workspace-card-head"><div><strong>Описание обновлений</strong><small>Полный журнал изменений по релизам и модулям</small></div></div>' +
      '<div id="workspaceChangelog" class="update-changelog"><div class="workspace-loading">Загружаю историю…</div></div>' +
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

  const loadChangelog = async () => {
    const modulesNode = el("workspaceModuleVersions");
    const changelogNode = el("workspaceChangelog");
    try {
      const data = await api("/api/update/changelog");
      const modules = data.manifest?.modules || [];
      modulesNode.innerHTML = modules.map(module => {
        const statusLabel = module.status === "active" ? "Развивается" :
          module.status === "foundation" ? "Основа" :
          module.status === "planned" ? "Запланирован" : module.status;
        return '<article class="module-version-card">' +
          '<div><strong>' + escapeHtml(module.name) + '</strong><small>' + escapeHtml(module.description) + '</small></div>' +
          '<span class="module-version-number">v' + escapeHtml(module.version) + '</span>' +
          '<span class="module-development-status ' + escapeHtml(module.status) + '">' + escapeHtml(statusLabel) + '</span>' +
        '</article>';
      }).join("");

      changelogNode.innerHTML = (data.releases || []).map((release, releaseIndex) =>
        '<article class="release-entry ' + (releaseIndex === 0 ? 'current' : '') + '">' +
          '<header><div><span>Релиз ' + escapeHtml(release.version) + '</span><strong>' + escapeHtml(release.title) + '</strong></div>' +
          (releaseIndex === 0 ? '<span class="soft-status ok">Текущий</span>' : '') + '</header>' +
          '<p>' + escapeHtml(release.summary) + '</p>' +
          '<div class="release-module-list">' +
          (release.modules || []).map(item => {
            const module = modules.find(candidate => candidate.key === item.key);
            return '<div class="release-module-change"><div><strong>' +
              escapeHtml(module?.name || item.key) + '</strong><span>v' + escapeHtml(item.version || module?.version || "—") + '</span></div>' +
              '<ul>' + (item.changes || []).map(change => '<li>' + escapeHtml(change) + '</li>').join("") + '</ul></div>';
          }).join("") +
          '</div>' +
        '</article>'
      ).join("");
    } catch (error) {
      modulesNode.innerHTML = workspaceResult(error.message, "error");
      changelogNode.innerHTML = workspaceResult(error.message, "error");
    }
  };

  await Promise.all([load(refresh), loadChangelog()]);
}
