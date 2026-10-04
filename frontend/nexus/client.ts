import {
  NEXUS_ACTION_SCHEMA_VERSION,
  NEXUS_EVENT_SCHEMA_VERSION,
  NEXUS_SCHEMA_VERSION,
  isNexusActionState,
  isNexusEventSeverity,
  isNexusOperationalState,
  type NexusActionCenter,
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
