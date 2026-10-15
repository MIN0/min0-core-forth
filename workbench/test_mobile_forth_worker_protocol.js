"use strict";

const assert = require("node:assert/strict");
const protocol = require("../viewer/mobile-forth-worker-protocol.js");

const runPayload = { source: ": TWICE DUP + ; 5 TWICE", chunkSize: 100 };
const run = protocol.createCommand("session-1", 1, "run", runPayload);
assert.equal(run.version, protocol.VERSION);
assert.equal(run.kind, "command");
assert.deepEqual(protocol.readCommand(JSON.parse(JSON.stringify(run))), run);
runPayload.source = "changed";
assert.equal(run.payload.source, ": TWICE DUP + ; 5 TWICE", "message owns a copy of payload data");

for (const [index, name] of ["pause", "step", "continue", "stop", "abort", "inspect"].entries()) {
  assert.equal(protocol.createCommand("session-1", index + 2, name).name, name);
}

const updatePayload = {
  requestSequence: 1,
  scheduler: { chunkSequence: 3, totalBoundaries: 201 },
  status: { state: "paused", currentSnapshot: { dataStack: [5, 10], location: { word: "TWICE", instructionIndex: 2 } } },
};
const update = protocol.createEvent("session-1", 1, "update", updatePayload);
assert.deepEqual(protocol.readEvent(JSON.parse(JSON.stringify(update))), update);

assert.throws(() => protocol.createCommand("bad session", 1, "run", { source: "" }), protocol.ProtocolError);
assert.throws(() => protocol.createCommand("session-1", 0, "run", { source: "" }), protocol.ProtocolError);
assert.throws(() => protocol.createCommand("session-1", 1, "unknown", {}), protocol.ProtocolError);
assert.throws(() => protocol.createCommand("session-1", 1, "pause", { extra: true }), protocol.ProtocolError);
assert.throws(() => protocol.createCommand("session-1", 1, "run", { source: "", chunkSize: 0 }), protocol.ProtocolError);
assert.throws(() => protocol.createCommand("session-1", 1, "run", { source: "あ".repeat(1366) }), protocol.ProtocolError);
assert.throws(() => protocol.readCommand({ ...run, version: "future" }), protocol.ProtocolError);
assert.throws(() => protocol.readEvent({ ...update, kind: "command" }), protocol.ProtocolError);
const circular = {}; circular.self = circular;
assert.throws(() => protocol.createEvent("session-1", 2, "fatal", circular), protocol.ProtocolError);

console.log("mobile forth worker protocol tests: PASS");
