"use strict";
const assert = require("node:assert/strict");
const { execute } = require("../viewer/virtual-assembler-core.js");

const add = `CODE: ADD-TEST ( a b -- result )
  IN V0, a
  IN V1, b
  ADD V0, V1
  OUT result, V0
;CODE`;
let result = execute(add, [12, 30]);
assert.equal(result.ok, true);
assert.deepEqual(result.afterStack, [42]);
assert.equal(result.trace.length, 4);

const maximum = `CODE: MAX ( a b -- max )
  IN V0, a
  IN V1, b
  CMP V0, V1
  BGE @a-wins
  OUT max, V1
  BRA @done
@a-wins:
  OUT max, V0
@done:
;CODE`;
assert.deepEqual(execute(maximum, [10, 20]).afterStack, [20]);
assert.deepEqual(execute(maximum, [30, 20]).afterStack, [30]);

const memory = `CODE: ROUND-TRIP ( value address -- observed )
  IN V0, value
  IN V1, address
  ST32 [DATA: V1], V0
  LD32 V2, [DATA: V1]
  OUT observed, V2
;CODE`;
result = execute(memory, [55, 0x1000]);
assert.equal(result.ok, true);
assert.deepEqual(result.afterStack, [55]);
assert.equal(result.memoryCommitted, 1);
result = execute(memory, [55, 0x2000]);
assert.equal(result.ok, false);
assert.equal(result.error.code, "E-MEM-RANGE");
assert.deepEqual(result.afterStack, [55, 0x2000]);
assert.equal(result.memoryCommitted, 0);

console.log("virtual assembler browser tests: PASS");
