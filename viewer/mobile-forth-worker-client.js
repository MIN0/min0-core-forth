(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(
      require("./mobile-forth-worker-protocol.js"),
      require("./mobile-forth-worker-engine.js"),
    );
  } else {
    root.Min0MobileWorkerClient = factory(root.Min0MobileWorkerProtocol, root.Min0MobileWorkerEngine);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (protocol, engineModule) {
  "use strict";

  if (!protocol || !engineModule) throw new Error("Mobile Worker client dependencies are required");

  const { MobileForthWorkerEngine } = engineModule;

  class MobileForthWorkerClient {
    constructor(options = {}) {
      this.workerSource = options.workerSource || "";
      this.WorkerClass = options.WorkerClass === undefined ? (typeof Worker === "function" ? Worker : null) : options.WorkerClass;
      this.BlobClass = options.BlobClass === undefined ? (typeof Blob === "function" ? Blob : null) : options.BlobClass;
      this.URLApi = options.URLApi === undefined ? (typeof URL === "function" ? URL : null) : options.URLApi;
      this.schedule = options.schedule;
      this.onEvent = options.onEvent || (() => {});
      this.onMode = options.onMode || (() => {});
      this.sessionIdFactory = options.sessionIdFactory || (() => `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`);
      this.mode = "disconnected";
      this.worker = null;
      this.workerUrl = null;
      this.localEngine = null;
      this.activeSessionId = null;
      this.commandSequence = 0;
      this.lastEventSequence = 0;
    }

    setMode(mode, reason = null) {
      this.mode = mode;
      this.onMode({ mode, reason });
    }

    connect() {
      if (this.mode !== "disconnected") return this.mode;
      if (this.workerSource && this.WorkerClass && this.BlobClass && this.URLApi && typeof this.URLApi.createObjectURL === "function") {
        try {
          const blob = new this.BlobClass([this.workerSource], { type: "text/javascript" });
          this.workerUrl = this.URLApi.createObjectURL(blob);
          this.worker = new this.WorkerClass(this.workerUrl);
          this.worker.onmessage = message => this.receiveEvent(message.data);
          this.worker.onerror = error => this.workerFailure(error);
          this.setMode("worker");
          return this.mode;
        } catch (error) {
          this.releaseWorker();
          this.startFallback(error.message);
          return this.mode;
        }
      }
      this.startFallback("Blob Worker is unavailable");
      return this.mode;
    }

    startFallback(reason) {
      this.localEngine = new MobileForthWorkerEngine(event => this.receiveEvent(event), { schedule: this.schedule });
      this.setMode("main-thread-fallback", reason);
    }

    workerFailure(error) {
      const reason = error && error.message ? error.message : "Worker execution failed";
      if (!this.activeSessionId) {
        this.releaseWorker();
        this.startFallback(reason);
        return;
      }
      this.setMode("worker-failed", reason);
      this.onEvent({
        version: protocol.VERSION,
        kind: "event",
        sessionId: this.activeSessionId,
        sequence: this.lastEventSequence + 1,
        name: "fatal",
        payload: { reason, recoverable: false },
      });
    }

    receiveEvent(raw) {
      let event;
      try { event = protocol.readEvent(raw); }
      catch (_) { return false; }
      if (event.sessionId !== this.activeSessionId) return false;
      if (event.sequence <= this.lastEventSequence) return false;
      this.lastEventSequence = event.sequence;
      this.onEvent(event);
      return true;
    }

    send(name, payload = {}) {
      if (!this.activeSessionId) throw new Error("no Mobile Worker session is active");
      this.commandSequence += 1;
      const command = protocol.createCommand(this.activeSessionId, this.commandSequence, name, payload);
      if (this.mode === "worker") this.worker.postMessage(command);
      else if (this.mode === "main-thread-fallback") this.localEngine.receive(command);
      else throw new Error(`cannot send while client mode is ${this.mode}`);
      return command;
    }

    run(source, chunkSize = 100) {
      this.connect();
      if (!["worker", "main-thread-fallback"].includes(this.mode)) throw new Error(`cannot run while client mode is ${this.mode}`);
      const sessionId = this.sessionIdFactory();
      protocol.createCommand(sessionId, 1, "run", { source, chunkSize });
      this.activeSessionId = sessionId;
      this.commandSequence = 0;
      this.lastEventSequence = 0;
      return this.send("run", { source, chunkSize });
    }

    pause() { return this.send("pause"); }
    step() { return this.send("step"); }
    continueExecution() { return this.send("continue"); }
    stop() { return this.send("stop"); }
    abort() { return this.send("abort"); }
    inspect() { return this.send("inspect"); }
    input(text) { return this.send("input", { text }); }

    releaseWorker() {
      if (this.worker && typeof this.worker.terminate === "function") this.worker.terminate();
      this.worker = null;
      if (this.workerUrl && this.URLApi && typeof this.URLApi.revokeObjectURL === "function") this.URLApi.revokeObjectURL(this.workerUrl);
      this.workerUrl = null;
    }

    close() {
      this.releaseWorker();
      this.localEngine = null;
      this.activeSessionId = null;
      this.setMode("disconnected");
    }
  }

  return { MobileForthWorkerClient };
});
