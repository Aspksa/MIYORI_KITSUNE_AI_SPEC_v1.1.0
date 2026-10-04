export const NEXUS_SCHEMA_VERSION = "1.0.0";
export const NEXUS_EVENT_SCHEMA_VERSION = "1.0.0";
export const NEXUS_ACTION_SCHEMA_VERSION = "1.0.0";
export const NEXUS_KNOWLEDGE_SCHEMA_VERSION = "1.0.0";
export const NEXUS_SURFACE_SCHEMA_VERSION = "1.0.0";
export const NEXUS_PRESENCE_SCHEMA_VERSION = "1.0.0";
export const NEXUS_PROACTIVE_SCHEMA_VERSION = "1.0.0";
export const NEXUS_VOICE_SCHEMA_VERSION = "1.0.0";
export const NEXUS_AGENT_WORKSPACE_SCHEMA_VERSION = "1.0.0";
export const NEXUS_HOME_SCHEMA_VERSION = "1.0.0";
export const NEXUS_BODY_SCHEMA_VERSION = "1.4.0";
export const BODY_RENDERER_SCHEMA_VERSION = "1.2.0";
export const MIYORI_APPEARANCE_SCHEMA_VERSION = "1.0.0";
export function isNexusOperationalState(value) {
    return [
        "disabled",
        "not_connected",
        "ready",
        "processing",
        "degraded",
        "error",
    ].includes(String(value));
}
export function isNexusEventSeverity(value) {
    return ["info", "success", "warning", "error"].includes(String(value));
}
export function isNexusActionState(value) {
    return [
        "planned",
        "waiting_permission",
        "running",
        "verifying",
        "recovery",
        "completed",
        "error",
        "cancelled",
    ].includes(String(value));
}
