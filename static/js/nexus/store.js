import { fetchNexusEvents, fetchNexusSnapshot, } from "./client.js";
export const browserNexusTransport = {
    snapshot: fetchNexusSnapshot,
    events: fetchNexusEvents,
};
export class NexusStore {
    projectId;
    transport;
    maxEvents;
    #snapshot = null;
    #events = [];
    #cursor = null;
    #synchronized = false;
    #listeners = new Set();
    constructor(projectId, transport = browserNexusTransport, maxEvents = 200) {
        if (!Number.isInteger(projectId) || projectId <= 0) {
            throw new Error("Некорректный projectId для NEXUS store.");
        }
        this.projectId = projectId;
        this.transport = transport;
        this.maxEvents = Math.max(20, Math.min(Math.trunc(maxEvents), 1000));
    }
    get state() {
        return {
            snapshot: this.#snapshot,
            events: this.#events.slice(),
            cursor: this.#cursor,
            synchronized: this.#synchronized,
        };
    }
    subscribe(listener) {
        this.#listeners.add(listener);
        listener(this.state);
        return () => this.#listeners.delete(listener);
    }
    async hydrate() {
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
    async sync() {
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
            if (!page.has_more)
                break;
        } while (true);
        if (sawEvents) {
            this.#snapshot = await this.transport.snapshot(this.projectId);
        }
        this.#synchronized = true;
        this.#emit();
        return this.state;
    }
    invalidate() {
        this.#synchronized = false;
        this.#emit();
    }
    #appendEvents(events) {
        const byId = new Map(this.#events.map((event) => [event.id, event]));
        for (const event of events)
            byId.set(event.id, event);
        this.#events = Array.from(byId.values())
            .sort((left, right) => {
            const time = left.created_at.localeCompare(right.created_at);
            if (time)
                return time;
            return left.id.localeCompare(right.id);
        })
            .slice(-this.maxEvents);
    }
    #emit() {
        const state = this.state;
        for (const listener of this.#listeners)
            listener(state);
    }
}
