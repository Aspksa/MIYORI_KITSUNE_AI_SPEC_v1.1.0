import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const body = readFileSync("frontend/nexus/body.ts", "utf8");
const client = readFileSync("frontend/nexus/client.ts", "utf8");
const contracts = readFileSync("frontend/nexus/contracts.ts", "utf8");
const css = readFileSync("static/css/nexus.css", "utf8");

assert.ok(
  contracts.includes('MIYORI_APPEARANCE_SCHEMA_VERSION = "1.0.0"') &&
    contracts.includes("MiyoriAppearanceSelection") &&
    contracts.includes("appearance_partial") &&
    contracts.includes("appearance_configured"),
  "owner-global Appearance Profile contract is missing",
);

assert.ok(
  client.includes('fetch("/api/miyori/appearance"') &&
    client.includes("updateMiyoriAppearance") &&
    client.includes("uploadMiyoriPortrait") &&
    client.includes("removeMiyoriPortrait"),
  "typed Appearance Profile lifecycle client is missing",
);

assert.ok(
  client.includes("system_defaults_allowed !== false") &&
    client.includes("model_may_choose_owner_fields !== false") &&
    client.includes("static_portrait_may_claim_dynamic_pose !== false"),
  "appearance client must fail closed on system/model defaults and fake portrait dynamics",
);

assert.ok(
  body.includes("Настроить внешность") &&
    body.includes("Пустые поля остаются невыбранными") &&
    body.includes('input.placeholder = "Не выбрано"') &&
    body.includes('outfit.placeholder = "Не выбрано"'),
  "appearance editor must preserve empty owner choices instead of proposing defaults",
);

assert.ok(
  body.includes('asset.kind === "static_portrait"') &&
    body.includes("nexus-body-static-portrait") &&
    body.includes("Статический портрет не изображает pose/expression"),
  "static portrait adapter must disclose non-dynamic behavior",
);

assert.ok(
  body.includes("5 МБ") &&
    body.includes("image/png,image/jpeg,image/webp"),
  "portrait upload constraints must be visible",
);

assert.ok(
  !body.includes("/api/account/profile/avatar") &&
    !client.includes("/api/account/profile/avatar"),
  "Miyori appearance must stay separate from the owner account avatar",
);

assert.ok(
  !body.includes("innerHTML") &&
    !body.includes("Math.random") &&
    !body.includes("setInterval") &&
    !body.includes("setTimeout"),
  "appearance editor must remain trusted DOM and free of fake liveness",
);

assert.ok(
  css.includes("/* N12.1 — Owner Appearance Profile.") &&
    css.includes(".nexus-body-portrait.has-static-asset") &&
    !css.includes("@keyframes"),
  "Appearance Profile styling must not add fake animation",
);

console.log("NEXUS Appearance Profile contract OK.");
