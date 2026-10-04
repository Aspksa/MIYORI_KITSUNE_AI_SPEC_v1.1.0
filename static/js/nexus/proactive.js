import { dismissNexusProactive, fetchNexusProactive, snoozeNexusProactive, } from "./client.js";
function currentProjectId() {
    const select = document.getElementById("projectSelect");
    const value = Number(select?.value);
    return Number.isInteger(value) && value > 0 ? value : null;
}
function navigate(target) {
    const id = target === "actions"
        ? "nexusNavActions"
        : target === "knowledge"
            ? "nexusNavKnowledge"
            : "nexusNavSystem";
    const button = document.getElementById(id);
    button?.click();
}
function setVisibilityState(visible) {
    document.documentElement.dataset.nexusProactiveVisible = visible ? "true" : "false";
    window.dispatchEvent(new CustomEvent("miyori:proactive-visibility", {
        detail: { visible },
    }));
}
function priorityLabel(priority) {
    return priority === "high"
        ? "важно"
        : priority === "normal"
            ? "проверить"
            : "когда удобно";
}
export function renderNexusProactivePage(host, page) {
    const previous = host.querySelector("details");
    const wasOpen = previous instanceof HTMLDetailsElement && previous.open;
    host.replaceChildren();
    const signals = page.signals.filter((signal) => signal.policy?.auto_execute_allowed === false &&
        signal.policy?.write_tools_allowed === false &&
        signal.policy?.chat_interruption_allowed === false &&
        signal.policy?.creates_chat_message === false &&
        signal.policy?.requires_explicit_user_action === true);
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
    note.textContent = `${signals.length} ${signals.length === 1 ? "пункт" : "пункта"} · без вмешательства в чат`;
    copy.append(title, note);
    const count = document.createElement("b");
    count.textContent = String(signals.length);
    summary.append(copy, count);
    details.appendChild(summary);
    const body = document.createElement("div");
    body.className = "nexus-proactive-list";
    for (const signal of signals) {
        const article = document.createElement("article");
        article.className = `nexus-proactive-item priority-${signal.priority}`;
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
        priority.textContent = priorityLabel(signal.priority);
        head.append(text, priority);
        article.appendChild(head);
        const controls = document.createElement("div");
        controls.className = "nexus-proactive-controls";
        const open = document.createElement("button");
        open.type = "button";
        open.className = "nexus-proactive-open";
        open.textContent = signal.action.label;
        open.addEventListener("click", () => navigate(signal.action.target));
        controls.appendChild(open);
        if (signal.controls.can_snooze) {
            const later = document.createElement("button");
            later.type = "button";
            later.className = "nexus-proactive-quiet";
            later.textContent = "Позже";
            later.title = "Отложить на 1 час";
            later.addEventListener("click", async () => {
                const projectId = currentProjectId();
                if (!projectId)
                    return;
                later.disabled = true;
                try {
                    const next = await snoozeNexusProactive(projectId, signal.id, 60);
                    renderNexusProactivePage(host, next);
                }
                catch {
                    later.disabled = false;
                }
            });
            controls.appendChild(later);
        }
        if (signal.controls.can_dismiss) {
            const dismiss = document.createElement("button");
            dismiss.type = "button";
            dismiss.className = "nexus-proactive-quiet";
            dismiss.textContent = "Скрыть";
            dismiss.addEventListener("click", async () => {
                const projectId = currentProjectId();
                if (!projectId)
                    return;
                dismiss.disabled = true;
                try {
                    const next = await dismissNexusProactive(projectId, signal.id);
                    renderNexusProactivePage(host, next);
                }
                catch {
                    dismiss.disabled = false;
                }
            });
            controls.appendChild(dismiss);
        }
        article.appendChild(controls);
        body.appendChild(article);
    }
    details.appendChild(body);
    host.appendChild(details);
    host.hidden = false;
}
export function installNexusProactive() {
    const host = document.getElementById("nexusProactiveHost");
    if (!host)
        return () => undefined;
    let stopped = false;
    let generation = 0;
    let lastFingerprint = "";
    const refresh = async () => {
        if (stopped)
            return;
        const projectId = currentProjectId();
        if (!projectId)
            return;
        const currentGeneration = ++generation;
        try {
            const page = await fetchNexusProactive(projectId);
            if (!stopped && currentGeneration === generation) {
                renderNexusProactivePage(host, page);
            }
        }
        catch {
            if (currentGeneration === generation) {
                host.hidden = true;
                setVisibilityState(false);
            }
        }
    };
    const onSnapshot = (event) => {
        if (!(event instanceof CustomEvent))
            return;
        const snapshot = event.detail?.snapshot;
        if (!snapshot)
            return;
        const counts = snapshot.counts || {};
        const fingerprint = [
            snapshot.project.id,
            event.detail?.last_event_id ?? "",
            counts.attention_actions ?? 0,
            counts.knowledge_attention ?? 0,
            counts.failed_tasks ?? 0,
            counts.recovering_workflows ?? 0,
        ].join(":");
        if (fingerprint === lastFingerprint)
            return;
        lastFingerprint = fingerprint;
        void refresh();
    };
    window.addEventListener("miyori:nexus-snapshot", onSnapshot);
    return () => {
        stopped = true;
        generation += 1;
        setVisibilityState(false);
        window.removeEventListener("miyori:nexus-snapshot", onSnapshot);
    };
}
