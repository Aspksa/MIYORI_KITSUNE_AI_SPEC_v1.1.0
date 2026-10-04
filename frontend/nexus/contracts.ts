export const NEXUS_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_EVENT_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_ACTION_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_KNOWLEDGE_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_SURFACE_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_PRESENCE_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_PROACTIVE_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_VOICE_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_AGENT_WORKSPACE_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_HOME_SCHEMA_VERSION = "1.0.0" as const;
export const NEXUS_BODY_SCHEMA_VERSION = "1.2.0" as const;
export const BODY_RENDERER_SCHEMA_VERSION = "1.0.0" as const;
export const MIYORI_APPEARANCE_SCHEMA_VERSION = "1.0.0" as const;

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

export interface NexusKnowledgeMemory {
  id: number;
  statement: string;
  status: "candidate" | "verified" | "disputed" | "superseded" | string;
  scope: "user" | "project" | string;
  kind: "fact" | "preference" | "process" | "constraint" | string;
  confidence: number | null;
  salience: number;
  verification_method: string | null;
  observed_at: string | null;
  valid_from: string | null;
  valid_until: string | null;
  possible_conflict_ids: number[];
  provenance: {
    source_kind: string | null;
    conversation_id: number | null;
    message_id: number | null;
    locator: string | null;
    origin_project_id: number | null;
    origin_project_name: string | null;
  };
  actions: {
    project_id: number;
    verify: boolean;
    dispute: boolean;
    supersede: boolean;
  };
}

export interface NexusKnowledgeDocument {
  id: number;
  filename: string;
  folder_id: number | null;
  folder_name: string | null;
  mime_type: string | null;
  size_bytes: number;
  created_at: string | null;
  provenance: {
    sha256: string;
    locator: string;
    source_kind: "original_document";
  };
  index: {
    chunks: number;
    nodes: number;
    parser_version: string | null;
  };
  intelligence: {
    status: string;
    title: string | null;
    document_kind: string | null;
    language: string | null;
    summary: string | null;
    word_count: number;
    page_count: number;
    section_count: number;
    table_count: number;
    coverage: number;
    extraction_status: string;
    extraction_coverage: number;
    warnings: string[];
    analysis_model: string | null;
    last_error: string | null;
    updated_at: string | null;
    limited: boolean;
  };
  exhaustive: {
    questions: number;
    complete: number;
    active: number;
    best_coverage: number;
  };
  actions: {
    analyze: boolean;
    rebuild: boolean;
  };
}

export interface NexusKnowledgeEvidencePreview {
  id: number | null;
  stance: "supports" | "contradicts" | "neutral" | string;
  excerpt: string | null;
  weight: number | null;
  source: {
    id: number | null;
    type: string | null;
    key: string | null;
    title: string | null;
    locator: string | null;
    publisher: string | null;
    quality: number | null;
    observed_at: string | null;
  };
}

export interface NexusKnowledgeClaim {
  id: number;
  statement: string;
  claim_type: string;
  status: string;
  assessment: string;
  confidence: number;
  supports: number;
  contradictions: number;
  open_contradictions: number;
  independent_sources: number;
  evidence_count: number;
  evidence_preview: NexusKnowledgeEvidencePreview[];
  created_at: string | null;
  updated_at: string | null;
  verified_at: string | null;
  can_verify: boolean;
}

export interface NexusKnowledgeCenter {
  schema_version: typeof NEXUS_KNOWLEDGE_SCHEMA_VERSION;
  project: NexusProjectRef;
  query: string;
  counts: {
    memory: Record<string, number>;
    documents: Record<string, number>;
    claims: Record<string, number>;
    attention: Record<string, number>;
  };
  results: {
    memory: number;
    documents: number;
    claims: number;
  };
  memory: NexusKnowledgeMemory[];
  documents: NexusKnowledgeDocument[];
  claims: NexusKnowledgeClaim[];
  semantics: {
    sections_are_distinct: boolean;
    memory_meaning: string;
    documents_meaning: string;
    claims_meaning: string;
    graph_is_optional: boolean;
    arbitrary_model_markup: boolean;
  };
  generated_at: string;
}

export type NexusPresenceMode =
  | "ready"
  | "working"
  | "verifying"
  | "waiting"
  | "attention"
  | "recovery"
  | "degraded";

export interface NexusPresenceReason {
  kind: "workflow" | "permission" | "action" | "task" | "knowledge" | string;
  label: string;
  state: string;
  entity_id: string | null;
}

export interface NexusPresence {
  schema_version: typeof NEXUS_PRESENCE_SCHEMA_VERSION;
  project: NexusProjectRef;
  mode: NexusPresenceMode;
  headline: string;
  detail: string;
  attention: "none" | "low" | "normal" | "high";
  reasons: NexusPresenceReason[];
  activity: {
    waiting_permissions: number;
    recovering_actions: number;
    failed_actions: number;
    active_actions: number;
    verifying_actions: number;
    failed_tasks: number;
    knowledge_attention: number;
  };
  last_event: {
    id: string;
    event_type: string;
    severity: NexusEventSeverity;
    summary: string;
    created_at: string;
    source: string;
  } | null;
  source_contract: {
    authoritative: true;
    sources: string[];
    random_liveness_allowed: false;
    decorative_activity_allowed: false;
    chat_interruption_allowed: false;
    knowledge_attention_changes_primary_presence: false;
  };
  generated_at: string;
}

export type NexusAgentWorkspaceStatus =
  | "planned"
  | "running"
  | "waiting_permission"
  | "recovery"
  | "completed"
  | "failed"
  | "cancelled";

export type NexusAgentWorkspaceNodeStatus =
  | "blocked"
  | "ready"
  | "running"
  | "waiting_permission"
  | "recovery"
  | "completed"
  | "failed"
  | "cancelled";

export interface NexusAgentWorkspaceNode {
  id: number;
  workspace_id: number;
  node_key: string;
  role: string;
  title: string;
  instruction: string;
  capability: "read_only" | "standard";
  dependencies: string[];
  step_budget: number;
  status: NexusAgentWorkspaceNodeStatus;
  workflow_id: number | null;
  result: unknown;
  error: unknown;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface NexusAgentWorkspaceSummary {
  id: number;
  project_id: number;
  goal: string;
  status: NexusAgentWorkspaceStatus;
  max_parallel: number;
  total_step_budget: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface NexusAgentWorkspace {
  schema_version: typeof NEXUS_AGENT_WORKSPACE_SCHEMA_VERSION;
  id: number;
  project_id: number;
  goal: string;
  status: NexusAgentWorkspaceStatus;
  max_parallel: number;
  total_step_budget: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  nodes: NexusAgentWorkspaceNode[];
  counts: Record<NexusAgentWorkspaceNodeStatus, number>;
}

export type NexusHomeConnectivityState =
  | "unlinked"
  | "revoked"
  | "never_seen"
  | "online"
  | "offline";

export interface NexusHomeDevice {
  id: number;
  name: string;
  device_type: string;
  address: string;
  declared_status: string;
  notes: string;
  link_status: "unlinked" | "linked" | "revoked";
  capabilities: string[];
  connectivity: {
    state: NexusHomeConnectivityState;
    online: boolean;
    freshness_seconds: number | null;
    last_seen_at: string | null;
    heartbeat_seq: number;
  };
  reported_state: Record<string, unknown>;
  linked_at: string | null;
  updated_at: string | null;
  actions: {
    can_link: boolean;
    can_unlink: boolean;
  };
}

export interface NexusHomeParentalProfile {
  id: number;
  project_id: number;
  child_name: string;
  device_name: string;
  daily_limit_minutes: number;
  bedtime_start: string;
  bedtime_end: string;
  blocked_categories: string;
  status: string;
  created_at: string;
  updated_at: string;
  binding: {
    device_id: number | null;
    device_name: string | null;
    explicitly_linked: boolean;
    enforcement_state:
      | "not_bound"
      | "device_not_linked"
      | "capability_missing"
      | "device_offline"
      | "ready_for_device_agent";
    applied: false;
    note: string;
  };
}

export interface NexusHomeCenter {
  schema_version: typeof NEXUS_HOME_SCHEMA_VERSION;
  project: NexusProjectRef;
  enabled: boolean;
  devices: NexusHomeDevice[];
  parental_profiles: NexusHomeParentalProfile[];
  counts: {
    devices: number;
    linked: number;
    online: number;
    offline_or_unseen: number;
    parental_profiles: number;
    parental_attention: number;
  };
  policy: {
    connectivity_source: "authenticated_heartbeat";
    legacy_status_is_connectivity_source: false;
    heartbeat_ttl_seconds: number;
    network_scanning_enabled: false;
    unknown_device_auto_link_allowed: false;
    parental_rules_require_explicit_binding: true;
    parental_rules_applied_by_server: false;
    device_commands_enabled: false;
  };
  generated_at: string;
}


export type NexusBodyState =
  | "ready"
  | "working"
  | "verifying"
  | "waiting"
  | "recovery"
  | "attention"
  | "degraded";

export type NexusBodyLocalState =
  | "idle"
  | "thinking"
  | "listening"
  | "transcribing"
  | "speaking"
  | "interrupted"
  | "voice_error";

export interface NexusBodyPresentation {
  pose: string;
  expression: string;
  gesture: string;
  label: string;
}

export type MiyoriAppearanceState =
  | "appearance_unconfigured"
  | "appearance_partial"
  | "appearance_configured";

export interface MiyoriAppearanceSelection {
  hair_color: string | null;
  eye_color: string | null;
  tail_count: number | null;
  main_outfit: string | null;
}

export interface MiyoriAppearanceAsset {
  kind: "static_portrait" | null;
  url: string | null;
  mime: string | null;
  sha256: string | null;
  size_bytes: number;
  supports_dynamic_pose: false;
  supports_expression: false;
}

export interface MiyoriAppearanceProfile {
  schema_version: typeof MIYORI_APPEARANCE_SCHEMA_VERSION;
  state: MiyoriAppearanceState;
  selection: MiyoriAppearanceSelection;
  completion: {
    selected: number;
    total: 4;
    complete: boolean;
  };
  fields: Array<{
    key: keyof MiyoriAppearanceSelection;
    label: string;
    owner_choice: true;
    selected: boolean;
  }>;
  persona_open_choices: string[];
  asset: MiyoriAppearanceAsset;
  policy: {
    system_defaults_allowed: false;
    model_may_choose_owner_fields: false;
    partial_configuration_allowed: true;
    asset_changes_persona_identity: false;
    static_portrait_may_claim_dynamic_pose: false;
  };
  revision: number;
  updated_at: string | null;
}

export type NexusBodyRendererAdapterId =
  | "neutral_shell"
  | "static_portrait";

export interface NexusBodyRendererAdapter {
  id: NexusBodyRendererAdapterId;
  label: string;
  installed: true;
  dynamic: false;
  requires_asset_kind: "static_portrait" | null;
  supports: {
    pose: boolean;
    expression: boolean;
    gesture: boolean;
  };
  semantics: string;
}

export interface NexusBodyRendererContract {
  schema_version: typeof BODY_RENDERER_SCHEMA_VERSION;
  selected_adapter: NexusBodyRendererAdapterId;
  selected_dynamic: false;
  trusted_adapters: NexusBodyRendererAdapter[];
  presentation_channels: {
    pose: "body.presentation.pose";
    expression: "body.presentation.expression";
    gesture: "body.presentation.gesture";
    state: "body.state_or_explicit_local_runtime";
  };
  dynamic_extension: {
    status: "not_installed";
    adapter_contract_required: true;
    must_be_trusted_registry_entry: true;
    must_consume_existing_presentation_channels: true;
    may_invent_owner_appearance_choices: false;
    may_execute_asset_javascript: false;
    may_override_operational_state: false;
  };
  policy: {
    trusted_registry_only: true;
    arbitrary_renderer_module_allowed: false;
    asset_authored_javascript_allowed: false;
    model_select_adapter_allowed: false;
    unknown_adapter_fallback: "neutral_shell";
    static_portrait_is_dynamic: false;
    dynamic_renderer_claim_requires_installed_adapter: true;
  };
}

export interface NexusDigitalBody {
  schema_version: typeof NEXUS_BODY_SCHEMA_VERSION;
  project: NexusProjectRef;
  state: NexusBodyState;
  presentation: NexusBodyPresentation;
  appearance: {
    persona_version: string;
    name: string;
    nickname: string;
    age_years: number;
    is_adult: true;
    species: string;
    confirmed: string[];
    open_for_owner_choice: string[];
    configuration_state: MiyoriAppearanceState;
    final_portrait_asset: null | string;
    selections: MiyoriAppearanceSelection;
    asset: MiyoriAppearanceAsset;
    appearance_profile_schema_version: typeof MIYORI_APPEARANCE_SCHEMA_VERSION;
    appearance_revision: number;
  };
  renderer: NexusBodyRendererContract;
  runtime: {
    presence_mode: string;
    presence_attention: string;
    headline: string;
    detail: string;
    source: "nexus_presence";
  };
  local_override_contract: {
    allowed_states: NexusBodyLocalState[];
    presentations: Record<string, NexusBodyPresentation>;
    idle_returns_to_server_state: true;
    voice_state_source: "miyori:voice-state";
    thinking_state_source: "miyori:interaction-state";
  };
  motion_policy: {
    random_liveness_allowed: false;
    timer_idle_animation_allowed: false;
    sentiment_to_expression_allowed: false;
    model_authored_motion_allowed: false;
    state_transition_motion_allowed: true;
    reduced_motion_must_be_respected: true;
  };
  render_policy: {
    neutral_shell_until_owner_appearance_choice: true;
    owner_global_appearance_profile: true;
    static_portrait_is_non_dynamic: true;
    invent_open_appearance_choices_allowed: false;
    tail_count_may_be_invented: false;
    hair_color_may_be_invented: false;
    eye_color_may_be_invented: false;
    outfit_may_be_invented: false;
    body_state_source: "presence_plus_explicit_local_runtime";
  };
  generated_at: string;
}

export type NexusVoiceState =
  | "unavailable"
  | "idle"
  | "listening"
  | "transcribing"
  | "thinking"
  | "speaking"
  | "interrupted"
  | "error";

export interface NexusVoiceContract {
  schema_version: typeof NEXUS_VOICE_SCHEMA_VERSION;
  project: NexusProjectRef;
  protocol: {
    states: NexusVoiceState[];
    default_state: "idle";
    final_transcript_required_before_submit: true;
    interim_transcript_is_ephemeral: true;
    confidence_is_advisory: true;
    barge_in_allowed: true;
    cancel_allowed: true;
  };
  permissions: {
    microphone_requires_explicit_user_gesture: true;
    microphone_permission_must_be_browser_or_os_managed: true;
    background_recording_allowed: false;
  };
  safety: {
    voice_can_bypass_action_permissions: false;
    voice_can_auto_approve_actions: false;
    voice_can_auto_execute_write_tools: false;
    final_transcript_uses_existing_chat_pipeline: true;
  };
  transport: {
    browser_recognition: "optional";
    browser_tts: "optional";
    desktop_transport_replaceable: true;
    server_audio_storage: false;
  };
  generated_at: string;
}

export type NexusProactiveSeverity = "high" | "normal" | "low";
export type NexusProactiveDestination = "actions" | "knowledge" | "system";
export type NexusProactiveChannelOwner = "presence" | "attention_shelf";

export interface NexusProactiveSignal {
  id: string;
  signal_key: string;
  fingerprint: string;
  kind: string;
  severity: NexusProactiveSeverity;
  priority: number;
  title: string;
  detail: string;
  destination: NexusProactiveDestination;
  channel_owner: NexusProactiveChannelOwner;
  source: Record<string, unknown>;
  controls: {
    open: boolean;
    dismiss: boolean;
    snooze: boolean;
    snooze_options_minutes: number[];
  };
  safety: {
    executes_action: false;
    changes_domain_state: false;
    requires_existing_permission_flow: true;
  };
}

export interface NexusProactivePage {
  schema_version: typeof NEXUS_PROACTIVE_SCHEMA_VERSION;
  project: NexusProjectRef;
  signals: NexusProactiveSignal[];
  display: {
    chat_shelf_ids: string[];
    presence_owned_ids: string[];
  };
  budget: {
    initiative_level: "low" | "medium" | "high";
    suggest_next_steps: boolean;
    max_contract_signals: number;
    max_chat_shelf: number;
    active_candidates: number;
    suppressed_candidates: number;
    selected_chat_shelf: number;
  };
  suppressed: Array<{
    id: string;
    reason: "dismissed" | "snoozed" | string;
    signal_key: string;
    until?: string;
  }>;
  next_wakeup_at: string | null;
  policy: {
    auto_execute_allowed: false;
    write_action_allowed: false;
    chat_message_injection_allowed: false;
    interrupt_user_allowed: false;
    os_notification_allowed: false;
    operational_blockers_owned_by_presence: true;
    decisions_change_signal_visibility_only: true;
  };
  generated_at: string;
}

export type NexusSurfaceKind =
  | "status"
  | "progress"
  | "action"
  | "source"
  | "collection";

export type NexusSurfaceComponent =
  | "status_summary"
  | "action_card"
  | "progress_card"
  | "knowledge_attention"
  | "result_collection";

export type NexusSurfaceTone =
  | "neutral"
  | "working"
  | "success"
  | "warning"
  | "error";

export interface NexusSurfaceAction {
  id: string;
  type: "navigate";
  label: string;
  target: "chat" | "actions" | "knowledge" | "home" | "system";
}

export interface NexusGenerativeSurface {
  schema_version: typeof NEXUS_SURFACE_SCHEMA_VERSION;
  id: string;
  kind: NexusSurfaceKind;
  component: NexusSurfaceComponent;
  title: string;
  description: string;
  tone: NexusSurfaceTone;
  priority: number;
  data: Record<string, unknown>;
  actions: NexusSurfaceAction[];
  policy: {
    model_html_allowed: false;
    script_allowed: false;
    trusted_component_only: true;
    interrupts_chat: false;
  };
}

export interface NexusSurfacePage {
  schema_version: typeof NEXUS_SURFACE_SCHEMA_VERSION;
  project: NexusProjectRef;
  context: "auto" | "chat" | "actions" | "knowledge" | "system";
  query: string;
  surfaces: NexusGenerativeSurface[];
  registry: {
    allowed_kinds: NexusSurfaceKind[];
    allowed_components: NexusSurfaceComponent[];
    model_html_allowed: false;
    script_allowed: false;
    unknown_components_rejected: true;
  };
  generated_at: string;
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
