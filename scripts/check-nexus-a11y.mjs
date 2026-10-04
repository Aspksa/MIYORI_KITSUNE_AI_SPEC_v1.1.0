import { readFileSync } from "node:fs";

const html = readFileSync("templates/index.html", "utf8");
const css = readFileSync("static/css/nexus.css", "utf8");
const errors = [];

const dialogCount = (html.match(/role="dialog"/g) ?? []).length;
const modalCount = (html.match(/aria-modal="true"/g) ?? []).length;
if (dialogCount === 0 || dialogCount !== modalCount) {
  errors.push(`dialogs=${dialogCount}, aria-modal=${modalCount}`);
}
if (!html.includes('id="messages" class="messages" aria-live="polite"')) {
  errors.push("messages must expose aria-live=polite");
}
if (!html.includes('id="errorBox" class="error" role="alert" aria-live="assertive"')) {
  errors.push("errorBox must expose alert semantics");
}
if (!html.includes('type="module" src="/static/js/nexus/index.js')) {
  errors.push("compiled NEXUS module is not loaded");
}
if (!css.includes(":focus-visible")) {
  errors.push("focus-visible styling is missing");
}
if (!css.includes("prefers-reduced-motion: reduce")) {
  errors.push("reduced-motion handling is missing");
}

if (errors.length) {
  console.error("NEXUS accessibility contract failed:\n- " + errors.join("\n- "));
  process.exit(1);
}
console.log(`NEXUS accessibility contract OK (${dialogCount} dialogs).`);
