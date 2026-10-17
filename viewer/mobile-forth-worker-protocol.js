(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Min0MobileWorkerProtocol = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const VERSION = "min0-mobile-monitor/0.3";
  const MAX_SOURCE_BYTES = 4096;
  const MAX_CHUNK_SIZE = 10000;
  const MAX_INPUT_BYTES = 256;
  const COMMANDS = Object.freeze(["run", "pause", "step", "continue", "stop", "abort", "inspect", "input", "write-variable"]);
  const EVENTS = Object.freeze(["ready", "accepted", "update", "rejected", "fatal"]);
  const commandNames = new Set(COMMANDS);
  const eventNames = new Set(EVENTS);
  const blockedKeys = new Set(["__proto__", "constructor", "prototype"]);

  class ProtocolError extends Error {}

  function jsonValue(value, path = "payload", ancestors = new WeakSet()) {
    if (value === null || typeof value === "string" || typeof value === "boolean") return value;
    if (typeof value === "number") {
      if (!Number.isFinite(value)) throw new ProtocolError(`${path} contains a non-finite number`);
      return value;
    }
    if (typeof value !== "object") throw new ProtocolError(`${path} is not JSON data`);
    if (ancestors.has(value)) throw new ProtocolError(`${path} contains a circular reference`);
    ancestors.add(value);
    if (Array.isArray(value)) {
      const result = value.map((item, index) => jsonValue(item, `${path}[${index}]`, ancestors));
      ancestors.delete(value);
      return result;
    }
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) throw new ProtocolError(`${path} must be a plain object`);
    const result = {};
    for (const [key, item] of Object.entries(value)) {
      if (blockedKeys.has(key)) throw new ProtocolError(`${path}.${key} is not allowed`);
      result[key] = jsonValue(item, `${path}.${key}`, ancestors);
    }
    ancestors.delete(value);
    return result;
  }

  function requireSessionId(value) {
    if (typeof value !== "string" || !/^[A-Za-z0-9._:-]{1,64}$/.test(value)) {
      throw new ProtocolError("sessionId must use 1-64 safe ASCII characters");
    }
    return value;
  }

  function requireSequence(value) {
    if (!Number.isSafeInteger(value) || value < 1) throw new ProtocolError("sequence must be a positive safe integer");
    return value;
  }

  function validateRunPayload(payload) {
    if (typeof payload.source !== "string") throw new ProtocolError("run payload.source must be a string");
    if (new TextEncoder().encode(payload.source).length > MAX_SOURCE_BYTES) {
      throw new ProtocolError(`run source exceeds ${MAX_SOURCE_BYTES} UTF-8 bytes`);
    }
    if (payload.chunkSize !== undefined && (!Number.isSafeInteger(payload.chunkSize) || payload.chunkSize < 1 || payload.chunkSize > MAX_CHUNK_SIZE)) {
      throw new ProtocolError(`run payload.chunkSize must be 1-${MAX_CHUNK_SIZE}`);
    }
    for (const key of Object.keys(payload)) {
      if (!new Set(["source", "chunkSize"]).has(key)) throw new ProtocolError(`run payload.${key} is not allowed`);
    }
  }

  function validateCommandPayload(name, payload) {
    if (name === "run") validateRunPayload(payload);
    else if (name === "input") {
      if (typeof payload.text !== "string") throw new ProtocolError("input payload.text must be a string");
      const length = new TextEncoder().encode(payload.text).length;
      if (length < 1 || length > MAX_INPUT_BYTES) throw new ProtocolError(`input payload.text must use 1-${MAX_INPUT_BYTES} UTF-8 bytes`);
      for (const key of Object.keys(payload)) {
        if (key !== "text") throw new ProtocolError(`input payload.${key} is not allowed`);
      }
    }
    else if (name === "write-variable") {
      if (typeof payload.name !== "string" || payload.name.length < 1 || payload.name.length > 64) {
        throw new ProtocolError("write-variable payload.name must use 1-64 characters");
      }
      if (!Number.isSafeInteger(payload.value) || payload.value < -2147483648 || payload.value > 0xFFFFFFFF) {
        throw new ProtocolError("write-variable payload.value must fit one 32-bit cell");
      }
      for (const key of Object.keys(payload)) {
        if (!new Set(["name", "value"]).has(key)) throw new ProtocolError(`write-variable payload.${key} is not allowed`);
      }
    }
    else if (Object.keys(payload).length) throw new ProtocolError(`${name} payload must be empty`);
  }

  function envelope(kind, names, sessionId, sequence, name, payload) {
    requireSessionId(sessionId);
    requireSequence(sequence);
    if (!names.has(name)) throw new ProtocolError(`unknown ${kind} name ${String(name)}`);
    const copiedPayload = jsonValue(payload === undefined ? {} : payload);
    if (!copiedPayload || Array.isArray(copiedPayload) || typeof copiedPayload !== "object") {
      throw new ProtocolError("payload must be an object");
    }
    return Object.freeze({ version: VERSION, kind, sessionId, sequence, name, payload: copiedPayload });
  }

  function createCommand(sessionId, sequence, name, payload = {}) {
    const message = envelope("command", commandNames, sessionId, sequence, name, payload);
    validateCommandPayload(name, message.payload);
    return message;
  }

  function readCommand(message) {
    if (!message || message.version !== VERSION || message.kind !== "command") throw new ProtocolError("invalid command envelope");
    return createCommand(message.sessionId, message.sequence, message.name, message.payload);
  }

  function createEvent(sessionId, sequence, name, payload = {}) {
    return envelope("event", eventNames, sessionId, sequence, name, payload);
  }

  function readEvent(message) {
    if (!message || message.version !== VERSION || message.kind !== "event") throw new ProtocolError("invalid event envelope");
    return createEvent(message.sessionId, message.sequence, message.name, message.payload);
  }

  return {
    VERSION, MAX_SOURCE_BYTES, MAX_CHUNK_SIZE, MAX_INPUT_BYTES, COMMANDS, EVENTS, ProtocolError,
    createCommand, readCommand, createEvent, readEvent,
  };
});
