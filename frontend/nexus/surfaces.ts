import { fetchNexusSurfaces } from "./client.js";
import type {
  NexusGenerativeSurface,
  NexusSnapshot,
  NexusSurfaceAction,
  NexusSurfacePage,
} from "./contracts.js";

type SurfaceRenderer = (surface: NexusGenerativeSurface) => HTMLElement;

const NAV_TARGETS: Record<NexusSurfaceAction["target"], string> = {
  chat: "nexusNavChat",
  actions: "nexusNavActions",
  knowledge: "nexusNavKnowledge",
  home: "nexusNavHome",
  system: "nexusNavSystem",
};

function currentProjectId(): number | null {
  const select = document.getElementById("projectSelect") as HTMLSelectElement | null;
  const value = Number(select?.value);
  return Number.isInteger(value) && value > 0 ? value : null;
}

function currentView(): string {
  return String(document.documentElement.dataset.nexusView || "chat");
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function asNumber(value: unknown): number {
  const result = Number(value);
  return Number.isFinite(result) ? result : 0;
}

function addText(
  parent: HTMLElement,
  tag: keyof HTMLElementTagNameMap,
  value: string,
  className?: string,
): HTMLElement {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = value;
  parent.appendChild(node);
  return node;
}

function addActions(parent: HTMLElement, actions: NexusSurfaceAction[]): void {
  if (!actions.length) return;
  const row = document.createElement("div");
  row.className = "nexus-surface-actions";

  for (const action of actions) {
    if (action.type !== "navigate" || !(action.target in NAV_TARGETS)) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "nexus-surface-action";
    button.textContent = action.label;
    button.addEventListener("click", () => {
      const targetId = NAV_TARGETS[action.target];
      const target = document.getElementById(targetId) as HTMLButtonElement | null;
      if (target) target.click();
      else {
        window.dispatchEvent(
          new CustomEvent("miyori:nexus-view", {
            detail: { view: action.target },
          }),
        );
      }
    });
    row.appendChild(button);
  }

  if (row.childElementCount) parent.appendChild(row);
}

function baseSurface(surface: NexusGenerativeSurface): HTMLElement {
  const article = document.createElement("article");
  article.className = `nexus-surface nexus-surface-${surface.component} tone-${surface.tone}`;
  article.dataset.surfaceId = surface.id;

  const head = document.createElement("header");
  head.className = "nexus-surface-head";
  const copy = document.createElement("div");
  addText(copy, "strong", surface.title);
  if (surface.description) addText(copy, "p", surface.description);
  head.appendChild(copy);

  const kind = document.createElement("span");
  kind.className = "nexus-surface-kind";
  kind.textContent = surface.kind;
  head.appendChild(kind);
  article.appendChild(head);
  return article;
}

function renderStatus(surface: NexusGenerativeSurface): HTMLElement {
  const article = baseSurface(surface);
  const data = asRecord(surface.data);
  const state = asString(data.state);
  if (state) addText(article, "small", `Состояние: ${state}`, "nexus-surface-meta");
  addActions(article, surface.actions);
  return article;
}

function renderAction(surface: NexusGenerativeSurface): HTMLElement {
  const article = baseSurface(surface);
  const data = asRecord(surface.data);
  const facts = document.createElement("div");
  facts.className = "nexus-surface-facts";
  const state = asString(data.state_label || data.state);
  const risk = asString(data.risk_level);
  if (state) addText(facts, "span", state);
  if (risk) addText(facts, "span", `risk: ${risk}`);
  if (data.destructive === true) addText(facts, "span", "изменяет данные", "warning");
  if (facts.childElementCount) article.appendChild(facts);
  addActions(article, surface.actions);
  return article;
}

function renderProgress(surface: NexusGenerativeSurface): HTMLElement {
  const article = baseSurface(surface);
  const data = asRecord(surface.data);
  const progress = asRecord(data.progress);
  const label = asString(progress.label || data.state_label || data.state);
  if (label) addText(article, "small", label, "nexus-surface-meta");
  addActions(article, surface.actions);
  return article;
}

function renderKnowledge(surface: NexusGenerativeSurface): HTMLElement {
  const article = baseSurface(surface);
  const data = asRecord(surface.data);
  const attention = asRecord(data.attention);
  const results = asRecord(data.results);
  const metrics = document.createElement("div");
  metrics.className = "nexus-surface-metrics";

  const entries: Array<[string, number]> = surface.component === "result_collection"
    ? [
        ["Память", asNumber(results.memory)],
        ["Документы", asNumber(results.documents)],
        ["Утверждения", asNumber(results.claims)],
      ]
    : [
        ["Проверить", asNumber(attention.total)],
        ["Документы", asNumber(attention.documents_limited)],
        [
          "Противоречия",
          asNumber(attention.memory_conflicts) +
            asNumber(attention.claim_open_contradictions),
        ],
      ];

  for (const [label, value] of entries) {
    const item = document.createElement("div");
    addText(item, "span", label);
    addText(item, "strong", String(value));
    metrics.appendChild(item);
  }
  article.appendChild(metrics);
  addActions(article, surface.actions);
  return article;
}

const SURFACE_REGISTRY: Record<string, SurfaceRenderer> = {
  status_summary: renderStatus,
  action_card: renderAction,
  progress_card: renderProgress,
  knowledge_attention: renderKnowledge,
  result_collection: renderKnowledge,
};

export function renderNexusSurfacePage(
  host: HTMLElement,
  page: NexusSurfacePage,
): void {
  const previous = host.querySelector("details");
  const wasOpen = previous instanceof HTMLDetailsElement && previous.open;
  host.replaceChildren();

  const valid = page.surfaces.filter(
    (surface) =>
      surface.policy?.model_html_allowed === false &&
      surface.policy?.script_allowed === false &&
      surface.policy?.trusted_component_only === true &&
      surface.policy?.interrupts_chat === false &&
      Boolean(SURFACE_REGISTRY[surface.component]),
  );

  if (
    !valid.length ||
    currentView() !== "chat" ||
    document.documentElement.dataset.nexusProactiveVisible === "true"
  ) {
    host.hidden = true;
    return;
  }

  const details = document.createElement("details");
  details.className = "nexus-surface-shelf";
  details.open = wasOpen;

  const summary = document.createElement("summary");
  const copy = document.createElement("span");
  addText(copy, "strong", "Структурный контекст");
  addText(
    copy,
    "small",
    `${valid.length} ${valid.length === 1 ? "блок" : "блока"} · открыть по желанию`,
  );
  summary.appendChild(copy);
  const count = document.createElement("b");
  count.textContent = String(valid.length);
  summary.appendChild(count);
  details.appendChild(summary);

  const body = document.createElement("div");
  body.className = "nexus-surface-shelf-body";
  for (const surface of valid) {
    const renderer = SURFACE_REGISTRY[surface.component];
    if (!renderer) continue;
    body.appendChild(renderer(surface));
  }
  details.appendChild(body);
  host.appendChild(details);
  host.hidden = false;
}

export function installNexusSurfaceHost(): () => void {
  const host = document.getElementById("nexusSurfaceHost");
  if (!host) return () => undefined;

  let stopped = false;
  let generation = 0;
  let lastFingerprint = "";

  const refresh = async (force = false): Promise<void> => {
    if (stopped) return;
    if (currentView() !== "chat") {
      host.hidden = true;
      return;
    }
    const projectId = currentProjectId();
    if (!projectId) return;

    const currentGeneration = ++generation;
    try {
      const page = await fetchNexusSurfaces(projectId, {
        context: "chat",
        limit: 3,
      });
      if (!stopped && currentGeneration === generation) {
        renderNexusSurfacePage(host, page);
      }
    } catch {
      if (!force && currentGeneration === generation) host.hidden = true;
    }
  };

  const onSnapshot = (event: Event): void => {
    if (!(event instanceof CustomEvent)) return;
    const snapshot = event.detail?.snapshot as NexusSnapshot | undefined;
    if (!snapshot) return;
    const counts = snapshot.counts || {};
    const fingerprint = [
      snapshot.project.id,
      snapshot.overall_state,
      counts.attention_actions ?? 0,
      counts.active_actions ?? 0,
      counts.knowledge_attention ?? 0,
      counts.failed_tasks ?? 0,
    ].join(":");
    if (fingerprint === lastFingerprint) return;
    lastFingerprint = fingerprint;
    void refresh();
  };

  const onView = (event: Event): void => {
    if (!(event instanceof CustomEvent)) return;
    const view = String(event.detail?.view || "");
    if (view !== "chat") {
      host.hidden = true;
      return;
    }
    void refresh(true);
  };

  const onProactiveVisibility = (event: Event): void => {
    if (!(event instanceof CustomEvent)) return;
    if (event.detail?.visible === true) {
      host.hidden = true;
    } else {
      void refresh(true);
    }
  };

  window.addEventListener("miyori:nexus-snapshot", onSnapshot);
  window.addEventListener("miyori:nexus-view", onView);
  window.addEventListener("miyori:proactive-visibility", onProactiveVisibility);

  return () => {
    stopped = true;
    generation += 1;
    window.removeEventListener("miyori:nexus-snapshot", onSnapshot);
    window.removeEventListener("miyori:nexus-view", onView);
    window.removeEventListener("miyori:proactive-visibility", onProactiveVisibility);
  };
}
