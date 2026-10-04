import { fetchNexusPresence } from "./client.js";
import type { NexusPresence, NexusSnapshot } from "./contracts.js";

type LocalInteractionState = "idle" | "thinking";

function currentView(): string {
  return String(document.documentElement.dataset.nexusView || "chat");
}

function currentProjectId(): number | null {
  const select = document.getElementById("projectSelect") as HTMLSelectElement | null;
  const value = Number(select?.value);
  return Number.isInteger(value) && value > 0 ? value : null;
}

function navigate(view: "actions" | "knowledge" | "system"): void {
  const target = document.getElementById(
    view === "actions"
      ? "nexusNavActions"
      : view === "knowledge"
        ? "nexusNavKnowledge"
        : "nexusNavSystem",
  ) as HTMLButtonElement | null;
  if (target) target.click();
}

function renderPresence(
  host: HTMLElement,
  presence: NexusPresence | null,
  interaction: LocalInteractionState,
): void {
  host.replaceChildren();

  if (currentView() !== "chat") {
    host.hidden = true;
    return;
  }

  if (interaction === "thinking") {
    host.dataset.mode = "working";
    const row = document.createElement("div");
    row.className = "nexus-presence-row";
    const mark = document.createElement("span");
    mark.className = "nexus-presence-mark";
    mark.setAttribute("aria-hidden", "true");
    const copy = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = "Думаю над сообщением";
    const detail = document.createElement("small");
    detail.textContent = "Запрос отправлен; жду реальный ответ текущего provider/workflow.";
    copy.append(title, detail);
    row.append(mark, copy);
    host.appendChild(row);
    host.hidden = false;
    return;
  }

  if (!presence || presence.mode === "ready") {
    host.hidden = true;
    delete host.dataset.mode;
    return;
  }

  host.dataset.mode = presence.mode;
  const row = document.createElement("div");
  row.className = "nexus-presence-row";

  const mark = document.createElement("span");
  mark.className = "nexus-presence-mark";
  mark.setAttribute("aria-hidden", "true");

  const copy = document.createElement("span");
  copy.className = "nexus-presence-copy";
  const title = document.createElement("strong");
  title.textContent = presence.headline;
  const detail = document.createElement("small");
  detail.textContent = presence.detail;
  copy.append(title, detail);
  row.append(mark, copy);

  const firstReason = presence.reasons[0];
  let view: "actions" | "knowledge" | "system" | null = null;
  if (
    presence.mode === "waiting" ||
    presence.mode === "verifying" ||
    presence.mode === "recovery" ||
    firstReason?.kind === "action" ||
    firstReason?.kind === "workflow" ||
    firstReason?.kind === "permission"
  ) {
    view = "actions";
  } else if (firstReason?.kind === "knowledge") {
    view = "knowledge";
  } else if (presence.mode === "degraded" || firstReason?.kind === "task") {
    view = "system";
  }

  if (view) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "nexus-presence-action";
    button.textContent =
      view === "actions"
        ? "Действия"
        : view === "knowledge"
          ? "Знания"
          : "Система";
    button.addEventListener("click", () => navigate(view!));
    row.appendChild(button);
  }

  host.appendChild(row);

  if (presence.last_event && presence.attention === "high") {
    const details = document.createElement("details");
    details.className = "nexus-presence-detail";
    const summary = document.createElement("summary");
    summary.textContent = "Последнее подтверждённое событие";
    const event = document.createElement("p");
    event.textContent = presence.last_event.summary;
    details.append(summary, event);
    host.appendChild(details);
  }

  host.hidden = false;
}

export function installNexusPresence(): () => void {
  const host = document.getElementById("nexusPresenceHost");
  if (!host) return () => undefined;

  let stopped = false;
  let generation = 0;
  let interaction: LocalInteractionState = "idle";
  let presence: NexusPresence | null = null;
  let lastFingerprint = "";

  const refresh = async (): Promise<void> => {
    if (stopped) return;
    const projectId = currentProjectId();
    if (!projectId) return;
    const currentGeneration = ++generation;
    try {
      const next = await fetchNexusPresence(projectId);
      if (!stopped && currentGeneration === generation) {
        presence = next;
        renderPresence(host, presence, interaction);
      }
    } catch {
      if (currentGeneration === generation && interaction === "idle") {
        host.hidden = true;
      }
    }
  };

  const onSnapshot = (event: Event): void => {
    if (!(event instanceof CustomEvent)) return;
    const snapshot = event.detail?.snapshot as NexusSnapshot | undefined;
    if (!snapshot) return;
    const c = snapshot.counts || {};
    const fingerprint = [
      snapshot.project.id,
      snapshot.overall_state,
      c.active_actions ?? 0,
      c.attention_actions ?? 0,
      c.knowledge_attention ?? 0,
      c.failed_tasks ?? 0,
      c.recovering_workflows ?? 0,
    ].join(":");
    if (fingerprint === lastFingerprint) return;
    lastFingerprint = fingerprint;
    void refresh();
  };

  const onInteraction = (event: Event): void => {
    if (!(event instanceof CustomEvent)) return;
    interaction = event.detail?.state === "thinking" ? "thinking" : "idle";
    renderPresence(host, presence, interaction);
    if (interaction === "idle") void refresh();
  };

  const onView = (): void => {
    renderPresence(host, presence, interaction);
  };

  window.addEventListener("miyori:nexus-snapshot", onSnapshot);
  window.addEventListener("miyori:interaction-state", onInteraction);
  window.addEventListener("miyori:nexus-view", onView);

  return () => {
    stopped = true;
    generation += 1;
    window.removeEventListener("miyori:nexus-snapshot", onSnapshot);
    window.removeEventListener("miyori:interaction-state", onInteraction);
    window.removeEventListener("miyori:nexus-view", onView);
  };
}
