(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.Min0MobileForth = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const TRUE = 0xFFFFFFFF;
  const MAX_SOURCE_BYTES = 4096;
  const DEFAULT_MAX_STEPS = 100000;
  const DEFAULT_MAX_TRACE_EVENTS = 2000;
  const MAX_CALL_DEPTH = 64;

  const cell = value => Number(value) >>> 0;
  const signed = value => Number(value) | 0;

  class ForthError extends Error {}
  class UnknownWord extends ForthError {}
  class StackUnderflow extends ForthError {}
  class DivisionByZero extends ForthError {}
  class DivisionOverflow extends ForthError {}
  class CompileError extends ForthError {}
  class StepLimitExceeded extends ForthError {}
  class CallDepthExceeded extends ForthError {}

  function sourcePosition(source, target) {
    let line = 1;
    let column = 1;
    for (let index = 0; index < target; index += 1) {
      if (source[index] === "\r") {
        if (source[index + 1] === "\n") index += 1;
        line += 1;
        column = 1;
      } else if (source[index] === "\n") {
        line += 1;
        column = 1;
      } else column += 1;
    }
    return { line, column };
  }

  function tokenizeDetailed(source) {
    const tokens = [];
    let index = 0;
    while (index < source.length) {
      if (/\s/.test(source[index])) { index += 1; continue; }
      if (source[index] === "\\") {
        while (index < source.length && !"\r\n".includes(source[index])) index += 1;
        continue;
      }
      if (source[index] === "(") {
        const start = index;
        index += 1;
        while (index < source.length && source[index] !== ")") index += 1;
        if (index >= source.length) {
          const before = source.slice(0, start);
          const line = before.split(/\r\n|\r|\n/).length;
          const lastBreak = Math.max(before.lastIndexOf("\n"), before.lastIndexOf("\r"));
          const column = start - lastBreak;
          throw new CompileError(`comment at line ${line}, column ${column} is missing closing )`);
        }
        index += 1;
        continue;
      }
      if (source.slice(index, index + 2) === '."') {
        const tokenStart = index;
        index += 2;
        if (source[index] === " " || source[index] === "\t") index += 1;
        const start = index;
        while (index < source.length && source[index] !== '"') {
          if ("\r\n".includes(source[index])) throw new CompileError('." string is missing closing quote');
          index += 1;
        }
        if (index >= source.length) throw new CompileError('." string is missing closing quote');
        tokens.push({ value: { kind: "PRINT", text: source.slice(start, index), label: '."' }, ...sourcePosition(source, tokenStart) });
        index += 1;
        continue;
      }
      const start = index;
      while (index < source.length && !/\s/.test(source[index]) && source[index] !== "\\") index += 1;
      tokens.push({ value: source.slice(start, index).toUpperCase(), ...sourcePosition(source, start) });
    }
    return tokens;
  }

  function tokenize(source) { return tokenizeDetailed(source).map(token => token.value); }

  function parseNumber(token) {
    if (typeof token !== "string") return null;
    if (!/^[+-]?(?:0X[0-9A-F]+|[0-9]+)$/.test(token)) return null;
    const negative = token.startsWith("-");
    const positive = token.startsWith("+");
    const unsigned = negative || positive ? token.slice(1) : token;
    const value = unsigned.startsWith("0X") ? parseInt(unsigned.slice(2), 16) : parseInt(unsigned, 10);
    return cell(negative ? -value : value);
  }

  function compileBody(tokens) {
    const code = [];
    const control = [];
    const nearest = kind => {
      for (let index = control.length - 1; index >= 0; index -= 1) {
        if (control[index].kind === kind) return control[index];
      }
      return null;
    };
    for (const entry of tokens) {
      const detailed = entry && typeof entry === "object" && Object.prototype.hasOwnProperty.call(entry, "value");
      const token = detailed ? entry.value : entry;
      const emit = instruction => code.push({ ...instruction, sourceLine: detailed ? entry.line : null, sourceColumn: detailed ? entry.column : null });
      if (typeof token === "object" && token.kind === "PRINT") {
        emit({ op: "PRINT", text: token.text });
        continue;
      }
      const number = parseNumber(token);
      if (number !== null) { emit({ op: "LIT", value: number }); continue; }
      if (token === "IF") {
        emit({ op: "JZ", target: null });
        control.push({ kind: "IF", index: code.length - 1 });
      } else if (token === "ELSE") {
        const mark = control.pop();
        if (!mark || mark.kind !== "IF") throw new CompileError("ELSE requires IF");
        emit({ op: "JUMP", target: null });
        code[mark.index].target = code.length;
        control.push({ kind: "ELSE", index: code.length - 1 });
      } else if (token === "THEN") {
        const mark = control.pop();
        if (!mark || !["IF", "ELSE"].includes(mark.kind)) throw new CompileError("THEN requires IF or ELSE");
        code[mark.index].target = code.length;
      } else if (token === "BEGIN") {
        control.push({ kind: "BEGIN", start: code.length });
      } else if (token === "UNTIL" || token === "AGAIN") {
        const mark = control.pop();
        if (!mark || mark.kind !== "BEGIN") throw new CompileError(`${token} requires BEGIN`);
        emit({ op: token === "UNTIL" ? "JZ" : "JUMP", target: mark.start });
      } else if (token === "WHILE") {
        const begin = control[control.length - 1];
        if (!begin || begin.kind !== "BEGIN") throw new CompileError("WHILE requires BEGIN");
        emit({ op: "JZ", target: null });
        control.push({ kind: "WHILE", index: code.length - 1, begin });
      } else if (token === "REPEAT") {
        const mark = control.pop();
        const begin = control.pop();
        if (!mark || mark.kind !== "WHILE" || !begin || begin !== mark.begin) throw new CompileError("REPEAT requires BEGIN WHILE");
        emit({ op: "JUMP", target: begin.start });
        code[mark.index].target = code.length;
      } else if (token === "DO" || token === "?DO") {
        emit({ op: token, target: null });
        control.push({ kind: "DO", index: code.length - 1, start: code.length, leaves: [] });
      } else if (token === "LEAVE") {
        const mark = nearest("DO");
        if (!mark) throw new CompileError("LEAVE requires DO or ?DO");
        emit({ op: "LEAVE", target: null });
        mark.leaves.push(code.length - 1);
      } else if (token === "LOOP" || token === "+LOOP") {
        const mark = control.pop();
        if (!mark || mark.kind !== "DO") throw new CompileError(`${token} requires DO or ?DO`);
        emit({ op: token, target: mark.start });
        code[mark.index].target = code.length;
        for (const leave of mark.leaves) code[leave].target = code.length;
      } else if (token === "RECURSE") {
        emit({ op: "RECURSE" });
      } else if (["IF", "ELSE", "THEN", "BEGIN", "UNTIL", "AGAIN", "WHILE", "REPEAT", "DO", "?DO", "LOOP", "+LOOP", "LEAVE"].includes(token)) {
        throw new CompileError(`unsupported structure ${token}`);
      } else {
        emit({ op: "WORD", name: token });
      }
    }
    if (control.length) throw new CompileError(`unresolved ${control[control.length - 1].kind}`);
    return code;
  }

  class MobileForth {
    constructor(options = {}) {
      this.maxSteps = options.maxSteps || DEFAULT_MAX_STEPS;
      this.maxTraceEvents = Math.max(2, options.maxTraceEvents || DEFAULT_MAX_TRACE_EVENTS);
      this.reset();
    }

    reset() {
      this.stack = [];
      this.returnStack = [];
      this.loopStack = [];
      this.nextLoopId = 1;
      this.output = "";
      this.steps = 0;
      this.dictionary = new Map();
      this.wordIds = new Map();
      this.nextWordId = 1;
      this.trace = [];
      this.traceTail = new Array(Math.ceil(this.maxTraceEvents / 2));
      this.traceTailCount = 0;
      this.traceTailNext = 0;
      this.traceSequence = 0;
      this.omittedTraceEvents = 0;
      this.callFrames = [];
      this.nextInvocationId = 1;
    }

    need(count, word) {
      if (this.stack.length < count) throw new StackUnderflow(`${word} needs ${count} item(s), has ${this.stack.length}`);
    }
    pop(word) { this.need(1, word); return this.stack.pop(); }
    push(value) { this.stack.push(cell(value)); }
    step() { this.steps += 1; if (this.steps > this.maxSteps) throw new StepLimitExceeded(`step limit ${this.maxSteps} exceeded`); }

    stackSnapshot() { return this.stack.map(signed); }
    loopSnapshot() { return this.loopStack.map((frame, depth) => ({ loopId: frame.loopId, depth: depth + 1, iteration: frame.iteration, limit: signed(frame.limit), index: signed(frame.index) })); }

    beginTrace(fields) {
      const event = {
        sequence: this.traceSequence + 1,
        scope: fields.scope,
        word: fields.word,
        wordId: fields.wordId,
        invocationId: fields.invocationId,
        callDepth: fields.callDepth,
        instructionIndex: fields.instructionIndex,
        sourceLine: fields.sourceLine || null,
        sourceColumn: fields.sourceColumn || null,
        token: fields.token,
        op: fields.op || null,
        dataBefore: this.stackSnapshot(),
        dataAfter: null,
        returnStackBefore: [...this.returnStack],
        returnStack: null,
        loopStackBefore: this.loopSnapshot(),
        loopStack: null,
        outputBefore: this.output,
        output: null,
        outputDelta: "",
        status: "running",
        error: null,
      };
      this.traceSequence += 1;
      const headLimit = Math.floor(this.maxTraceEvents / 2);
      if (this.trace.length < headLimit) this.trace.push(event);
      else if (this.traceTailCount < this.traceTail.length) {
        this.traceTail[this.traceTailCount] = event;
        this.traceTailCount += 1;
      } else {
        this.traceTail[this.traceTailNext] = event;
        this.traceTailNext = (this.traceTailNext + 1) % this.traceTail.length;
        this.omittedTraceEvents += 1;
      }
      return event;
    }

    traceEvents() {
      const tail = this.traceTailCount < this.traceTail.length
        ? this.traceTail.slice(0, this.traceTailCount)
        : [...this.traceTail.slice(this.traceTailNext), ...this.traceTail.slice(0, this.traceTailNext)];
      return [...this.trace, ...tail];
    }

    finishTrace(event, error = null) {
      event.dataAfter = this.stackSnapshot();
      event.returnStack = [...this.returnStack];
      event.loopStack = this.loopSnapshot();
      event.output = this.output;
      event.outputDelta = this.output.slice(event.outputBefore.length);
      event.status = error ? "error" : "ok";
      event.error = error ? { name: error.constructor.name, message: error.message } : null;
    }

    instructionLabel(instruction) {
      if (instruction.op === "LIT") return String(signed(instruction.value));
      if (instruction.op === "PRINT") return '."';
      if (instruction.op === "WORD") return instruction.name;
      return instruction.op;
    }

    executeWord(name) {
      this.step();
      const builtin = this.builtins()[name];
      if (builtin) { builtin(); return; }
      const code = this.dictionary.get(name);
      if (!code) throw new UnknownWord(`unknown word ${name}`);
      this.executeDefinition(name, code);
    }

    executeDefinition(name, code) {
      if (this.returnStack.length >= MAX_CALL_DEPTH) throw new CallDepthExceeded(`call depth ${MAX_CALL_DEPTH} exceeded`);
      const frame = { word: name, wordId: this.wordIds.get(name) || null, invocationId: this.nextInvocationId, callDepth: this.callFrames.length + 1 };
      this.nextInvocationId += 1;
      this.returnStack.push(name);
      this.callFrames.push(frame);
      try { this.runCode(code, frame); } finally { this.callFrames.pop(); this.returnStack.pop(); }
    }

    runCode(code, frame) {
      let ip = 0;
      while (ip < code.length) {
        const instruction = code[ip];
        const event = this.beginTrace({ scope: "colon", word: frame.word, wordId: frame.wordId, invocationId: frame.invocationId, callDepth: frame.callDepth, instructionIndex: ip + 1, sourceLine: instruction.sourceLine, sourceColumn: instruction.sourceColumn, token: this.instructionLabel(instruction), op: instruction.op });
        let nextIp = ip + 1;
        try {
          this.step();
          if (instruction.op === "LIT") this.push(instruction.value);
          else if (instruction.op === "PRINT") this.output += instruction.text;
          else if (instruction.op === "WORD") this.executeWord(instruction.name);
          else if (instruction.op === "RECURSE") {
            const name = this.returnStack[this.returnStack.length - 1];
            if (!name) throw new CompileError("RECURSE requires a colon definition");
            this.executeDefinition(name, code);
          }
          else if (instruction.op === "JUMP") nextIp = instruction.target;
          else if (instruction.op === "JZ") { if (this.pop("branch") === 0) nextIp = instruction.target; }
          else if (instruction.op === "DO" || instruction.op === "?DO") {
            this.need(2, instruction.op);
            const start = this.stack[this.stack.length - 1];
            const limit = this.stack[this.stack.length - 2];
            this.stack.splice(-2, 2);
            if (instruction.op === "?DO" && start === limit) nextIp = instruction.target;
            else {
              this.loopStack.push({ loopId: this.nextLoopId, iteration: 0, limit, index: start });
              this.nextLoopId += 1;
            }
          } else if (instruction.op === "LOOP") {
            if (!this.loopStack.length) throw new StackUnderflow("LOOP needs a loop frame");
            const loopFrame = this.loopStack[this.loopStack.length - 1];
            loopFrame.index = cell(loopFrame.index + 1);
            if (loopFrame.index === loopFrame.limit) this.loopStack.pop();
            else { loopFrame.iteration += 1; nextIp = instruction.target; }
          } else if (instruction.op === "+LOOP") {
            if (!this.loopStack.length) throw new StackUnderflow("+LOOP needs a loop frame");
            const increment = signed(this.pop("+LOOP"));
            const loopFrame = this.loopStack[this.loopStack.length - 1];
            const oldDelta = signed(loopFrame.index - loopFrame.limit);
            loopFrame.index = cell(loopFrame.index + increment);
            const newDelta = signed(loopFrame.index - loopFrame.limit);
            const crossed = (increment > 0 && oldDelta < 0 && newDelta >= 0) || (increment < 0 && oldDelta > 0 && newDelta <= 0);
            if (crossed) this.loopStack.pop();
            else { loopFrame.iteration += 1; nextIp = instruction.target; }
          } else if (instruction.op === "LEAVE") {
            if (!this.loopStack.length) throw new StackUnderflow("LEAVE needs a loop frame");
            this.loopStack.pop(); nextIp = instruction.target;
          } else throw new CompileError(`invalid instruction ${instruction.op}`);
          this.finishTrace(event);
        } catch (error) {
          this.finishTrace(event, error);
          throw error;
        }
        ip = nextIp;
      }
    }

    builtins() {
      if (this._builtins) return this._builtins;
      const binary = (name, operation) => () => { this.need(2, name); const right = this.stack.pop(); const left = this.stack.pop(); this.push(operation(left, right)); };
      const unary = (name, operation) => () => { this.need(1, name); this.stack[this.stack.length - 1] = cell(operation(this.stack[this.stack.length - 1])); };
      this._builtins = {
        "NOP": () => {}, "DROP": () => { this.pop("DROP"); },
        "DUP": () => { this.need(1, "DUP"); this.push(this.stack[this.stack.length - 1]); },
        "SWAP": () => { this.need(2, "SWAP"); const n = this.stack.length; [this.stack[n - 2], this.stack[n - 1]] = [this.stack[n - 1], this.stack[n - 2]]; },
        "OVER": () => { this.need(2, "OVER"); this.push(this.stack[this.stack.length - 2]); },
        "ROT": () => { this.need(3, "ROT"); const n = this.stack.length; const value = this.stack[n - 3]; this.stack[n - 3] = this.stack[n - 2]; this.stack[n - 2] = this.stack[n - 1]; this.stack[n - 1] = value; },
        "2DUP": () => { this.need(2, "2DUP"); const n = this.stack.length; this.push(this.stack[n - 2]); this.push(this.stack[n - 1]); },
        "2DROP": () => { this.need(2, "2DROP"); this.stack.splice(-2, 2); },
        "DEPTH": () => { this.push(this.stack.length); },
        "+": binary("+", (a, b) => a + b), "-": binary("-", (a, b) => a - b),
        "*": binary("*", (a, b) => Math.imul(a, b)),
        "AND": binary("AND", (a, b) => a & b), "OR": binary("OR", (a, b) => a | b), "XOR": binary("XOR", (a, b) => a ^ b),
        "<": binary("<", (a, b) => signed(a) < signed(b) ? TRUE : 0), "=": binary("=", (a, b) => a === b ? TRUE : 0),
        "0=": unary("0=", a => a === 0 ? TRUE : 0), "NEGATE": unary("NEGATE", a => -signed(a)),
        "ABS": unary("ABS", a => Math.abs(signed(a))), "1+": unary("1+", a => a + 1), "1-": unary("1-", a => a - 1),
        "/MOD": () => { this.need(2, "/MOD"); const dividend = signed(this.stack[this.stack.length - 2]); const divisor = signed(this.stack[this.stack.length - 1]); if (divisor === 0) throw new DivisionByZero("division by zero in /MOD"); if (dividend === -2147483648 && divisor === -1) throw new DivisionOverflow("signed division overflow in /MOD"); const quotient = Math.trunc(dividend / divisor); const remainder = dividend - quotient * divisor; this.stack.splice(-2, 2); this.push(remainder); this.push(quotient); },
        "/": () => { this._builtins["/MOD"](); const quotient = this.stack.pop(); this.stack.pop(); this.push(quotient); },
        "MOD": () => { this._builtins["/MOD"](); this.stack.pop(); },
        ".": () => { this.output += String(signed(this.pop("."))); },
        ".S": () => { this.output += `<${this.stack.length}>${this.stack.length ? " " + this.stack.map(signed).join(" ") : ""}`; },
        "EMIT": () => { this.output += String.fromCharCode(this.pop("EMIT") & 0xFF); }, "CR": () => { this.output += "\n"; },
        "I": () => { if (!this.loopStack.length) throw new StackUnderflow("I needs a loop frame"); this.push(this.loopStack[this.loopStack.length - 1].index); },
        "J": () => { if (this.loopStack.length < 2) throw new StackUnderflow("J needs two loop frames"); this.push(this.loopStack[this.loopStack.length - 2].index); },
        "UNLOOP": () => { if (!this.loopStack.length) throw new StackUnderflow("UNLOOP needs a loop frame"); this.loopStack.pop(); },
        "WORDS": () => { this.output += [...Object.keys(this._builtins), ...this.dictionary.keys()].sort().join(" "); },
      };
      return this._builtins;
    }

    interpret(source) {
      this.reset();
      let tokens = [];
      let index = 0;
      try {
        if (new TextEncoder().encode(source).length > MAX_SOURCE_BYTES) throw new CompileError(`source exceeds ${MAX_SOURCE_BYTES} UTF-8 bytes`);
        tokens = tokenizeDetailed(source);
        while (index < tokens.length) {
          const sourceToken = tokens[index];
          const token = sourceToken.value;
          const event = this.beginTrace({ scope: "main", word: "#0 MAIN", wordId: 0, invocationId: 0, callDepth: 0, instructionIndex: index + 1, sourceLine: sourceToken.line, sourceColumn: sourceToken.column, token: typeof token === "object" ? '."' : token, op: token === ":" ? "DEFINE" : "TOKEN" });
          try {
            if (token === ":") {
              const name = tokens[index + 1] && tokens[index + 1].value;
              if (typeof name !== "string" || [":", ";"].includes(name)) throw new CompileError(":" + " requires a word name");
              const body = [];
              index += 2;
              while (index < tokens.length && tokens[index].value !== ";") { body.push(tokens[index]); index += 1; }
              if (index >= tokens.length) throw new CompileError(`definition ${name} is missing ;`);
              this.dictionary.set(name, compileBody(body));
              this.wordIds.set(name, this.nextWordId);
              event.wordId = this.nextWordId;
              this.nextWordId += 1;
              event.token = `: ${name} ... ;`;
              event.word = name;
              event.scope = "definition";
            } else if (typeof token === "object" && token.kind === "PRINT") {
              this.step(); this.output += token.text;
            } else {
              const number = parseNumber(token);
              if (number !== null) { this.step(); this.push(number); }
              else {
                if ([";", "IF", "ELSE", "THEN", "BEGIN", "UNTIL", "AGAIN", "WHILE", "REPEAT", "DO", "?DO", "LOOP", "+LOOP", "LEAVE", "RECURSE"].includes(token)) throw new CompileError(`${token} is compile-only`);
                this.executeWord(token);
              }
            }
            this.finishTrace(event);
          } catch (error) {
            this.finishTrace(event, error);
            throw error;
          }
          index += 1;
        }
        return this.result(null);
      } catch (error) {
        const stoppedAt = tokens[Math.min(index, Math.max(0, tokens.length - 1))];
        const failureEvent = [...this.traceEvents()].reverse().find(event => event.status === "error");
        return this.result({ name: error.constructor.name, message: error.message, tokenIndex: index + 1, sourceLine: failureEvent && failureEvent.sourceLine || stoppedAt && stoppedAt.line || null, sourceColumn: failureEvent && failureEvent.sourceColumn || stoppedAt && stoppedAt.column || null, word: failureEvent && failureEvent.word || "#0 MAIN", wordId: failureEvent && failureEvent.wordId !== null ? failureEvent.wordId : 0, instructionIndex: failureEvent && failureEvent.instructionIndex || null });
      }
    }

    result(error) {
      return { ok: error === null, terminal: this.output, dataStack: this.stack.map(signed), returnStack: [...this.returnStack], loopStack: this.loopSnapshot(), steps: this.steps, words: this.traceEvents(), traceSummary: { limit: this.maxTraceEvents, recorded: Math.min(this.traceSequence, this.maxTraceEvents), omitted: this.omittedTraceEvents, total: this.traceSequence }, userWords: [...this.wordIds.entries()].map(([name, id]) => ({ id, name })).sort((left, right) => left.id - right.id), error };
    }
  }

  return { MobileForth, tokenize, tokenizeDetailed, parseNumber, compileBody, signed, cell, MAX_SOURCE_BYTES, DEFAULT_MAX_TRACE_EVENTS };
});
