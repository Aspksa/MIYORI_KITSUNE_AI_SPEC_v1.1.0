import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync("templates/index.html", "utf8");
const voice = readFileSync("frontend/nexus/voice.ts", "utf8");
const built = readFileSync("static/js/nexus/voice.js", "utf8");
const client = readFileSync("frontend/nexus/client.ts", "utf8");
const presence = readFileSync("frontend/nexus/presence.ts", "utf8");
const core = readFileSync("static/js/core.js", "utf8");
const css = readFileSync("static/css/nexus.css", "utf8");

assert.ok(html.includes('id="voiceButton"') && html.includes('id="voicePanel"'), "Voice controls are missing");
assert.ok(voice.includes("navigator.mediaDevices.getUserMedia({ audio: true })"), "microphone permission must be explicit");
assert.ok(voice.includes("track.stop()"), "permission probe stream must be closed");
assert.ok(voice.includes("form.requestSubmit()"), "final Voice transcript must use the existing chat form");
assert.ok(!voice.includes("fetch(\"/api/chat\""), "Voice must not create a parallel chat execution path");
assert.ok(!voice.includes("form.requestSubmit();\n    }\n\n    speak"), "Voice transcript must require explicit send button");
assert.ok(voice.includes("SpeechSynthesisUtterance") && voice.includes("speechSynthesis.cancel()"), "TTS and interruption are missing");
assert.ok(voice.includes('new CustomEvent("miyori:voice-state"'), "Voice state events are missing");
assert.ok(core.includes('new CustomEvent("miyori:assistant-message"'), "assistant messages must be available to opt-in TTS");
assert.ok(presence.includes('window.addEventListener("miyori:voice-state"'), "Living Presence must consume real Voice states");
assert.ok(client.includes("fetchNexusVoice") && client.includes("voice_can_bypass_action_permissions"), "typed Voice safety client is missing");
assert.ok(!voice.includes("setInterval") && !voice.includes("Math.random"), "Voice must not simulate activity");
assert.ok(!built.includes(".innerHTML"), "Voice renderer must not inject transcript through innerHTML");
assert.ok(css.includes("/* N5 — Voice Core.") && [...css.matchAll(/@keyframes\s+([a-zA-Z0-9_-]+)/g)].every((match) => ["miyori-character-recover", "nexus-rig-active", "nexus-rig-recover", "nexus-rig-speak"].includes(match[1])), "Voice UI must remain state-driven and animation-free");

assert.ok(
  voice.includes("Прервать ответ и говорить") &&
    voice.includes('panel.dataset.state === "speaking"') &&
    voice.includes("cancelSpeech(true)") &&
    built.includes("Прервать ответ и говорить"),
  "Voice must support explicit barge-in without pretending to hear continuously",
);

console.log("NEXUS Voice contract OK.");
