import { NexusStore } from "./store.js";
import type {
  NexusModuleState,
  NexusOperationalState,
  NexusSnapshot,
} from "./contracts.js";

type NexusView = "chat" | "actions" | "knowledge" | "home" | "system";

const VIEW_LABELS: Record<NexusView, string> = {
  chat: "Чат",
  actions: "Действия",
  knowledge: "Знания",
  home: "Дом",
  system: "Система",
};

const STATE_LABELS: Record<NexusOperationalState, string> = {
  disabled: "Отключено",
  not_connected: "Не подключено",
  ready: "Готово",
  processing: "В работе",
  degraded: "Ограничено",
  error: "Ошибка",
};

const NAV_IDS: Record<NexusView, string> = {
  chat: "nexusNavChat",
  actions: "nexusNavActions",
  knowledge: "nexusNavKnowledge",
  home: "nexusNavHome",
  system: "nexusNavSystem",
};

function element<T extends HTMLElement>(id: string): T | null {
  const node = document.getElementById(id);
  return node instanceof HTMLElement ? (node as T) : null;
}

function currentProjectId(): number | null {
  const select = document.getElementById("projectSelect");
  if (!(select instanceof HTMLSelectElement)) return null;
  const value = Number(select.value);
  return Number.isInteger(value) && value > 0 ? value : null;
}

function moduleById(snapshot: NexusSnapshot, id: string): NexusModuleState | null {
  return snapshot.modules.find((item) => item.id === id) ?? null;
}

function setText(id: string, value: string): void {
  const node = element(id);
  if (node) node.textContent = value;
}

function setStateDot(id: string, state: NexusOperationalState): void {
  const node = element(id);
  if (node) node.dataset.state = state;
}

function detailForSnapshot(snapshot: NexusSnapshot): string {
  const pending = Number(snapshot.counts.pending_permissions ?? 0);
  const tasks = Number(snapshot.counts.active_tasks ?? 0);
  const workflows = Number(snapshot.counts.active_workflows ?? 0);
  if (pending > 0) return "Нужно решений: " + pending;
  if (tasks + workflows > 0) return "В работе: " + (tasks + workflows);
  const docs = Number(snapshot.counts.documents ?? 0);
  const memory = Number(snapshot.counts.verified_memory ?? 0);
  return "Документы: " + docs + " · память: " + memory;
}

function renderSnapshot(snapshot: NexusSnapshot): void {
  const state = snapshot.overall_state;
  const label = STATE_LABELS[state];
  const detail = detailForSnapshot(snapshot);

  setText("nexusRailState", label);
  setText("nexusRailDetail", detail);
  setStateDot("nexusRailStateDot", state);

  setText("nexusHeaderState", label);
  setText("nexusHeaderDetail", detail);
  setStateDot("nexusHeaderStateDot", state);

  const pending = Number(snapshot.counts.pending_permissions ?? 0);
  const tasks = Number(snapshot.counts.active_tasks ?? 0);
  const workflows = Number(snapshot.counts.active_workflows ?? 0);
  const actionCount = pending + tasks + workflows;
  setText("nexusNavActionsMeta", actionCount ? String(actionCount) : "чисто");

  const documents = Number(snapshot.counts.documents ?? 0);
  setText("nexusNavKnowledgeMeta", documents ? String(documents) : "0");

  const home = moduleById(snapshot, "home");
  setText(
    "nexusNavHomeMeta",
    home ? STATE_LABELS[home.state].toLowerCase() : "—",
  );

  setText("nexusNavSystemMeta", label.toLowerCase());
  setText("nexusNavChatMeta", state === "processing" ? "в работе" : "готово");
}

function renderConnectionError(message: string): void {
  setText("nexusRailState", "Нет связи");
  setText("nexusRailDetail", message);
  setStateDot("nexusRailStateDot", "error");
  setText("nexusHeaderState", "Нет связи");
  setText("nexusHeaderDetail", message);
  setStateDot("nexusHeaderStateDot", "error");
}

function setActiveView(view: NexusView): void {
  for (const [name, id] of Object.entries(NAV_IDS) as Array<[NexusView, string]>) {
    const button = element<HTMLButtonElement>(id);
    if (!button) continue;
    const active = name === view;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  document.documentElement.dataset.nexusView = view;
  setText("nexusViewEyebrow", "NEXUS · " + VIEW_LABELS[view]);
}

function installNavigationKeyboard(): () => void {
  const nav = element<HTMLElement>("nexusPrimaryNav");
  if (!nav) return () => undefined;
  const buttons = Object.values(NAV_IDS)
    .map((id) => element<HTMLButtonElement>(id))
    .filter((item): item is HTMLButtonElement => item !== null);

  const onKeyDown = (event: KeyboardEvent): void => {
    if (!["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return;
    }
    const activeIndex = buttons.findIndex((button) => button === document.activeElement);
    if (activeIndex < 0) return;

    event.preventDefault();
    let nextIndex = activeIndex;
    if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = buttons.length - 1;
    else if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      nextIndex = (activeIndex + 1) % buttons.length;
    } else {
      nextIndex = (activeIndex - 1 + buttons.length) % buttons.length;
    }
    buttons[nextIndex]?.focus();
  };

  nav.addEventListener("keydown", onKeyDown);
  return () => nav.removeEventListener("keydown", onKeyDown);
}

export function installNexusShell(): () => void {
  let store: NexusStore | null = null;
  let unsubscribeStore: (() => void) | null = null;
  let pollTimer: number | null = null;
  let generation = 0;
  let pollCount = 0;
  let stopped = false;

  const select = document.getElementById("projectSelect");
  const onView = (event: Event): void => {
    if (!(event instanceof CustomEvent)) return;
    const value = String(event.detail?.view ?? "");
    if (value in VIEW_LABELS) setActiveView(value as NexusView);
  };

  const schedulePoll = (): void => {
    if (stopped) return;
    if (pollTimer !== null) window.clearTimeout(pollTimer);
    pollTimer = window.setTimeout(async () => {
      if (!store || document.visibilityState === "hidden") {
        schedulePoll();
        return;
      }
      try {
        pollCount += 1;
        await store.sync({ forceSnapshot: pollCount % 10 === 0 });
      } catch (error) {
        renderConnectionError(error instanceof Error ? error.message : "NEXUS недоступен");
      } finally {
        schedulePoll();
      }
    }, 3000);
  };

  const connect = async (): Promise<void> => {
    const projectId = currentProjectId();
    if (!projectId) {
      window.setTimeout(() => {
        if (!stopped) void connect();
      }, 250);
      return;
    }

    generation += 1;
    pollCount = 0;
    const currentGeneration = generation;
    unsubscribeStore?.();
    store = new NexusStore(projectId, undefined, 160);
    unsubscribeStore = store.subscribe((state) => {
      if (currentGeneration !== generation) return;
      if (state.snapshot) renderSnapshot(state.snapshot);
    });

    try {
      await store.hydrate();
    } catch (error) {
      if (currentGeneration === generation) {
        renderConnectionError(error instanceof Error ? error.message : "NEXUS недоступен");
      }
    }
  };

  const onProjectChange = (): void => {
    void connect();
  };
  const onVisibility = (): void => {
    if (document.visibilityState === "visible" && store) {
      void store.sync().catch((error: unknown) => {
        renderConnectionError(error instanceof Error ? error.message : "NEXUS недоступен");
      });
    }
  };

  window.addEventListener("miyori:nexus-view", onView);
  select?.addEventListener("change", onProjectChange);
  document.addEventListener("visibilitychange", onVisibility);
  const removeKeyboard = installNavigationKeyboard();

  setActiveView("chat");
  void connect();
  schedulePoll();

  return () => {
    stopped = true;
    generation += 1;
    unsubscribeStore?.();
    if (pollTimer !== null) window.clearTimeout(pollTimer);
    removeKeyboard();
    window.removeEventListener("miyori:nexus-view", onView);
    select?.removeEventListener("change", onProjectChange);
    document.removeEventListener("visibilitychange", onVisibility);
  };
}
