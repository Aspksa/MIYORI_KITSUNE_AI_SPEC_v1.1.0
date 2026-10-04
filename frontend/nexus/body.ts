import { fetchNexusBody } from "./client.js";
import type {
  NexusBodyLocalState,
  NexusBodyPresentation,
  NexusDigitalBody,
  NexusSnapshot,
} from "./contracts.js";

function currentProjectId(): number | null {
  const select = document.getElementById("projectSelect") as HTMLSelectElement | null;
  const value = Number(select?.value);
  return Number.isInteger(value) && value > 0 ? value : null;
}

function currentView(): string {
  return String(document.documentElement.dataset.nexusView || "chat");
}

function effectiveLocalState(
  voice: NexusBodyLocalState,
  interaction: NexusBodyLocalState,
): NexusBodyLocalState {
  if (voice !== "idle") return voice;
  return interaction;
}

function presentationFor(
  body: NexusDigitalBody,
  local: NexusBodyLocalState,
): NexusBodyPresentation {
  if (local !== "idle") {
    const override = body.local_override_contract.presentations[local];
    if (override) return override;
  }
  return body.presentation;
}

function appendTextList(
  host: HTMLElement,
  title: string,
  values: string[],
): void {
  const group = document.createElement("div");
  group.className = "nexus-body-canon-group";
  const strong = document.createElement("strong");
  strong.textContent = title;
  group.appendChild(strong);

  const list = document.createElement("ul");
  for (const value of values) {
    const item = document.createElement("li");
    item.textContent = value;
    list.appendChild(item);
  }
  group.appendChild(list);
  host.appendChild(group);
}

function buildPortrait(
  presentation: NexusBodyPresentation,
  effectiveState: string,
): HTMLElement {
  const portrait = document.createElement("div");
  portrait.className = "nexus-body-portrait";
  portrait.dataset.pose = presentation.pose;
  portrait.dataset.expression = presentation.expression;
  portrait.dataset.gesture = presentation.gesture;
  portrait.dataset.state = effectiveState;
  portrait.setAttribute("aria-hidden", "true");

  const leftEar = document.createElement("span");
  leftEar.className = "nexus-body-ear left";
  const rightEar = document.createElement("span");
  rightEar.className = "nexus-body-ear right";

  const face = document.createElement("span");
  face.className = "nexus-body-face";
  const leftEye = document.createElement("span");
  leftEye.className = "nexus-body-eye left";
  const rightEye = document.createElement("span");
  rightEye.className = "nexus-body-eye right";
  const mouth = document.createElement("span");
  mouth.className = "nexus-body-mouth";
  face.append(leftEye, rightEye, mouth);

  const stateMark = document.createElement("span");
  stateMark.className = "nexus-body-state-mark";

  portrait.append(leftEar, rightEar, face, stateMark);
  return portrait;
}

function renderBody(
  host: HTMLElement,
  body: NexusDigitalBody | null,
  voiceState: NexusBodyLocalState,
  interactionState: NexusBodyLocalState,
): void {
  host.replaceChildren();

  if (currentView() !== "chat" || !body) {
    host.hidden = true;
    return;
  }

  const local = effectiveLocalState(voiceState, interactionState);
  const presentation = presentationFor(body, local);
  const effectiveState = local === "idle" ? body.state : local;

  host.dataset.state = effectiveState;
  host.dataset.pose = presentation.pose;
  host.dataset.expression = presentation.expression;

  const shell = document.createElement("div");
  shell.className = "nexus-body-shell";
  shell.appendChild(buildPortrait(presentation, effectiveState));

  const copy = document.createElement("div");
  copy.className = "nexus-body-copy";
  const identity = document.createElement("span");
  identity.className = "nexus-body-identity";
  identity.textContent = body.appearance.nickname || body.appearance.name;

  const status = document.createElement("strong");
  status.className = "nexus-body-status";
  status.textContent = presentation.label;

  const detail = document.createElement("small");
  detail.className = "nexus-body-detail";
  detail.textContent =
    local === "idle"
      ? body.runtime.detail
      : "Состояние подтверждено локальным runtime-событием.";

  const appearance = document.createElement("small");
  appearance.className = "nexus-body-appearance-state";
  appearance.textContent =
    body.appearance.configuration_state === "appearance_unconfigured"
      ? "Внешность ждёт вашего выбора"
      : "Канонический образ настроен";

  copy.append(identity, status, detail, appearance);
  shell.appendChild(copy);

  const canon = document.createElement("details");
  canon.className = "nexus-body-canon";
  const summary = document.createElement("summary");
  summary.textContent = "Канон образа";
  canon.appendChild(summary);

  const bodyCanon = document.createElement("div");
  bodyCanon.className = "nexus-body-canon-body";
  appendTextList(bodyCanon, "Подтверждено", body.appearance.confirmed);
  appendTextList(
    bodyCanon,
    "Оставлено на ваш выбор",
    body.appearance.open_for_owner_choice,
  );

  const note = document.createElement("p");
  note.textContent =
    "До выбора внешности Digital Body использует нейтральную монохромную оболочку и не придумывает цвет волос, глаз, число хвостов или наряд.";
  bodyCanon.appendChild(note);
  canon.appendChild(bodyCanon);
  shell.appendChild(canon);

  host.appendChild(shell);
  host.hidden = false;
}

function mapVoiceState(value: string): NexusBodyLocalState {
  if (value === "error") return "voice_error";
  if (
    value === "thinking" ||
    value === "listening" ||
    value === "transcribing" ||
    value === "speaking" ||
    value === "interrupted"
  ) {
    return value;
  }
  return "idle";
}

export function installNexusDigitalBody(): () => void {
  const host = document.getElementById("nexusBodyHost");
  if (!host) return () => undefined;

  let stopped = false;
  let generation = 0;
  let body: NexusDigitalBody | null = null;
  let voiceState: NexusBodyLocalState = "idle";
  let interactionState: NexusBodyLocalState = "idle";
  let lastSnapshotFingerprint = "";

  const refresh = async (): Promise<void> => {
    if (stopped) return;
    const projectId = currentProjectId();
    if (!projectId) {
      body = null;
      renderBody(host, body, voiceState, interactionState);
      return;
    }
    const currentGeneration = ++generation;
    try {
      const next = await fetchNexusBody(projectId);
      if (!stopped && currentGeneration === generation) {
        body = next;
        renderBody(host, body, voiceState, interactionState);
      }
    } catch {
      if (currentGeneration === generation) {
        body = null;
        renderBody(host, body, voiceState, interactionState);
      }
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
      counts.active_actions ?? 0,
      counts.attention_actions ?? 0,
      counts.failed_tasks ?? 0,
      counts.recovering_workflows ?? 0,
    ].join(":");
    if (fingerprint === lastSnapshotFingerprint) return;
    lastSnapshotFingerprint = fingerprint;
    void refresh();
  };

  const onInteraction = (event: Event): void => {
    if (!(event instanceof CustomEvent)) return;
    interactionState =
      event.detail?.state === "thinking" ? "thinking" : "idle";
    renderBody(host, body, voiceState, interactionState);
  };

  const onVoice = (event: Event): void => {
    if (!(event instanceof CustomEvent)) return;
    voiceState = mapVoiceState(String(event.detail?.state || "idle"));
    renderBody(host, body, voiceState, interactionState);
  };

  const onView = (): void => {
    renderBody(host, body, voiceState, interactionState);
  };

  window.addEventListener("miyori:nexus-snapshot", onSnapshot);
  window.addEventListener("miyori:interaction-state", onInteraction);
  window.addEventListener("miyori:voice-state", onVoice);
  window.addEventListener("miyori:nexus-view", onView);

  void refresh();

  return () => {
    stopped = true;
    generation += 1;
    window.removeEventListener("miyori:nexus-snapshot", onSnapshot);
    window.removeEventListener("miyori:interaction-state", onInteraction);
    window.removeEventListener("miyori:voice-state", onVoice);
    window.removeEventListener("miyori:nexus-view", onView);
  };
}
