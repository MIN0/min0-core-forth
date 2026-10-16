"use strict";

const assert = require("node:assert/strict");
const { MobileForth, tokenize, WORD_METADATA } = require("../viewer/mobile-forth-core.js");

function run(source, options = {}) {
  return new MobileForth(options).interpret(source);
}

function ok(source, stack, terminal = "") {
  const result = run(source);
  assert.equal(result.ok, true, result.error && result.error.message);
  assert.deepEqual(result.dataStack, stack, source);
  assert.equal(result.terminal, terminal, source);
  return result;
}

const metadataNames = WORD_METADATA.map(item => item.name);
assert.equal(new Set(metadataNames).size, metadataNames.length, "word metadata names must be unique");
Object.keys(new MobileForth().builtins()).forEach(name => assert.ok(metadataNames.includes(name), `metadata missing for ${name}`));

const inputVm = new MobileForth();
inputVm.executeWord("KEY?");
assert.deepEqual(inputVm.stackSnapshot(), [0]);
inputVm.stack.length = 0;
assert.equal(inputVm.enqueueInput("Aあ"), 4, "input queue stores UTF-8 bytes");
inputVm.executeWord("KEY?");
assert.deepEqual(inputVm.stackSnapshot(), [-1]);
assert.equal(inputVm.inputQueue.length, 4, "KEY? must not consume input");
inputVm.stack.length = 0;
inputVm.executeWord("KEY");
assert.deepEqual(inputVm.stackSnapshot(), [65]);
assert.equal(inputVm.inputQueue.length, 3, "KEY consumes exactly one UTF-8 byte");
assert.throws(() => inputVm.enqueueInput("x".repeat(254)), /input queue exceeds 256 UTF-8 bytes/);
const inputState = inputVm.captureTransactionalState();
inputVm.inputQueue.length = 0;
inputVm.restoreTransactionalState(inputState);
assert.equal(inputVm.inputQueue.length, 3, "input queue participates in rollback state");
assert.throws(() => new MobileForth().executeWord("KEY"), /KEY needs one queued input byte/);

ok("2 3 4 * + . CR", [], "14\n");
ok("1 2 3 ROT", [2, 3, 1]);
ok("7 8 2DUP", [7, 8, 7, 8]);
ok("7 8 2DROP DEPTH", [0]);
ok("1 2 OVER SWAP", [1, 1, 2]);
ok("-7 3 /MOD", [-1, -2]);
ok("-7 3 /", [-2]);
ok("-7 3 MOD", [-1]);
ok("-5 ABS 5 = 0=", [0]);
ok("10 .S", [10], "<1> 10");
ok('65 EMIT ." BC" CR', [], "ABC\n");
ok(": SQUARE DUP * ; 5 SQUARE .", [], "25");
ok(": MAG DUP 0 < IF NEGATE ELSE 1+ THEN ; -5 MAG 4 MAG", [5, 5]);
ok(": DOWN BEGIN 1- DUP 0= UNTIL ; 3 DOWN", [0]);
ok(": SUM 0 SWAP 0 DO I + LOOP ; 5 SUM", [10]);
ok(": EMPTY 99 SWAP DUP ?DO 1 + LOOP ; 3 EMPTY", [99]);
ok(": TWOS 0 SWAP 0 DO I + 2 +LOOP ; 6 TWOS", [6]);
ok(": FIRST 0 SWAP 0 DO I + LEAVE LOOP ; 9 FIRST", [0]);
ok("( stack effect comment ) 1 ( across\nlines ) 2 +", [3]);
ok('." (this is text)"', [], "(this is text)");
ok(": HEX-DIGIT ( n -- ) DUP 10 < IF 48 + ELSE 10 - 65 + THEN EMIT ; : HEX-PRT ( u -- ) DUP 16 < IF HEX-DIGIT ELSE 16 /MOD RECURSE HEX-DIGIT THEN ; 255 HEX-PRT CR", [], "FF\n");

const atomic = run("7 0 /MOD");
assert.equal(atomic.ok, false);
assert.equal(atomic.error.name, "DivisionByZero");
assert.deepEqual(atomic.dataStack, [7, 0]);
assert.equal(atomic.executionState, "error-rolled-back");
assert.deepEqual(atomic.initialDataStack, []);
assert.deepEqual(atomic.stoppedDataStack, [7, 0]);
assert.deepEqual(atomic.recoveredDataStack, []);
assert.deepEqual(atomic.finalDataStack, []);
assert.equal(atomic.recovery.performed, true);
assert.equal(atomic.recovery.outputReversible, false);

const completedLifecycle = run("2 3 +");
assert.equal(completedLifecycle.executionState, "completed");
assert.deepEqual(completedLifecycle.initialDataStack, []);
assert.equal(completedLifecycle.stoppedDataStack, null);
assert.equal(completedLifecycle.recoveredDataStack, null);
assert.deepEqual(completedLifecycle.finalDataStack, [5]);
assert.equal(completedLifecycle.recovery.performed, false);

const rollbackVm = new MobileForth();
const rolledBack = rollbackVm.interpret(': TEMP 1 ; TEMP ." BEFORE" NOPE');
assert.equal(rolledBack.ok, false);
assert.equal(rolledBack.terminal, "BEFORE");
assert.deepEqual(rolledBack.stoppedDataStack, [1]);
assert.deepEqual(rolledBack.finalDataStack, []);
assert.deepEqual(rollbackVm.stackSnapshot(), []);
assert.equal(rollbackVm.dictionary.size, 0);
assert.ok(rolledBack.wordCatalog.some(item => item.name === "TEMP"), "failed-run word catalog must remain available for diagnosis");
assert.match(rolledBack.recovery.note, /端末出力は取り消せません/);

const unknown = run("NO-SUCH-WORD");
assert.equal(unknown.ok, false);
assert.equal(unknown.error.name, "UnknownWord");

const runaway = run(": FOREVER BEGIN AGAIN ; FOREVER", { maxSteps: 40 });
assert.equal(runaway.ok, false);
assert.equal(runaway.error.name, "StepLimitExceeded");

assert.deepEqual(tokenize("1 \\ comment\n2"), ["1", "2"]);
assert.equal(run(": BAD IF ;").error.name, "CompileError");
assert.equal(run("DUP").error.name, "StackUnderflow");

const openComment = run("1 ( missing close");
assert.equal(openComment.ok, false);
assert.equal(openComment.error.name, "CompileError");
assert.match(openComment.error.message, /line 1, column 3/);

const topLevelRecurse = run("RECURSE");
assert.equal(topLevelRecurse.ok, false);
assert.equal(topLevelRecurse.error.name, "CompileError");

const deepRecursion = run(": DIVE 1+ RECURSE ; 0 DIVE");
assert.equal(deepRecursion.ok, false);
assert.equal(deepRecursion.error.name, "CallDepthExceeded");

const nestedTrace = ok(": INNER\n 1+\n;\n: OUTER\n INNER DUP\n;\n4 OUTER", [5, 5]);
const outerCall = nestedTrace.words.find(item => item.scope === "colon" && item.word === "OUTER" && item.token === "INNER");
const innerStep = nestedTrace.words.find(item => item.scope === "colon" && item.word === "INNER" && item.token === "1+");
assert.ok(outerCall, "OUTER must expose its INNER instruction");
assert.ok(innerStep, "INNER must expose its 1+ instruction");
assert.equal(outerCall.callDepth, 1);
assert.equal(innerStep.callDepth, 2);
assert.notEqual(outerCall.invocationId, innerStep.invocationId);
assert.deepEqual(innerStep.dataBefore, [4]);
assert.deepEqual(innerStep.dataAfter, [5]);
assert.deepEqual(innerStep.returnStackBefore, ["OUTER", "INNER"]);
assert.equal(innerStep.status, "ok");
assert.deepEqual(nestedTrace.userWords, [{ id: 1, name: "INNER" }, { id: 2, name: "OUTER" }]);
assert.equal(outerCall.wordId, 2);
assert.equal(innerStep.wordId, 1);
assert.equal(outerCall.sourceLine, 5);
assert.equal(outerCall.sourceColumn, 2);
assert.equal(innerStep.sourceLine, 2);
assert.equal(innerStep.sourceColumn, 2);

const catalogTrace = ok(": DOUBLE ( n -- n2 ) DUP + ; 3 DOUBLE", [6]);
const doubleMeta = catalogTrace.wordCatalog.find(item => item.id === 1 && item.name === "DOUBLE");
assert.ok(doubleMeta);
assert.equal(doubleMeta.stackEffect, "( n -- n2 )");
assert.equal(doubleMeta.category, "利用者定義");
assert.equal(doubleMeta.invocationCount, 1);
assert.deepEqual(doubleMeta.lastDataBefore, [3]);
assert.deepEqual(doubleMeta.lastDataAfter, [6]);
assert.match(doubleMeta.source, /^: DOUBLE/);
const dupMeta = catalogTrace.wordCatalog.find(item => item.name === "DUP" && item.type === "builtin");
assert.equal(dupMeta.stackEffect, "( x -- x x )");
assert.match(dupMeta.description, /複製/);

const failedTrace = run(": BAD 0 /MOD ; 7 BAD");
assert.equal(failedTrace.ok, false);
assert.equal(failedTrace.error.word, "BAD");
assert.equal(failedTrace.error.wordId, 1);
assert.equal(failedTrace.error.instructionIndex, 2);
const failedInstruction = failedTrace.words.find(item => item.scope === "colon" && item.word === "BAD" && item.token === "/MOD");
assert.ok(failedInstruction, "failed colon instruction must remain observable");
assert.equal(failedInstruction.status, "error");
assert.equal(failedInstruction.error.name, "DivisionByZero");
assert.deepEqual(failedInstruction.dataBefore, [7, 0]);
assert.deepEqual(failedInstruction.dataAfter, [7, 0]);

const boundedTrace = run("1 2 3 4 5 6 7 8", { maxTraceEvents: 6 });
assert.equal(boundedTrace.ok, true);
assert.deepEqual(boundedTrace.words.map(item => item.sequence), [1, 2, 3, 6, 7, 8]);
assert.deepEqual(boundedTrace.traceSummary, { limit: 6, recorded: 6, omitted: 2, total: 8 });

const loopTrace = run(": COUNT 0 DO I DROP LOOP ; 6 COUNT");
assert.equal(loopTrace.ok, true);
const loopBody = loopTrace.words.filter(item => item.scope === "colon" && item.word === "COUNT" && item.token === "I");
assert.deepEqual(loopBody.map(item => item.loopStackBefore[0].iteration), [0, 1, 2, 3, 4, 5]);
assert.equal(new Set(loopBody.map(item => item.loopStackBefore[0].loopId)).size, 1);
assert.deepEqual(loopBody.map(item => item.loopStackBefore[0].index), [0, 1, 2, 3, 4, 5]);

console.log("mobile forth tests: PASS");
