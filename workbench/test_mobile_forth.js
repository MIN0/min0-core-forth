"use strict";

const assert = require("node:assert/strict");
const { MobileForth, tokenize } = require("../viewer/mobile-forth-core.js");

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

console.log("mobile forth tests: PASS");
