(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./mobile-forth-core.js"), require("./mobile-monitor-state.js"));
  } else {
    root.Min0MobileForthSession = factory(root.Min0MobileForth, root.Min0MobileMonitor);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (core, monitor) {
  "use strict";

  if (!core || !monitor) throw new Error("MobileForth core and Monitor state modules are required");

  const { MobileForth, tokenizeDetailed, parseNumber, compileBody, signed, MAX_SOURCE_BYTES, MAX_CALL_DEPTH, errors } = core;
  const { STATES, MonitorExecutionControl, MonitorTransitionError } = monitor;
  const { UnknownWord, StackUnderflow, CompileError, CallDepthExceeded } = errors;
  const COMPILE_ONLY = [";", "IF", "ELSE", "THEN", "BEGIN", "UNTIL", "AGAIN", "WHILE", "REPEAT", "DO", "?DO", "LOOP", "+LOOP", "LEAVE", "RECURSE"];

  class MobileForthSession {
    constructor(source, options = {}) {
      this.source = source;
      this.vm = new MobileForth(options);
      this.initialState = this.vm.captureTransactionalState();
      this.tokens = [];
      this.mainIndex = 0;
      this.frames = [];
      this.error = null;
      this.failureSnapshot = null;
      this.preRollbackDiagnostics = null;
      this.lastBoundary = null;
      this.control = new MonitorExecutionControl();
      if (new TextEncoder().encode(source).length > MAX_SOURCE_BYTES) throw new CompileError(`source exceeds ${MAX_SOURCE_BYTES} UTF-8 bytes`);
      this.tokens = tokenizeDetailed(source);
      this.control.start(this.snapshot("start"));
    }

    get state() { return this.control.state; }

    activeFrame() { return this.frames.length ? this.frames[this.frames.length - 1] : null; }

    location() {
      const frame = this.activeFrame();
      if (frame) {
        const instruction = frame.code[frame.ip] || null;
        return {
          word: frame.word,
          wordId: frame.wordId,
          invocationId: frame.invocationId,
          callDepth: frame.callDepth,
          instructionIndex: instruction ? frame.ip + 1 : null,
          sourceLine: instruction && instruction.sourceLine || null,
          sourceColumn: instruction && instruction.sourceColumn || null,
          token: instruction ? this.vm.instructionLabel(instruction) : "return",
        };
      }
      const sourceToken = this.tokens[this.mainIndex] || null;
      return {
        word: "#0 MAIN",
        wordId: 0,
        invocationId: 0,
        callDepth: 0,
        instructionIndex: sourceToken ? this.mainIndex + 1 : null,
        sourceLine: sourceToken && sourceToken.line || null,
        sourceColumn: sourceToken && sourceToken.column || null,
        token: sourceToken ? (typeof sourceToken.value === "object" ? '."' : sourceToken.value) : "end",
      };
    }

    snapshot(reason = "instruction-boundary") {
      return {
        reason,
        steps: this.vm.steps,
        dataStack: this.vm.stackSnapshot(),
        returnStack: [...this.vm.returnStack],
        loopStack: this.vm.loopSnapshot(),
        output: this.vm.output,
        location: this.location(),
        callFrames: this.frames.map(frame => ({
          type: "CALL_RETURN",
          word: frame.word,
          wordId: frame.wordId,
          invocationId: frame.invocationId,
          callDepth: frame.callDepth,
          nextInstruction: frame.ip + 1,
        })),
        inputDepth: this.vm.inputQueue.length,
      };
    }

    enqueueInput(text) {
      const count = this.vm.enqueueInput(text);
      if (this.state === STATES.WAITING_INPUT) this.control.inputAvailable(this.snapshot("input-available"));
      else this.control.observe(this.snapshot("input-enqueued"), "input-enqueued");
      return count;
    }

    requestPause() { return this.control.requestPause(); }
    continueExecution() { return this.control.continueExecution(); }
    step() { return this.control.step(); }
    requestStop() { return this.control.requestStop(); }

    requestAbort() {
      this.control.requestAbort();
      if (this.control.state === STATES.ABORTED) this.rollback();
      return this.control.status();
    }

    rollback() {
      if (!this.preRollbackDiagnostics) this.preRollbackDiagnostics = this.buildDiagnostics();
      this.vm.restoreTransactionalState(this.initialState);
      this.frames = [];
      this.mainIndex = 0;
      this.lastBoundary = this.snapshot("abort-rollback");
      this.control.confirmRollback(this.lastBoundary);
    }

    buildDiagnostics() {
      const clone = value => JSON.parse(JSON.stringify(value));
      const userWords = [...this.vm.wordDefinitions.values()].map(item => ({ id: item.id, name: item.name })).sort((left, right) => left.id - right.id);
      return {
        words: clone(this.vm.traceEvents()),
        traceSummary: { limit: this.vm.maxTraceEvents, recorded: Math.min(this.vm.traceSequence, this.vm.maxTraceEvents), omitted: this.vm.omittedTraceEvents, total: this.vm.traceSequence },
        userWords,
        wordCatalog: clone(this.vm.wordCatalog()),
        error: clone(this.error),
        failureSnapshot: clone(this.failureSnapshot),
      };
    }

    diagnostics() { return this.preRollbackDiagnostics || this.buildDiagnostics(); }

    enterDefinition(name, code, pendingEvent) {
      if (this.vm.returnStack.length >= MAX_CALL_DEPTH) throw new CallDepthExceeded(`call depth ${MAX_CALL_DEPTH} exceeded`);
      const frame = { word: name, wordId: this.vm.wordIds.get(name) || null, invocationId: this.vm.nextInvocationId, callDepth: this.frames.length + 1, code, ip: 0, pendingEvent };
      this.vm.nextInvocationId += 1;
      const runtime = this.vm.wordRuntime.get(frame.wordId) || { invocationCount: 0, lastDataBefore: [], lastDataAfter: [] };
      runtime.invocationCount += 1;
      runtime.lastDataBefore = this.vm.stackSnapshot();
      this.vm.wordRuntime.set(frame.wordId, runtime);
      frame.runtime = runtime;
      this.vm.returnStack.push(name);
      this.vm.callFrames.push({ word: name, wordId: frame.wordId, invocationId: frame.invocationId, callDepth: frame.callDepth });
      this.frames.push(frame);
    }

    settleCompletedFrames() {
      while (this.frames.length) {
        const frame = this.activeFrame();
        if (frame.ip < frame.code.length) break;
        frame.runtime.lastDataAfter = this.vm.stackSnapshot();
        this.frames.pop();
        this.vm.callFrames.pop();
        this.vm.returnStack.pop();
        if (frame.pendingEvent) this.vm.finishTrace(frame.pendingEvent);
      }
    }

    unwindFailedFrames(error) {
      while (this.frames.length) {
        const frame = this.frames.pop();
        frame.runtime.lastDataAfter = this.vm.stackSnapshot();
        this.vm.callFrames.pop();
        this.vm.returnStack.pop();
        if (frame.pendingEvent && frame.pendingEvent.status === "running") this.vm.finishTrace(frame.pendingEvent, error);
      }
    }

    defineAtMain(event) {
      const sourceToken = this.tokens[this.mainIndex];
      const nameToken = this.tokens[this.mainIndex + 1];
      const name = nameToken && nameToken.value;
      if (typeof name !== "string" || [":", ";"].includes(name)) throw new CompileError(":" + " requires a word name");
      const body = [];
      let index = this.mainIndex + 2;
      while (index < this.tokens.length && this.tokens[index].value !== ";") { body.push(this.tokens[index]); index += 1; }
      if (index >= this.tokens.length) throw new CompileError(`definition ${name} is missing ;`);
      const previousAddress = this.vm.variables.get(name);
      if (previousAddress !== undefined) this.vm.variableMemory.delete(previousAddress);
      this.vm.variables.delete(name);
      this.vm.dictionary.set(name, compileBody(body));
      this.vm.wordIds.set(name, this.vm.nextWordId);
      event.wordId = this.vm.nextWordId;
      const terminator = this.tokens[index];
      const firstBodyStart = body.length ? body[0].start : terminator.start;
      const stackComment = this.source.slice(nameToken.end, firstBodyStart).match(/\(\s*([^)]*--[^)]*)\)/s);
      this.vm.wordDefinitions.set(this.vm.nextWordId, {
        id: this.vm.nextWordId,
        name,
        type: "colon",
        category: "利用者定義",
        stackEffect: stackComment ? `( ${stackComment[1].trim().replace(/\s+/g, " ")} )` : "未記載",
        description: "このsourceで登録したcolon wordです。",
        availability: "実行・定義内",
        source: this.source.slice(sourceToken.start, terminator.end),
      });
      this.vm.nextWordId += 1;
      event.token = `: ${name} ... ;`;
      event.word = name;
      event.scope = "definition";
      this.mainIndex = index + 1;
    }

    defineVariableAtMain(event) {
      const sourceToken = this.tokens[this.mainIndex];
      const nameToken = this.tokens[this.mainIndex + 1];
      const name = nameToken && nameToken.value;
      const address = this.vm.defineVariable(name, nameToken ? this.source.slice(sourceToken.start, nameToken.end) : "VARIABLE");
      event.wordId = this.vm.wordIds.get(name);
      event.token = `VARIABLE ${name}`;
      event.word = name;
      event.scope = "definition";
      event.op = "DEFINE_VARIABLE";
      event.address = address;
      this.mainIndex += 2;
    }

    dispatchWord(name, pendingEvent, recurseCode = null) {
      if (recurseCode) {
        const currentName = this.vm.returnStack[this.vm.returnStack.length - 1];
        if (!currentName) throw new CompileError("RECURSE requires a colon definition");
        this.enterDefinition(currentName, recurseCode, pendingEvent);
        return "entered";
      }
      this.vm.step();
      const builtin = this.vm.builtins()[name];
      if (builtin) { builtin(); return "completed"; }
      if (this.vm.variables.has(name)) { this.vm.push(this.vm.variables.get(name)); return "completed"; }
      const code = this.vm.dictionary.get(name);
      if (!code) throw new UnknownWord(`unknown word ${name}`);
      this.enterDefinition(name, code, pendingEvent);
      return "entered";
    }

    waitForInput() {
      const snapshot = this.snapshot("waiting-input");
      if ([STATES.PAUSE_REQUESTED, STATES.STOP_REQUESTED, STATES.ABORT_REQUESTED].includes(this.state)) {
        const outcome = this.control.atInstructionBoundary(snapshot);
        if (outcome === "aborted") this.rollback();
      } else this.control.waitForInput(snapshot);
      this.lastBoundary = this.control.currentSnapshot;
      return "waiting-input";
    }

    executeMainInstruction() {
      const sourceToken = this.tokens[this.mainIndex];
      const token = sourceToken.value;
      if (token === "KEY" && !this.vm.inputQueue.length) return this.waitForInput();
      const event = this.vm.beginTrace({ scope: "main", word: "#0 MAIN", wordId: 0, invocationId: 0, callDepth: 0, instructionIndex: this.mainIndex + 1, sourceLine: sourceToken.line, sourceColumn: sourceToken.column, token: typeof token === "object" ? '."' : token, op: token === ":" ? "DEFINE" : "TOKEN" });
      let pending = false;
      try {
        if (token === ":") this.defineAtMain(event);
        else if (token === "VARIABLE") this.defineVariableAtMain(event);
        else {
          this.mainIndex += 1;
          if (typeof token === "object" && token.kind === "PRINT") { this.vm.step(); this.vm.output += token.text; }
          else {
            const number = parseNumber(token);
            if (number !== null) { this.vm.step(); this.vm.push(number); }
            else {
              if (COMPILE_ONLY.includes(token)) throw new CompileError(`${token} is compile-only`);
              pending = this.dispatchWord(token, event) === "entered";
            }
          }
        }
        if (!pending) this.vm.finishTrace(event);
      } catch (error) {
        this.vm.finishTrace(event, error);
        throw error;
      }
    }

    executeColonInstruction(frame) {
      const instruction = frame.code[frame.ip];
      if (instruction.op === "WORD" && instruction.name === "KEY" && !this.vm.inputQueue.length) return this.waitForInput();
      const event = this.vm.beginTrace({ scope: "colon", word: frame.word, wordId: frame.wordId, invocationId: frame.invocationId, callDepth: frame.callDepth, instructionIndex: frame.ip + 1, sourceLine: instruction.sourceLine, sourceColumn: instruction.sourceColumn, token: this.vm.instructionLabel(instruction), op: instruction.op });
      let nextIp = frame.ip + 1;
      let pending = false;
      try {
        this.vm.step();
        if (instruction.op === "LIT") this.vm.push(instruction.value);
        else if (instruction.op === "PRINT") this.vm.output += instruction.text;
        else if (instruction.op === "WORD") pending = this.dispatchWord(instruction.name, event) === "entered";
        else if (instruction.op === "RECURSE") pending = this.dispatchWord(null, event, frame.code) === "entered";
        else if (instruction.op === "JUMP") nextIp = instruction.target;
        else if (instruction.op === "JZ") { if (this.vm.pop("branch") === 0) nextIp = instruction.target; }
        else if (instruction.op === "DO" || instruction.op === "?DO") {
          this.vm.need(2, instruction.op);
          const start = this.vm.stack[this.vm.stack.length - 1];
          const limit = this.vm.stack[this.vm.stack.length - 2];
          this.vm.stack.splice(-2, 2);
          if (instruction.op === "?DO" && start === limit) nextIp = instruction.target;
          else {
            this.vm.loopStack.push({ loopId: this.vm.nextLoopId, iteration: 0, limit, index: start });
            this.vm.nextLoopId += 1;
          }
        } else if (instruction.op === "LOOP") {
          if (!this.vm.loopStack.length) throw new StackUnderflow("LOOP needs a loop frame");
          const loopFrame = this.vm.loopStack[this.vm.loopStack.length - 1];
          loopFrame.index = core.cell(loopFrame.index + 1);
          if (loopFrame.index === loopFrame.limit) this.vm.loopStack.pop();
          else { loopFrame.iteration += 1; nextIp = instruction.target; }
        } else if (instruction.op === "+LOOP") {
          if (!this.vm.loopStack.length) throw new StackUnderflow("+LOOP needs a loop frame");
          const increment = signed(this.vm.pop("+LOOP"));
          const loopFrame = this.vm.loopStack[this.vm.loopStack.length - 1];
          const oldDelta = signed(loopFrame.index - loopFrame.limit);
          loopFrame.index = core.cell(loopFrame.index + increment);
          const newDelta = signed(loopFrame.index - loopFrame.limit);
          const crossed = (increment > 0 && oldDelta < 0 && newDelta >= 0) || (increment < 0 && oldDelta > 0 && newDelta <= 0);
          if (crossed) this.vm.loopStack.pop();
          else { loopFrame.iteration += 1; nextIp = instruction.target; }
        } else if (instruction.op === "LEAVE") {
          if (!this.vm.loopStack.length) throw new StackUnderflow("LEAVE needs a loop frame");
          this.vm.loopStack.pop(); nextIp = instruction.target;
        } else throw new CompileError(`invalid instruction ${instruction.op}`);
        frame.ip = nextIp;
        if (!pending) this.vm.finishTrace(event);
      } catch (error) {
        this.vm.finishTrace(event, error);
        throw error;
      }
    }

    isProgramComplete() { return this.frames.length === 0 && this.mainIndex >= this.tokens.length; }

    advance() {
      if (![STATES.RUNNING, STATES.PAUSE_REQUESTED, STATES.STEPPING, STATES.STOP_REQUESTED, STATES.ABORT_REQUESTED].includes(this.state)) {
        throw new MonitorTransitionError(`advance is not allowed while ${this.state}`);
      }
      try {
        this.settleCompletedFrames();
        if (this.isProgramComplete()) {
          this.lastBoundary = this.snapshot("completed");
          if ([STATES.RUNNING, STATES.STEPPING].includes(this.state)) this.control.complete(this.lastBoundary);
          else {
            const outcome = this.control.atInstructionBoundary(this.lastBoundary);
            if (outcome === "aborted") this.rollback();
          }
          return this.control.status();
        }
        const frame = this.activeFrame();
        const outcome = frame ? this.executeColonInstruction(frame) : this.executeMainInstruction();
        if (outcome === "waiting-input") return this.control.status();
        this.settleCompletedFrames();
        this.lastBoundary = this.snapshot("instruction-boundary");
        const complete = this.isProgramComplete();
        if (complete && [STATES.RUNNING, STATES.STEPPING].includes(this.state)) this.control.complete(this.lastBoundary);
        else {
          const outcome = this.control.atInstructionBoundary(this.lastBoundary);
          if (outcome === "aborted") this.rollback();
        }
        return this.control.status();
      } catch (error) {
        const failureSnapshot = this.snapshot("error");
        this.failureSnapshot = failureSnapshot;
        this.unwindFailedFrames(error);
        this.lastBoundary = failureSnapshot;
        this.error = { name: error.constructor.name, message: error.message, location: this.lastBoundary.location };
        this.control.fail(this.lastBoundary, this.error);
        return this.control.status();
      }
    }

    runUntilBlocked(maxBoundaries = 100000) {
      let count = 0;
      while ([STATES.RUNNING, STATES.PAUSE_REQUESTED, STATES.STEPPING, STATES.STOP_REQUESTED, STATES.ABORT_REQUESTED].includes(this.state)) {
        this.advance();
        count += 1;
        if (count > maxBoundaries) throw new Error(`boundary limit ${maxBoundaries} exceeded`);
      }
      return this.control.status();
    }

    status() { return this.control.status(); }
  }

  return { MobileForthSession };
});
