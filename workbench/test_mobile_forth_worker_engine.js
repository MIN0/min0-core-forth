"use strict";

const assert = require("node:assert/strict");
const protocol = require("../viewer/mobile-forth-worker-protocol.js");
const { MobileForthWorkerEngine } = require("../viewer/mobile-forth-worker-engine.js");

function fakeQueue() {
  const callbacks = [];
  return {
    schedule(callback) { callbacks.push(callback); },
    flushOne() { assert.ok(callbacks.length, "expected a scheduled chunk"); callbacks.shift()(); },
    get length() { return callbacks.length; },
  };
}

const events = [];
const queue = fakeQueue();
const engine = new MobileForthWorkerEngine(event => events.push(event), { schedule: callback => queue.schedule(callback) });
const command = (sequence, name, payload = {}) => protocol.createCommand("session-1", sequence, name, payload);

assert.equal(engine.receive(command(1, "run", { source: ": SPIN BEGIN 1 DROP AGAIN ; SPIN", chunkSize: 4 })), true);
assert.deepEqual(events.slice(0, 2).map(event => event.name), ["accepted", "update"]);
assert.equal(queue.length, 1);
queue.flushOne();
assert.equal(engine.session.state, "running");
assert.equal(events.at(-1).payload.scheduler.executed, 4);

engine.receive(command(2, "pause"));
queue.flushOne();
assert.equal(engine.session.state, "paused");
assert.equal(events.at(-1).payload.status.state, "paused");
assert.ok(events.at(-1).payload.diagnostics);

engine.receive(command(3, "step"));
queue.flushOne();
assert.equal(engine.session.state, "paused");
assert.equal(events.at(-1).payload.scheduler.executed, 1);

engine.receive(command(4, "continue"));
queue.flushOne();
assert.equal(engine.session.state, "running");
engine.receive(command(5, "stop"));
queue.flushOne();
assert.equal(engine.session.state, "stopped");
engine.receive(command(6, "inspect"));
assert.equal(events.at(-1).name, "update");
assert.equal(events.at(-1).payload.status.state, "stopped");
engine.receive(command(7, "abort"));
assert.equal(engine.session.state, "aborted");

const rejectedBefore = events.filter(event => event.name === "rejected").length;
engine.receive(command(7, "inspect"));
assert.equal(events.filter(event => event.name === "rejected").length, rejectedBefore + 1, "replayed sequence is rejected");
engine.receive(protocol.createCommand("stale-session", 8, "inspect"));
assert.equal(events.at(-1).payload.code, "rejected-operation");
assert.equal(events.at(-1).sessionId, "session-1", "stale messages cannot replace the active session identity");

assert.equal(engine.receive(protocol.createCommand("session-2", 1, "run", { source: "2 3 +", chunkSize: 2 })), true);
while (queue.length) queue.flushOne();
assert.equal(engine.session.state, "completed");
assert.deepEqual(engine.session.status().currentSnapshot.dataStack, [5]);
const session2Events = events.filter(event => event.sessionId === "session-2");
assert.deepEqual(session2Events.map(event => event.sequence), session2Events.map((_, index) => index + 1));

const malformed = { version: protocol.VERSION, kind: "command", sessionId: "session-2", sequence: 2, name: "pause", payload: { extra: true } };
engine.receive(malformed);
assert.equal(events.at(-1).name, "rejected");
assert.equal(events.at(-1).payload.code, "invalid-envelope");
engine.receive(protocol.createCommand("session-2", 2, "pause"));
assert.equal(events.at(-1).name, "rejected");
assert.match(events.at(-1).payload.reason, /not allowed while completed/);
engine.receive(protocol.createCommand("session-2", 3, "inspect"));
assert.equal(events.at(-1).name, "update", "a rejected operation consumes its valid command sequence");

console.log("mobile forth worker engine tests: PASS");
