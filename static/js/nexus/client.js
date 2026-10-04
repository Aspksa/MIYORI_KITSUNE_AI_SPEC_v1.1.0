import { NEXUS_ACTION_SCHEMA_VERSION, NEXUS_KNOWLEDGE_SCHEMA_VERSION, NEXUS_SURFACE_SCHEMA_VERSION, NEXUS_PRESENCE_SCHEMA_VERSION, NEXUS_PROACTIVE_SCHEMA_VERSION, NEXUS_VOICE_SCHEMA_VERSION, NEXUS_AGENT_WORKSPACE_SCHEMA_VERSION, NEXUS_HOME_SCHEMA_VERSION, NEXUS_BODY_SCHEMA_VERSION, NEXUS_EVENT_SCHEMA_VERSION, NEXUS_SCHEMA_VERSION, isNexusActionState, isNexusEventSeverity, isNexusOperationalState, } from "./contracts.js";
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
        !Array.isArray(payload.display?.chat_shelf_ids) ||
        payload.policy?.auto_execute_allowed !== false ||
        payload.policy?.write_action_allowed !== false ||
        payload.policy?.chat_message_injection_allowed !== false ||
        payload.policy?.interrupt_user_allowed !== false ||
        payload.policy?.os_notification_allowed !== false ||
        payload.policy?.operational_blockers_owned_by_presence !== true ||
        payload.policy?.decisions_change_signal_visibility_only !== true) {
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
async function decideNexusProactive(projectId, signal, decision, snoozeMinutes) {
    validateProjectId(projectId);
    const body = {
        signal_key: signal.signal_key,
        fingerprint: signal.fingerprint,
        decision,
    };
    if (decision === "snoozed") {
        body.snooze_minutes = snoozeMinutes ?? 60;
    }
    const response = await fetch(`/api/projects/${projectId}/nexus/proactive/decision`, {
        method: "POST",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        throw new Error(`NEXUS proactive decision: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    return validateProactivePage(payload.proactive ?? {});
}
export async function dismissNexusProactive(projectId, signal) {
    return decideNexusProactive(projectId, signal, "dismissed");
}
export async function snoozeNexusProactive(projectId, signal, minutes = 60) {
    return decideNexusProactive(projectId, signal, "snoozed", minutes);
}
export async function fetchNexusVoice(projectId) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/nexus/voice`, {
        headers: { Accept: "application/json" },
    });
    if (!response.ok) {
        throw new Error(`NEXUS voice API: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    if (payload.schema_version !== NEXUS_VOICE_SCHEMA_VERSION ||
        !Array.isArray(payload.protocol?.states) ||
        payload.permissions?.background_recording_allowed !== false ||
        payload.safety?.voice_can_bypass_action_permissions !== false ||
        payload.safety?.voice_can_auto_approve_actions !== false ||
        payload.safety?.voice_can_auto_execute_write_tools !== false ||
        payload.safety?.final_transcript_uses_existing_chat_pipeline !== true ||
        payload.transport?.server_audio_storage !== false) {
        throw new Error("NEXUS voice API нарушил Voice safety contract.");
    }
    return payload;
}
function validateAgentWorkspace(value) {
    const workspace = value;
    if (!workspace ||
        workspace.schema_version !== NEXUS_AGENT_WORKSPACE_SCHEMA_VERSION ||
        !Array.isArray(workspace.nodes) ||
        typeof workspace.id !== "number") {
        throw new Error("NEXUS Agent Workspace API вернул некорректный contract.");
    }
    return workspace;
}
export async function fetchNexusAgentWorkspaces(projectId) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/agent-workspaces`, {
        headers: { Accept: "application/json" },
    });
    if (!response.ok) {
        throw new Error(`Agent Workspace API: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    return Array.isArray(payload.workspaces) ? payload.workspaces : [];
}
export async function fetchNexusAgentWorkspace(projectId, workspaceId) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/agent-workspaces/${workspaceId}`, { headers: { Accept: "application/json" } });
    if (!response.ok) {
        throw new Error(`Agent Workspace API: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    return validateAgentWorkspace(payload.workspace);
}
export async function createNexusAgentWorkspace(projectId, goal, maxParallel = 2) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/agent-workspaces`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ goal, max_parallel: maxParallel }),
    });
    if (!response.ok) {
        throw new Error(`Agent Workspace create: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    return validateAgentWorkspace(payload.workspace);
}
export async function runNexusAgentWorkspace(projectId, workspaceId) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/agent-workspaces/${workspaceId}/run`, { method: "POST", headers: { Accept: "application/json" } });
    if (!response.ok) {
        throw new Error(`Agent Workspace run: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    return validateAgentWorkspace(payload.workspace);
}
export async function cancelNexusAgentWorkspace(projectId, workspaceId) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/agent-workspaces/${workspaceId}/cancel`, { method: "POST", headers: { Accept: "application/json" } });
    if (!response.ok) {
        throw new Error(`Agent Workspace cancel: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    return validateAgentWorkspace(payload.workspace);
}
export async function fetchNexusHome(projectId) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/nexus/home`, {
        headers: { Accept: "application/json" },
    });
    if (!response.ok) {
        throw new Error(`NEXUS Home API: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    if (payload.schema_version !== NEXUS_HOME_SCHEMA_VERSION ||
        !Array.isArray(payload.devices) ||
        !Array.isArray(payload.parental_profiles) ||
        payload.policy?.connectivity_source !== "authenticated_heartbeat" ||
        payload.policy?.legacy_status_is_connectivity_source !== false ||
        payload.policy?.network_scanning_enabled !== false ||
        payload.policy?.parental_rules_require_explicit_binding !== true ||
        payload.policy?.parental_rules_applied_by_server !== false ||
        payload.policy?.device_commands_enabled !== false) {
        throw new Error("NEXUS Home API нарушил device evidence contract.");
    }
    return payload;
}
export async function fetchNexusBody(projectId) {
    validateProjectId(projectId);
    const response = await fetch(`/api/projects/${projectId}/nexus/body`, {
        headers: { Accept: "application/json" },
    });
    if (!response.ok) {
        throw new Error(`NEXUS body API: HTTP ${response.status}`);
    }
    const payload = (await response.json());
    if (payload.schema_version !== NEXUS_BODY_SCHEMA_VERSION ||
        !payload.presentation ||
        !payload.appearance ||
        !Array.isArray(payload.appearance.confirmed) ||
        !Array.isArray(payload.appearance.open_for_owner_choice) ||
        payload.runtime?.source !== "nexus_presence" ||
        payload.motion_policy?.random_liveness_allowed !== false ||
        payload.motion_policy?.timer_idle_animation_allowed !== false ||
        payload.motion_policy?.sentiment_to_expression_allowed !== false ||
        payload.motion_policy?.model_authored_motion_allowed !== false ||
        payload.render_policy?.invent_open_appearance_choices_allowed !== false ||
        payload.render_policy?.body_state_source !== "presence_plus_explicit_local_runtime") {
        throw new Error("NEXUS Digital Body API нарушил runtime truth contract.");
    }
    return payload;
}
