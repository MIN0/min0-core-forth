"use strict";

const assert = require("node:assert/strict");
const { STATES } = require("../viewer/mobile-monitor-state.js");
const { MobileForthSession } = require("../viewer/mobile-forth-session.js");
const { MobileForthScheduler } = require("../viewer/mobile-forth-scheduler.js");

function fakeQueue() {
  const queue = [];
  return {
    schedule(callback) { queue.push(callback); },
    get length() { return queue.length; },
    flushOne() {
      assert.ok(queue.length, "a scheduled chunk is required");
      queue.shift()();
    },
  };
}

const queue = fakeQueue();
const updates = [];
const looping = new MobileForthSession(": FOREVER BEGIN 1 AGAIN ; FOREVER", { maxSteps: 10000 });
const scheduler = new MobileForthScheduler(looping, {
  chunkSize: 4,
  schedule: callback => queue.schedule(callback),
  onUpdate: event => updates.push(event),
});
scheduler.start();
assert.equal(queue.length, 1);
queue.flushOne();
assert.equal(looping.state, STATES.RUNNING);
assert.equal(updates.at(-1).kind, "chunk");
assert.equal(updates.at(-1).executed, 4);
assert.equal(queue.length, 1, "one and only one next chunk must be pending");

scheduler.requestPause();
assert.equal(looping.state, STATES.PAUSE_REQUESTED);
assert.equal(queue.length, 1, "pause must not duplicate a scheduled chunk");
const beforePause = looping.vm.steps;
queue.flushOne();
assert.equal(looping.state, STATES.PAUSED);
assert.equal(looping.vm.steps - beforePause, 1, "pause is accepted at the next instruction boundary");
assert.equal(queue.length, 0);
assert.ok(updates.at(-1).diagnostics);

const beforeStep = looping.vm.steps;
scheduler.step();
assert.equal(queue.length, 1);
queue.flushOne();
assert.equal(looping.state, STATES.PAUSED);
assert.equal(looping.vm.steps - beforeStep, 1);

scheduler.continueExecution();
queue.flushOne();
assert.equal(looping.state, STATES.RUNNING);
assert.equal(updates.at(-1).executed, 4);
scheduler.requestStop();
queue.flushOne();
assert.equal(looping.state, STATES.STOPPED);
assert.equal(queue.length, 0);
assert.ok(looping.vm.stackSnapshot().length > 0, "Stop keeps the current stack");
assert.ok(updates.filter(event => event.kind === "chunk").every(event => event.executed <= 4));

const abortQueue = fakeQueue();
const abortSession = new MobileForthSession(': TEMP 1 ; ." VISIBLE" TEMP BEGIN 1 AGAIN', { maxSteps: 10000 });
const abortScheduler = new MobileForthScheduler(abortSession, { chunkSize: 3, schedule: callback => abortQueue.schedule(callback) });
abortScheduler.start();
abortQueue.flushOne();
assert.ok(abortSession.vm.dictionary.has("TEMP"));
assert.equal(abortSession.vm.output, "VISIBLE");
abortScheduler.requestAbort();
abortQueue.flushOne();
assert.equal(abortSession.state, STATES.ABORTED);
assert.equal(abortSession.vm.dictionary.size, 0);
assert.deepEqual(abortSession.vm.stackSnapshot(), []);
assert.equal(abortSession.vm.output, "VISIBLE", "already visible output is not transactional");
assert.ok(abortScheduler.update("inspect").diagnostics.wordCatalog.some(item => item.name === "TEMP"));

const completeQueue = fakeQueue();
const completeSession = new MobileForthSession("2 3 +");
const completeScheduler = new MobileForthScheduler(completeSession, { chunkSize: 2, schedule: callback => completeQueue.schedule(callback) });
completeScheduler.start();
completeQueue.flushOne();
assert.equal(completeSession.state, STATES.RUNNING);
assert.equal(completeQueue.length, 1);
completeQueue.flushOne();
assert.equal(completeSession.state, STATES.COMPLETED);
assert.deepEqual(completeSession.vm.stackSnapshot(), [5]);
assert.equal(completeQueue.length, 0);

const inputScheduleQueue = fakeQueue();
const waitingSession = new MobileForthSession("KEY 1+");
const waitingScheduler = new MobileForthScheduler(waitingSession, { chunkSize: 4, schedule: callback => inputScheduleQueue.schedule(callback) });
waitingScheduler.start();
inputScheduleQueue.flushOne();
assert.equal(waitingSession.state, STATES.WAITING_INPUT);
assert.equal(inputScheduleQueue.length, 0, "waiting-input must not busy-loop");
const inputUpdate = waitingScheduler.enqueueInput("A");
assert.equal(inputUpdate.count, 1);
assert.equal(waitingSession.state, STATES.RUNNING);
assert.equal(inputScheduleQueue.length, 1, "input arrival schedules resumed execution");
inputScheduleQueue.flushOne();
assert.equal(waitingSession.state, STATES.COMPLETED);
assert.deepEqual(waitingSession.vm.stackSnapshot(), [66]);

assert.throws(() => new MobileForthScheduler(new MobileForthSession(""), { chunkSize: 0 }), RangeError);
assert.throws(() => scheduler.start(), /already started/);

console.log("mobile forth scheduler tests: PASS");
