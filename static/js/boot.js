function renderMobileWorkspace() {
  showWorkspaceShell("mobile", "Клиенты", "Мобильное приложение", "Отдельная рабочая область будущего iOS / Android клиента.");
  workspaceBody.innerHTML =
    '<div class="workspace-grid">' +
      '<section class="workspace-card workspace-card-wide"><div class="workspace-hero-icon">▣</div>' +
      '<strong>Мобильная Miyori</strong><p>Этот раздел вынесен из чата. Здесь будут привязка устройства, QR-код, push-уведомления и синхронизация мобильного клиента.</p>' +
      workspaceResult("Мобильный клиент ещё не реализован.", "neutral") + '</section>' +
    '</div>';
}

if (menuMiyoriAI) menuMiyoriAI.onclick = renderMiyoriAiWorkspace;
if (el("workspaceBackToChat")) el("workspaceBackToChat").onclick = showChatWorkspace;
if (menuAccount) menuAccount.onclick = renderAccountWorkspace;
if (menuProjectUpdate) menuProjectUpdate.onclick = () => renderUpdateWorkspace(false);
if (menuSettings) menuSettings.onclick = renderSettingsWorkspace;
if (menuMobileApp) menuMobileApp.onclick = renderMobileWorkspace;
if (menuDocumentsHub) menuDocumentsHub.onclick = renderDocumentsWorkspace;
if (menuWorkProjects) menuWorkProjects.onclick = () => renderProjectsWorkspace("work");
if (menuHomeProjects) menuHomeProjects.onclick = () => renderProjectsWorkspace("home");

const systemStatusOverlay = el("systemStatusOverlay");
const openSystemStatus = el("openSystemStatus");
const closeSystemStatus = el("closeSystemStatus");

function openSystemStatusModal() {
  if (!systemStatusOverlay) return;
  systemStatusOverlay.hidden = false;
  document.body.classList.add("sheet-open");
  loadStatus();
  if (state.projectId) loadNexus();
}

function closeSystemStatusModal() {
  if (!systemStatusOverlay) return;
  systemStatusOverlay.hidden = true;
  document.body.classList.remove("sheet-open");
}

if (openSystemStatus) openSystemStatus.onclick = openSystemStatusModal;
if (closeSystemStatus) closeSystemStatus.onclick = closeSystemStatusModal;
if (systemStatusOverlay) {
  systemStatusOverlay.addEventListener("click", (event) => {
    if (event.target === systemStatusOverlay) closeSystemStatusModal();
  });
}

async function loadModuleVersions() {
  try {
    const manifest = await api("/api/modules");
    const versions = new Map((manifest.modules || []).map(item => [item.key, item]));
    state.moduleVersions = Object.fromEntries(versions);
    const mapping = [
      [menuMiyoriAI, "miyori_ai"],
      [menuMobileApp, "mobile"],
      [menuAccount, "account"],
      [menuSettings, "settings"],
      [menuDocumentsHub, "drive"],
      [menuWorkProjects, "projects"],
      [menuHomeProjects, "projects"],
      [menuProjectUpdate, "updater"]
    ];
    for (const [button, key] of mapping) {
      if (!button) continue;
      const module = versions.get(key);
      if (!module) continue;
      let badge = button.querySelector(".module-version-badge");
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "module-version-badge";
        button.appendChild(badge);
      }
      badge.textContent = "v" + module.version;
      badge.title = module.description + " · " + module.status;
    }
  } catch (_) {
    // Version badges are informative; navigation must still work without them.
  }
}

async function applyStartupPreferences() {
  try {
    const data = await api("/api/settings");
    const general = data.settings?.general || {};
    applyInterfaceSettings(general);
    const screen = general.startup_screen || "chat";
    if (screen === "ai") await renderMiyoriAiWorkspace();
    else if (screen === "account") await renderAccountWorkspace();
    else if (screen === "drive") await renderDocumentsWorkspace();
    else if (screen === "settings") await renderSettingsWorkspace();
    else showChatWorkspace();
  } catch (_) {
    showChatWorkspace();
  }
}

async function boot() {
  showWelcome();
  showChatWorkspace();
  await loadStatus();
  await loadModuleVersions();
  try { await loadProjects(); } catch (error) { showError(error.message); }
  await applyStartupPreferences();
  input.focus();
}
boot();


function activateInspectorTab(name) {
  document.querySelectorAll(".inspector-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });
  document.querySelectorAll(".inspector-page").forEach((page) => {
    page.classList.toggle("active", page.dataset.page === name);
  });
}

document.querySelectorAll(".inspector-tab").forEach((button) => {
  button.addEventListener("click", () => activateInspectorTab(button.dataset.tab));
});

if (consoleHeader) {
  consoleHeader.addEventListener("click", toggleConsoleState);
}
if (toggleConsole) {
  toggleConsole.addEventListener("click", () => {
    toggleConsoleState();
    input.focus();
  });
}
