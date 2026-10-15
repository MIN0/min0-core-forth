"use strict";

const assert = require("node:assert/strict");
const protocol = require("../viewer/mobile-forth-worker-protocol.js");
const { MobileForthWorkerClient } = require("../viewer/mobile-forth-worker-client.js");

class FakeBlob {
  constructor(parts, options) { this.parts = parts; this.options = options; }
}
class FakeWorker {
  constructor(url) { this.url = url; this.sent = []; this.terminated = false; FakeWorker.instance = this; }
  postMessage(message) { this.sent.push(message); }
  terminate() { this.terminated = true; }
  emit(message) { this.onmessage({ data: message }); }
}
const fakeUrl = {
  revoked: [],
  createObjectURL(blob) { assert.ok(blob instanceof FakeBlob); return "blob:min0-worker"; },
  revokeObjectURL(url) { this.revoked.push(url); },
};

const workerEvents = [];
const modes = [];
const client = new MobileForthWorkerClient({
  workerSource: "self.onmessage = () => {};",
  WorkerClass: FakeWorker,
  BlobClass: FakeBlob,
  URLApi: fakeUrl,
  sessionIdFactory: () => "session-worker",
  onEvent: event => workerEvents.push(event),
  onMode: event => modes.push(event),
});
client.run("2 3 +", 10);
assert.equal(client.mode, "worker");
assert.equal(FakeWorker.instance.sent[0].name, "run");
client.pause();
assert.equal(FakeWorker.instance.sent[1].sequence, 2);

const update = protocol.createEvent("session-worker", 1, "update", { status: { state: "paused" } });
FakeWorker.instance.emit(update);
FakeWorker.instance.emit(update);
FakeWorker.instance.emit(protocol.createEvent("stale-session", 2, "update", {}));
assert.equal(workerEvents.length, 1, "duplicate and stale events are ignored");
client.close();
assert.equal(FakeWorker.instance.terminated, true);
assert.deepEqual(fakeUrl.revoked, ["blob:min0-worker"]);

function fakeQueue() {
  const callbacks = [];
  return { schedule: callback => callbacks.push(callback), flush() { while (callbacks.length) callbacks.shift()(); } };
}
const queue = fakeQueue();
const fallbackEvents = [];
const fallbackModes = [];
class RefusingWorker { constructor() { throw new Error("worker blocked"); } }
const fallback = new MobileForthWorkerClient({
  workerSource: "blocked",
  WorkerClass: RefusingWorker,
  BlobClass: FakeBlob,
  URLApi: fakeUrl,
  schedule: callback => queue.schedule(callback),
  sessionIdFactory: () => "session-fallback",
  onEvent: event => fallbackEvents.push(event),
  onMode: event => fallbackModes.push(event),
});
fallback.run("2 3 +", 2);
queue.flush();
assert.equal(fallback.mode, "main-thread-fallback");
assert.match(fallbackModes[0].reason, /worker blocked/);
const completed = fallbackEvents.filter(event => event.name === "update").at(-1);
assert.equal(completed.payload.status.state, "completed");
assert.deepEqual(completed.payload.status.currentSnapshot.dataStack, [5]);

console.log("mobile forth worker client tests: PASS");
