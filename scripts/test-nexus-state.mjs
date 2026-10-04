import assert from "node:assert/strict";
import { NexusStore } from "../static/js/nexus/store.js";

const projectId = 7;
let snapshotCalls = 0;
let eventCalls = 0;

const snapshot = (revision) => ({
  schema_version: "1.0.0",
  project: { id: projectId, name: "NEXUS Test", kind: "work" },
  counts: { revision },
  suggestions: [],
  epistemic: {},
  modules: [],
  overall_state: "ready",
  generated_at: "2026-10-04T00:00:00+00:00",
});

const event = (id, createdAt) => ({
  schema_version: "1.0.0",
  id,
  source: "audit",
  source_id: Number(id.split(":")[1]),
  project_id: projectId,
  event_type: "test.event",
  severity: "info",
  actor: "system",
  summary: id,
  payload: {},
  entity: { type: "test", id },
  workflow_id: null,
  task_id: null,
  created_at: createdAt,
  requires_resync: true,
});

const transport = {
  async snapshot() {
    snapshotCalls += 1;
    return snapshot(snapshotCalls);
  },
  async events(_projectId, options = {}) {
    eventCalls += 1;
    if (options.tail) {
      return {
        schema_version: "1.0.0",
        events: [event("audit:1", "2026-10-04T00:00:01+00:00")],
        next_cursor: "cursor-1",
        has_more: false,
        tail: true,
        resync: {
          authoritative_source: "snapshot",
          required_after_events: true,
        },
      };
    }
    if (options.after === "cursor-1") {
      return {
        schema_version: "1.0.0",
        events: [
          event("audit:1", "2026-10-04T00:00:01+00:00"),
          event("audit:2", "2026-10-04T00:00:02+00:00"),
        ],
        next_cursor: "cursor-2",
        has_more: false,
        tail: false,
        resync: {
          authoritative_source: "snapshot",
          required_after_events: true,
        },
      };
    }
    assert.equal(options.after, "cursor-2");
    return {
      schema_version: "1.0.0",
      events: [],
      next_cursor: "cursor-2",
      has_more: false,
      tail: false,
      resync: {
        authoritative_source: "snapshot",
        required_after_events: true,
      },
    };
  },
};

const store = new NexusStore(projectId, transport, 50);
const notifications = [];
const unsubscribe = store.subscribe((state) => {
  notifications.push({
    synchronized: state.synchronized,
    events: state.events.length,
    revision: state.snapshot?.counts.revision ?? 0,
  });
});

const hydrated = await store.hydrate();
assert.equal(hydrated.synchronized, true);
assert.equal(hydrated.events.length, 1);
assert.equal(hydrated.cursor, "cursor-1");
assert.equal(snapshotCalls, 1);

const synchronized = await store.sync();
assert.equal(synchronized.events.length, 2, "event ids must be deduplicated");
assert.equal(synchronized.cursor, "cursor-2");
assert.equal(snapshotCalls, 2, "new events must trigger authoritative snapshot resync");
assert.equal(eventCalls, 2);

const refreshed = await store.sync({ forceSnapshot: true });
assert.equal(refreshed.events.length, 2);
assert.equal(snapshotCalls, 3, "forced refresh must update authoritative snapshot without events");
assert.equal(refreshed.snapshot?.counts.revision, 3);

store.invalidate();
assert.equal(store.state.synchronized, false);
unsubscribe();
assert.ok(notifications.length >= 4);

console.log("NEXUS state store contract OK.");
