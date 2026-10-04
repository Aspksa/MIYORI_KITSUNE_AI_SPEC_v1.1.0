import { NexusStore } from "./store.js";
const VIEW_LABELS = {
    chat: "Чат",
    actions: "Действия",
    knowledge: "Знания",
    home: "Дом",
    system: "Система",
};
const STATE_LABELS = {
    disabled: "Отключено",
    not_connected: "Не подключено",
    ready: "Готово",
    processing: "В работе",
    degraded: "Ограничено",
    error: "Ошибка",
};
const NAV_IDS = {
    chat: "nexusNavChat",
    actions: "nexusNavActions",
    knowledge: "nexusNavKnowledge",
    home: "nexusNavHome",
    system: "nexusNavSystem",
};
function element(id) {
    const node = document.getElementById(id);
    return node instanceof HTMLElement ? node : null;
}
function currentProjectId() {
    const select = document.getElementById("projectSelect");
    if (!(select instanceof HTMLSelectElement))
        return null;
    const value = Number(select.value);
    return Number.isInteger(value) && value > 0 ? value : null;
}
function moduleById(snapshot, id) {
    return snapshot.modules.find((item) => item.id === id) ?? null;
}
function setText(id, value) {
    const node = element(id);
    if (node)
        node.textContent = value;
}
function setStateDot(id, state) {
    const node = element(id);
    if (node)
        node.dataset.state = state;
}
function detailForSnapshot(snapshot) {
    const pending = Number(snapshot.counts.pending_permissions ?? 0);
    const tasks = Number(snapshot.counts.active_tasks ?? 0);
    const workflows = Number(snapshot.counts.active_workflows ?? 0);
    if (pending > 0)
        return "Нужно решений: " + pending;
    if (tasks + workflows > 0)
        return "В работе: " + (tasks + workflows);
    const docs = Number(snapshot.counts.documents ?? 0);
    const memory = Number(snapshot.counts.verified_memory ?? 0);
    return "Документы: " + docs + " · память: " + memory;
}
function renderSnapshot(snapshot) {
    const state = snapshot.overall_state;
    const label = STATE_LABELS[state];
    const detail = detailForSnapshot(snapshot);
    setText("nexusRailState", label);
    setText("nexusRailDetail", detail);
    setStateDot("nexusRailStateDot", state);
  setText("systemDocumentCount", String(Number(snapshot.counts.documents ?? 0)));
  setText("systemMemoryCount", String(Number(snapshot.counts.verified_memory ?? 0)));
    setText("nexusHeaderState", label);
    setText("nexusHeaderDetail", detail);
    setStateDot("nexusHeaderStateDot", state);
    const actionCount = Number(snapshot.counts.active_actions ??
        (Number(snapshot.counts.active_tasks ?? 0) +
            Number(snapshot.counts.active_workflows ?? 0)));
    setText("nexusNavActionsMeta", actionCount ? String(actionCount) : "чисто");
    const documents = Number(snapshot.counts.documents ?? 0);
    const knowledgeAttention = Number(snapshot.counts.knowledge_attention ?? 0);
    setText("nexusNavKnowledgeMeta", knowledgeAttention > 0 ? `${knowledgeAttention} проверить` : documents ? String(documents) : "0");
    const home = moduleById(snapshot, "home");
    const homeLinked = Number(snapshot.counts.home_linked ?? 0);
    const homeOnline = Number(snapshot.counts.home_online ?? 0);
    setText("nexusNavHomeMeta", home?.state === "disabled"
        ? "отключено"
        : homeLinked > 0
            ? `${homeOnline}/${homeLinked} online`
            : "нет связей");
    setText("nexusNavSystemMeta", label.toLowerCase());
    setText("nexusNavChatMeta", label.toLowerCase());
}
function renderConnectionError(message) {
    setText("nexusRailState", "Нет связи");
    setText("nexusRailDetail", message);
    setStateDot("nexusRailStateDot", "error");
  setText("systemDocumentCount", "—");
  setText("systemMemoryCount", "—");
    setText("nexusHeaderState", "Нет связи");
    setText("nexusHeaderDetail", message);
    setStateDot("nexusHeaderStateDot", "error");
}
function setActiveView(view) {
    for (const [name, id] of Object.entries(NAV_IDS)) {
        const button = element(id);
        if (!button)
            continue;
        const active = name === view;
        button.classList.toggle("active", active);
        if (active)
            button.setAttribute("aria-current", "page");
        else
            button.removeAttribute("aria-current");
    }
    document.documentElement.dataset.nexusView = view;
    setText("nexusViewEyebrow", "NEXUS · " + VIEW_LABELS[view]);
}
function installNavigationKeyboard() {
    const nav = element("nexusPrimaryNav");
    if (!nav)
        return () => undefined;
    const buttons = Object.values(NAV_IDS)
        .map((id) => element(id))
        .filter((item) => item !== null && !item.hidden);
    const onKeyDown = (event) => {
        if (!["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
            return;
        }
        const activeIndex = buttons.findIndex((button) => button === document.activeElement);
        if (activeIndex < 0)
            return;
        event.preventDefault();
        let nextIndex = activeIndex;
        if (event.key === "Home")
            nextIndex = 0;
        else if (event.key === "End")
            nextIndex = buttons.length - 1;
        else if (event.key === "ArrowDown" || event.key === "ArrowRight") {
            nextIndex = (activeIndex + 1) % buttons.length;
        }
        else {
            nextIndex = (activeIndex - 1 + buttons.length) % buttons.length;
        }
        buttons[nextIndex]?.focus();
    };
    nav.addEventListener("keydown", onKeyDown);
    return () => nav.removeEventListener("keydown", onKeyDown);
}
export function installNexusShell() {
    let store = null;
    let unsubscribeStore = null;
    let pollTimer = null;
    let generation = 0;
    let stopped = false;
    const select = document.getElementById("projectSelect");
    const onView = (event) => {
        if (!(event instanceof CustomEvent))
            return;
        const value = String(event.detail?.view ?? "");
        if (value in VIEW_LABELS)
            setActiveView(value);
    };
    const schedulePoll = () => {
        if (stopped)
            return;
        if (pollTimer !== null)
            window.clearTimeout(pollTimer);
        pollTimer = window.setTimeout(async () => {
            if (!store || document.visibilityState === "hidden") {
                schedulePoll();
                return;
            }
            try {
                await store.sync();
            }
            catch (error) {
                renderConnectionError(error instanceof Error ? error.message : "NEXUS недоступен");
            }
            finally {
                schedulePoll();
            }
        }, 3000);
    };
    const connect = async () => {
        const projectId = currentProjectId();
        if (!projectId) {
            window.setTimeout(() => {
                if (!stopped)
                    void connect();
            }, 250);
            return;
        }
        generation += 1;
        const currentGeneration = generation;
        unsubscribeStore?.();
        store = new NexusStore(projectId, undefined, 160);
        unsubscribeStore = store.subscribe((state) => {
            if (currentGeneration !== generation)
                return;
            if (state.snapshot) {
                renderSnapshot(state.snapshot);
                window.dispatchEvent(new CustomEvent("miyori:nexus-snapshot", {
                    detail: {
                        snapshot: state.snapshot,
                        event_cursor: state.cursor,
                        last_event_id: state.events.at(-1)?.id ?? null,
                    },
                }));
            }
        });
        try {
            await store.hydrate();
        }
        catch (error) {
            if (currentGeneration === generation) {
                renderConnectionError(error instanceof Error ? error.message : "NEXUS недоступен");
            }
        }
    };
    const onProjectChange = () => {
        void connect();
    };
    const onVisibility = () => {
        if (document.visibilityState === "visible" && store) {
            void store.sync().catch((error) => {
                renderConnectionError(error instanceof Error ? error.message : "NEXUS недоступен");
            });
        }
    };
    window.addEventListener("miyori:nexus-view", onView);
    select?.addEventListener("change", onProjectChange);
    document.addEventListener("visibilitychange", onVisibility);
    const removeKeyboard = installNavigationKeyboard();
    const initialView = String(document.documentElement.dataset.nexusView || "chat");
    setActiveView(initialView in VIEW_LABELS ? initialView : "chat");
    void connect();
    schedulePoll();
    return () => {
        stopped = true;
        generation += 1;
        unsubscribeStore?.();
        if (pollTimer !== null)
            window.clearTimeout(pollTimer);
        removeKeyboard();
        window.removeEventListener("miyori:nexus-view", onView);
        select?.removeEventListener("change", onProjectChange);
        document.removeEventListener("visibilitychange", onVisibility);
    };
}
