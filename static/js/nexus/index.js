import { installDialogAccessibility, installDisclosureAccessibility } from "./a11y.js";
const NEXUS_FRONTEND_VERSION = "0.1.0";
function boot() {
    document.documentElement.dataset.nexus = "ready";
    installDialogAccessibility();
    installDisclosureAccessibility();
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
