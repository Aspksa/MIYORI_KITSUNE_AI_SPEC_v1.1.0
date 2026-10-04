function basePortrait(presentation, effectiveState) {
    const portrait = document.createElement("div");
    portrait.className = "nexus-body-portrait";
    portrait.dataset.pose = presentation.pose;
    portrait.dataset.expression = presentation.expression;
    portrait.dataset.gesture = presentation.gesture;
    portrait.dataset.state = effectiveState;
    portrait.setAttribute("aria-hidden", "true");
    return portrait;
}
function appendStateMark(portrait) {
    const stateMark = document.createElement("span");
    stateMark.className = "nexus-body-state-mark";
    portrait.appendChild(stateMark);
}
function renderNeutralShell(presentation, effectiveState) {
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
function renderStaticPortrait(body, presentation, effectiveState) {
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
export function renderTrustedBodyVisual(body, presentation, effectiveState) {
    switch (body.renderer.selected_adapter) {
        case "static_portrait":
            return renderStaticPortrait(body, presentation, effectiveState);
        case "neutral_shell":
        default:
            return renderNeutralShell(presentation, effectiveState);
    }
}
