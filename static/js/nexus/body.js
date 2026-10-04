import { fetchNexusBody, removeMiyoriPortrait, updateMiyoriAppearance, uploadMiyoriPortrait, } from "./client.js";
import { renderTrustedBodyVisual } from "./body_renderer.js";
function currentProjectId() {
    const select = document.getElementById("projectSelect");
    const value = Number(select?.value);
    return Number.isInteger(value) && value > 0 ? value : null;
}
function currentView() {
    return String(document.documentElement.dataset.nexusView || "chat");
}
function effectiveLocalState(voice, interaction) {
    if (voice !== "idle")
        return voice;
    return interaction;
}
function presentationFor(body, local) {
    if (local !== "idle") {
        const override = body.local_override_contract.presentations[local];
        if (override)
            return override;
    }
    return body.presentation;
}
function appendTextList(host, title, values) {
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
function appearanceStateText(body) {
    if (body.renderer.selected_adapter === "trusted_character_rig") {
        const selected = [
            body.appearance.selections.hair_color,
            body.appearance.selections.eye_color,
            body.appearance.selections.tail_count,
            body.appearance.selections.main_outfit,
        ].filter((value) => value !== null && value !== "").length;
        return selected === 4
            ? "Персонаж Миёри активен · внешность выбрана владельцем"
            : `Персонаж Миёри активен · выбрано параметров: ${selected}/4`;
    }
    if (body.renderer.selected_adapter === "trusted_vector_rig") {
        return body.appearance.configuration_state === "appearance_unconfigured"
            ? "Динамическое тело активно · внешность нейтральная"
            : "Динамическое тело активно · выбранные параметры сохранены";
    }
    if (body.appearance.configuration_state === "appearance_configured") {
        return body.appearance.asset.kind === "static_portrait"
            ? "Внешность выбрана · статический портрет"
            : "Внешность выбрана · портрет не загружен";
    }
    if (body.appearance.configuration_state === "appearance_partial") {
        return "Внешность настроена частично";
    }
    return "Внешность ждёт вашего выбора";
}
function createTextField(labelText, value, maxLength) {
    const wrapper = document.createElement("label");
    wrapper.className = "nexus-body-field";
    const label = document.createElement("span");
    label.textContent = labelText;
    const input = document.createElement("input");
    input.type = "text";
    input.maxLength = maxLength;
    input.value = value ?? "";
    input.placeholder = "Не выбрано";
    wrapper.append(label, input);
    return { wrapper, input };
}
function buildAppearanceEditor(body, actions) {
    const details = document.createElement("details");
    details.className = "nexus-body-appearance-editor";
    const summary = document.createElement("summary");
    summary.textContent = "Настроить внешность";
    details.appendChild(summary);
    const panel = document.createElement("div");
    panel.className = "nexus-body-appearance-panel";
    const explanation = document.createElement("p");
    explanation.textContent =
        "Это ваши четыре открытых параметра Persona Pack. Пустые поля остаются невыбранными; Miyori не подставляет значения автоматически.";
    panel.appendChild(explanation);
    const form = document.createElement("form");
    form.className = "nexus-body-appearance-form";
    const hair = createTextField("Цвет волос", body.appearance.selections.hair_color, 80);
    const eyes = createTextField("Цвет глаз", body.appearance.selections.eye_color, 80);
    const tailsWrapper = document.createElement("label");
    tailsWrapper.className = "nexus-body-field";
    const tailsLabel = document.createElement("span");
    tailsLabel.textContent = "Точное число хвостов";
    const tails = document.createElement("input");
    tails.type = "number";
    tails.min = "1";
    tails.step = "1";
    tails.inputMode = "numeric";
    tails.value =
        body.appearance.selections.tail_count === null
            ? ""
            : String(body.appearance.selections.tail_count);
    tails.placeholder = "Не выбрано";
    tailsWrapper.append(tailsLabel, tails);
    const outfitWrapper = document.createElement("label");
    outfitWrapper.className = "nexus-body-field wide";
    const outfitLabel = document.createElement("span");
    outfitLabel.textContent = "Основной наряд";
    const outfit = document.createElement("textarea");
    outfit.rows = 2;
    outfit.maxLength = 500;
    outfit.value = body.appearance.selections.main_outfit ?? "";
    outfit.placeholder = "Не выбрано";
    outfitWrapper.append(outfitLabel, outfit);
    form.append(hair.wrapper, eyes.wrapper, tailsWrapper, outfitWrapper);
    const status = document.createElement("div");
    status.className = "nexus-body-editor-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const save = document.createElement("button");
    save.type = "submit";
    save.className = "primary-soft";
    save.textContent = "Сохранить выбор";
    const formActions = document.createElement("div");
    formActions.className = "nexus-body-editor-actions";
    formActions.appendChild(save);
    form.append(formActions, status);
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        const tailText = tails.value.trim();
        const tailCount = tailText ? Number(tailText) : null;
        if (tailCount !== null &&
            (!Number.isInteger(tailCount) || tailCount < 1)) {
            status.textContent = "Количество хвостов должно быть положительным целым числом.";
            return;
        }
        const selection = {
            hair_color: hair.input.value.trim() || null,
            eye_color: eyes.input.value.trim() || null,
            tail_count: tailCount,
            main_outfit: outfit.value.trim() || null,
        };
        save.disabled = true;
        status.textContent = "Сохраняю…";
        void actions.save(selection).catch((error) => {
            save.disabled = false;
            status.textContent =
                error instanceof Error ? error.message : "Не удалось сохранить внешность.";
        });
    });
    const asset = document.createElement("div");
    asset.className = "nexus-body-asset-editor";
    const assetTitle = document.createElement("strong");
    assetTitle.textContent = "Статический портрет";
    const assetNote = document.createElement("p");
    assetNote.textContent =
        "PNG/JPEG/WEBP до 5 МБ. Статический портрет не изображает pose/expression; реальные состояния остаются в индикаторе и подписи.";
    const file = document.createElement("input");
    file.type = "file";
    file.accept = "image/png,image/jpeg,image/webp";
    file.setAttribute("aria-label", "Файл портрета Миёри");
    const upload = document.createElement("button");
    upload.type = "button";
    upload.className = "secondary-sheet-button";
    upload.textContent = body.appearance.asset.kind
        ? "Заменить портрет"
        : "Загрузить портрет";
    upload.addEventListener("click", () => {
        const selected = file.files?.[0];
        if (!selected) {
            status.textContent = "Сначала выберите PNG, JPEG или WEBP.";
            return;
        }
        upload.disabled = true;
        status.textContent = "Загружаю портрет…";
        void actions.upload(selected).catch((error) => {
            upload.disabled = false;
            status.textContent =
                error instanceof Error ? error.message : "Не удалось загрузить портрет.";
        });
    });
    const assetActions = document.createElement("div");
    assetActions.className = "nexus-body-editor-actions";
    assetActions.append(file, upload);
    if (body.appearance.asset.kind) {
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "secondary-sheet-button";
        remove.textContent = "Удалить портрет";
        remove.addEventListener("click", () => {
            remove.disabled = true;
            status.textContent = "Удаляю портрет…";
            void actions.remove().catch((error) => {
                remove.disabled = false;
                status.textContent =
                    error instanceof Error ? error.message : "Не удалось удалить портрет.";
            });
        });
        assetActions.appendChild(remove);
    }
    asset.append(assetTitle, assetNote, assetActions);
    panel.append(form, asset);
    details.appendChild(panel);
    return details;
}
function renderBody(host, body, voiceState, interactionState, actions) {
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
    shell.appendChild(renderTrustedBodyVisual(body, presentation, effectiveState));
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
    appearance.textContent = appearanceStateText(body);
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
    appendTextList(bodyCanon, "Оставлено на ваш выбор", body.appearance.open_for_owner_choice);
    const note = document.createElement("p");
    note.textContent =
        "Digital Body не придумывает цвет волос, глаз, число хвостов или наряд. Статический портрет, если вы его загрузите, не выдаётся за динамический rig.";
    bodyCanon.append(note, buildAppearanceEditor(body, actions));
    canon.appendChild(bodyCanon);
    shell.appendChild(canon);
    host.appendChild(shell);
    host.hidden = false;
}
function mapVoiceState(value) {
    if (value === "error")
        return "voice_error";
    if (value === "thinking" ||
        value === "listening" ||
        value === "transcribing" ||
        value === "speaking" ||
        value === "interrupted") {
        return value;
    }
    return "idle";
}
export function installNexusDigitalBody() {
    const host = document.getElementById("nexusBodyHost");
    if (!host)
        return () => undefined;
    const bodyHost = host;
    let stopped = false;
    let generation = 0;
    let body = null;
    let voiceState = "idle";
    let interactionState = "idle";
    let lastSnapshotFingerprint = "";
    const actions = {
        save: async (selection) => {
            await updateMiyoriAppearance(selection);
            await refresh();
        },
        upload: async (file) => {
            await uploadMiyoriPortrait(file);
            await refresh();
        },
        remove: async () => {
            await removeMiyoriPortrait();
            await refresh();
        },
    };
    async function refresh() {
        if (stopped)
            return;
        const projectId = currentProjectId();
        if (!projectId) {
            body = null;
            renderBody(bodyHost, body, voiceState, interactionState, actions);
            return;
        }
        const currentGeneration = ++generation;
        try {
            const next = await fetchNexusBody(projectId);
            if (!stopped && currentGeneration === generation) {
                body = next;
                renderBody(bodyHost, body, voiceState, interactionState, actions);
            }
        }
        catch {
            if (currentGeneration === generation) {
                body = null;
                renderBody(bodyHost, body, voiceState, interactionState, actions);
            }
        }
    }
    const onSnapshot = (event) => {
        if (!(event instanceof CustomEvent))
            return;
        const snapshot = event.detail?.snapshot;
        if (!snapshot)
            return;
        const counts = snapshot.counts || {};
        const fingerprint = [
            snapshot.project.id,
            snapshot.overall_state,
            counts.active_actions ?? 0,
            counts.attention_actions ?? 0,
            counts.failed_tasks ?? 0,
            counts.recovering_workflows ?? 0,
        ].join(":");
        if (fingerprint === lastSnapshotFingerprint)
            return;
        lastSnapshotFingerprint = fingerprint;
        void refresh();
    };
    const onInteraction = (event) => {
        if (!(event instanceof CustomEvent))
            return;
        interactionState =
            event.detail?.state === "thinking" ? "thinking" : "idle";
        renderBody(bodyHost, body, voiceState, interactionState, actions);
    };
    const onVoice = (event) => {
        if (!(event instanceof CustomEvent))
            return;
        voiceState = mapVoiceState(String(event.detail?.state || "idle"));
        renderBody(bodyHost, body, voiceState, interactionState, actions);
    };
    const onView = () => {
        renderBody(bodyHost, body, voiceState, interactionState, actions);
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
