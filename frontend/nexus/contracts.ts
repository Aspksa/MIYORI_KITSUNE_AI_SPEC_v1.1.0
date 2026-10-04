export const NEXUS_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_EVENT_SCHEMA_VERSION = "1.0.0" as const;

export type NexusOperationalState =
  | "disabled"
  | "not_connected"
  | "ready"
  | "processing"
  | "degraded"
  | "error";

export type NexusEventSeverity = "info" | "success" | "warning" | "error";

export interface NexusModuleState {
  id: string;
  label: string;
  state: NexusOperationalState;
  operation: string | null;
  last_result: string | null;
  limitation: string | null;
  updated_at: string | null;
}

export interface NexusSuggestion {
  kind: string;
  label: string;
  detail: string;
}

export interface NexusProjectRef {
  id: number;
  name: string;
  kind?: string;
}

export interface NexusSnapshot {
  schema_version: typeof NEXUS_SCHEMA_VERSION;
  project: NexusProjectRef;
  counts: Record<string, number>;
  suggestions: NexusSuggestion[];
  epistemic: Record<string, unknown>;
  modules: NexusModuleState[];
  overall_state: NexusOperationalState;
  generated_at: string;
}

export interface NexusEventEntity {
  type: string | null;
  id: string | null;
}

export interface NexusEventEnvelope {
  schema_version: typeof NEXUS_EVENT_SCHEMA_VERSION;
  id: string;
  source: "audit" | "workflow" | "task";
  source_id: number;
  project_id: number;
  event_type: string;
  severity: NexusEventSeverity;
  actor: string;
  summary: string;
  payload: Record<string, unknown>;
  entity: NexusEventEntity;
  workflow_id: number | null;
  task_id: number | null;
  created_at: string;
  requires_resync: boolean;
}

export interface NexusEventPage {
  schema_version: typeof NEXUS_EVENT_SCHEMA_VERSION;
  events: NexusEventEnvelope[];
  next_cursor: string | null;
  has_more: boolean;
  tail: boolean;
  resync: {
    authoritative_source: string;
    required_after_events: boolean;
  };
}

export interface NexusGenerativeSurface {
  id: string;
  kind: "status" | "progress" | "action" | "source" | "collection";
  title: string;
  description?: string;
  state?: NexusOperationalState;
  action_id?: string;
  data?: Record<string, unknown>;
}

export function isNexusOperationalState(value: unknown): value is NexusOperationalState {
  return [
    "disabled",
    "not_connected",
    "ready",
    "processing",
    "degraded",
    "error",
  ].includes(String(value));
}

export function isNexusEventSeverity(value: unknown): value is NexusEventSeverity {
  return ["info", "success", "warning", "error"].includes(String(value));
}
