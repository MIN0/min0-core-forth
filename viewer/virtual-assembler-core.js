(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.Min0VirtualAssembler = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
"use strict";

const MASK = 0xffffffff;
const REGS = new Set(["V0", "V1", "V2", "V3"]);
const BRANCHES = new Set(["BEQ", "BNE", "BLT", "BGE", "BLTU", "BGEU"]);
const OPS2 = new Set(["MOV", "LIT", "ADD", "SUB", "MUL", "AND", "OR", "XOR", "LSL", "LSR", "ASR", "ROL", "ROR", "CMP", "IN", "OUT", "LD32", "ST32"]);

class AssemblerError extends Error {
  constructor(code, message, line = 0) { super(message); this.name = "AssemblerError"; this.code = code; this.line = line; }
}

function u32(value) { return Number(BigInt.asUintN(32, BigInt(value))); }
function s32(value) { return value >= 0x80000000 ? value - 0x100000000 : value; }
function number(text, line) {
  if (!/^-?(?:0x[0-9a-f]+|\d+)$/i.test(text)) throw new AssemblerError("E-PARSE-NUMBER", `数値 ${text} を解釈できません`, line);
  return u32(BigInt(text));
}
function names(text, line) {
  const result = text.trim() ? text.trim().split(/\s+/) : [];
  for (const value of result) if (!/^[A-Za-z][A-Za-z0-9_-]*$/.test(value)) throw new AssemblerError("E-PARSE-NAME", `名前 ${value} は使用できません`, line);
  if (new Set(result).size !== result.length) throw new AssemblerError("E-VERIFY-NAME", "入出力名が重複しています", line);
  return result;
}
function parse(source) {
  const raw = source.split(/\r?\n/).map((text, index) => ({ text: text.split("\\", 1)[0].trim(), line: index + 1 })).filter(x => x.text);
  if (!raw.length) throw new AssemblerError("E-PARSE-EMPTY", "sourceが空です");
  const header = raw[0].text.match(/^CODE:\s+([A-Za-z][A-Za-z0-9_-]*)\s*\(\s*(.*?)\s*--\s*(.*?)\s*\)$/i);
  if (!header) throw new AssemblerError("E-PARSE-HEADER", "CODE headerを確認してください", raw[0].line);
  const result = { name: header[1].toUpperCase(), inputs: names(header[2], raw[0].line), outputs: names(header[3], raw[0].line), instructions: [], labels: {} };
  let ended = false;
  for (const row of raw.slice(1)) {
    if (/^;CODE$/i.test(row.text)) { ended = true; break; }
    const label = row.text.match(/^@([A-Za-z][A-Za-z0-9_-]*):$/);
    if (label) {
      if (result.labels[label[1]] !== undefined) throw new AssemblerError("E-VERIFY-LABEL", `label @${label[1]} が重複しています`, row.line);
      result.labels[label[1]] = result.instructions.length;
      result.instructions.push({ op: "LABEL", args: [label[1]], line: row.line, source: row.text });
      continue;
    }
    const split = row.text.match(/^(\S+)(?:\s+(.*))?$/);
    const op = split[1].toUpperCase();
    let args = split[2] ? split[2].split(",").map(x => x.trim()) : [];
    const arity = BRANCHES.has(op) || op === "BRA" || op === "NOT" ? 1 : OPS2.has(op) ? 2 : -1;
    if (arity < 0) throw new AssemblerError("E-PARSE-OPCODE", `未知の命令 ${op} です`, row.line);
    if (args.length !== arity || args.some(x => !x)) throw new AssemblerError("E-PARSE-OPERAND", `${op}には${arity}個のoperandが必要です`, row.line);
    if (BRANCHES.has(op) || op === "BRA") args = [args[0].replace(/^@/, "")];
    result.instructions.push({ op, args, line: row.line, source: row.text });
  }
  if (!ended) throw new AssemblerError("E-PARSE-END", ";CODEがありません");
  verify(result);
  return result;
}

function reg(value, line) { const name = value.toUpperCase(); if (!REGS.has(name)) throw new AssemblerError("E-VERIFY-REGISTER", `register ${value} は使用できません`, line); return name; }
function addressRegister(text, line) {
  const match = text.replace(/\s+/g, "").match(/^\[(?:\w+:)?(V[0-3])(?:[+-]\d+)?\]$/i);
  if (!match) throw new AssemblerError("E-VERIFY-ADDRESS", `address ${text} を解釈できません`, line);
  return match[1].toUpperCase();
}
function address(text, registers, line) {
  const match = text.replace(/\s+/g, "").match(/^\[(?:(\w+):)?(V[0-3])(?:([+-])(\d+))?\]$/i);
  if (!match) throw new AssemblerError("E-VERIFY-ADDRESS", `address ${text} を解釈できません`, line);
  const base = registers[match[2].toUpperCase()];
  if (base === undefined) throw new AssemblerError("E-VERIFY-UNINITIALIZED", `${match[2]}は未初期化です`, line);
  const delta = match[4] ? Number(match[4]) * (match[3] === "-" ? -1 : 1) : 0;
  return { capability: (match[1] || "DATA").toUpperCase(), value: u32(BigInt(base) + BigInt(delta)) };
}
function verify(def) {
  const initialized = new Set();
  const assigned = new Set();
  let compared = false;
  for (const ins of def.instructions) {
    const [a, b] = ins.args;
    if (ins.op === "IN") { reg(a, ins.line); if (!def.inputs.includes(b)) throw new AssemblerError("E-VERIFY-INPUT", `input ${b} は宣言されていません`, ins.line); initialized.add(a.toUpperCase()); }
    else if (ins.op === "LIT") { initialized.add(reg(a, ins.line)); number(b, ins.line); }
    else if (ins.op === "OUT") { if (!def.outputs.includes(a)) throw new AssemblerError("E-VERIFY-OUTPUT", `output ${a} は宣言されていません`, ins.line); const r = reg(b, ins.line); if (!initialized.has(r)) throw new AssemblerError("E-VERIFY-UNINITIALIZED", `${r}は未初期化です`, ins.line); assigned.add(a); }
    else if (["MOV","ADD","SUB","MUL","AND","OR","XOR","CMP"].includes(ins.op)) { const ra=reg(a,ins.line), rb=reg(b,ins.line); if (!initialized.has(rb) || (ins.op !== "MOV" && !initialized.has(ra))) throw new AssemblerError("E-VERIFY-UNINITIALIZED", "未初期化registerを読みました", ins.line); if (ins.op !== "CMP") initialized.add(ra); else compared=true; }
    else if (["NOT","LSL","LSR","ASR","ROL","ROR"].includes(ins.op)) { const ra=reg(a,ins.line); if (!initialized.has(ra)) throw new AssemblerError("E-VERIFY-UNINITIALIZED", `${ra}は未初期化です`, ins.line); if (ins.op !== "NOT") { const count=Number(b); if (!Number.isInteger(count)||count<0||count>31) throw new AssemblerError("E-VERIFY-SHIFT", "shift量は0..31です", ins.line); } }
    else if (ins.op === "LD32") { const target=addressRegister(b,ins.line); if(!initialized.has(target))throw new AssemblerError("E-VERIFY-UNINITIALIZED",`${target}は未初期化です`,ins.line); initialized.add(reg(a,ins.line)); }
    else if (ins.op === "ST32") { const target=addressRegister(a,ins.line), value=reg(b,ins.line); if(!initialized.has(target)||!initialized.has(value))throw new AssemblerError("E-VERIFY-UNINITIALIZED","未初期化registerを読みました",ins.line); }
    else if (BRANCHES.has(ins.op)) { if (!compared) throw new AssemblerError("E-VERIFY-CMP", `${ins.op}の前にCMPが必要です`, ins.line); }
    if (BRANCHES.has(ins.op) || ins.op === "BRA") if (def.labels[a] === undefined) throw new AssemblerError("E-VERIFY-LABEL", `label @${a} がありません`, ins.line);
  }
  for (const output of def.outputs) if (!assigned.has(output)) throw new AssemblerError("E-VERIFY-OUTPUT", `output ${output} が設定されていません`);
}

function execute(source, inputValues, options = {}) {
  const def = parse(source);
  if (inputValues.length !== def.inputs.length) throw new AssemblerError("E-STACK-INPUT", `${def.name}には${def.inputs.length}個の入力が必要です`);
  const beforeStack = inputValues.map(u32), entry = Object.fromEntries(def.inputs.map((name,i)=>[name,beforeStack[i]]));
  const registers = {}, staged = {}, memory = new Map(), pending = new Map(), trace = [];
  const base = options.memoryBase ?? 0x1000, size = options.memorySize ?? 16, maxSteps = options.maxSteps ?? 1000;
  for (let p=0;p<size;p+=4) memory.set(base+p, 0);
  let comparison = null, pc=0, steps=0;
  try {
    while (pc < def.instructions.length) {
      if (++steps > maxSteps) throw new AssemblerError("E-EXEC-STEPS", `実行step上限${maxSteps}を超えました`);
      const ins=def.instructions[pc], before={...registers}; const [a,b]=ins.args; let note="";
      if (ins.op==="IN") registers[reg(a,ins.line)]=entry[b];
      else if (ins.op==="OUT") staged[a]=registers[reg(b,ins.line)];
      else if (ins.op==="MOV") registers[reg(a,ins.line)]=registers[reg(b,ins.line)];
      else if (ins.op==="LIT") registers[reg(a,ins.line)]=number(b,ins.line);
      else if (["ADD","SUB","MUL","AND","OR","XOR"].includes(ins.op)) { const x=registers[reg(a,ins.line)], y=registers[reg(b,ins.line)]; registers[a.toUpperCase()]=u32({ADD:BigInt(x)+BigInt(y),SUB:BigInt(x)-BigInt(y),MUL:BigInt(x)*BigInt(y),AND:BigInt(x&y),OR:BigInt(x|y),XOR:BigInt(x^y)}[ins.op]); }
      else if (ins.op==="NOT") registers[reg(a,ins.line)]=u32(~registers[reg(a,ins.line)]);
      else if (["LSL","LSR","ASR","ROL","ROR"].includes(ins.op)) { const r=reg(a,ins.line), x=registers[r], n=Number(b); let y; if(ins.op==="LSL")y=x<<n;else if(ins.op==="LSR")y=x>>>n;else if(ins.op==="ASR")y=s32(x)>>n;else if(ins.op==="ROL")y=n?((x<<n)|(x>>>(32-n))):x;else y=n?((x>>>n)|(x<<(32-n))):x; registers[r]=u32(y); }
      else if (ins.op==="CMP") comparison=[registers[reg(a,ins.line)],registers[reg(b,ins.line)]];
      else if (BRANCHES.has(ins.op)) { const [x,y]=comparison; const take={BEQ:x===y,BNE:x!==y,BLT:s32(x)<s32(y),BGE:s32(x)>=s32(y),BLTU:x<y,BGEU:x>=y}[ins.op]; note=take?"branch taken":"branch not taken"; if(take){trace.push({step:steps,line:ins.line,source:ins.source,before,after:{...registers},note});pc=def.labels[a];continue;} }
      else if (ins.op==="BRA") { note="branch taken"; trace.push({step:steps,line:ins.line,source:ins.source,before,after:{...registers},note});pc=def.labels[a];continue; }
      else if (ins.op==="LD32" || ins.op==="ST32") { const target=address(ins.op==="LD32"?b:a,registers,ins.line); if(target.capability!=="DATA")throw new AssemblerError("E-MEM-CAP", `capability ${target.capability} は登録されていません`,ins.line); if(target.value%4)throw new AssemblerError("E-MEM-ALIGN", `address 0x${target.value.toString(16)} は4-byte境界ではありません`,ins.line); if(target.value<base||target.value+4>base+size)throw new AssemblerError("E-MEM-RANGE", `address 0x${target.value.toString(16)} はDATA範囲外です`,ins.line); if(ins.op==="LD32")registers[reg(a,ins.line)]=pending.has(target.value)?pending.get(target.value):memory.get(target.value);else pending.set(target.value,registers[reg(b,ins.line)]); note=`DATA 0x${target.value.toString(16).padStart(8,"0")}`; }
      trace.push({step:steps,line:ins.line,source:ins.source,before,after:{...registers},note}); pc++;
    }
    const missing=def.outputs.filter(name=>staged[name]===undefined); if(missing.length)throw new AssemblerError("E-EXEC-OUTPUT", `output ${missing.join(", ")} が設定されませんでした`);
    for (const [key,value] of pending) memory.set(key,value);
    return {ok:true,name:def.name,inputs:def.inputs,outputs:def.outputs,beforeStack,afterStack:def.outputs.map(x=>staged[x]),registers,trace,memoryCommitted:pending.size,audit:["SOURCE CHECK PASS","STACK CONTRACT PASS","TRANSACTION COMMIT PASS","REFERENCE EXECUTION PASS","RP2350 MACHINE EXECUTION DISABLED"]};
  } catch (error) {
    if (!(error instanceof AssemblerError)) throw error;
    return {ok:false,name:def.name,beforeStack,afterStack:[...beforeStack],trace,error:{code:error.code,message:error.message,line:error.line},memoryCommitted:0,audit:["REFERENCE EXECUTION ABORTED","STACK RESTORED","MEMORY WRITE DISCARDED","RP2350 MACHINE EXECUTION DISABLED"]};
  }
}

return { AssemblerError, parse, execute };
});
