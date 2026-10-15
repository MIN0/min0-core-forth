"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const { Worker } = require("node:worker_threads");
const protocol = require("../viewer/mobile-forth-worker-protocol.js");

const sourcePath = process.argv[2];
if (!sourcePath) throw new Error("worker source path is required");
const source = fs.readFileSync(sourcePath, "utf8");
const bootstrap = `
const { parentPort } = require("node:worker_threads");
module = undefined;
globalThis.self = { postMessage: message => parentPort.postMessage(message) };
${source}
parentPort.on("message", data => self.onmessage({ data }));
`;

const worker = new Worker(bootstrap, { eval: true });
const events = [];
const timeout = setTimeout(() => {
  worker.terminate();
  throw new Error("embedded Worker did not complete");
}, 5000);

worker.on("error", error => { clearTimeout(timeout); throw error; });
worker.on("message", event => {
  events.push(protocol.readEvent(event));
  if (event.name !== "update" || event.payload.status.state !== "completed") return;
  clearTimeout(timeout);
  assert.deepEqual(event.payload.status.currentSnapshot.dataStack, [5]);
  assert.ok(events.some(item => item.name === "accepted"));
  worker.terminate().then(() => console.log("embedded mobile Worker test: PASS"));
});

worker.postMessage(protocol.createCommand("embedded-1", 1, "run", { source: "2 3 +", chunkSize: 2 }));
