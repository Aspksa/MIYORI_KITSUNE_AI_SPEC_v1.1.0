export const NEXUS_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_EVENT_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_ACTION_SCHEMA_VERSION = "1.0.0" as const;

export type NexusOperationalState =
  | "disabled"
  | "not_connected"
  | "ready"
  | "processing"
  | "degraded"
  | "error";

export type NexusEventSeverity = "info" | "success" | "warning" | "error";

export type NexusActionState =
  | "planned"
  | "waiting_permission"
  | "running"
  | "verifying"
  | "recovery"
  | "completed"
  | "error"
  | "cancelled";

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

export interface NexusActionTool {
  name: string | null;
  description: string;
  category: string;
  risk_level: "low" | "medium" | "high" | string;
  destructive: boolean;
  idempotent: boolean;
  rollback_capability: string;
  recovery_strategy: string;
}

export interface NexusActionControls {
  approve_permission: number | null;
  deny_permission: number | null;
  recover_workflow: number | null;
  cancel_workflow: number | null;
  cancel_task: number | null;
  check_recovery: boolean;
}

export interface NexusActionCard {
  id: string;
  kind: "workflow" | "tool" | "task";
  state: NexusActionState;
  state_label: string;
  title: string;
  summary: string;
  project_id: number;
  workflow_id: number | null;
  task_id: number | null;
  permission_id: number | null;
  operation_id: number | null;
  tool: NexusActionTool | null;
  preview: Record<string, unknown> | null;
  progress: Record<string, unknown> | null;
  steps: Array<Record<string, unknown>>;
  evidence: Array<Record<string, unknown>>;
  result: unknown;
  error: unknown;
  controls: NexusActionControls;
  history: Array<Record<string, unknown>>;
  created_at: string | null;
  updated_at: string | null;
  finished_at: string | null;
}

export interface NexusActionCenter {
  schema_version: typeof NEXUS_ACTION_SCHEMA_VERSION;
  project: NexusProjectRef;
  counts: Record<string, number>;
  actions: NexusActionCard[];
  generated_at: string;
  semantics: {
    authoritative_sources: string[];
    permission_embedded_in_workflow: boolean;
    speculative_progress_allowed: boolean;
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

export function isNexusActionState(value: unknown): value is NexusActionState {
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
