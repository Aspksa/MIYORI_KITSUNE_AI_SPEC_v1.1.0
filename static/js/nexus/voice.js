import { fetchNexusVoice } from "./client.js";
function projectId() {
    const select = document.getElementById("projectSelect");
    const value = Number(select?.value);
    return Number.isInteger(value) && value > 0 ? value : null;
}
function currentView() {
    return String(document.documentElement.dataset.nexusView || "chat");
}
function stateLabel(state) {
    return {
        unavailable: "Голос недоступен",
        idle: "Готова слушать",
        listening: "Слушаю",
        transcribing: "Распознаю",
        thinking: "Думаю",
        speaking: "Говорю",
        interrupted: "Остановлено",
        error: "Ошибка голоса",
    }[state];
}
function dispatchVoiceState(state, extra = {}) {
    window.dispatchEvent(new CustomEvent("miyori:voice-state", {
        detail: { state, label: stateLabel(state), ...extra },
    }));
}
export function installNexusVoice() {
    const button = document.getElementById("voiceButton");
    const panel = document.getElementById("voicePanel");
    const status = document.getElementById("voiceStatus");
    const transcript = document.getElementById("voiceTranscript");
    const confidence = document.getElementById("voiceConfidence");
    const send = document.getElementById("voiceSend");
    const speak = document.getElementById("voiceSpeak");
    const stop = document.getElementById("voiceStop");
    const input = document.getElementById("messageInput");
    const form = document.getElementById("chatForm");
    if (!button || !panel || !status || !transcript || !confidence || !send || !speak || !stop || !input || !form) {
        return () => undefined;
    }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const hasRecognition = Boolean(Recognition);
    const hasMicrophone = Boolean(navigator.mediaDevices?.getUserMedia);
    const hasTts = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
    let recognition = null;
    let listening = false;
    let finalTranscript = "";
    let interimTranscript = "";
    let lastConfidence = null;
    let lastAssistantText = "";
    let submittedFromVoice = false;
    let speaking = false;
    let stopped = false;
    const setState = (next, options = {}) => {
        panel.dataset.state = next;
        status.textContent = options.error || stateLabel(next);
        button.dataset.state = next;
        button.setAttribute("aria-pressed", next === "listening" ? "true" : "false");
        button.title =
            next === "listening"
                ? "Остановить прослушивание"
                : "Голосовой ввод";
        if (options.transcript !== undefined) {
            transcript.textContent = options.transcript || "Скажите фразу…";
        }
        const score = options.confidence;
        confidence.textContent =
            score === null || score === undefined
                ? ""
                : `confidence ${Math.round(score * 100)}%`;
        panel.hidden = next === "idle" && !finalTranscript && !lastAssistantText;
        dispatchVoiceState(next, {
            transcript: options.transcript,
            confidence: score,
            error: options.error,
        });
    };
    const stopRecognition = (interrupted = false) => {
        if (!recognition)
            return;
        try {
            recognition.stop();
        }
        catch {
            recognition.abort();
        }
        listening = false;
        if (interrupted)
            setState("interrupted");
    };
    const cancelSpeech = (interrupted = true) => {
        if (!hasTts)
            return;
        if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
            window.speechSynthesis.cancel();
            speaking = false;
            if (interrupted)
                setState("interrupted");
        }
    };
    const ensureContract = async () => {
        const id = projectId();
        if (!id)
            return false;
        try {
            await fetchNexusVoice(id);
            return true;
        }
        catch (error) {
            setState("error", {
                error: error instanceof Error ? error.message : "Voice contract недоступен.",
            });
            return false;
        }
    };
    const requestMicrophone = async () => {
        if (!hasMicrophone)
            return false;
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            for (const track of stream.getTracks())
                track.stop();
            return true;
        }
        catch (error) {
            setState("error", {
                error: error instanceof DOMException && error.name === "NotAllowedError"
                    ? "Доступ к микрофону не разрешён."
                    : "Не удалось открыть микрофон.",
            });
            return false;
        }
    };
    const startListening = async () => {
        if (stopped || currentView() !== "chat")
            return;
        cancelSpeech(false);
        if (!(await ensureContract()))
            return;
        if (!Recognition || !hasMicrophone) {
            setState("unavailable", {
                error: !hasMicrophone
                    ? "Браузер не предоставляет безопасный доступ к микрофону."
                    : "Распознавание речи не поддерживается этим браузером.",
            });
            return;
        }
        if (!(await requestMicrophone()))
            return;
        finalTranscript = "";
        interimTranscript = "";
        lastConfidence = null;
        recognition = new Recognition();
        recognition.lang = document.documentElement.lang || "ru-RU";
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;
        recognition.addEventListener("start", () => {
            listening = true;
            setState("listening", { transcript: "Слушаю…" });
        });
        recognition.addEventListener("result", (event) => {
            interimTranscript = "";
            for (let index = event.resultIndex; index < event.results.length; index += 1) {
                const result = event.results[index];
                const alternative = result?.[0];
                if (!alternative)
                    continue;
                if (result.isFinal) {
                    finalTranscript += alternative.transcript;
                    if (Number.isFinite(alternative.confidence)) {
                        lastConfidence = alternative.confidence;
                    }
                }
                else {
                    interimTranscript += alternative.transcript;
                }
            }
            const text = (finalTranscript || interimTranscript).trim();
            setState(finalTranscript ? "transcribing" : "listening", {
                transcript: text || "Слушаю…",
                confidence: finalTranscript ? lastConfidence : null,
            });
        });
        recognition.addEventListener("error", (event) => {
            listening = false;
            const reason = event.error || event.message || "unknown";
            setState("error", { error: `Распознавание: ${reason}` });
        });
        recognition.addEventListener("end", () => {
            listening = false;
            recognition = null;
            const text = finalTranscript.trim();
            if (text) {
                input.value = text;
                input.dispatchEvent(new Event("input", { bubbles: true }));
                setState("transcribing", {
                    transcript: text,
                    confidence: lastConfidence,
                });
                send.disabled = false;
            }
            else if (panel.dataset.state !== "error") {
                setState("idle");
            }
        });
        try {
            recognition.start();
        }
        catch {
            recognition = null;
            setState("error", { error: "Не удалось запустить распознавание." });
        }
    };
    button.addEventListener("click", () => {
        if (panel.dataset.state === "speaking") {
            cancelSpeech(true);
            void startListening();
        }
        else if (listening) {
            stopRecognition(true);
        }
        else {
            void startListening();
        }
    });
    send.addEventListener("click", () => {
        const text = finalTranscript.trim();
        if (!text || !input.value.trim())
            return;
        submittedFromVoice = true;
        finalTranscript = "";
        send.disabled = true;
        form.requestSubmit();
    });
    speak.addEventListener("click", () => {
        if (!hasTts || !lastAssistantText.trim())
            return;
        cancelSpeech(false);
        const utterance = new SpeechSynthesisUtterance(lastAssistantText);
        utterance.lang = document.documentElement.lang || "ru-RU";
        utterance.addEventListener("start", () => {
            speaking = true;
            setState("speaking");
        });
        utterance.addEventListener("end", () => {
            speaking = false;
            setState("idle");
        });
        utterance.addEventListener("error", () => {
            speaking = false;
            setState("error", { error: "Не удалось озвучить ответ." });
        });
        window.speechSynthesis.speak(utterance);
    });
    stop.addEventListener("click", () => {
        stopRecognition(true);
        cancelSpeech(true);
    });
    const onAssistant = (event) => {
        if (!(event instanceof CustomEvent))
            return;
        const text = String(event.detail?.text || "").trim();
        if (!text)
            return;
        lastAssistantText = text;
        speak.disabled = !hasTts;
        if (submittedFromVoice) {
            submittedFromVoice = false;
            setState("idle");
        }
    };
    const onInteraction = (event) => {
        if (!(event instanceof CustomEvent) || !submittedFromVoice)
            return;
        if (event.detail?.state === "thinking")
            setState("thinking");
    };
    const onView = () => {
        if (currentView() !== "chat") {
            stopRecognition(true);
            cancelSpeech(false);
            panel.hidden = true;
        }
    };
    window.addEventListener("miyori:assistant-message", onAssistant);
    window.addEventListener("miyori:interaction-state", onInteraction);
    window.addEventListener("miyori:nexus-view", onView);
    send.disabled = true;
    speak.disabled = !hasTts;
    if (!hasRecognition || !hasMicrophone) {
        button.setAttribute("aria-disabled", "true");
        button.title = "Голосовой ввод недоступен в этом браузере";
    }
    setState(hasRecognition && hasMicrophone ? "idle" : "unavailable");
    return () => {
        stopped = true;
        stopRecognition(false);
        cancelSpeech(false);
        window.removeEventListener("miyori:assistant-message", onAssistant);
        window.removeEventListener("miyori:interaction-state", onInteraction);
        window.removeEventListener("miyori:nexus-view", onView);
    };
}
