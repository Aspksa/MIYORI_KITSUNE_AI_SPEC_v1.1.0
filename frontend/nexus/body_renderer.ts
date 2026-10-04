import type {
  NexusBodyPresentation,
  NexusDigitalBody,
} from "./contracts.js";

function basePortrait(
  presentation: NexusBodyPresentation,
  effectiveState: string,
): HTMLDivElement {
  const portrait = document.createElement("div");
  portrait.className = "nexus-body-portrait";
  portrait.dataset.pose = presentation.pose;
  portrait.dataset.expression = presentation.expression;
  portrait.dataset.gesture = presentation.gesture;
  portrait.dataset.state = effectiveState;
  portrait.setAttribute("aria-hidden", "true");
  return portrait;
}

function appendStateMark(portrait: HTMLElement): void {
  const stateMark = document.createElement("span");
  stateMark.className = "nexus-body-state-mark";
  portrait.appendChild(stateMark);
}

function renderNeutralShell(
  presentation: NexusBodyPresentation,
  effectiveState: string,
): HTMLElement {
  const portrait = basePortrait(presentation, effectiveState);
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
  portrait.append(leftEar, rightEar, face);
  appendStateMark(portrait);
  return portrait;
}

function renderStaticPortrait(
  body: NexusDigitalBody,
  presentation: NexusBodyPresentation,
  effectiveState: string,
): HTMLElement {
  const asset = body.appearance.asset;
  if (asset.kind !== "static_portrait" || !asset.url) {
    return renderNeutralShell(presentation, effectiveState);
  }
  const portrait = basePortrait(presentation, effectiveState);
  portrait.classList.add("has-static-asset");
  const image = document.createElement("img");
  image.className = "nexus-body-static-portrait";
  image.src = asset.url;
  image.alt = "";
  image.decoding = "async";
  portrait.appendChild(image);
  appendStateMark(portrait);
  return portrait;
}

function rigPart(className: string): HTMLSpanElement {
  const part = document.createElement("span");
  part.className = className;
  return part;
}

function renderTrustedVectorRig(
  presentation: NexusBodyPresentation,
  effectiveState: string,
): HTMLElement {
  const portrait = basePortrait(presentation, effectiveState);
  portrait.classList.add("nexus-body-vector-rig");
  const rig = rigPart("nexus-rig-root");
  const torso = rigPart("nexus-rig-torso");
  const head = rigPart("nexus-rig-head");
  const leftEar = rigPart("nexus-rig-ear left");
  const rightEar = rigPart("nexus-rig-ear right");
  const face = rigPart("nexus-rig-face");
  const leftEye = rigPart("nexus-rig-eye left");
  const rightEye = rigPart("nexus-rig-eye right");
  const mouth = rigPart("nexus-rig-mouth");
  const leftArm = rigPart("nexus-rig-arm left");
  const rightArm = rigPart("nexus-rig-arm right");
  face.append(leftEye, rightEye, mouth);
  head.append(leftEar, rightEar, face);
  torso.append(leftArm, rightArm);
  rig.append(torso, head);
  portrait.appendChild(rig);
  appendStateMark(portrait);
  return portrait;
}

function safeOwnerColor(value: string | null): string | null {
  if (!value || typeof CSS === "undefined" || !CSS.supports("color", value)) {
    return null;
  }
  return value;
}

function renderTrustedCharacterRig(
  body: NexusDigitalBody,
  presentation: NexusBodyPresentation,
  effectiveState: string,
): HTMLElement {
  const portrait = basePortrait(presentation, effectiveState);
  portrait.classList.add("nexus-body-character-rig");

  const root = rigPart("miyori-character-root");
  const tails = rigPart("miyori-character-tails");
  const tailCount = body.appearance.selections.tail_count;
  if (Number.isInteger(tailCount) && Number(tailCount) > 0) {
    const capped = Math.min(Number(tailCount), 9);
    tails.dataset.ownerTailCount = String(tailCount);
    for (let index = 0; index < capped; index += 1) {
      const tail = rigPart("miyori-character-tail");
      const center = (capped - 1) / 2;
      const angle = (index - center) * 11;
      tail.style.setProperty("--tail-angle", `${angle}deg`);
      tails.appendChild(tail);
    }
  } else {
    tails.classList.add("unresolved");
    tails.appendChild(rigPart("miyori-character-tail-aura"));
  }

  const legs = rigPart("miyori-character-legs");
  legs.append(
    rigPart("miyori-character-leg left"),
    rigPart("miyori-character-leg right"),
  );

  const torso = rigPart("miyori-character-torso");
  const outfit = rigPart("miyori-character-outfit");
  if (body.appearance.selections.main_outfit) {
    outfit.dataset.ownerOutfit = body.appearance.selections.main_outfit;
  } else {
    outfit.classList.add("unresolved");
  }
  const leftArm = rigPart("miyori-character-arm left");
  const rightArm = rigPart("miyori-character-arm right");
  torso.append(outfit, leftArm, rightArm);

  const head = rigPart("miyori-character-head");
  const hair = rigPart("miyori-character-hair");
  const ownerHair = safeOwnerColor(body.appearance.selections.hair_color);
  if (ownerHair) hair.style.setProperty("--owner-hair-color", ownerHair);
  else hair.classList.add("neutral-owner-color");

  const leftEar = rigPart("miyori-character-ear left");
  const rightEar = rigPart("miyori-character-ear right");
  const face = rigPart("miyori-character-face");
  const leftEye = rigPart("miyori-character-eye left");
  const rightEye = rigPart("miyori-character-eye right");
  const ownerEyes = safeOwnerColor(body.appearance.selections.eye_color);
  if (ownerEyes) {
    leftEye.style.setProperty("--owner-eye-color", ownerEyes);
    rightEye.style.setProperty("--owner-eye-color", ownerEyes);
  } else {
    leftEye.classList.add("neutral-owner-color");
    rightEye.classList.add("neutral-owner-color");
  }
  const mouth = rigPart("miyori-character-mouth");
  face.append(leftEye, rightEye, mouth);
  head.append(hair, leftEar, rightEar, face);

  root.append(tails, legs, torso, head);
  portrait.appendChild(root);
  appendStateMark(portrait);
  return portrait;
}

export function renderTrustedBodyVisual(
  body: NexusDigitalBody,
  presentation: NexusBodyPresentation,
  effectiveState: string,
): HTMLElement {
  const selectedAdapter = String(body.renderer.selected_adapter);
  switch (selectedAdapter) {
    case "trusted_character_rig":
      return renderTrustedCharacterRig(body, presentation, effectiveState);
    case "trusted_vector_rig":
      return renderTrustedVectorRig(presentation, effectiveState);
    case "static_portrait":
      return renderStaticPortrait(body, presentation, effectiveState);
    case "neutral_shell":
    default:
      return renderNeutralShell(presentation, effectiveState);
  }
}
