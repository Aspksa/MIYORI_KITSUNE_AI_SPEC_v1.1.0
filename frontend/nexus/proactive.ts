import {
  dismissNexusProactive,
  fetchNexusProactive,
  snoozeNexusProactive,
} from "./client.js";
import type {
  NexusProactivePage,
  NexusProactiveSignal,
  NexusSnapshot,
} from "./contracts.js";

type PageHandler = (page: NexusProactivePage) => void;

function currentProjectId(): number | null {
  const select = document.getElementById("projectSelect") as HTMLSelectElement | null;
  const value = Number(select?.value);
  return Number.isInteger(value) && value > 0 ? value : null;
}

function currentView(): string {
  return String(document.documentElement.dataset.nexusView || "chat");
}

function navigate(target: NexusProactiveSignal["destination"]): void {
  const id =
    target === "actions"
      ? "nexusNavActions"
      : target === "knowledge"
        ? "nexusNavKnowledge"
        : "nexusNavSystem";
  const button = document.getElementById(id) as HTMLButtonElement | null;
  button?.click();
}

function openLabel(target: NexusProactiveSignal["destination"]): string {
  return target === "actions"
    ? "Открыть действия"
    : target === "knowledge"
      ? "Открыть знания"
      : "Открыть систему";
}

function setVisibilityState(visible: boolean): void {
  document.documentElement.dataset.nexusProactiveVisible = visible ? "true" : "false";
  window.dispatchEvent(
    new CustomEvent("miyori:proactive-visibility", {
      detail: { visible },
    }),
  );
}

function severityLabel(severity: NexusProactiveSignal["severity"]): string {
  return severity === "high"
    ? "важно"
    : severity === "normal"
      ? "проверить"
      : "когда удобно";
}

function shelfSignals(page: NexusProactivePage): NexusProactiveSignal[] {
  const allowed = new Set(page.display.chat_shelf_ids);
  return page.signals.filter(
    (signal) =>
      allowed.has(signal.id) &&
      signal.channel_owner === "attention_shelf" &&
      signal.safety?.executes_action === false &&
      signal.safety?.changes_domain_state === false &&
      signal.safety?.requires_existing_permission_flow === true,
  );
}

export function renderNexusProactivePage(
  host: HTMLElement,
  page: NexusProactivePage,
  onPage?: PageHandler,
): void {
  const previous = host.querySelector("details");
  const wasOpen = previous instanceof HTMLDetailsElement && previous.open;
  host.replaceChildren();

  const signals = currentView() === "chat" ? shelfSignals(page) : [];
  if (!signals.length) {
    host.hidden = true;
    setVisibilityState(false);
    return;
  }

  setVisibilityState(true);

  const details = document.createElement("details");
  details.className = "nexus-proactive-shelf";
  details.open = wasOpen;

  const summary = document.createElement("summary");
  const copy = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = "Миёри заметила";
  const note = document.createElement("small");
  note.textContent =
    `${signals.length} ${signals.length === 1 ? "пункт" : "пункта"} · без вмешательства в чат`;
  copy.append(title, note);

  const count = document.createElement("b");
  count.textContent = String(signals.length);
  summary.append(copy, count);
  details.appendChild(summary);

  const body = document.createElement("div");
  body.className = "nexus-proactive-list";

  for (const signal of signals) {
    const article = document.createElement("article");
    article.className = `nexus-proactive-item priority-${signal.severity}`;
    article.dataset.signalId = signal.id;

    const head = document.createElement("div");
    head.className = "nexus-proactive-item-head";
    const text = document.createElement("div");
    const heading = document.createElement("strong");
    heading.textContent = signal.title;
    const detail = document.createElement("p");
    detail.textContent = signal.detail;
    text.append(heading, detail);

    const priority = document.createElement("span");
    priority.className = "nexus-proactive-priority";
    priority.textContent = severityLabel(signal.severity);
    head.append(text, priority);
    article.appendChild(head);

    const controls = document.createElement("div");
    controls.className = "nexus-proactive-controls";

    if (signal.controls.open) {
      const open = document.createElement("button");
      open.type = "button";
      open.className = "nexus-proactive-open";
      open.textContent = openLabel(signal.destination);
      open.addEventListener("click", () => navigate(signal.destination));
      controls.appendChild(open);
    }

    if (signal.controls.snooze) {
      const later = document.createElement("button");
      later.type = "button";
      later.className = "nexus-proactive-quiet";
      later.textContent = "Позже";
      later.title = "Отложить на 1 час";
      later.addEventListener("click", async () => {
        const projectId = currentProjectId();
        if (!projectId) return;
        later.disabled = true;
        try {
          const next = await snoozeNexusProactive(projectId, signal, 60);
          if (onPage) onPage(next);
          else renderNexusProactivePage(host, next);
        } catch {
          later.disabled = false;
        }
      });
      controls.appendChild(later);
    }

    if (signal.controls.dismiss) {
      const dismiss = document.createElement("button");
      dismiss.type = "button";
      dismiss.className = "nexus-proactive-quiet";
      dismiss.textContent = "Скрыть";
      dismiss.addEventListener("click", async () => {
        const projectId = currentProjectId();
        if (!projectId) return;
        dismiss.disabled = true;
        try {
          const next = await dismissNexusProactive(projectId, signal);
          if (onPage) onPage(next);
          else renderNexusProactivePage(host, next);
        } catch {
          dismiss.disabled = false;
        }
      });
      controls.appendChild(dismiss);
    }

    if (controls.childElementCount) article.appendChild(controls);
    body.appendChild(article);
  }

  details.appendChild(body);
  host.appendChild(details);
  host.hidden = false;
}

export function installNexusProactive(): () => void {
  const host = document.getElementById("nexusProactiveHost");
  if (!host) return () => undefined;

  let stopped = false;
  let generation = 0;
  let lastFingerprint = "";
  let wakeTimer: number | null = null;
  let lastPage: NexusProactivePage | null = null;

  const clearWake = (): void => {
    if (wakeTimer !== null) {
      window.clearTimeout(wakeTimer);
      wakeTimer = null;
    }
  };

  const refresh = async (): Promise<void> => {
    if (stopped) return;
    const projectId = currentProjectId();
    if (!projectId) return;
    const currentGeneration = ++generation;
    try {
      const page = await fetchNexusProactive(projectId);
      if (!stopped && currentGeneration === generation) acceptPage(page);
    } catch {
      if (currentGeneration === generation) {
        host.hidden = true;
        setVisibilityState(false);
      }
    }
  };

  const scheduleWake = (page: NexusProactivePage): void => {
    clearWake();
    if (!page.next_wakeup_at) return;
    const due = Date.parse(page.next_wakeup_at);
    if (!Number.isFinite(due)) return;
    const delay = Math.max(1000, Math.min(due - Date.now() + 250, 86_400_000));
    wakeTimer = window.setTimeout(() => {
      wakeTimer = null;
      void refresh();
    }, delay);
  };

  const acceptPage = (page: NexusProactivePage): void => {
    lastPage = page;
    renderNexusProactivePage(host, page, acceptPage);
    scheduleWake(page);
  };

  const onSnapshot = (event: Event): void => {
    if (!(event instanceof CustomEvent)) return;
    const snapshot = event.detail?.snapshot as NexusSnapshot | undefined;
    if (!snapshot) return;
    const counts = snapshot.counts || {};
    const fingerprint = [
      snapshot.project.id,
      event.detail?.last_event_id ?? "",
      counts.attention_actions ?? 0,
      counts.knowledge_attention ?? 0,
      counts.failed_tasks ?? 0,
      counts.recovering_workflows ?? 0,
    ].join(":");
    if (fingerprint === lastFingerprint) return;
    lastFingerprint = fingerprint;
    void refresh();
  };

  const onView = (): void => {
    if (lastPage) renderNexusProactivePage(host, lastPage, acceptPage);
    if (currentView() === "chat") void refresh();
  };

  window.addEventListener("miyori:nexus-snapshot", onSnapshot);
  window.addEventListener("miyori:nexus-view", onView);

  return () => {
    stopped = true;
    generation += 1;
    clearWake();
    setVisibilityState(false);
    window.removeEventListener("miyori:nexus-snapshot", onSnapshot);
    window.removeEventListener("miyori:nexus-view", onView);
  };
}
