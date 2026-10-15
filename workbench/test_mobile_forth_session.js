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
]) {
  const synchronous = new MobileForth().interpret(source);
  const session = finish(source);
  assert.deepEqual(session.vm.stackSnapshot(), synchronous.finalDataStack, source);
  assert.equal(session.vm.output, synchronous.terminal, source);
  assert.equal(session.vm.steps, synchronous.steps, source);
}

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
