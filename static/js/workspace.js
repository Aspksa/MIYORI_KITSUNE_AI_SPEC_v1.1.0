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
const nexusNavChat = el("nexusNavChat");
const nexusNavActions = el("nexusNavActions");
const nexusNavKnowledge = el("nexusNavKnowledge");
const nexusNavHome = el("nexusNavHome");
const nexusNavSystem = el("nexusNavSystem");

const NEXUS_VIEW_BY_WORKSPACE = {
  actions: "actions",
  knowledge: "knowledge",
  documents: "knowledge",
  work: "knowledge",
  home: "home",
  ai: "system",
  mobile: "system",
  account: "system",
  settings: "system",
  update: "system",
};

function announceNexusView(view) {
  const resolved = view || "chat";
  document.documentElement.dataset.nexusView = resolved;
  window.dispatchEvent(new CustomEvent("miyori:nexus-view", {
    detail: {view: resolved}
  }));
}

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
  setWorkspaceMenuActive(null);
  announceNexusView("chat");
  input.focus();
}

function showWorkspaceShell(name, eyebrow, title, subtitle) {
  if (chatHeader) chatHeader.hidden = true;
  const bodyHost = el("nexusBodyHost");
  if (bodyHost) bodyHost.dataset.appearanceOpen = "false";
  if (messages) messages.hidden = true;
  if (chatComposer) chatComposer.hidden = true;
  if (workspaceView) {
    workspaceView.hidden = false;
    workspaceView.style.display = "grid";
  }
  const cleanEyebrow = String(eyebrow || "").trim();
  const cleanSubtitle = String(subtitle || "").trim();
  if (workspaceEyebrow) {
    workspaceEyebrow.textContent = cleanEyebrow;
    workspaceEyebrow.hidden = !cleanEyebrow;
  }
  workspaceTitle.textContent = title;
  if (workspaceSubtitle) {
    workspaceSubtitle.textContent = cleanSubtitle;
    workspaceSubtitle.hidden = !cleanSubtitle;
  }
  workspaceBody.innerHTML = '<div class="workspace-loading">Загружаю раздел…</div>';
  setWorkspaceMenuActive(name);
  announceNexusView(NEXUS_VIEW_BY_WORKSPACE[name] || "system");
}

function workspaceResult(message, tone = "neutral") {
  return '<div class="sheet-result ' + tone + '">' + escapeHtml(message) + '</div>';
}

function shortSha(value) {
  if (!value) return "—";
  const text = String(value).trim();
  return text.length > 10 ? text.slice(0, 10) : text;
}


function nexusActionTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function nexusActionStateLabel(stateName) {
  return ({
    planned: "Планируется",
    waiting_permission: "Ждёт разрешения",
    running: "Выполняется",
    verifying: "Проверяется",
    recovery: "Требует восстановления",
    completed: "Завершено",
    error: "Ошибка",
    cancelled: "Отменено"
  }[stateName] || stateName || "—");
}

function nexusActionJson(value) {
  if (value === null || value === undefined) return "";
  try {
    return escapeHtml(JSON.stringify(value, null, 2));
  } catch (_) {
    return escapeHtml(String(value));
  }
}

function nexusActionValue(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch (_) {
    return String(value);
  }
}

function nexusActionPreviewMarkup(preview) {
  if (!preview || typeof preview !== "object") return "";
  const changes = Array.isArray(preview.changes) ? preview.changes : [];
  const rows = changes.map(change =>
    '<li><strong>' + escapeHtml(change.field || "изменение") + '</strong><span>' +
      escapeHtml(nexusActionValue(change.value)) + '</span></li>'
  ).join("");
  const flags = [
    preview.destructive ? "разрушительное" : null,
    preview.reversible === true ? "обратимое" : null,
    preview.reversible === false ? "без гарантированного отката" : null
  ].filter(Boolean).join(" · ");
  return '<details class="nexus-action-detail nexus-action-preview">' +
    '<summary>Что изменится</summary>' +
    '<div class="nexus-action-detail-body">' +
      (preview.title ? '<strong>' + escapeHtml(preview.title) + '</strong>' : '') +
      (preview.summary ? '<p>' + escapeHtml(preview.summary) + '</p>' : '') +
      (flags ? '<small>' + escapeHtml(flags) + '</small>' : '') +
      (rows ? '<ul class="nexus-action-change-list">' + rows + '</ul>' : '') +
    '</div>' +
  '</details>';
}

function nexusActionEvidenceMarkup(evidence) {
  if (!Array.isArray(evidence) || !evidence.length) return "";
  return '<details class="nexus-action-detail">' +
    '<summary>Источники проверки · ' + evidence.length + '</summary>' +
    '<div class="nexus-action-evidence-list">' +
      evidence.map(item =>
        '<article><div><strong>' + escapeHtml(item.label || item.kind || "Источник") + '</strong>' +
          '<small>' + escapeHtml(item.status || "recorded") + '</small></div>' +
          (item.data !== null && item.data !== undefined
            ? '<pre>' + nexusActionJson(item.data) + '</pre>'
            : '') +
        '</article>'
      ).join("") +
    '</div>' +
  '</details>';
}

function nexusActionStepsMarkup(action) {
  const steps = Array.isArray(action.steps) ? action.steps : [];
  if (!steps.length) return "";
  return '<details class="nexus-action-detail">' +
    '<summary>Шаги · ' + steps.length + '</summary>' +
    '<ol class="nexus-action-step-list">' +
      steps.map(step =>
        '<li><span class="nexus-action-step-state">' + escapeHtml(step.status || "planned") + '</span>' +
          '<div><strong>' + escapeHtml(step.tool_name || step.kind || ("Шаг " + step.index)) + '</strong>' +
          '<small>' + escapeHtml(step.reason || "") + '</small></div></li>'
      ).join("") +
    '</ol>' +
  '</details>';
}

function nexusActionHistoryMarkup(history) {
  if (!Array.isArray(history) || !history.length) return "";
  const visible = history.slice(-20).reverse();
  return '<details class="nexus-action-detail">' +
    '<summary>История · ' + history.length + '</summary>' +
    '<div class="nexus-action-history">' +
      visible.map(item =>
        '<article class="severity-' + escapeHtml(item.severity || "info") + '">' +
          '<span class="nexus-event-mark" aria-hidden="true"></span>' +
          '<div><strong>' + escapeHtml(item.summary || item.type || "Событие") + '</strong>' +
          '<small>' + escapeHtml(nexusActionTime(item.created_at)) + '</small></div>' +
        '</article>'
      ).join("") +
    '</div>' +
  '</details>';
}

function nexusActionResultMarkup(label, value, tone) {
  if (value === null || value === undefined) return "";
  return '<details class="nexus-action-detail ' + (tone || "") + '">' +
    '<summary>' + escapeHtml(label) + '</summary>' +
    '<pre>' + nexusActionJson(value) + '</pre>' +
  '</details>';
}

function nexusActionControlsMarkup(action) {
  const controls = action.controls || {};
  const buttons = [];
  if (controls.approve_permission) {
    buttons.push(
      '<button type="button" data-nexus-permission="' + controls.approve_permission +
      '" data-decision="allow" class="primary-sheet-button">Разрешить</button>'
    );
  }
  if (controls.deny_permission) {
    buttons.push(
      '<button type="button" data-nexus-permission="' + controls.deny_permission +
      '" data-decision="deny" class="secondary-sheet-button">Отклонить</button>'
    );
  }
  if (controls.recover_workflow) {
    buttons.push(
      '<button type="button" data-nexus-workflow-resume="' + controls.recover_workflow +
      '" class="primary-sheet-button">Восстановить</button>'
    );
  }
  if (controls.cancel_workflow) {
    buttons.push(
      '<button type="button" data-nexus-workflow-cancel="' + controls.cancel_workflow +
      '" class="secondary-sheet-button">Отменить workflow</button>'
    );
  }
  if (controls.cancel_task) {
    buttons.push(
      '<button type="button" data-nexus-task-cancel="' + controls.cancel_task +
      '" class="secondary-sheet-button">Отменить задачу</button>'
    );
  }
  if (controls.check_recovery) {
    buttons.push(
      '<button type="button" data-nexus-recovery-check="1" class="primary-sheet-button">Проверить recovery</button>'
    );
  }
  return buttons.length
    ? '<div class="nexus-action-controls">' + buttons.join("") + '</div>'
    : "";
}

function nexusActionCardMarkup(action) {
  const tool = action.tool || {};
  const meta = [
    action.kind === "workflow" ? "Процесс #" + action.workflow_id :
      action.kind === "task" ? "Задача #" + action.task_id : "Операция",
    tool.name || null,
    tool.risk_level ? "Риск: " + tool.risk_level : null,
    action.updated_at ? nexusActionTime(action.updated_at) : null
  ].filter(Boolean).join(" · ");
  const progress = action.progress?.label
    ? '<div class="nexus-action-progress"><span>Ход выполнения</span><strong>' +
        escapeHtml(action.progress.label) + '</strong></div>'
    : "";
  const destructive = tool.destructive
    ? '<span class="nexus-action-warning">Изменяет существующие данные</span>'
    : "";
  return '<article class="nexus-action-card state-' + escapeHtml(action.state || "planned") + '">' +
    '<header class="nexus-action-card-header">' +
      '<div class="nexus-action-card-title">' +
        '<div class="nexus-action-card-meta"><span>' + escapeHtml(meta) + '</span>' + destructive + '</div>' +
        '<h4>' + escapeHtml(action.title || "Действие") + '</h4>' +
        '<p>' + escapeHtml(action.summary || "") + '</p>' +
      '</div>' +
      '<span class="nexus-action-state-chip">' +
        escapeHtml(action.state_label || nexusActionStateLabel(action.state)) +
      '</span>' +
    '</header>' +
    progress +
    nexusActionControlsMarkup(action) +
    '<div class="nexus-action-details-grid">' +
      nexusActionPreviewMarkup(action.preview) +
      nexusActionStepsMarkup(action) +
      nexusActionEvidenceMarkup(action.evidence) +
      nexusActionResultMarkup("Результат", action.result, "result") +
      nexusActionResultMarkup("Ошибка", action.error, "error") +
      nexusActionHistoryMarkup(action.history) +
    '</div>' +
  '</article>';
}

async function renderNexusActionsWorkspace() {
  showWorkspaceShell("actions", "", "Действия", "");

  try {
    const center = await api(
      "/api/projects/" + state.projectId + "/nexus/actions?limit=80"
    );
    const actions = Array.isArray(center.actions) ? center.actions : [];
    const counts = center.counts || {};
    const attention = actions.filter(item =>
      ["waiting_permission", "recovery", "error"].includes(item.state)
    );
    const active = actions.filter(item =>
      ["planned", "running", "verifying"].includes(item.state)
    );
    const history = actions.filter(item =>
      ["completed", "cancelled"].includes(item.state)
    );

    const metric = (label, value, note, tone = "neutral") =>
      '<div class="nexus-action-metric tone-' + tone + '">' +
        '<span>' + escapeHtml(label) + '</span><strong>' + escapeHtml(String(value || 0)) + '</strong>' +
        '<small>' + escapeHtml(note) + '</small>' +
      '</div>';

    const group = (title, note, items, empty, collapsed = false) => {
      const body = '<div class="nexus-action-card-list">' +
        (items.length ? items.map(nexusActionCardMarkup).join("") :
          '<div class="nexus-actions-empty"><strong>' + escapeHtml(empty) + '</strong></div>') +
        '</div>';
      const label = '<strong>' + escapeHtml(title) + '</strong><small>' +
        escapeHtml(note) + '</small><span>' + items.length + '</span>';
      return collapsed
        ? '<details class="nexus-action-group nexus-actions-history">' +
            '<summary class="nexus-actions-history-summary">' + label + '</summary>' +
            body + '</details>'
        : '<section class="nexus-action-group"><header><div>' +
            '<strong>' + escapeHtml(title) + '</strong><small>' +
            escapeHtml(note) + '</small></div><span>' + items.length +
          '</span></header>' + body + '</section>';
    };

    workspaceBody.innerHTML =
      '<section class="nexus-actions-dashboard nexus-actions-v2">' +
        '<div class="nexus-actions-overview">' +
          '<div><h3>Что делает Миёри</h3>' +
            '<p>Здесь видны текущие задачи, ожидающие вашего решения, и завершённые результаты.</p></div>' +
          '<div class="nexus-actions-head-controls">' +
            '<button id="nexusAgentWorkspaceOpen" class="primary-sheet-button" type="button">Команда агентов</button>' +
            '<button id="nexusActionsRefresh" class="secondary-sheet-button" type="button">Обновить</button>' +
          '</div>' +
        '</div>' +
        '<div class="nexus-action-metrics">' +
          metric("Нужно ваше решение", counts.attention, "Разрешения и ошибки",
            counts.attention ? "warning" : "success") +
          metric("Сейчас выполняется", counts.active, "Активные задачи",
            counts.active ? "working" : "neutral") +
          metric("Завершено", counts.history, "Сохранённые результаты", "neutral") +
        '</div>' +
        '<div class="nexus-action-groups">' +
          (!attention.length && !active.length
            ? '<div class="nexus-actions-quiet"><strong>Сейчас всё спокойно</strong>' +
              '<p>Миёри не выполняет задач и не ждёт ваших решений.</p></div>'
            : group("Требуют вашего внимания",
                "Здесь можно подтвердить действия или устранить ошибку.",
                attention, "Ничего не требует решения.") +
              group("Выполняются сейчас",
                "Показываются только реальные задачи.",
                active, "Активных задач нет.")) +
          group("История действий",
            "Завершённые задачи и результаты — нажмите, чтобы посмотреть.",
            history, "Пока нет завершённых задач.", true) +
        '</div>' +
      '</section>';

    el("nexusActionsRefresh").onclick = renderNexusActionsWorkspace;
    el("nexusAgentWorkspaceOpen").onclick = renderNexusAgentWorkspace;

    const refreshActionState = async () => {
      await Promise.all([
        loadPermissions(),
        loadAudit(),
        loadTasks(),
        loadNexus()
      ]);
      await renderNexusActionsWorkspace();
    };

    workspaceBody.querySelectorAll("[data-nexus-permission]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await decidePermission(
            Number(button.dataset.nexusPermission),
            button.dataset.decision === "allow"
          );
          await refreshActionState();
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });

    workspaceBody.querySelectorAll("[data-nexus-workflow-resume]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(
            "/api/projects/" + state.projectId + "/workflows/" +
              button.dataset.nexusWorkflowResume + "/resume",
            {method: "POST"}
          );
          await refreshActionState();
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });

    workspaceBody.querySelectorAll("[data-nexus-workflow-cancel]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(
            "/api/projects/" + state.projectId + "/workflows/" +
              button.dataset.nexusWorkflowCancel + "/cancel",
            {method: "POST"}
          );
          await refreshActionState();
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });

    workspaceBody.querySelectorAll("[data-nexus-task-cancel]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(
            "/api/projects/" + state.projectId + "/tasks/" +
              button.dataset.nexusTaskCancel + "/cancel",
            {method: "POST"}
          );
          await refreshActionState();
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });

    workspaceBody.querySelectorAll("[data-nexus-recovery-check]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(
            "/api/projects/" + state.projectId + "/recovery/check",
            {method: "POST"}
          );
          await refreshActionState();
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });
  } catch (error) {
    workspaceBody.innerHTML = workspaceResult(error.message, "error");
  }
}


function nexusAgentWorkspaceStatus(value) {
  return ({
    planned: "Запланировано",
    running: "Работает",
    waiting_permission: "Ждёт разрешения",
    recovery: "Recovery",
    completed: "Завершено",
    failed: "Ошибка",
    cancelled: "Отменено",
    blocked: "Ждёт зависимостей",
    ready: "Готов к запуску"
  }[value] || value || "—");
}

function nexusAgentNodeMarkup(node) {
  const deps = Array.isArray(node.dependencies) ? node.dependencies : [];
  const result = node.result || {};
  const workflowStatus = result.workflow_status || "";
  return '<article class="agent-workspace-node status-' + escapeHtml(node.status || "blocked") + '">' +
    '<header><div><span>' + escapeHtml(node.role || "Agent") + '</span>' +
      '<strong>' + escapeHtml(node.title || node.node_key || "Node") + '</strong></div>' +
      '<b>' + escapeHtml(nexusAgentWorkspaceStatus(node.status)) + '</b></header>' +
    '<p>' + escapeHtml(node.instruction || "") + '</p>' +
    '<div class="agent-workspace-node-meta">' +
      '<span>budget ' + Number(node.step_budget || 0) + '</span>' +
      '<span>' + (node.capability === "standard" ? "standard · write через разрешение" : "read-only") + '</span>' +
      (deps.length ? '<span>после: ' + deps.map(escapeHtml).join(", ") + '</span>' : '<span>независимый старт</span>') +
      (node.workflow_id ? '<span>workflow #' + Number(node.workflow_id) + '</span>' : '') +
      (workflowStatus ? '<span>' + escapeHtml(workflowStatus) + '</span>' : '') +
    '</div>' +
    (node.error ? '<details><summary>Ошибка</summary><pre>' + nexusActionJson(node.error) + '</pre></details>' : '') +
    (node.result ? '<details><summary>Handoff / result</summary><pre>' + nexusActionJson(node.result) + '</pre></details>' : '') +
  '</article>';
}

function nexusAgentWorkspaceMarkup(workspace) {
  const nodes = Array.isArray(workspace.nodes) ? workspace.nodes : [];
  const active = ["planned", "running", "waiting_permission", "recovery"].includes(workspace.status);
  return '<article class="agent-workspace-card">' +
    '<header class="agent-workspace-card-head">' +
      '<div><span class="section-caption">Workspace #' + Number(workspace.id) + '</span>' +
        '<h4>' + escapeHtml(workspace.goal || "Agent Workspace") + '</h4>' +
        '<small>' + Number(workspace.max_parallel || 1) + ' параллельно · ' +
          Number(workspace.total_step_budget || 0) + ' шагов budget</small></div>' +
      '<span class="knowledge-status tone-' +
        (workspace.status === "failed" ? "error" :
         workspace.status === "waiting_permission" || workspace.status === "recovery" ? "warning" :
         workspace.status === "completed" ? "success" :
         workspace.status === "running" ? "working" : "neutral") + '">' +
        escapeHtml(nexusAgentWorkspaceStatus(workspace.status)) + '</span>' +
    '</header>' +
    '<div class="agent-workspace-node-grid">' + nodes.map(nexusAgentNodeMarkup).join("") + '</div>' +
    (active ? '<div class="agent-workspace-controls">' +
      '<button type="button" class="primary-sheet-button" data-agent-workspace-run="' + Number(workspace.id) + '">' +
        (workspace.status === "planned" ? "Запустить" : "Продолжить") + '</button>' +
      '<button type="button" class="secondary-sheet-button" data-agent-workspace-cancel="' + Number(workspace.id) + '">Остановить</button>' +
    '</div>' : '') +
  '</article>';
}

async function renderNexusAgentWorkspace() {
  showWorkspaceShell("actions", "", "Команда агентов", "");

  workspaceBody.innerHTML =
    '<section class="agent-workspace-page">' +
      '<header class="agent-workspace-intro">' +
        '<div><h3>Оркестрация задач</h3>' +
          '<p>Независимые узлы могут работать параллельно. Зависимости, бюджеты шагов и handoff контролируются сервером; запись требует разрешения.</p></div>' +
        '<button id="agentWorkspaceBack" class="secondary-sheet-button" type="button">← Действия</button>' +
      '</header>' +
      '<form id="agentWorkspaceCreate" class="agent-workspace-create">' +
        '<label for="agentWorkspaceGoal">Цель</label>' +
        '<div><textarea id="agentWorkspaceGoal" rows="3" maxlength="6000" placeholder="Например: проверь договор, найди риски и подготовь безопасный план действий" required></textarea>' +
        '<button class="primary-sheet-button" type="submit">Создать workspace</button></div>' +
        '<small>По умолчанию: два read-only агента параллельно → Координатор standard после handoff; write всегда через permission.</small>' +
      '</form>' +
      '<div id="agentWorkspaceStatus" class="knowledge-quiet-status" role="status" aria-live="polite"></div>' +
      '<div id="agentWorkspaceList" class="agent-workspace-list"><div class="workspace-loading">Загружаю workspace…</div></div>' +
    '</section>';

  const load = async () => {
    const list = el("agentWorkspaceList");
    const data = await api("/api/projects/" + state.projectId + "/agent-workspaces?limit=30");
    const summaries = Array.isArray(data.workspaces) ? data.workspaces : [];
    const full = [];
    for (const item of summaries) {
      try {
        const detail = await api("/api/projects/" + state.projectId + "/agent-workspaces/" + item.id);
        full.push(detail.workspace);
      } catch (_) {
        full.push(item);
      }
    }
    list.innerHTML = full.length
      ? full.map(nexusAgentWorkspaceMarkup).join("")
      : '<div class="knowledge-empty"><strong>Agent Workspace пока нет</strong><span>Создайте цель — структура появится отдельно от чата.</span></div>';

    list.querySelectorAll("[data-agent-workspace-run]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(
            "/api/projects/" + state.projectId + "/agent-workspaces/" +
              button.dataset.agentWorkspaceRun + "/run",
            {method: "POST"}
          );
          el("agentWorkspaceStatus").textContent = "Workspace передан coordinator worker.";
          await Promise.all([loadTasks(), loadNexus()]);
          await load();
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });
    list.querySelectorAll("[data-agent-workspace-cancel]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(
            "/api/projects/" + state.projectId + "/agent-workspaces/" +
              button.dataset.agentWorkspaceCancel + "/cancel",
            {method: "POST"}
          );
          await Promise.all([loadTasks(), loadNexus()]);
          await load();
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });
  };

  el("agentWorkspaceBack").onclick = renderNexusActionsWorkspace;
  el("agentWorkspaceCreate").onsubmit = async event => {
    event.preventDefault();
    const goal = el("agentWorkspaceGoal").value.trim();
    if (!goal) return;
    const submit = event.submitter;
    if (submit) submit.disabled = true;
    try {
      const created = await api("/api/projects/" + state.projectId + "/agent-workspaces", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({goal, max_parallel: 2})
      });
      el("agentWorkspaceGoal").value = "";
      el("agentWorkspaceStatus").textContent =
        "Workspace #" + created.workspace.id + " создан. Проверьте роли и запустите его.";
      await load();
    } catch (error) {
      showError(error.message);
    } finally {
      if (submit) submit.disabled = false;
    }
  };

  try {
    await load();
  } catch (error) {
    workspaceBody.innerHTML = workspaceResult(error.message, "error");
  }
}



function nexusHomeConnectivityLabel(value) {
  return ({
    unlinked: "Не привязано",
    revoked: "Привязка отозвана",
    never_seen: "Heartbeat ещё не получен",
    online: "Online",
    offline: "Offline"
  }[value] || value || "—");
}

function nexusHomeTone(value) {
  if (value === "online") return "success";
  if (value === "offline" || value === "never_seen") return "warning";
  if (value === "revoked") return "error";
  return "neutral";
}

function nexusHomeDeviceMarkup(item) {
  const connectivity = item.connectivity || {};
  const capabilities = Array.isArray(item.capabilities) ? item.capabilities : [];
  const freshness = connectivity.freshness_seconds;
  const evidence = [
    connectivity.last_seen_at ? "heartbeat " + nexusActionTime(connectivity.last_seen_at) : "heartbeat отсутствует",
    freshness !== null && freshness !== undefined ? freshness + " сек. назад" : null,
    connectivity.heartbeat_seq ? "seq " + Number(connectivity.heartbeat_seq) : null
  ].filter(Boolean).join(" · ");

  return '<article class="nexus-home-device">' +
    '<header><div><span>' + escapeHtml(item.device_type || "device") + '</span>' +
      '<strong>' + escapeHtml(item.name || "Устройство") + '</strong></div>' +
      '<b class="knowledge-status tone-' + nexusHomeTone(connectivity.state) + '">' +
        escapeHtml(nexusHomeConnectivityLabel(connectivity.state)) + '</b></header>' +
    '<div class="nexus-home-device-meta">' +
      '<span>link: ' + escapeHtml(item.link_status || "unlinked") + '</span>' +
      '<span>legacy status: ' + escapeHtml(item.declared_status || "—") + '</span>' +
      (item.address ? '<span>' + escapeHtml(item.address) + '</span>' : '') +
    '</div>' +
    '<p class="nexus-home-evidence">' + escapeHtml(evidence) + '</p>' +
    '<div class="nexus-home-capabilities">' +
      (capabilities.length
        ? capabilities.map(value => '<span>' + escapeHtml(value) + '</span>').join("")
        : '<span class="muted">capabilities ещё не подтверждены heartbeat</span>') +
    '</div>' +
    '<div class="nexus-home-controls">' +
      (item.actions?.can_link
        ? '<button type="button" class="primary-sheet-button" data-home-link="' + Number(item.id) + '">Привязать</button>'
        : '') +
      (item.actions?.can_unlink
        ? '<button type="button" class="secondary-sheet-button" data-home-unlink="' + Number(item.id) + '">Отозвать привязку</button>'
        : '') +
    '</div>' +
    '<details class="knowledge-disclosure"><summary>Runtime evidence</summary>' +
      '<div class="knowledge-disclosure-body"><pre>' +
        nexusActionJson({
          connectivity: item.connectivity,
          reported_state: item.reported_state,
          linked_at: item.linked_at
        }) +
      '</pre></div></details>' +
  '</article>';
}

function nexusHomeParentalMarkup(profile, eligibleDevices) {
  const binding = profile.binding || {};
  const labels = {
    not_bound: "Не привязано",
    device_not_linked: "Устройство не связано",
    capability_missing: "Нет parental_policy capability",
    device_offline: "Устройство offline",
    ready_for_device_agent: "Готово для device-agent"
  };
  const options = eligibleDevices.map(device =>
    '<option value="' + Number(device.id) + '">' + escapeHtml(device.name) + '</option>'
  ).join("");

  return '<article class="nexus-home-parental">' +
    '<header><div><span>' + escapeHtml(profile.status || "draft") + '</span>' +
      '<strong>' + escapeHtml(profile.child_name || "Профиль") + '</strong></div>' +
      '<b>' + escapeHtml(labels[binding.enforcement_state] || binding.enforcement_state || "—") + '</b></header>' +
    '<p>' + Number(profile.daily_limit_minutes || 0) + ' мин/день · ' +
      escapeHtml(profile.bedtime_start || "—") + '–' + escapeHtml(profile.bedtime_end || "—") + '</p>' +
    (binding.device_name
      ? '<small>Связано с: ' + escapeHtml(binding.device_name) + '</small>'
      : '<small>Правила не имеют device binding.</small>') +
    '<p class="nexus-home-evidence">' + escapeHtml(binding.note || "") + '</p>' +
    (eligibleDevices.length
      ? '<div class="nexus-home-bind-row"><select data-home-profile-device="' + Number(profile.id) + '">' +
          options + '</select><button type="button" class="secondary-sheet-button" data-home-bind-profile="' +
          Number(profile.id) + '">Привязать профиль</button></div>'
      : '<small class="nexus-home-muted">Нужен явно linked device с capability parental_policy.</small>') +
  '</article>';
}

function showNexusHomeCredential(deviceName, credential) {
  const host = el("nexusHomeCredential");
  if (!host) return;
  host.replaceChildren();
  host.hidden = false;

  const title = document.createElement("strong");
  title.textContent = "Heartbeat credential · " + deviceName;
  const note = document.createElement("p");
  note.textContent = "Показывается один раз. Передайте его доверенному device-agent; Miyori хранит только SHA-256.";
  const code = document.createElement("code");
  code.textContent = credential;
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "secondary-sheet-button";
  copy.textContent = "Копировать";
  copy.onclick = async () => {
    try {
      await navigator.clipboard.writeText(credential);
      copy.textContent = "Скопировано";
    } catch (_) {
      copy.textContent = "Скопируйте вручную";
    }
  };
  host.append(title, note, code, copy);
}

async function renderNexusHomeWorkspace() {
  showWorkspaceShell("home", "", "Дом", "");

  workspaceBody.innerHTML =
    '<section class="nexus-home-page">' +
      '<header class="nexus-home-intro"><div><h3>Устройства и связи</h3>' +
        '<p>Online определяется только свежим authenticated heartbeat. Legacy status и адрес устройства не являются доказательством связи.</p></div>' +
        '<button id="nexusHomeRefresh" class="secondary-sheet-button" type="button">Обновить</button>' +
      '</header>' +
      '<div id="nexusHomeCredential" class="nexus-home-credential" hidden></div>' +
      '<div id="nexusHomeBody"><div class="workspace-loading">Загружаю Home…</div></div>' +
    '</section>';

  const load = async () => {
    const page = await api("/api/projects/" + state.projectId + "/nexus/home");
    const body = el("nexusHomeBody");
    if (!page.enabled) {
      body.innerHTML =
        '<div class="knowledge-empty"><strong>Home отключён для рабочего проекта</strong>' +
        '<span>Переключитесь на домашний проект. Устройства рабочего проекта не получают Home capability автоматически.</span>' +
        '<button id="nexusHomeProjects" type="button" class="primary-sheet-button">Домашние проекты</button></div>';
      el("nexusHomeProjects").onclick = () => renderProjectsWorkspace("home");
      return;
    }

    const counts = page.counts || {};
    const devices = Array.isArray(page.devices) ? page.devices : [];
    const profiles = Array.isArray(page.parental_profiles) ? page.parental_profiles : [];
    const eligibleDevices = devices.filter(item =>
      item.link_status === "linked" &&
      Array.isArray(item.capabilities) &&
      item.capabilities.includes("parental_policy")
    );

    const metric = (label, value, note, tone = "neutral") =>
      '<div class="nexus-action-metric tone-' + tone + '"><span>' + escapeHtml(label) +
      '</span><strong>' + Number(value || 0) + '</strong><small>' + escapeHtml(note) + '</small></div>';

    body.innerHTML =
      '<div class="nexus-action-metrics nexus-home-metrics">' +
        metric("Online", counts.online, "authenticated heartbeat", counts.online ? "success" : "neutral") +
        metric("Linked", counts.linked, "explicit identity binding") +
        metric("Offline / unseen", counts.offline_or_unseen, "по TTL evidence", counts.offline_or_unseen ? "warning" : "neutral") +
        metric("Parental attention", counts.parental_attention, "не выдаём правила за applied", counts.parental_attention ? "warning" : "neutral") +
      '</div>' +
      '<section class="nexus-home-policy"><strong>Контракт Home</strong>' +
        '<span>Heartbeat TTL: ' + Number(page.policy?.heartbeat_ttl_seconds || 0) + ' сек.</span>' +
        '<span>Network scanning: отключён</span><span>Device commands: отключены</span></section>' +
      '<section class="nexus-home-section"><header><div><strong>Устройства</strong>' +
        '<small>Inventory отделён от runtime evidence.</small></div><span>' + devices.length + '</span></header>' +
        '<div class="nexus-home-device-list">' +
          (devices.length ? devices.map(nexusHomeDeviceMarkup).join("") :
            '<div class="knowledge-empty"><strong>Устройств нет</strong><span>Добавьте устройство через существующий Home inventory API/раздел.</span></div>') +
        '</div></section>' +
      '<section class="nexus-home-section"><header><div><strong>Parental bindings</strong>' +
        '<small>Binding не означает OS-level enforcement.</small></div><span>' + profiles.length + '</span></header>' +
        '<div class="nexus-home-parental-list">' +
          (profiles.length ? profiles.map(item => nexusHomeParentalMarkup(item, eligibleDevices)).join("") :
            '<div class="knowledge-empty"><strong>Профилей нет</strong><span>Существующий parental-control CRUD сохранён.</span></div>') +
        '</div></section>';

    body.querySelectorAll("[data-home-link]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          const deviceId = Number(button.dataset.homeLink);
          const result = await api(
            "/api/projects/" + state.projectId + "/nexus/home/devices/" + deviceId + "/link",
            {
              method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({capabilities: []})
            }
          );
          const device = devices.find(item => Number(item.id) === deviceId);
          await load();
          showNexusHomeCredential(device?.name || ("Device #" + deviceId), result.credential);
          await loadNexus();
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });

    body.querySelectorAll("[data-home-unlink]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(
            "/api/projects/" + state.projectId + "/nexus/home/devices/" +
              button.dataset.homeUnlink + "/unlink",
            {method: "POST"}
          );
          await Promise.all([load(), loadNexus()]);
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });

    body.querySelectorAll("[data-home-bind-profile]").forEach(button => {
      button.onclick = async () => {
        const profileId = Number(button.dataset.homeBindProfile);
        const select = body.querySelector('[data-home-profile-device="' + profileId + '"]');
        const deviceId = Number(select?.value || 0);
        if (!deviceId) return;
        button.disabled = true;
        try {
          await api(
            "/api/projects/" + state.projectId + "/nexus/home/parental/" + profileId + "/bind",
            {
              method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({device_id: deviceId})
            }
          );
          await Promise.all([load(), loadNexus()]);
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });
  };

  el("nexusHomeRefresh").onclick = async () => {
    try {
      await Promise.all([load(), loadNexus()]);
    } catch (error) {
      showError(error.message);
    }
  };

  try {
    await load();
  } catch (error) {
    el("nexusHomeBody").innerHTML = workspaceResult(error.message, "error");
  }
}

function nexusKnowledgePercent(value) {
  const numeric = Number(value || 0);
  return Math.max(0, Math.min(100, Math.round(numeric * 100)));
}

function nexusKnowledgeStatusLabel(value) {
  return ({
    verified: "Подтверждено",
    candidate: "Нужно проверить",
    disputed: "Есть спор",
    superseded: "Заменено",
    supported: "Поддержано",
    rejected: "Отклонено",
    complete: "Готово",
    partial: "Частично",
    indexed: "Структура готова",
    queued: "В очереди",
    analyzing: "Анализируется",
    needs_ocr: "Нужен OCR",
    unsupported: "Только оригинал",
    failed: "Ошибка",
    not_indexed: "Не проиндексировано",
    unknown: "Неизвестно"
  }[value] || value || "—");
}

function nexusKnowledgeTone(value) {
  if (["verified", "complete"].includes(value)) return "success";
  if (["supported", "indexed", "queued", "analyzing"].includes(value)) return "working";
  if (["candidate", "partial", "needs_ocr", "unknown"].includes(value)) return "warning";
  if (["disputed", "rejected", "failed", "unsupported"].includes(value)) return "error";
  return "neutral";
}

function nexusKnowledgeTime(value) {
  return nexusActionTime(value);
}

function nexusKnowledgeProvenanceMarkup(provenance) {
  const data = provenance || {};
  const rows = [
    ["Источник", data.source_kind],
    ["Проект происхождения", data.origin_project_name],
    ["Conversation", data.conversation_id],
    ["Message", data.message_id],
    ["Locator", data.locator],
    ["SHA-256", data.sha256]
  ].filter(row => row[1] !== null && row[1] !== undefined && row[1] !== "");
  if (!rows.length) return '<p class="knowledge-muted">Provenance пока не записан.</p>';
  return '<dl class="knowledge-provenance">' +
    rows.map(row =>
      '<div><dt>' + escapeHtml(String(row[0])) + '</dt><dd>' +
      escapeHtml(String(row[1])) + '</dd></div>'
    ).join("") +
  '</dl>';
}

function nexusKnowledgeMemoryMarkup(item) {
  const conflicts = Array.isArray(item.possible_conflict_ids)
    ? item.possible_conflict_ids
    : [];
  const meta = [
    item.scope === "user" ? "Личная память" : "Память проекта",
    item.kind,
    item.observed_at ? nexusKnowledgeTime(item.observed_at) : null
  ].filter(Boolean).join(" · ");

  const actions = [];
  if (item.actions?.verify) {
    actions.push(
      '<button type="button" class="knowledge-action-button" data-knowledge-memory="' +
      item.id + '" data-memory-project="' + Number(item.actions?.project_id || 0) +
      '" data-memory-status="verified">Подтвердить</button>'
    );
  }
  if (item.actions?.dispute) {
    actions.push(
      '<button type="button" class="knowledge-action-button quiet" data-knowledge-memory="' +
      item.id + '" data-memory-project="' + Number(item.actions?.project_id || 0) +
      '" data-memory-status="disputed">Оспорить</button>'
    );
  }

  return '<article class="knowledge-item knowledge-memory-item">' +
    '<div class="knowledge-item-main">' +
      '<div class="knowledge-item-copy"><strong>' + escapeHtml(item.statement || "") + '</strong>' +
      '<small>' + escapeHtml(meta) + '</small></div>' +
      '<span class="knowledge-status tone-' + nexusKnowledgeTone(item.status) + '">' +
        escapeHtml(nexusKnowledgeStatusLabel(item.status)) + '</span>' +
    '</div>' +
    (actions.length ? '<div class="knowledge-inline-actions">' + actions.join("") + '</div>' : '') +
    '<details class="knowledge-disclosure">' +
      '<summary>Происхождение и состояние</summary>' +
      '<div class="knowledge-disclosure-body">' +
        nexusKnowledgeProvenanceMarkup(item.provenance) +
        '<div class="knowledge-facts-grid">' +
          '<div><span>Confidence</span><strong>' +
            escapeHtml(item.confidence === null || item.confidence === undefined ? "—" : Math.round(Number(item.confidence) * 100) + "%") +
          '</strong></div>' +
          '<div><span>Salience</span><strong>' +
            escapeHtml(Math.round(Number(item.salience || 0) * 100) + "%") +
          '</strong></div>' +
          '<div><span>Метод проверки</span><strong>' +
            escapeHtml(item.verification_method || "—") +
          '</strong></div>' +
          '<div><span>Возможные конфликты</span><strong>' + conflicts.length + '</strong></div>' +
        '</div>' +
        (conflicts.length
          ? '<p class="knowledge-attention-note">Возможные связанные конфликты: #' +
            conflicts.map(value => escapeHtml(String(value))).join(", #") + '</p>'
          : '') +
      '</div>' +
    '</details>' +
  '</article>';
}

function nexusKnowledgeDocumentMarkup(item) {
  const intel = item.intelligence || {};
  const exhaustive = item.exhaustive || {};
  const extraction = nexusKnowledgePercent(intel.extraction_coverage);
  const understanding = nexusKnowledgePercent(intel.coverage);
  const exhaustiveCoverage = nexusKnowledgePercent(exhaustive.best_coverage);
  const warnings = Array.isArray(intel.warnings) ? intel.warnings : [];
  const status = intel.status || "not_indexed";
  const meta = [
    item.folder_name || "Мои файлы",
    item.mime_type || "файл",
    item.index?.chunks ? item.index.chunks + " фрагментов" : null,
    item.created_at ? nexusKnowledgeTime(item.created_at) : null
  ].filter(Boolean).join(" · ");

  const actions = [];
  if (item.actions?.analyze && !["queued", "analyzing"].includes(status)) {
    actions.push(
      '<button type="button" class="knowledge-action-button" data-knowledge-analyze="' +
      item.id + '">Глубокий анализ</button>'
    );
  }

  return '<article class="knowledge-item knowledge-document-item">' +
    '<div class="knowledge-item-main">' +
      '<div class="knowledge-item-copy"><strong>' + escapeHtml(item.filename || "Документ") + '</strong>' +
        '<small>' + escapeHtml(meta) + '</small>' +
        (intel.summary ? '<p>' + escapeHtml(intel.summary) + '</p>' : '') +
      '</div>' +
      '<span class="knowledge-status tone-' + nexusKnowledgeTone(status) + '">' +
        escapeHtml(nexusKnowledgeStatusLabel(status)) + '</span>' +
    '</div>' +
    '<div class="knowledge-coverage-pair">' +
      '<div class="knowledge-coverage">' +
        '<div><span>Извлечение оригинала</span><strong>' + extraction + '%</strong></div>' +
        '<progress max="100" value="' + extraction + '" aria-label="Покрытие извлечения ' + extraction + '%"></progress>' +
      '</div>' +
      '<div class="knowledge-coverage">' +
        '<div><span>Понимание документа</span><strong>' + understanding + '%</strong></div>' +
        '<progress max="100" value="' + understanding + '" aria-label="Покрытие понимания ' + understanding + '%"></progress>' +
      '</div>' +
    '</div>' +
    (actions.length ? '<div class="knowledge-inline-actions">' + actions.join("") + '</div>' : '') +
    '<details class="knowledge-disclosure">' +
      '<summary>Coverage, provenance и exhaustive verification</summary>' +
      '<div class="knowledge-disclosure-body">' +
        '<div class="knowledge-facts-grid">' +
          '<div><span>Страниц</span><strong>' + Number(intel.page_count || 0) + '</strong></div>' +
          '<div><span>Разделов</span><strong>' + Number(intel.section_count || 0) + '</strong></div>' +
          '<div><span>Структурных узлов</span><strong>' + Number(item.index?.nodes || 0) + '</strong></div>' +
          '<div><span>Exhaustive Q&A</span><strong>' + Number(exhaustive.complete || 0) + ' / ' + Number(exhaustive.questions || 0) + '</strong></div>' +
          '<div><span>Лучшее exhaustive coverage</span><strong>' + exhaustiveCoverage + '%</strong></div>' +
          '<div><span>Parser</span><strong>' + escapeHtml(item.index?.parser_version || "—") + '</strong></div>' +
        '</div>' +
        nexusKnowledgeProvenanceMarkup(item.provenance) +
        (warnings.length
          ? '<div class="knowledge-warning-list"><strong>Ограничения извлечения</strong><ul>' +
            warnings.map(warning => '<li>' + escapeHtml(String(warning)) + '</li>').join("") +
            '</ul></div>'
          : '') +
        (intel.last_error
          ? '<p class="knowledge-error-note">' + escapeHtml(intel.last_error) + '</p>'
          : '') +
        '<div class="knowledge-inline-actions nested">' +
          '<button type="button" class="knowledge-action-button quiet" data-knowledge-rebuild="' +
            item.id + '">Перестроить структуру</button>' +
        '</div>' +
      '</div>' +
    '</details>' +
  '</article>';
}

function nexusKnowledgeClaimMarkup(item) {
  const evidence = Array.isArray(item.evidence_preview) ? item.evidence_preview : [];
  const meta = [
    item.claim_type,
    item.independent_sources + " независимых источников",
    item.evidence_count + " evidence",
    item.updated_at ? nexusKnowledgeTime(item.updated_at) : null
  ].filter(Boolean).join(" · ");

  return '<article class="knowledge-item knowledge-claim-item">' +
    '<div class="knowledge-item-main">' +
      '<div class="knowledge-item-copy"><strong>' + escapeHtml(item.statement || "") + '</strong>' +
      '<small>' + escapeHtml(meta) + '</small></div>' +
      '<span class="knowledge-status tone-' + nexusKnowledgeTone(item.status) + '">' +
        escapeHtml(item.assessment || nexusKnowledgeStatusLabel(item.status)) + '</span>' +
    '</div>' +
    '<div class="knowledge-claim-score">' +
      '<span>Confidence</span><strong>' + Math.round(Number(item.confidence || 0) * 100) + '%</strong>' +
      '<span>Поддержка</span><strong>' + Number(item.supports || 0) + '</strong>' +
      '<span>Противоречия</span><strong>' + Number(item.contradictions || 0) + '</strong>' +
    '</div>' +
    (item.can_verify
      ? '<div class="knowledge-inline-actions"><button type="button" class="knowledge-action-button" data-knowledge-verify="' +
        item.id + '">Перепроверить evidence</button></div>'
      : '') +
    '<details class="knowledge-disclosure">' +
      '<summary>Evidence и источники</summary>' +
      '<div class="knowledge-disclosure-body">' +
        (evidence.length
          ? '<div class="knowledge-evidence-list">' + evidence.map(ev => {
              const source = ev.source || {};
              return '<article class="knowledge-evidence stance-' + escapeHtml(ev.stance || "neutral") + '">' +
                '<div><span>' + escapeHtml(ev.stance === "supports" ? "Поддерживает" : ev.stance === "contradicts" ? "Противоречит" : "Нейтрально") + '</span>' +
                '<strong>' + escapeHtml(source.title || source.type || "Источник") + '</strong></div>' +
                (ev.excerpt ? '<p>' + escapeHtml(ev.excerpt) + '</p>' : '') +
                '<small>' +
                  escapeHtml([
                    source.type,
                    source.publisher,
                    source.locator,
                    source.quality !== null && source.quality !== undefined
                      ? "quality " + Math.round(Number(source.quality) * 100) + "%"
                      : null
                  ].filter(Boolean).join(" · ")) +
                '</small>' +
              '</article>';
            }).join("") + '</div>'
          : '<p class="knowledge-muted">Evidence пока не записан.</p>') +
        (Number(item.open_contradictions || 0) > 0
          ? '<p class="knowledge-attention-note">Открытых противоречий: ' +
            Number(item.open_contradictions || 0) + '</p>'
          : '') +
      '</div>' +
    '</details>' +
  '</article>';
}

async function renderNexusKnowledgeWorkspace() {
  showWorkspaceShell("knowledge", "", "Знания", "");

  workspaceBody.innerHTML =
    '<section class="nexus-knowledge">' +
      '<header class="knowledge-head">' +
        '<div><h3>Карта знаний проекта</h3>' +
          '<p>Память, документы и проверенные знания показаны рядом, но не смешиваются. Детали источников раскрываются по запросу.</p></div>' +
        '<button id="knowledgeOpenDrive" class="secondary-sheet-button" type="button">Открыть файлы</button>' +
      '</header>' +
      '<form id="knowledgeSearchForm" class="knowledge-search" role="search">' +
        '<label for="knowledgeSearchInput">Поиск по знаниям</label>' +
        '<div><input id="knowledgeSearchInput" type="search" autocomplete="off" placeholder="Факт, документ, источник или утверждение…">' +
        '<button class="primary-sheet-button" type="submit">Найти</button>' +
        '<button id="knowledgeSearchClear" class="secondary-sheet-button" type="button" hidden>Сбросить</button></div>' +
      '</form>' +
      '<div id="knowledgeQuietStatus" class="knowledge-quiet-status" role="status" aria-live="polite"></div>' +
      '<div id="knowledgeTabs" class="knowledge-tabs" role="tablist" aria-label="Разделы Knowledge">' +
        '<button id="knowledgeTabOverview" role="tab" aria-selected="true" tabindex="0" data-knowledge-tab="overview" type="button">Обзор <span id="knowledgeTabOverviewCount"></span></button>' +
        '<button id="knowledgeTabMemory" role="tab" aria-selected="false" tabindex="-1" data-knowledge-tab="memory" type="button">Память <span id="knowledgeTabMemoryCount"></span></button>' +
        '<button id="knowledgeTabDocuments" role="tab" aria-selected="false" tabindex="-1" data-knowledge-tab="documents" type="button">Документы <span id="knowledgeTabDocumentsCount"></span></button>' +
        '<button id="knowledgeTabClaims" role="tab" aria-selected="false" tabindex="-1" data-knowledge-tab="claims" type="button">Проверенные знания <span id="knowledgeTabClaimsCount"></span></button>' +
      '</div>' +
      '<section id="knowledgePanel" class="knowledge-panel" role="tabpanel" tabindex="0" aria-labelledby="knowledgeTabOverview">' +
        '<div class="workspace-loading">Загружаю Knowledge…</div>' +
      '</section>' +
    '</section>';

  let center = null;
  let activeTab = "overview";
  let currentQuery = "";

  const tabId = tab => ({
    overview: "knowledgeTabOverview",
    memory: "knowledgeTabMemory",
    documents: "knowledgeTabDocuments",
    claims: "knowledgeTabClaims"
  }[tab]);

  const renderOverview = () => {
    const memory = center?.counts?.memory || {};
    const documents = center?.counts?.documents || {};
    const claims = center?.counts?.claims || {};
    const attention = center?.counts?.attention || {};
    const resultCounts = center?.results || {};
    const queryNotice = currentQuery
      ? '<div class="knowledge-query-summary"><strong>Поиск: «' + escapeHtml(currentQuery) + '»</strong>' +
        '<span>Память ' + Number(resultCounts.memory || 0) + ' · документы ' +
        Number(resultCounts.documents || 0) + ' · утверждения ' + Number(resultCounts.claims || 0) + '</span></div>'
      : "";

    const domainCard = (tab, title, note, value, sub, attentionCount) =>
      '<button type="button" class="knowledge-domain-card" data-knowledge-open="' + tab + '">' +
        '<span>' + escapeHtml(title) + '</span><strong>' + escapeHtml(String(value)) + '</strong>' +
        '<small>' + escapeHtml(note) + '</small>' +
        '<em>' + escapeHtml(sub) + '</em>' +
        (attentionCount > 0 ? '<b>' + attentionCount + ' проверить</b>' : '') +
      '</button>';

    const attentionItems = [
      [attention.memory_disputed, "Спорные записи памяти"],
      [attention.memory_conflicts, "Возможные конфликты памяти"],
      [attention.documents_limited, "Документы с ограниченным извлечением"],
      [attention.claim_disputed, "Спорные утверждения"],
      [attention.claim_open_contradictions, "Открытые противоречия evidence"]
    ].filter(item => Number(item[0] || 0) > 0);

    return queryNotice +
      '<div class="knowledge-domain-grid">' +
        domainCard(
          "memory",
          "Память",
          "Контекст, предпочтения, процессы и ограничения",
          memory.visible || 0,
          (memory.verified || 0) + " подтверждено",
          Number(attention.memory_disputed || 0) + Number(attention.memory_conflicts || 0)
        ) +
        domainCard(
          "documents",
          "Документы",
          "Оригиналы, структура, extraction и coverage",
          documents.total || 0,
          nexusKnowledgePercent(documents.average_extraction_coverage) + "% извлечено",
          Number(attention.documents_limited || 0)
        ) +
        domainCard(
          "claims",
          "Проверенные знания",
          "Утверждения с evidence и противоречиями",
          claims.total || 0,
          (claims.verified || 0) + " подтверждено",
          Number(attention.claim_disputed || 0) + Number(attention.claim_open_contradictions || 0)
        ) +
      '</div>' +
      (attentionItems.length
        ? '<section class="knowledge-attention"><header><strong>Нужно проверить</strong><span>' +
          Number(attention.total || 0) + '</span></header><ul>' +
          attentionItems.map(item =>
            '<li><span>' + escapeHtml(item[1]) + '</span><strong>' + Number(item[0]) + '</strong></li>'
          ).join("") + '</ul></section>'
        : '<div class="knowledge-calm-state"><strong>Критичных конфликтов не видно</strong><span>Подробности остаются внутри соответствующих разделов.</span></div>') +
      '<details class="knowledge-principles">' +
        '<summary>Как NEXUS различает источники</summary>' +
        '<div><p><strong>Память</strong> — сохранённый контекст и пользовательские/проектные факты.</p>' +
        '<p><strong>Документы</strong> — оригинальные материалы и измеримое покрытие их извлечения/анализа.</p>' +
        '<p><strong>Проверенные знания</strong> — отдельные утверждения, чей статус определяется evidence, а не уверенностью модели.</p>' +
        '<p>Эти слои связаны навигацией, но не сливаются в одну сущность.</p></div>' +
      '</details>';
  };

  const renderList = (items, renderer, emptyTitle) =>
    items.length
      ? '<div class="knowledge-list">' + items.map(renderer).join("") + '</div>'
      : '<div class="knowledge-empty"><strong>' + escapeHtml(emptyTitle) + '</strong>' +
        '<span>' + (currentQuery ? 'Попробуйте другой запрос.' : 'Данные появятся после работы с проектом.') + '</span></div>';

  const bindActions = () => {
    workspaceBody.querySelectorAll("[data-knowledge-memory]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(
            "/api/projects/" + Number(button.dataset.memoryProject || state.projectId) +
              "/memory/" + button.dataset.knowledgeMemory,
            {
              method: "PATCH",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({status: button.dataset.memoryStatus})
            }
          );
          await Promise.all([loadAudit(), loadNexus()]);
          await loadKnowledge(currentQuery, false);
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });

    workspaceBody.querySelectorAll("[data-knowledge-verify]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(
            "/api/projects/" + state.projectId + "/epistemic/claims/" +
              button.dataset.knowledgeVerify + "/verify",
            {method: "POST"}
          );
          await loadKnowledge(currentQuery, false);
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });

    workspaceBody.querySelectorAll("[data-knowledge-analyze]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(
            "/api/projects/" + state.projectId + "/documents/" +
              button.dataset.knowledgeAnalyze + "/intelligence/analyze",
            {
              method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({force: false})
            }
          );
          await Promise.all([loadTasks(), loadNexus()]);
          await loadKnowledge(currentQuery, false);
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });

    workspaceBody.querySelectorAll("[data-knowledge-rebuild]").forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(
            "/api/projects/" + state.projectId + "/documents/" +
              button.dataset.knowledgeRebuild + "/intelligence/rebuild",
            {method: "POST"}
          );
          await loadKnowledge(currentQuery, false);
        } catch (error) {
          showError(error.message);
          button.disabled = false;
        }
      };
    });

    workspaceBody.querySelectorAll("[data-knowledge-open]").forEach(button => {
      button.onclick = () => setActiveTab(button.dataset.knowledgeOpen);
    });
  };

  const renderPanel = () => {
    const panel = el("knowledgePanel");
    if (!center) {
      panel.innerHTML = '<div class="workspace-loading">Загружаю Knowledge…</div>';
      return;
    }
    if (activeTab === "memory") {
      panel.innerHTML = renderList(center.memory || [], nexusKnowledgeMemoryMarkup, "Память пока пуста");
    } else if (activeTab === "documents") {
      panel.innerHTML = renderList(center.documents || [], nexusKnowledgeDocumentMarkup, "Документов пока нет");
    } else if (activeTab === "claims") {
      panel.innerHTML = renderList(center.claims || [], nexusKnowledgeClaimMarkup, "Проверяемых утверждений пока нет");
    } else {
      panel.innerHTML = renderOverview();
    }
    bindActions();
  };

  const setActiveTab = tab => {
    if (!["overview", "memory", "documents", "claims"].includes(tab)) return;
    activeTab = tab;
    workspaceBody.querySelectorAll("[data-knowledge-tab]").forEach(button => {
      const selected = button.dataset.knowledgeTab === activeTab;
      button.setAttribute("aria-selected", selected ? "true" : "false");
      button.tabIndex = selected ? 0 : -1;
    });
    const panel = el("knowledgePanel");
    panel.setAttribute("aria-labelledby", tabId(activeTab));
    renderPanel();
  };

  const updateCounts = () => {
    const memory = center?.counts?.memory || {};
    const documents = center?.counts?.documents || {};
    const claims = center?.counts?.claims || {};
    const attention = center?.counts?.attention || {};
    el("knowledgeTabOverviewCount").textContent = Number(attention.total || 0)
      ? String(attention.total)
      : "";
    el("knowledgeTabMemoryCount").textContent = String(memory.visible || 0);
    el("knowledgeTabDocumentsCount").textContent = String(documents.total || 0);
    el("knowledgeTabClaimsCount").textContent = String(claims.total || 0);
  };

  const loadKnowledge = async (query = "", announce = true) => {
    const statusNode = el("knowledgeQuietStatus");
    if (announce) statusNode.textContent = query ? "Ищу по трём независимым слоям…" : "Обновляю Knowledge…";
    try {
      const params = new URLSearchParams({limit: "80"});
      if (query) params.set("q", query);
      center = await api(
        "/api/projects/" + state.projectId + "/nexus/knowledge?" + params.toString()
      );
      currentQuery = center.query || query || "";
      el("knowledgeSearchInput").value = currentQuery;
      el("knowledgeSearchClear").hidden = !currentQuery;
      updateCounts();
      renderPanel();
      statusNode.textContent = currentQuery
        ? "Результаты разделены по источникам: память, документы, утверждения."
        : "Knowledge синхронизирован.";
    } catch (error) {
      statusNode.textContent = "";
      el("knowledgePanel").innerHTML = workspaceResult(error.message, "error");
    }
  };

  workspaceBody.querySelectorAll("[data-knowledge-tab]").forEach(button => {
    button.onclick = () => setActiveTab(button.dataset.knowledgeTab);
  });

  el("knowledgeTabs").onkeydown = event => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const buttons = [...workspaceBody.querySelectorAll("[data-knowledge-tab]")];
    const current = buttons.indexOf(document.activeElement);
    if (current < 0) return;
    event.preventDefault();
    let next = current;
    if (event.key === "Home") next = 0;
    else if (event.key === "End") next = buttons.length - 1;
    else if (event.key === "ArrowRight") next = (current + 1) % buttons.length;
    else next = (current - 1 + buttons.length) % buttons.length;
    buttons[next].focus();
    setActiveTab(buttons[next].dataset.knowledgeTab);
  };

  el("knowledgeSearchForm").onsubmit = async event => {
    event.preventDefault();
    const query = el("knowledgeSearchInput").value.trim();
    await loadKnowledge(query);
  };

  el("knowledgeSearchClear").onclick = async () => {
    el("knowledgeSearchInput").value = "";
    await loadKnowledge("");
  };

  el("knowledgeOpenDrive").onclick = () => renderDocumentsWorkspace();

  await loadKnowledge("");
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


if (nexusNavChat) nexusNavChat.onclick = showChatWorkspace;
if (nexusNavActions) nexusNavActions.onclick = renderNexusActionsWorkspace;
if (nexusNavKnowledge) nexusNavKnowledge.onclick = renderNexusKnowledgeWorkspace;
if (nexusNavHome) nexusNavHome.onclick = renderNexusHomeWorkspace;
if (nexusNavSystem) nexusNavSystem.onclick = () => renderSettingsWorkspace();
