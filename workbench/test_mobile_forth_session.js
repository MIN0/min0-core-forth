"use strict";

const assert = require("node:assert/strict");
const { MobileForth } = require("../viewer/mobile-forth-core.js");
const { STATES } = require("../viewer/mobile-monitor-state.js");
const { MobileForthSession } = require("../viewer/mobile-forth-session.js");

function finish(source) {
  const session = new MobileForthSession(source);
  session.runUntilBlocked();
  assert.equal(session.state, STATES.COMPLETED, session.error && session.error.message);
  return session;
}

for (const source of [
  "2 3 4 * +",
  ": SQUARE DUP * ; 5 SQUARE",
  ": MAG DUP 0 < IF NEGATE ELSE 1+ THEN ; -5 MAG 4 MAG",
  ": SUM 0 SWAP 0 DO I + LOOP ; 5 SUM",
  ': HEX-DIGIT DUP 10 < IF 48 + ELSE 10 - 65 + THEN EMIT ; : HEX-PRT DUP 16 < IF HEX-DIGIT ELSE 16 /MOD RECURSE HEX-DIGIT THEN ; 255 HEX-PRT CR',
  "VARIABLE SCORE : ADD-SCORE SCORE @ + SCORE ! ; 10 SCORE ! 5 ADD-SCORE SCORE @",
]) {
  const synchronous = new MobileForth().interpret(source);
  const session = finish(source);
  assert.deepEqual(session.vm.stackSnapshot(), synchronous.finalDataStack, source);
  assert.equal(session.vm.output, synchronous.terminal, source);
  assert.equal(session.vm.steps, synchronous.steps, source);
}

const safeVariable = finish("VARIABLE SCORE 42 SCORE ! SCORE @");
assert.deepEqual(safeVariable.vm.stackSnapshot(), [42]);
assert.equal(safeVariable.vm.variableMemory.get(safeVariable.vm.variables.get("SCORE")), 42);

const invalidVariableAddress = new MobileForthSession("7 123 !");
invalidVariableAddress.runUntilBlocked();
assert.equal(invalidVariableAddress.state, STATES.FAILED);
assert.equal(invalidVariableAddress.error.name, "InvalidAddress");
assert.deepEqual(invalidVariableAddress.vm.stackSnapshot(), [7, 123]);
invalidVariableAddress.requestAbort();
assert.equal(invalidVariableAddress.state, STATES.ABORTED);
assert.deepEqual(invalidVariableAddress.vm.stackSnapshot(), []);

const abortedVariable = new MobileForthSession("VARIABLE SCORE 42 SCORE ! SCORE @");
abortedVariable.advance();
abortedVariable.advance();
abortedVariable.advance();
abortedVariable.advance();
assert.equal(abortedVariable.vm.variableMemory.get(abortedVariable.vm.variables.get("SCORE")), 42);
abortedVariable.requestAbort();
abortedVariable.advance();
assert.equal(abortedVariable.state, STATES.ABORTED);
assert.equal(abortedVariable.vm.variables.size, 0);
assert.equal(abortedVariable.vm.variableMemory.size, 0);
assert.equal(abortedVariable.vm.nextVariableAddress, 0x10000000);

const pausedVariable = new MobileForthSession("VARIABLE SCORE 10 SCORE ! : SPIN BEGIN 1 DROP AGAIN ; SPIN");
pausedVariable.advance();
pausedVariable.requestPause();
pausedVariable.advance();
assert.equal(pausedVariable.state, STATES.PAUSED);
const variableEdit = pausedVariable.writeVariable("SCORE", -7);
assert.deepEqual(variableEdit, { sequence: 1, name: "SCORE", address: 0x10000000, before: 0, after: -7, steps: 1 });
assert.equal(pausedVariable.status().currentSnapshot.variables[0].value, -7);
assert.throws(() => pausedVariable.writeVariable("MISSING", 1), /unknown variable MISSING/);
pausedVariable.continueExecution();
assert.throws(() => pausedVariable.writeVariable("SCORE", 2), /not allowed while running/);
pausedVariable.requestAbort();
pausedVariable.advance();
assert.equal(pausedVariable.state, STATES.ABORTED);
assert.equal(pausedVariable.vm.variables.size, 0);

const explicitBreak = new MobileForthSession("VARIABLE SCORE : WATCH 1 SCORE ! BREAK 2 SCORE ! ; WATCH SCORE @");
explicitBreak.runUntilBlocked();
assert.equal(explicitBreak.state, STATES.PAUSED);
assert.equal(explicitBreak.status().currentSnapshot.reason, "break");
assert.equal(explicitBreak.status().currentSnapshot.location.word, "WATCH");
assert.equal(explicitBreak.status().currentSnapshot.location.token, "BREAK");
assert.equal(explicitBreak.vm.variableMemory.get(explicitBreak.vm.variables.get("SCORE")), 1);
explicitBreak.continueExecution();
explicitBreak.runUntilBlocked();
assert.equal(explicitBreak.state, STATES.COMPLETED);
assert.deepEqual(explicitBreak.vm.stackSnapshot(), [2]);

const breakAbort = new MobileForthSession("VARIABLE SCORE : WATCH 7 SCORE ! BREAK ; WATCH");
breakAbort.runUntilBlocked();
assert.equal(breakAbort.state, STATES.PAUSED);
breakAbort.requestAbort();
assert.equal(breakAbort.state, STATES.ABORTED);
assert.equal(breakAbort.vm.variables.size, 0);
assert.equal(breakAbort.status().currentSnapshot.reason, "abort-rollback");

const controlled = new MobileForthSession(": TWICE 1+ 1+ ; 10 TWICE 3 +");
controlled.advance(); // definition
controlled.advance(); // literal 10
controlled.advance(); // enter TWICE
controlled.requestPause();
controlled.advance(); // first 1+, then pause
assert.equal(controlled.state, STATES.PAUSED);
assert.deepEqual(controlled.vm.stackSnapshot(), [11]);
assert.equal(controlled.status().currentSnapshot.location.word, "TWICE");
controlled.step();
controlled.advance(); // second 1+, then pause
assert.equal(controlled.state, STATES.PAUSED);
assert.deepEqual(controlled.vm.stackSnapshot(), [12]);
controlled.continueExecution();
controlled.runUntilBlocked();
assert.equal(controlled.state, STATES.COMPLETED);
assert.deepEqual(controlled.vm.stackSnapshot(), [15]);

const stopped = new MobileForthSession("1 2 3 + +");
stopped.advance();
stopped.requestStop();
stopped.advance();
assert.equal(stopped.state, STATES.STOPPED);
assert.deepEqual(stopped.vm.stackSnapshot(), [1, 2]);

const inputReady = new MobileForthSession("KEY?");
assert.equal(inputReady.enqueueInput("A"), 1);
inputReady.runUntilBlocked();
assert.equal(inputReady.state, STATES.COMPLETED);
assert.deepEqual(inputReady.vm.stackSnapshot(), [-1]);
assert.equal(inputReady.vm.inputQueue.length, 1, "KEY? does not consume queued input");
assert.equal(inputReady.status().currentSnapshot.inputDepth, 1);

const inputWaiting = new MobileForthSession(": READ KEY ; READ 1+");
inputWaiting.runUntilBlocked();
assert.equal(inputWaiting.state, STATES.WAITING_INPUT);
assert.equal(inputWaiting.vm.steps, 1, "READ entry executes, while the empty KEY consumes no step");
assert.equal(inputWaiting.status().currentSnapshot.location.word, "READ");
assert.equal(inputWaiting.status().currentSnapshot.location.token, "KEY");
inputWaiting.enqueueInput("A");
assert.equal(inputWaiting.state, STATES.RUNNING);
inputWaiting.runUntilBlocked();
assert.equal(inputWaiting.state, STATES.COMPLETED);
assert.deepEqual(inputWaiting.vm.stackSnapshot(), [66]);
assert.equal(inputWaiting.vm.inputQueue.length, 0);

const steppedKey = new MobileForthSession("KEY 1+");
steppedKey.requestPause();
steppedKey.advance();
assert.equal(steppedKey.state, STATES.PAUSED);
steppedKey.step();
steppedKey.advance();
assert.equal(steppedKey.state, STATES.WAITING_INPUT);
steppedKey.enqueueInput("A");
assert.equal(steppedKey.state, STATES.STEPPING);
steppedKey.advance();
assert.equal(steppedKey.state, STATES.PAUSED);
assert.deepEqual(steppedKey.vm.stackSnapshot(), [65]);

const pausedInput = new MobileForthSession("KEY EMIT KEY EMIT");
pausedInput.runUntilBlocked();
assert.equal(pausedInput.state, STATES.WAITING_INPUT);
pausedInput.requestPause();
assert.equal(pausedInput.state, STATES.PAUSED);
assert.equal(pausedInput.enqueueInput("AB"), 2);
assert.equal(pausedInput.state, STATES.PAUSED, "input sent while paused must not resume execution");
assert.equal(pausedInput.status().currentSnapshot.inputDepth, 2);
pausedInput.continueExecution();
pausedInput.runUntilBlocked();
assert.equal(pausedInput.state, STATES.COMPLETED);
assert.equal(pausedInput.vm.output, "AB");
assert.equal(pausedInput.vm.inputQueue.length, 0);

const stoppedKey = new MobileForthSession("KEY 1+");
stoppedKey.runUntilBlocked();
stoppedKey.requestStop();
assert.equal(stoppedKey.state, STATES.STOPPED);
assert.deepEqual(stoppedKey.vm.stackSnapshot(), []);

const abortedKey = new MobileForthSession("9 KEY 1+");
abortedKey.runUntilBlocked();
assert.equal(abortedKey.state, STATES.WAITING_INPUT);
assert.deepEqual(abortedKey.vm.stackSnapshot(), [9]);
abortedKey.enqueueInput("A");
abortedKey.requestAbort();
assert.equal(abortedKey.state, STATES.ABORT_REQUESTED);
abortedKey.advance();
assert.equal(abortedKey.state, STATES.ABORTED);
assert.deepEqual(abortedKey.vm.stackSnapshot(), []);
assert.equal(abortedKey.vm.inputQueue.length, 0, "Abort restores the initial empty input queue");

const aborted = new MobileForthSession(": KEEP 99 ; 7 KEEP");
aborted.advance();
aborted.advance();
assert.ok(aborted.vm.dictionary.has("KEEP"));
aborted.requestAbort();
aborted.advance();
assert.equal(aborted.state, STATES.ABORTED);
assert.deepEqual(aborted.vm.stackSnapshot(), []);
assert.equal(aborted.vm.dictionary.size, 0);

const outputAbort = new MobileForthSession('." VISIBLE" 9');
outputAbort.advance();
assert.equal(outputAbort.vm.output, "VISIBLE");
outputAbort.requestAbort();
outputAbort.advance();
assert.equal(outputAbort.state, STATES.ABORTED);
assert.deepEqual(outputAbort.vm.stackSnapshot(), []);
assert.equal(outputAbort.vm.output, "VISIBLE");
assert.equal(outputAbort.status().currentSnapshot.output, "VISIBLE");

const emptyStop = new MobileForthSession("");
emptyStop.requestStop();
emptyStop.advance();
assert.equal(emptyStop.state, STATES.STOPPED);

const failed = new MobileForthSession(": BAD 0 /MOD ; 7 BAD");
failed.runUntilBlocked();
assert.equal(failed.state, STATES.FAILED);
assert.deepEqual(failed.vm.stackSnapshot(), [7, 0]);
assert.equal(failed.error.name, "DivisionByZero");
assert.equal(failed.error.location.word, "BAD");
assert.equal(failed.error.location.instructionIndex, 2);
assert.deepEqual(failed.status().currentSnapshot.returnStack, ["BAD"]);
assert.equal(failed.status().currentSnapshot.callFrames[0].type, "CALL_RETURN");
failed.requestAbort();
assert.equal(failed.state, STATES.ABORTED);
assert.deepEqual(failed.vm.stackSnapshot(), []);
assert.equal(failed.vm.dictionary.size, 0);

console.log("mobile forth session tests: PASS");
