import { installDialogAccessibility, installDisclosureAccessibility } from "./a11y.js";
import { installNexusShell } from "./shell.js";
import { installNexusSurfaceHost } from "./surfaces.js";
import { installNexusPresence } from "./presence.js";
import { installNexusProactive } from "./proactive.js";
import { installNexusVoice } from "./voice.js";
const NEXUS_FRONTEND_VERSION = "0.9.0";
function boot() {
    document.documentElement.dataset.nexus = "ready";
    installDialogAccessibility();
    installDisclosureAccessibility();
    installNexusShell();
    installNexusSurfaceHost();
    installNexusPresence();
    installNexusProactive();
    installNexusVoice();
    window.dispatchEvent(new CustomEvent("miyori:nexus-ready", {
        detail: { version: NEXUS_FRONTEND_VERSION },
    }));
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
}
else {
    boot();
}
