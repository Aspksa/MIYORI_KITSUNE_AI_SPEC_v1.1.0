const FOCUSABLE = [
    "button:not([disabled])",
    "a[href]",
    "input:not([disabled]):not([type='hidden'])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
].join(",");
function visible(element) {
    return !element.hidden && element.getClientRects().length > 0;
}
function focusables(dialog) {
    return Array.from(dialog.querySelectorAll(FOCUSABLE)).filter(visible);
}
function activeOverlay() {
    const overlays = Array.from(document.querySelectorAll(".settings-overlay:not([hidden])"));
    return overlays.at(-1) ?? null;
}
export function installDialogAccessibility() {
    const returnFocus = new WeakMap();
    const onOpened = (overlay) => {
        const current = document.activeElement;
        if (current instanceof HTMLElement && current !== document.body) {
            returnFocus.set(overlay, current);
        }
        const dialog = overlay.querySelector("[role='dialog']");
        if (!dialog)
            return;
        const candidates = focusables(dialog);
        if (candidates.length) {
            candidates[0]?.focus({ preventScroll: true });
            return;
        }
        dialog.tabIndex = -1;
        dialog.focus({ preventScroll: true });
    };
    const onClosed = (overlay) => {
        const target = returnFocus.get(overlay);
        if (target?.isConnected) {
            target.focus({ preventScroll: true });
        }
        returnFocus.delete(overlay);
    };
    const observer = new MutationObserver((records) => {
        for (const record of records) {
            if (record.type !== "attributes" || record.attributeName !== "hidden")
                continue;
            const overlay = record.target;
            if (!(overlay instanceof HTMLElement) || !overlay.classList.contains("settings-overlay")) {
                continue;
            }
            if (overlay.hidden)
                onClosed(overlay);
            else
                onOpened(overlay);
        }
    });
    for (const overlay of Array.from(document.querySelectorAll(".settings-overlay"))) {
        observer.observe(overlay, { attributes: true, attributeFilter: ["hidden"] });
    }
    const onKeyDown = (event) => {
        const overlay = activeOverlay();
        if (!overlay)
            return;
        const dialog = overlay.querySelector("[role='dialog']");
        if (!dialog)
            return;
        if (event.key === "Escape") {
            const closeButton = dialog.querySelector("button[aria-label='Закрыть'], button.sheet-close");
            if (closeButton && !closeButton.disabled) {
                event.preventDefault();
                closeButton.click();
            }
            return;
        }
        if (event.key !== "Tab")
            return;
        const candidates = focusables(dialog);
        if (!candidates.length) {
            event.preventDefault();
            dialog.focus();
            return;
        }
        const first = candidates[0];
        const last = candidates[candidates.length - 1];
        if (!first || !last)
            return;
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        }
        else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => {
        observer.disconnect();
        document.removeEventListener("keydown", onKeyDown, true);
    };
}
export function installDisclosureAccessibility() {
    const header = document.getElementById("consoleHeader");
    const consolePanel = document.getElementById("miyoriConsole");
    if (!(header instanceof HTMLButtonElement) || !(consolePanel instanceof HTMLElement)) {
        return () => undefined;
    }
    const sync = () => {
        const expanded = !consolePanel.classList.contains("collapsed") && !consolePanel.hidden;
        header.setAttribute("aria-expanded", String(expanded));
    };
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(consolePanel, {
        attributes: true,
        attributeFilter: ["class", "hidden"],
    });
    return () => observer.disconnect();
}
