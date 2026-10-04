import {
  fetchNexusEvents,
  fetchNexusSnapshot,
} from "./client.js";
import type {
  NexusEventEnvelope,
  NexusEventPage,
  NexusSnapshot,
} from "./contracts.js";

export interface NexusTransport {
  snapshot(projectId: number): Promise<NexusSnapshot>;
  events(
    projectId: number,
    options?: { after?: string | null; limit?: number; tail?: boolean },
  ): Promise<NexusEventPage>;
}

export const browserNexusTransport: NexusTransport = {
  snapshot: fetchNexusSnapshot,
  events: fetchNexusEvents,
};

export interface NexusStoreState {
  snapshot: NexusSnapshot | null;
  events: readonly NexusEventEnvelope[];
  cursor: string | null;
  synchronized: boolean;
}

type NexusListener = (state: NexusStoreState) => void;

export class NexusStore {
  readonly projectId: number;
  readonly transport: NexusTransport;
  readonly maxEvents: number;

  #snapshot: NexusSnapshot | null = null;
  #events: NexusEventEnvelope[] = [];
  #cursor: string | null = null;
  #synchronized = false;
  #listeners = new Set<NexusListener>();

  constructor(
    projectId: number,
    transport: NexusTransport = browserNexusTransport,
    maxEvents = 200,
  ) {
    if (!Number.isInteger(projectId) || projectId <= 0) {
      throw new Error("Некорректный projectId для NEXUS store.");
    }
    this.projectId = projectId;
    this.transport = transport;
    this.maxEvents = Math.max(20, Math.min(Math.trunc(maxEvents), 1000));
  }

  get state(): NexusStoreState {
    return {
      snapshot: this.#snapshot,
      events: this.#events.slice(),
      cursor: this.#cursor,
      synchronized: this.#synchronized,
    };
  }

  subscribe(listener: NexusListener): () => void {
    this.#listeners.add(listener);
    listener(this.state);
    return () => this.#listeners.delete(listener);
  }

  async hydrate(): Promise<NexusStoreState> {
    const [snapshot, page] = await Promise.all([
      this.transport.snapshot(this.projectId),
      this.transport.events(this.projectId, {
        tail: true,
        limit: Math.min(this.maxEvents, 100),
      }),
    ]);
    this.#snapshot = snapshot;
    this.#events = page.events.slice(-this.maxEvents);
    this.#cursor = page.next_cursor;
    this.#synchronized = true;
    this.#emit();
    return this.state;
  }

  async sync(): Promise<NexusStoreState> {
    if (!this.#synchronized) {
      return this.hydrate();
    }

    let after = this.#cursor;
    let sawEvents = false;
    do {
      const page = await this.transport.events(this.projectId, {
        after,
        limit: 100,
      });
      if (page.events.length) {
        sawEvents = true;
        this.#appendEvents(page.events);
      }
      after = page.next_cursor;
      this.#cursor = after;
      if (!page.has_more) break;
    } while (true);

    if (sawEvents) {
      this.#snapshot = await this.transport.snapshot(this.projectId);
    }
    this.#synchronized = true;
    this.#emit();
    return this.state;
  }

  invalidate(): void {
    this.#synchronized = false;
    this.#emit();
  }

  #appendEvents(events: readonly NexusEventEnvelope[]): void {
    const byId = new Map(this.#events.map((event) => [event.id, event]));
    for (const event of events) byId.set(event.id, event);
    this.#events = Array.from(byId.values())
      .sort((left, right) => {
        const time = left.created_at.localeCompare(right.created_at);
        if (time) return time;
        return left.id.localeCompare(right.id);
      })
      .slice(-this.maxEvents);
  }

  #emit(): void {
    const state = this.state;
    for (const listener of this.#listeners) listener(state);
  }
}
