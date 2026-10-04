export const NEXUS_SCHEMA_VERSION = "1.0.0" as const;

export type NexusOperationalState =
  | "disabled"
  | "not_connected"
  | "ready"
  | "processing"
  | "degraded"
  | "error";

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
