import { NEXUS_ACTION_SCHEMA_VERSION, NEXUS_KNOWLEDGE_SCHEMA_VERSION, NEXUS_SURFACE_SCHEMA_VERSION, NEXUS_PRESENCE_SCHEMA_VERSION, NEXUS_PROACTIVE_SCHEMA_VERSION, NEXUS_EVENT_SCHEMA_VERSION, NEXUS_SCHEMA_VERSION, isNexusActionState, isNexusEventSeverity, isNexusOperationalState, } from "./contracts.js";
function validateProjectId(projectId) {
    if (!Number.isInteger(projectId) || projectId <= 0) {
        throw new Error("Некорректный projectId для MIYORI NEXUS.");
    }
}
export async function fetchNexusSnapshot(projectId) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/nexus`, {
        headers: { Accept: "application/json" },
    });
    if (!response.ok) {
        throw new Error(`NEXUS API: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    if (payload.schema_version !== NEXUS_SCHEMA_VERSION) {
        throw new Error("Несовместимая версия NEXUS API.");
    }
    if (!isNexusOperationalState(payload.overall_state)) {
        throw new Error("NEXUS API вернул неизвестное состояние системы.");
    }
    if (!Array.isArray(payload.modules)) {
        throw new Error("NEXUS API не вернул список модулей.");
    }
    for (const module of payload.modules) {
        if (!module || !isNexusOperationalState(module.state)) {
            throw new Error("NEXUS API вернул некорректное состояние модуля.");
        }
    }
    return payload;
}
export async function fetchNexusEvents(projectId, options = {}) {
    validateProjectId(projectId);
    const params = new URLSearchParams();
    if (options.after)
        params.set("after", options.after);
    if (options.limit !== undefined)
        params.set("limit", String(options.limit));
    if (options.tail)
        params.set("tail", "true");
    const query = params.size ? `?${params.toString()}` : "";
    const response = await fetch(`/api/projects/${projectId}/nexus/events${query}`, {
        headers: { Accept: "application/json" },
    });
    if (!response.ok) {
        throw new Error(`NEXUS events API: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    if (payload.schema_version !== NEXUS_EVENT_SCHEMA_VERSION) {
        throw new Error("Несовместимая версия NEXUS event API.");
    }
    if (!Array.isArray(payload.events)) {
        throw new Error("NEXUS event API не вернул список событий.");
    }
    for (const event of payload.events) {
        if (!event ||
            event.schema_version !== NEXUS_EVENT_SCHEMA_VERSION ||
            !isNexusEventSeverity(event.severity) ||
            event.project_id !== projectId) {
            throw new Error("NEXUS event API вернул некорректное событие.");
        }
    }
    return payload;
}
export async function fetchNexusActions(projectId, limit = 60) {
    validateProjectId(projectId);
    const params = new URLSearchParams({ limit: String(limit) });
    const response = await fetch(`/api/projects/${projectId}/nexus/actions?${params.toString()}`, { headers: { Accept: "application/json" } });
    if (!response.ok) {
        throw new Error(`NEXUS actions API: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    if (payload.schema_version !== NEXUS_ACTION_SCHEMA_VERSION) {
        throw new Error("Несовместимая версия NEXUS actions API.");
    }
    if (!Array.isArray(payload.actions)) {
        throw new Error("NEXUS actions API не вернул список действий.");
    }
    for (const action of payload.actions) {
        if (!action ||
            action.project_id !== projectId ||
            !isNexusActionState(action.state)) {
            throw new Error("NEXUS actions API вернул некорректное действие.");
        }
    }
    return payload;
}
export async function fetchNexusKnowledge(projectId, options = {}) {
    validateProjectId(projectId);
    const params = new URLSearchParams();
    if (options.query?.trim())
        params.set("q", options.query.trim());
    if (options.limit !== undefined)
        params.set("limit", String(options.limit));
    const suffix = params.size ? `?${params.toString()}` : "";
    const response = await fetch(`/api/projects/${projectId}/nexus/knowledge${suffix}`, { headers: { Accept: "application/json" } });
    if (!response.ok) {
        throw new Error(`NEXUS knowledge API: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    if (payload.schema_version !== NEXUS_KNOWLEDGE_SCHEMA_VERSION) {
        throw new Error("Несовместимая версия NEXUS knowledge API.");
    }
    if (!Array.isArray(payload.memory) ||
        !Array.isArray(payload.documents) ||
        !Array.isArray(payload.claims) ||
        payload.semantics?.sections_are_distinct !== true) {
        throw new Error("NEXUS knowledge API нарушил разделение источников.");
    }
    return payload;
}
export async function fetchNexusSurfaces(projectId, options = {}) {
    validateProjectId(projectId);
    const params = new URLSearchParams();
    params.set("context", options.context ?? "auto");
    if (options.query?.trim())
        params.set("q", options.query.trim());
    if (options.limit !== undefined)
        params.set("limit", String(options.limit));
    const response = await fetch(`/api/projects/${projectId}/nexus/surfaces?${params.toString()}`, { headers: { Accept: "application/json" } });
    if (!response.ok) {
        throw new Error(`NEXUS surfaces API: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    if (payload.schema_version !== NEXUS_SURFACE_SCHEMA_VERSION ||
        !Array.isArray(payload.surfaces) ||
        payload.registry?.model_html_allowed !== false ||
        payload.registry?.script_allowed !== false ||
        payload.registry?.unknown_components_rejected !== true) {
        throw new Error("NEXUS surfaces API нарушил trusted component contract.");
    }
    return payload;
}
export async function fetchNexusPresence(projectId) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/nexus/presence`, { headers: { Accept: "application/json" } });
    if (!response.ok) {
        throw new Error(`NEXUS presence API: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    if (payload.schema_version !== NEXUS_PRESENCE_SCHEMA_VERSION ||
        payload.source_contract?.authoritative !== true ||
        payload.source_contract?.random_liveness_allowed !== false ||
        payload.source_contract?.decorative_activity_allowed !== false) {
        throw new Error("NEXUS presence API нарушил authoritative state contract.");
    }
    return payload;
}
function validateProactivePage(payload) {
    if (payload.schema_version !== NEXUS_PROACTIVE_SCHEMA_VERSION ||
        !Array.isArray(payload.signals) ||
        payload.policy?.chat_interruption_allowed !== false ||
        payload.policy?.auto_execute_allowed !== false ||
        payload.policy?.write_tools_allowed !== false ||
        payload.policy?.creates_chat_messages !== false ||
        payload.policy?.persistent_dismiss_snooze !== true ||
        payload.policy?.derived_from_authoritative_state !== true) {
        throw new Error("NEXUS proactive API нарушил attention safety contract.");
    }
    return payload;
}
export async function fetchNexusProactive(projectId) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/nexus/proactive`, { headers: { Accept: "application/json" } });
    if (!response.ok) {
        throw new Error(`NEXUS proactive API: HTTP ${response.status}`);
    }
    return validateProactivePage((await response.json()));
}
export async function dismissNexusProactive(projectId, signalId) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/nexus/proactive/${encodeURIComponent(signalId)}/dismiss`, { method: "POST", headers: { Accept: "application/json" } });
    if (!response.ok) {
        throw new Error(`NEXUS proactive dismiss: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    return validateProactivePage(payload.proactive ?? {});
}
export async function snoozeNexusProactive(projectId, signalId, minutes = 60) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/nexus/proactive/${encodeURIComponent(signalId)}/snooze`, {
        method: "POST",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ minutes }),
    });
    if (!response.ok) {
        throw new Error(`NEXUS proactive snooze: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    return validateProactivePage(payload.proactive ?? {});
}
