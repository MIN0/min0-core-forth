"use strict";

const assert = require("node:assert/strict");
const { STATES, MonitorTransitionError, MonitorExecutionControl } = require("../viewer/mobile-monitor-state.js");

function snapshot(stack, word = "#0 MAIN", instruction = 0) {
  return { dataStack: [...stack], location: { word, instruction } };
}

const pause = new MonitorExecutionControl();
pause.start(snapshot([]));
pause.requestPause();
assert.equal(pause.state, STATES.PAUSE_REQUESTED);
assert.equal(pause.atInstructionBoundary(snapshot([1], "COUNT", 3)), "paused");
assert.equal(pause.state, STATES.PAUSED);
assert.equal(pause.stopReason, "pause");
assert.deepEqual(pause.currentSnapshot.dataStack, [1]);
pause.continueExecution();
assert.equal(pause.state, STATES.RUNNING);

pause.requestPause();
pause.atInstructionBoundary(snapshot([2], "COUNT", 4));
pause.step();
assert.equal(pause.state, STATES.STEPPING);
assert.equal(pause.atInstructionBoundary(snapshot([3], "COUNT", 5)), "paused");
assert.equal(pause.stopReason, "step-complete");
assert.deepEqual(pause.currentSnapshot.dataStack, [3]);

const stop = new MonitorExecutionControl();
stop.start(snapshot([10]));
stop.requestStop();
assert.equal(stop.state, STATES.STOP_REQUESTED);
assert.equal(stop.atInstructionBoundary(snapshot([10, 20], "WORK", 7)), "stopped");
assert.equal(stop.state, STATES.STOPPED);
assert.deepEqual(stop.currentSnapshot.dataStack, [10, 20]);

const abort = new MonitorExecutionControl();
const initial = snapshot([7]);
abort.start(initial);
initial.dataStack.push(99);
abort.requestAbort();
assert.equal(abort.state, STATES.ABORT_REQUESTED);
assert.equal(abort.atInstructionBoundary(snapshot([7, 8], "WORK", 2)), "aborted");
assert.equal(abort.state, STATES.ABORTED);
assert.deepEqual(abort.currentSnapshot.dataStack, [7]);
assert.deepEqual(abort.initialSnapshot.dataStack, [7]);
abort.confirmRollback({ ...snapshot([7]), output: "already visible" });
assert.equal(abort.currentSnapshot.output, "already visible");

const pausedAbort = new MonitorExecutionControl();
pausedAbort.start(snapshot([4]));
pausedAbort.requestPause();
pausedAbort.atInstructionBoundary(snapshot([4, 5]));
pausedAbort.requestAbort();
assert.equal(pausedAbort.state, STATES.ABORTED);
assert.deepEqual(pausedAbort.currentSnapshot.dataStack, [4]);

const completed = new MonitorExecutionControl();
completed.start(snapshot([]));
completed.complete(snapshot([5]));
assert.equal(completed.state, STATES.COMPLETED);
assert.equal(completed.stopReason, "completed");

const failed = new MonitorExecutionControl();
failed.start(snapshot([]));
failed.fail(snapshot([7, 0]), { name: "DivisionByZero" });
assert.equal(failed.state, STATES.FAILED);
assert.deepEqual(failed.currentSnapshot.dataStack, [7, 0]);
failed.requestAbort();
assert.equal(failed.state, STATES.ABORTED);
assert.deepEqual(failed.currentSnapshot.dataStack, []);

assert.throws(() => new MonitorExecutionControl().requestPause(), MonitorTransitionError);
assert.throws(() => stop.continueExecution(), MonitorTransitionError);
assert.ok(pause.transitions.every((item, index) => item.sequence === index + 1));

console.log("mobile monitor state tests: PASS");
