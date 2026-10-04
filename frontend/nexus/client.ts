import {
  NEXUS_SCHEMA_VERSION,
  isNexusOperationalState,
  type NexusSnapshot,
} from "./contracts.js";

export async function fetchNexusSnapshot(projectId: number): Promise<NexusSnapshot> {
  if (!Number.isInteger(projectId) || projectId <= 0) {
    throw new Error("Некорректный projectId для MIYORI NEXUS.");
  }

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
