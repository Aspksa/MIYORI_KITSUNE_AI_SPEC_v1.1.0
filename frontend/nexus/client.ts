import {
  NEXUS_ACTION_SCHEMA_VERSION,
  NEXUS_KNOWLEDGE_SCHEMA_VERSION,
  NEXUS_SURFACE_SCHEMA_VERSION,
  NEXUS_PRESENCE_SCHEMA_VERSION,
  NEXUS_PROACTIVE_SCHEMA_VERSION,
  NEXUS_VOICE_SCHEMA_VERSION,
  NEXUS_AGENT_WORKSPACE_SCHEMA_VERSION,
  NEXUS_EVENT_SCHEMA_VERSION,
  NEXUS_SCHEMA_VERSION,
  isNexusActionState,
  isNexusEventSeverity,
  isNexusOperationalState,
  type NexusActionCenter,
  type NexusKnowledgeCenter,
  type NexusSurfacePage,
  type NexusPresence,
  type NexusProactivePage,
  type NexusProactiveSignal,
  type NexusVoiceContract,
  type NexusAgentWorkspace,
  type NexusAgentWorkspaceSummary,
  type NexusEventPage,
  type NexusSnapshot,
} from "./contracts.js";

function validateProjectId(projectId: number): void {
  if (!Number.isInteger(projectId) || projectId <= 0) {
    throw new Error("Некорректный projectId для MIYORI NEXUS.");
  }
}

export async function fetchNexusSnapshot(projectId: number): Promise<NexusSnapshot> {
  validateProjectId(projectId);

  const response = await fetch(`/api/projects/${projectId}/nexus`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`NEXUS API: HTTP ${response.status}`);
  }

  const payload = (await response.json()) as Partial<NexusSnapshot>;
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
  return payload as NexusSnapshot;
}

export async function fetchNexusEvents(
  projectId: number,
  options: { after?: string | null; limit?: number; tail?: boolean } = {},
): Promise<NexusEventPage> {
  validateProjectId(projectId);
  const params = new URLSearchParams();
  if (options.after) params.set("after", options.after);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.tail) params.set("tail", "true");

  const query = params.size ? `?${params.toString()}` : "";
  const response = await fetch(`/api/projects/${projectId}/nexus/events${query}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`NEXUS events API: HTTP ${response.status}`);
  }

  const payload = (await response.json()) as Partial<NexusEventPage>;
  if (payload.schema_version !== NEXUS_EVENT_SCHEMA_VERSION) {
    throw new Error("Несовместимая версия NEXUS event API.");
  }
  if (!Array.isArray(payload.events)) {
    throw new Error("NEXUS event API не вернул список событий.");
  }
  for (const event of payload.events) {
    if (
      !event ||
      event.schema_version !== NEXUS_EVENT_SCHEMA_VERSION ||
      !isNexusEventSeverity(event.severity) ||
      event.project_id !== projectId
    ) {
      throw new Error("NEXUS event API вернул некорректное событие.");
    }
  }
  return payload as NexusEventPage;
}

export async function fetchNexusActions(
  projectId: number,
  limit = 60,
): Promise<NexusActionCenter> {
  validateProjectId(projectId);
  const params = new URLSearchParams({ limit: String(limit) });
  const response = await fetch(
    `/api/projects/${projectId}/nexus/actions?${params.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(`NEXUS actions API: HTTP ${response.status}`);
  }

  const payload = (await response.json()) as Partial<NexusActionCenter>;
  if (payload.schema_version !== NEXUS_ACTION_SCHEMA_VERSION) {
    throw new Error("Несовместимая версия NEXUS actions API.");
  }
  if (!Array.isArray(payload.actions)) {
    throw new Error("NEXUS actions API не вернул список действий.");
  }
  for (const action of payload.actions) {
    if (
      !action ||
      action.project_id !== projectId ||
      !isNexusActionState(action.state)
    ) {
      throw new Error("NEXUS actions API вернул некорректное действие.");
    }
  }
  return payload as NexusActionCenter;
}

export async function fetchNexusKnowledge(
  projectId: number,
  options: { query?: string; limit?: number } = {},
): Promise<NexusKnowledgeCenter> {
  validateProjectId(projectId);
  const params = new URLSearchParams();
  if (options.query?.trim()) params.set("q", options.query.trim());
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  const suffix = params.size ? `?${params.toString()}` : "";
  const response = await fetch(
    `/api/projects/${projectId}/nexus/knowledge${suffix}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(`NEXUS knowledge API: HTTP ${response.status}`);
  }

  const payload = (await response.json()) as Partial<NexusKnowledgeCenter>;
  if (payload.schema_version !== NEXUS_KNOWLEDGE_SCHEMA_VERSION) {
    throw new Error("Несовместимая версия NEXUS knowledge API.");
  }
  if (
    !Array.isArray(payload.memory) ||
    !Array.isArray(payload.documents) ||
    !Array.isArray(payload.claims) ||
    payload.semantics?.sections_are_distinct !== true
  ) {
    throw new Error("NEXUS knowledge API нарушил разделение источников.");
  }
  return payload as NexusKnowledgeCenter;
}

export async function fetchNexusSurfaces(
  projectId: number,
  options: {
    context?: "auto" | "chat" | "actions" | "knowledge" | "system";
    query?: string;
    limit?: number;
  } = {},
): Promise<NexusSurfacePage> {
  validateProjectId(projectId);
  const params = new URLSearchParams();
  params.set("context", options.context ?? "auto");
  if (options.query?.trim()) params.set("q", options.query.trim());
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  const response = await fetch(
    `/api/projects/${projectId}/nexus/surfaces?${params.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(`NEXUS surfaces API: HTTP ${response.status}`);
  }

  const payload = (await response.json()) as Partial<NexusSurfacePage>;
  if (
    payload.schema_version !== NEXUS_SURFACE_SCHEMA_VERSION ||
    !Array.isArray(payload.surfaces) ||
    payload.registry?.model_html_allowed !== false ||
    payload.registry?.script_allowed !== false ||
    payload.registry?.unknown_components_rejected !== true
  ) {
    throw new Error("NEXUS surfaces API нарушил trusted component contract.");
  }
  return payload as NexusSurfacePage;
}

export async function fetchNexusPresence(
  projectId: number,
): Promise<NexusPresence> {
  validateProjectId(projectId);
  const response = await fetch(
    `/api/projects/${projectId}/nexus/presence`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(`NEXUS presence API: HTTP ${response.status}`);
  }
  const payload = (await response.json()) as Partial<NexusPresence>;
  if (
    payload.schema_version !== NEXUS_PRESENCE_SCHEMA_VERSION ||
    payload.source_contract?.authoritative !== true ||
    payload.source_contract?.random_liveness_allowed !== false ||
    payload.source_contract?.decorative_activity_allowed !== false
  ) {
    throw new Error("NEXUS presence API нарушил authoritative state contract.");
  }
  return payload as NexusPresence;
}

function validateProactivePage(
  payload: Partial<NexusProactivePage>,
): NexusProactivePage {
  if (
    payload.schema_version !== NEXUS_PROACTIVE_SCHEMA_VERSION ||
    !Array.isArray(payload.signals) ||
    !Array.isArray(payload.display?.chat_shelf_ids) ||
    payload.policy?.auto_execute_allowed !== false ||
    payload.policy?.write_action_allowed !== false ||
    payload.policy?.chat_message_injection_allowed !== false ||
    payload.policy?.interrupt_user_allowed !== false ||
    payload.policy?.os_notification_allowed !== false ||
    payload.policy?.operational_blockers_owned_by_presence !== true ||
    payload.policy?.decisions_change_signal_visibility_only !== true
  ) {
    throw new Error("NEXUS proactive API нарушил attention safety contract.");
  }
  return payload as NexusProactivePage;
}

export async function fetchNexusProactive(
  projectId: number,
): Promise<NexusProactivePage> {
  validateProjectId(projectId);
  const response = await fetch(
    `/api/projects/${projectId}/nexus/proactive`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(`NEXUS proactive API: HTTP ${response.status}`);
  }
  return validateProactivePage(
    (await response.json()) as Partial<NexusProactivePage>,
  );
}

async function decideNexusProactive(
  projectId: number,
  signal: Pick<NexusProactiveSignal, "signal_key" | "fingerprint">,
  decision: "dismissed" | "snoozed",
  snoozeMinutes?: number,
): Promise<NexusProactivePage> {
  validateProjectId(projectId);
  const body: Record<string, unknown> = {
    signal_key: signal.signal_key,
    fingerprint: signal.fingerprint,
    decision,
  };
  if (decision === "snoozed") {
    body.snooze_minutes = snoozeMinutes ?? 60;
  }

  const response = await fetch(
    `/api/projects/${projectId}/nexus/proactive/decision`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    throw new Error(`NEXUS proactive decision: HTTP ${response.status}`);
  }
  const payload = (await response.json()) as {
    proactive?: Partial<NexusProactivePage>;
  };
  return validateProactivePage(payload.proactive ?? {});
}

export async function dismissNexusProactive(
  projectId: number,
  signal: Pick<NexusProactiveSignal, "signal_key" | "fingerprint">,
): Promise<NexusProactivePage> {
  return decideNexusProactive(projectId, signal, "dismissed");
}

export async function snoozeNexusProactive(
  projectId: number,
  signal: Pick<NexusProactiveSignal, "signal_key" | "fingerprint">,
  minutes = 60,
): Promise<NexusProactivePage> {
  return decideNexusProactive(projectId, signal, "snoozed", minutes);
}

export async function fetchNexusVoice(
  projectId: number,
): Promise<NexusVoiceContract> {
  validateProjectId(projectId);
  const response = await fetch(`/api/projects/${projectId}/nexus/voice`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`NEXUS voice API: HTTP ${response.status}`);
  }
  const payload = (await response.json()) as Partial<NexusVoiceContract>;
  if (
    payload.schema_version !== NEXUS_VOICE_SCHEMA_VERSION ||
    !Array.isArray(payload.protocol?.states) ||
    payload.permissions?.background_recording_allowed !== false ||
    payload.safety?.voice_can_bypass_action_permissions !== false ||
    payload.safety?.voice_can_auto_approve_actions !== false ||
    payload.safety?.voice_can_auto_execute_write_tools !== false ||
    payload.safety?.final_transcript_uses_existing_chat_pipeline !== true ||
    payload.transport?.server_audio_storage !== false
  ) {
    throw new Error("NEXUS voice API нарушил Voice safety contract.");
  }
  return payload as NexusVoiceContract;
}

function validateAgentWorkspace(value: unknown): NexusAgentWorkspace {
  const workspace = value as Partial<NexusAgentWorkspace> | null;
  if (
    !workspace ||
    workspace.schema_version !== NEXUS_AGENT_WORKSPACE_SCHEMA_VERSION ||
    !Array.isArray(workspace.nodes) ||
    typeof workspace.id !== "number"
  ) {
    throw new Error("NEXUS Agent Workspace API вернул некорректный contract.");
  }
  return workspace as NexusAgentWorkspace;
}

export async function fetchNexusAgentWorkspaces(
  projectId: number,
): Promise<NexusAgentWorkspaceSummary[]> {
  validateProjectId(projectId);
  const response = await fetch(`/api/projects/${projectId}/agent-workspaces`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Agent Workspace API: HTTP ${response.status}`);
  }
  const payload = (await response.json()) as { workspaces?: NexusAgentWorkspaceSummary[] };
  return Array.isArray(payload.workspaces) ? payload.workspaces : [];
}

export async function fetchNexusAgentWorkspace(
  projectId: number,
  workspaceId: number,
): Promise<NexusAgentWorkspace> {
  validateProjectId(projectId);
  const response = await fetch(
    `/api/projects/${projectId}/agent-workspaces/${workspaceId}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(`Agent Workspace API: HTTP ${response.status}`);
  }
  const payload = (await response.json()) as { workspace?: NexusAgentWorkspace };
  return validateAgentWorkspace(payload.workspace);
}

export async function createNexusAgentWorkspace(
  projectId: number,
  goal: string,
  maxParallel = 2,
): Promise<NexusAgentWorkspace> {
  validateProjectId(projectId);
  const response = await fetch(`/api/projects/${projectId}/agent-workspaces`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ goal, max_parallel: maxParallel }),
  });
  if (!response.ok) {
    throw new Error(`Agent Workspace create: HTTP ${response.status}`);
  }
  const payload = (await response.json()) as { workspace?: NexusAgentWorkspace };
  return validateAgentWorkspace(payload.workspace);
}

export async function runNexusAgentWorkspace(
  projectId: number,
  workspaceId: number,
): Promise<NexusAgentWorkspace> {
  validateProjectId(projectId);
  const response = await fetch(
    `/api/projects/${projectId}/agent-workspaces/${workspaceId}/run`,
    { method: "POST", headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(`Agent Workspace run: HTTP ${response.status}`);
  }
  const payload = (await response.json()) as { workspace?: NexusAgentWorkspace };
  return validateAgentWorkspace(payload.workspace);
}

export async function cancelNexusAgentWorkspace(
  projectId: number,
  workspaceId: number,
): Promise<NexusAgentWorkspace> {
  validateProjectId(projectId);
  const response = await fetch(
    `/api/projects/${projectId}/agent-workspaces/${workspaceId}/cancel`,
    { method: "POST", headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(`Agent Workspace cancel: HTTP ${response.status}`);
  }
  const payload = (await response.json()) as { workspace?: NexusAgentWorkspace };
  return validateAgentWorkspace(payload.workspace);
}

export async function fetchNexusHome(
  projectId: number,
): Promise<NexusHomeCenter> {
  validateProjectId(projectId);
  const response = await fetch(`/api/projects/${projectId}/nexus/home`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`NEXUS Home API: HTTP ${response.status}`);
  }
  const payload = (await response.json()) as Partial<NexusHomeCenter>;
  if (
    payload.schema_version !== NEXUS_HOME_SCHEMA_VERSION ||
    !Array.isArray(payload.devices) ||
    !Array.isArray(payload.parental_profiles) ||
    payload.policy?.connectivity_source !== "authenticated_heartbeat" ||
    payload.policy?.legacy_status_is_connectivity_source !== false ||
    payload.policy?.network_scanning_enabled !== false ||
    payload.policy?.parental_rules_require_explicit_binding !== true ||
    payload.policy?.parental_rules_applied_by_server !== false ||
    payload.policy?.device_commands_enabled !== false
  ) {
    throw new Error("NEXUS Home API нарушил device evidence contract.");
  }
  return payload as NexusHomeCenter;
}
