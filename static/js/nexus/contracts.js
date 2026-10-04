export const NEXUS_SCHEMA_VERSION = "1.0.0";
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
