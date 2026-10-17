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
  const DEFAULT_MAX_INPUT_BYTES = 256;
  const VARIABLE_ADDRESS_BASE = 0x10000000;
  const MAX_VARIABLE_CELLS = 256;

  const cell = value => Number(value) >>> 0;
  const signed = value => Number(value) | 0;
  const wordMeta = (name, stackEffect, category, description, availability = "実行・定義内") => Object.freeze({ name, stackEffect, category, description, availability, type: "builtin" });
  const WORD_METADATA = Object.freeze([
    wordMeta("NOP", "( -- )", "スタック", "何も変更しません。"),
    wordMeta("DROP", "( x -- )", "スタック", "最上位の値を捨てます。"),
    wordMeta("DUP", "( x -- x x )", "スタック", "最上位の値を複製します。"),
    wordMeta("SWAP", "( x1 x2 -- x2 x1 )", "スタック", "上位2値を交換します。"),
    wordMeta("OVER", "( x1 x2 -- x1 x2 x1 )", "スタック", "上から2番目の値を複製します。"),
    wordMeta("ROT", "( x1 x2 x3 -- x2 x3 x1 )", "スタック", "上位3値を回転します。"),
    wordMeta("2DUP", "( x1 x2 -- x1 x2 x1 x2 )", "スタック", "上位2値をまとめて複製します。"),
    wordMeta("2DROP", "( x1 x2 -- )", "スタック", "上位2値を捨てます。"),
    wordMeta("DEPTH", "( -- u )", "スタック", "現在のdata stack深さを積みます。"),
    wordMeta("+", "( n1 n2 -- n3 )", "算術", "2値を加算します。"),
    wordMeta("-", "( n1 n2 -- n3 )", "算術", "n1からn2を減算します。"),
    wordMeta("*", "( n1 n2 -- n3 )", "算術", "2値を32ビット乗算します。"),
    wordMeta("/", "( n1 n2 -- quot )", "算術", "符号付き除算の商を返します。"),
    wordMeta("MOD", "( n1 n2 -- rem )", "算術", "符号付き除算の余りを返します。"),
    wordMeta("/MOD", "( n1 n2 -- rem quot )", "算術", "符号付き除算の余りと商を返します。"),
    wordMeta("1+", "( n -- n+1 )", "算術", "1を加算します。"),
    wordMeta("1-", "( n -- n-1 )", "算術", "1を減算します。"),
    wordMeta("NEGATE", "( n -- -n )", "算術", "符号を反転します。"),
    wordMeta("ABS", "( n -- u )", "算術", "絶対値を返します。"),
    wordMeta("=", "( x1 x2 -- flag )", "比較", "2値が等しければtrueを返します。"),
    wordMeta("<", "( n1 n2 -- flag )", "比較", "n1がn2より小さければtrueを返します。"),
    wordMeta("0=", "( x -- flag )", "比較", "値が0ならtrueを返します。"),
    wordMeta("AND", "( x1 x2 -- x3 )", "論理", "ビット単位ANDを行います。"),
    wordMeta("OR", "( x1 x2 -- x3 )", "論理", "ビット単位ORを行います。"),
    wordMeta("XOR", "( x1 x2 -- x3 )", "論理", "ビット単位XORを行います。"),
    wordMeta(".", "( n -- )", "出力", "数値を端末出力します。"),
    wordMeta(".S", "( -- )", "出力", "data stackを変更せず表示します。"),
    wordMeta("EMIT", "( char -- )", "出力", "下位8ビットを1文字として出力します。"),
    wordMeta("CR", "( -- )", "出力", "改行を出力します。"),
    wordMeta('."', "( -- )", "出力", "終端quoteまでの文字列を出力します。", "解釈・compile"),
    wordMeta("WORDS", "( -- )", "辞書", "利用可能なword名を表示します。"),
    wordMeta("VARIABLE", "( \"name\" -- )", "安全な変数", "0で初期化した1 cell変数を登録します。名前は直後に記述します。", "解釈時"),
    wordMeta("@", "( a -- x )", "安全な変数", "VARIABLEが発行した有効なアドレスから1 cellを読みます。"),
    wordMeta("!", "( x a -- )", "安全な変数", "VARIABLEが発行した有効なアドレスへ1 cellを書きます。"),
    wordMeta("KEY?", "( -- flag )", "入力", "入力queueに1バイト以上あればtrueを返します。入力は消費しません。"),
    wordMeta("KEY", "( -- byte )", "入力", "入力queueの先頭UTF-8 byteを取り出します。空ならsession版は安全な入力待ちへ入ります。"),
    wordMeta("I", "( -- n )", "LOOP", "現在のLOOP indexを積みます。", "定義内"),
    wordMeta("J", "( -- n )", "LOOP", "1段外側のLOOP indexを積みます。", "定義内"),
    wordMeta("UNLOOP", "( -- )", "LOOP", "現在のLOOP frameを破棄します。", "定義内"),
    wordMeta(":", "( -- )", "定義", "新しいcolon wordの定義を開始します。", "解釈時"),
    wordMeta(";", "( -- )", "定義", "colon wordの定義を終了します。", "compile時"),
    wordMeta("RECURSE", "( -- )", "定義", "現在定義中のwordを再帰呼出しします。", "compile時"),
    wordMeta("IF", "( flag -- )", "分岐", "flagがtrueの場合だけ後続部分を実行します。", "compile時"),
    wordMeta("ELSE", "( -- )", "分岐", "IFのfalse側を開始します。", "compile時"),
    wordMeta("THEN", "( -- )", "分岐", "IF／ELSE構造を終了します。", "compile時"),
    wordMeta("BEGIN", "( -- )", "反復", "条件反復の開始位置を示します。", "compile時"),
    wordMeta("UNTIL", "( flag -- )", "反復", "flagがfalseの間BEGINへ戻ります。", "compile時"),
    wordMeta("AGAIN", "( -- )", "反復", "無条件にBEGINへ戻ります。", "compile時"),
    wordMeta("WHILE", "( flag -- )", "反復", "flagがfalseならBEGIN／REPEATを抜けます。", "compile時"),
    wordMeta("REPEAT", "( -- )", "反復", "BEGIN／WHILEへ戻ります。", "compile時"),
    wordMeta("DO", "( limit start -- )", "LOOP", "counted LOOPを開始します。", "compile時"),
    wordMeta("?DO", "( limit start -- )", "LOOP", "limitとstartが等しい場合はLOOPを実行しません。", "compile時"),
    wordMeta("LOOP", "( -- )", "LOOP", "indexを1増やしてDOへ戻ります。", "compile時"),
    wordMeta("+LOOP", "( n -- )", "LOOP", "指定値だけindexを進めてDOへ戻ります。", "compile時"),
    wordMeta("LEAVE", "( -- )", "LOOP", "現在のcounted LOOPを終了します。", "compile時"),
  ]);

  class ForthError extends Error {}
  class UnknownWord extends ForthError {}
  class StackUnderflow extends ForthError {}
  class DivisionByZero extends ForthError {}
  class DivisionOverflow extends ForthError {}
  class CompileError extends ForthError {}
  class StepLimitExceeded extends ForthError {}
  class CallDepthExceeded extends ForthError {}
  class InputQueueOverflow extends ForthError {}
  class InputUnavailable extends ForthError {}
  class InvalidAddress extends ForthError {}
  class VariableSpaceExhausted extends ForthError {}

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
        tokens.push({ value: { kind: "PRINT", text: source.slice(start, index), label: '."' }, start: tokenStart, end: index + 1, ...sourcePosition(source, tokenStart) });
        index += 1;
        continue;
      }
      const start = index;
      while (index < source.length && !/\s/.test(source[index]) && source[index] !== "\\") index += 1;
      tokens.push({ value: source.slice(start, index).toUpperCase(), start, end: index, ...sourcePosition(source, start) });
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
      } else if (token === "VARIABLE") {
        throw new CompileError("VARIABLE is interpretation-only");
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
      this.maxInputBytes = options.maxInputBytes || DEFAULT_MAX_INPUT_BYTES;
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
      this.variables = new Map();
      this.variableMemory = new Map();
      this.nextVariableAddress = VARIABLE_ADDRESS_BASE;
      this.wordIds = new Map();
      this.wordDefinitions = new Map();
      this.wordRuntime = new Map();
      this.nextWordId = 1;
      this.trace = [];
      this.traceTail = new Array(Math.ceil(this.maxTraceEvents / 2));
      this.traceTailCount = 0;
      this.traceTailNext = 0;
      this.traceSequence = 0;
      this.omittedTraceEvents = 0;
      this.callFrames = [];
      this.nextInvocationId = 1;
      this.inputQueue = [];
    }

    need(count, word) {
      if (this.stack.length < count) throw new StackUnderflow(`${word} needs ${count} item(s), has ${this.stack.length}`);
    }
    pop(word) { this.need(1, word); return this.stack.pop(); }
    push(value) { this.stack.push(cell(value)); }
    step() { this.steps += 1; if (this.steps > this.maxSteps) throw new StepLimitExceeded(`step limit ${this.maxSteps} exceeded`); }

    enqueueInput(text) {
      if (typeof text !== "string") throw new TypeError("input must be a string");
      const bytes = [...new TextEncoder().encode(text)];
      if (this.inputQueue.length + bytes.length > this.maxInputBytes) {
        throw new InputQueueOverflow(`input queue exceeds ${this.maxInputBytes} UTF-8 bytes`);
      }
      this.inputQueue.push(...bytes);
      return bytes.length;
    }

    stackSnapshot() { return this.stack.map(signed); }
    loopSnapshot() { return this.loopStack.map((frame, depth) => ({ loopId: frame.loopId, depth: depth + 1, iteration: frame.iteration, limit: signed(frame.limit), index: signed(frame.index) })); }

    captureTransactionalState() {
      return {
        stack: [...this.stack],
        returnStack: [...this.returnStack],
        loopStack: this.loopStack.map(frame => ({ ...frame })),
        dictionary: new Map(this.dictionary),
        variables: new Map(this.variables),
        variableMemory: new Map(this.variableMemory),
        nextVariableAddress: this.nextVariableAddress,
        wordIds: new Map(this.wordIds),
        wordDefinitions: new Map([...this.wordDefinitions].map(([id, item]) => [id, { ...item }])),
        wordRuntime: new Map([...this.wordRuntime].map(([id, item]) => [id, { ...item, lastDataBefore: [...item.lastDataBefore], lastDataAfter: [...item.lastDataAfter] }])),
        nextLoopId: this.nextLoopId,
        nextWordId: this.nextWordId,
        nextInvocationId: this.nextInvocationId,
        callFrames: this.callFrames.map(frame => ({ ...frame })),
        inputQueue: [...this.inputQueue],
      };
    }

    restoreTransactionalState(state) {
      this.stack = [...state.stack];
      this.returnStack = [...state.returnStack];
      this.loopStack = state.loopStack.map(frame => ({ ...frame }));
      this.dictionary = new Map(state.dictionary);
      this.variables = new Map(state.variables);
      this.variableMemory = new Map(state.variableMemory);
      this.nextVariableAddress = state.nextVariableAddress;
      this.wordIds = new Map(state.wordIds);
      this.wordDefinitions = new Map([...state.wordDefinitions].map(([id, item]) => [id, { ...item }]));
      this.wordRuntime = new Map([...state.wordRuntime].map(([id, item]) => [id, { ...item, lastDataBefore: [...item.lastDataBefore], lastDataAfter: [...item.lastDataAfter] }]));
      this.nextLoopId = state.nextLoopId;
      this.nextWordId = state.nextWordId;
      this.nextInvocationId = state.nextInvocationId;
      this.callFrames = state.callFrames.map(frame => ({ ...frame }));
      this.inputQueue = [...state.inputQueue];
    }

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
      if (this.variables.has(name)) { this.push(this.variables.get(name)); return; }
      const code = this.dictionary.get(name);
      if (!code) throw new UnknownWord(`unknown word ${name}`);
      this.executeDefinition(name, code);
    }

    executeDefinition(name, code) {
      if (this.returnStack.length >= MAX_CALL_DEPTH) throw new CallDepthExceeded(`call depth ${MAX_CALL_DEPTH} exceeded`);
      const frame = { word: name, wordId: this.wordIds.get(name) || null, invocationId: this.nextInvocationId, callDepth: this.callFrames.length + 1 };
      this.nextInvocationId += 1;
      const runtime = this.wordRuntime.get(frame.wordId) || { invocationCount: 0, lastDataBefore: [], lastDataAfter: [] };
      runtime.invocationCount += 1;
      runtime.lastDataBefore = this.stackSnapshot();
      this.wordRuntime.set(frame.wordId, runtime);
      this.returnStack.push(name);
      this.callFrames.push(frame);
      try { this.runCode(code, frame); } finally { runtime.lastDataAfter = this.stackSnapshot(); this.callFrames.pop(); this.returnStack.pop(); }
    }

    defineVariable(name, source = `VARIABLE ${name}`) {
      if (typeof name !== "string" || !name || [":", ";", "VARIABLE"].includes(name)) {
        throw new CompileError("VARIABLE requires a word name");
      }
      if (parseNumber(name) !== null || WORD_METADATA.some(item => item.name === name)) {
        throw new CompileError(`VARIABLE name ${name} is reserved or numeric`);
      }
      if ((this.nextVariableAddress - VARIABLE_ADDRESS_BASE) / 4 >= MAX_VARIABLE_CELLS) {
        throw new VariableSpaceExhausted(`VARIABLE space is limited to ${MAX_VARIABLE_CELLS} cells`);
      }
      const previousAddress = this.variables.get(name);
      if (previousAddress !== undefined) this.variableMemory.delete(previousAddress);
      this.dictionary.delete(name);
      const address = this.nextVariableAddress;
      this.nextVariableAddress += 4;
      this.variables.set(name, address);
      this.variableMemory.set(address, 0);
      this.wordIds.set(name, this.nextWordId);
      this.wordDefinitions.set(this.nextWordId, {
        id: this.nextWordId,
        name,
        type: "variable",
        category: "安全な変数",
        stackEffect: "( -- a )",
        description: "安全な1 cell変数のアドレスを積みます。",
        availability: "実行・定義内",
        source,
      });
      this.nextWordId += 1;
      return address;
    }

    requireVariableAddress(address, word) {
      if (!this.variableMemory.has(address)) {
        throw new InvalidAddress(`${word} rejected unregistered address 0x${cell(address).toString(16).padStart(8, "0")}`);
      }
      return address;
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
        "WORDS": () => { this.output += [...new Set([...WORD_METADATA.map(item => item.name), ...this.dictionary.keys(), ...this.variables.keys()])].sort().join(" "); },
        "@": () => {
          this.need(1, "@");
          const address = this.requireVariableAddress(this.stack[this.stack.length - 1], "@");
          this.stack[this.stack.length - 1] = this.variableMemory.get(address);
        },
        "!": () => {
          this.need(2, "!");
          const address = this.requireVariableAddress(this.stack[this.stack.length - 1], "!");
          const value = this.stack[this.stack.length - 2];
          this.variableMemory.set(address, value);
          this.stack.splice(-2, 2);
        },
        "KEY?": () => { this.push(this.inputQueue.length ? TRUE : 0); },
        "KEY": () => {
          if (!this.inputQueue.length) throw new InputUnavailable("KEY needs one queued input byte");
          this.push(this.inputQueue.shift());
        },
      };
      return this._builtins;
    }

    interpret(source) {
      this.reset();
      const initialState = this.captureTransactionalState();
      const initialDataStack = this.stackSnapshot();
      const initialReturnStack = [...this.returnStack];
      const initialLoopStack = this.loopSnapshot();
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
              const nameToken = tokens[index + 1];
              const name = nameToken && nameToken.value;
              if (typeof name !== "string" || [":", ";"].includes(name)) throw new CompileError(":" + " requires a word name");
              const body = [];
              index += 2;
              while (index < tokens.length && tokens[index].value !== ";") { body.push(tokens[index]); index += 1; }
              if (index >= tokens.length) throw new CompileError(`definition ${name} is missing ;`);
              const previousAddress = this.variables.get(name);
              if (previousAddress !== undefined) this.variableMemory.delete(previousAddress);
              this.variables.delete(name);
              this.dictionary.set(name, compileBody(body));
              this.wordIds.set(name, this.nextWordId);
              event.wordId = this.nextWordId;
              const terminator = tokens[index];
              const headerEnd = nameToken.end;
              const firstBodyStart = body.length ? body[0].start : terminator.start;
              const stackComment = source.slice(headerEnd, firstBodyStart).match(/\(\s*([^)]*--[^)]*)\)/s);
              this.wordDefinitions.set(this.nextWordId, {
                id: this.nextWordId,
                name,
                type: "colon",
                category: "利用者定義",
                stackEffect: stackComment ? `( ${stackComment[1].trim().replace(/\s+/g, " ")} )` : "未記載",
                description: "このsourceで登録したcolon wordです。",
                availability: "実行・定義内",
                source: source.slice(sourceToken.start, terminator.end),
              });
              this.nextWordId += 1;
              event.token = `: ${name} ... ;`;
              event.word = name;
              event.scope = "definition";
            } else if (token === "VARIABLE") {
              const nameToken = tokens[index + 1];
              const name = nameToken && nameToken.value;
              const address = this.defineVariable(name, nameToken ? source.slice(sourceToken.start, nameToken.end) : "VARIABLE");
              event.wordId = this.wordIds.get(name);
              event.token = `VARIABLE ${name}`;
              event.word = name;
              event.scope = "definition";
              event.op = "DEFINE_VARIABLE";
              event.address = address;
              index += 1;
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
        return this.result(null, {
          executionState: "completed",
          initialDataStack,
          initialReturnStack,
          initialLoopStack,
          stoppedDataStack: null,
          stoppedReturnStack: null,
          stoppedLoopStack: null,
          recoveredDataStack: null,
          recoveredReturnStack: null,
          recoveredLoopStack: null,
          finalDataStack: this.stackSnapshot(),
          finalReturnStack: [...this.returnStack],
          finalLoopStack: this.loopSnapshot(),
          recovery: { performed: false, outputReversible: false, note: "正常終了したためrollbackは行っていません。" },
        });
      } catch (error) {
        const stoppedAt = tokens[Math.min(index, Math.max(0, tokens.length - 1))];
        const failureEvent = [...this.traceEvents()].reverse().find(event => event.status === "error");
        const stoppedDataStack = this.stackSnapshot();
        const stoppedReturnStack = [...this.returnStack];
        const stoppedLoopStack = this.loopSnapshot();
        const diagnosticUserWords = [...this.wordDefinitions.values()].map(item => ({ id: item.id, name: item.name })).sort((left, right) => left.id - right.id);
        const diagnosticWordCatalog = this.wordCatalog();
        this.restoreTransactionalState(initialState);
        return this.result({ name: error.constructor.name, message: error.message, tokenIndex: index + 1, sourceLine: failureEvent && failureEvent.sourceLine || stoppedAt && stoppedAt.line || null, sourceColumn: failureEvent && failureEvent.sourceColumn || stoppedAt && stoppedAt.column || null, word: failureEvent && failureEvent.word || "#0 MAIN", wordId: failureEvent && failureEvent.wordId !== null ? failureEvent.wordId : 0, instructionIndex: failureEvent && failureEvent.instructionIndex || null }, {
          executionState: "error-rolled-back",
          initialDataStack,
          initialReturnStack,
          initialLoopStack,
          stoppedDataStack,
          stoppedReturnStack,
          stoppedLoopStack,
          recoveredDataStack: this.stackSnapshot(),
          recoveredReturnStack: [...this.returnStack],
          recoveredLoopStack: this.loopSnapshot(),
          finalDataStack: this.stackSnapshot(),
          finalReturnStack: [...this.returnStack],
          finalLoopStack: this.loopSnapshot(),
          recovery: { performed: true, outputReversible: false, note: "stackと辞書は実行前へ復旧しました。すでに表示した端末出力は取り消せません。" },
          legacyDataStack: stoppedDataStack,
          legacyReturnStack: stoppedReturnStack,
          legacyLoopStack: stoppedLoopStack,
          userWords: diagnosticUserWords,
          wordCatalog: diagnosticWordCatalog,
        });
      }
    }

    wordCatalog() {
      const builtins = WORD_METADATA.map(item => ({ ...item, id: null, invocationCount: null, lastDataBefore: null, lastDataAfter: null, source: null }));
      const definitions = [...this.wordDefinitions.values()].map(item => {
        const runtime = this.wordRuntime.get(item.id) || { invocationCount: 0, lastDataBefore: [], lastDataAfter: [] };
        return { ...item, invocationCount: runtime.invocationCount, lastDataBefore: [...runtime.lastDataBefore], lastDataAfter: [...runtime.lastDataAfter] };
      });
      return [...builtins, ...definitions];
    }

    result(error, lifecycle = {}) {
      const userWords = lifecycle.userWords || [...this.wordDefinitions.values()].map(item => ({ id: item.id, name: item.name })).sort((left, right) => left.id - right.id);
      const dataStack = lifecycle.legacyDataStack || this.stackSnapshot();
      const returnStack = lifecycle.legacyReturnStack || [...this.returnStack];
      const loopStack = lifecycle.legacyLoopStack || this.loopSnapshot();
      return { ok: error === null, terminal: this.output, dataStack, returnStack, loopStack, steps: this.steps, words: this.traceEvents(), traceSummary: { limit: this.maxTraceEvents, recorded: Math.min(this.traceSequence, this.maxTraceEvents), omitted: this.omittedTraceEvents, total: this.traceSequence }, userWords, wordCatalog: lifecycle.wordCatalog || this.wordCatalog(), executionState: lifecycle.executionState || (error ? "error" : "completed"), initialDataStack: lifecycle.initialDataStack || [], initialReturnStack: lifecycle.initialReturnStack || [], initialLoopStack: lifecycle.initialLoopStack || [], stoppedDataStack: lifecycle.stoppedDataStack || null, stoppedReturnStack: lifecycle.stoppedReturnStack || null, stoppedLoopStack: lifecycle.stoppedLoopStack || null, recoveredDataStack: lifecycle.recoveredDataStack || null, recoveredReturnStack: lifecycle.recoveredReturnStack || null, recoveredLoopStack: lifecycle.recoveredLoopStack || null, finalDataStack: lifecycle.finalDataStack || this.stackSnapshot(), finalReturnStack: lifecycle.finalReturnStack || [...this.returnStack], finalLoopStack: lifecycle.finalLoopStack || this.loopSnapshot(), recovery: lifecycle.recovery || { performed: false, outputReversible: false, note: "" }, error };
    }
  }

  return { MobileForth, tokenize, tokenizeDetailed, parseNumber, compileBody, signed, cell, WORD_METADATA, MAX_SOURCE_BYTES, DEFAULT_MAX_TRACE_EVENTS, MAX_CALL_DEPTH, DEFAULT_MAX_INPUT_BYTES, VARIABLE_ADDRESS_BASE, MAX_VARIABLE_CELLS, errors: { ForthError, UnknownWord, StackUnderflow, DivisionByZero, DivisionOverflow, CompileError, StepLimitExceeded, CallDepthExceeded, InputQueueOverflow, InputUnavailable, InvalidAddress, VariableSpaceExhausted } };
});
