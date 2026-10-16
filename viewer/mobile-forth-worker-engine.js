(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(
      require("./mobile-forth-worker-protocol.js"),
      require("./mobile-forth-session.js"),
      require("./mobile-forth-scheduler.js"),
    );
  } else {
    root.Min0MobileWorkerEngine = factory(
      root.Min0MobileWorkerProtocol,
      root.Min0MobileForthSession,
      root.Min0MobileForthScheduler,
    );
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (protocol, sessionModule, schedulerModule) {
  "use strict";

  if (!protocol || !sessionModule || !schedulerModule) throw new Error("Mobile Worker engine dependencies are required");

  const { MobileForthSession } = sessionModule;
  const { MobileForthScheduler } = schedulerModule;
  const TERMINAL = new Set(["stopped", "aborted", "completed", "failed"]);
  const ALLOWED_STATES = Object.freeze({
    pause: new Set(["running", "waiting-input"]),
    step: new Set(["paused"]),
    continue: new Set(["paused"]),
    stop: new Set(["running", "pause-requested", "stepping", "waiting-input", "paused"]),
    abort: new Set(["running", "pause-requested", "stepping", "waiting-input", "paused", "stopped", "failed", "completed"]),
    inspect: new Set(["running", "pause-requested", "paused", "stepping", "waiting-input", "stop-requested", "stopped", "abort-requested", "aborted", "completed", "failed"]),
    input: new Set(["running", "pause-requested", "paused", "stepping", "waiting-input"]),
  });

  class MobileForthWorkerEngine {
    constructor(send, options = {}) {
      if (typeof send !== "function") throw new TypeError("send must be a function");
      this.send = send;
      this.schedule = options.schedule;
      this.activeSessionId = null;
      this.lastCommandSequence = 0;
      this.eventSequence = 0;
      this.session = null;
      this.scheduler = null;
    }

    emit(name, payload, sessionId = this.activeSessionId || "invalid") {
      this.eventSequence += 1;
      const event = protocol.createEvent(sessionId, this.eventSequence, name, payload);
      this.send(event);
      return event;
    }

    reject(reason, raw, code = "invalid-command") {
      const receivedSessionId = raw && typeof raw.sessionId === "string" ? raw.sessionId : null;
      const requestSequence = raw && Number.isSafeInteger(raw.sequence) ? raw.sequence : null;
      return this.emit("rejected", { code, reason: String(reason), requestSequence, receivedSessionId });
    }

    isTerminal() {
      return !this.session || TERMINAL.has(this.session.state);
    }

    schedulerUpdate(requestSequence, update) {
      return this.emit("update", {
        requestSequence,
        scheduler: {
          kind: update.kind,
          chunkSequence: update.chunkSequence,
          executed: update.executed,
          totalBoundaries: update.totalBoundaries,
          scheduled: update.scheduled,
        },
        status: update.status,
        diagnostics: update.diagnostics,
      });
    }

    beginRun(command) {
      if (this.session && !this.isTerminal()) throw new Error("an execution session is already active");
      if (command.sequence !== 1) throw new Error("a new session must start at command sequence 1");
      this.activeSessionId = command.sessionId;
      this.lastCommandSequence = 1;
      this.eventSequence = 0;
      this.session = new MobileForthSession(command.payload.source);
      this.scheduler = new MobileForthScheduler(this.session, {
        chunkSize: command.payload.chunkSize === undefined ? 100 : command.payload.chunkSize,
        schedule: this.schedule,
        onUpdate: update => this.schedulerUpdate(this.lastCommandSequence, update),
      });
      this.emit("accepted", { requestSequence: command.sequence, command: command.name });
      this.scheduler.start();
    }

    dispatch(command) {
      if (command.name === "run") {
        this.beginRun(command);
        return;
      }
      if (!this.session || !this.scheduler) throw new Error("no execution session is active");
      if (command.sessionId !== this.activeSessionId) throw new Error("command belongs to a stale or unknown session");
      if (command.sequence !== this.lastCommandSequence + 1) throw new Error("command sequence is not the next expected value");
      this.lastCommandSequence = command.sequence;
      if (!ALLOWED_STATES[command.name].has(this.session.state)) {
        throw new Error(`${command.name} is not allowed while ${this.session.state}`);
      }
      this.emit("accepted", { requestSequence: command.sequence, command: command.name });
      const actions = {
        pause: () => this.scheduler.requestPause(),
        step: () => this.scheduler.step(),
        continue: () => this.scheduler.continueExecution(),
        stop: () => this.scheduler.requestStop(),
        abort: () => this.scheduler.requestAbort(),
        inspect: () => this.scheduler.update("inspect"),
        input: () => {
          return this.scheduler.enqueueInput(command.payload.text);
        },
      };
      actions[command.name]();
    }

    receive(raw) {
      let command;
      try {
        command = protocol.readCommand(raw);
      } catch (error) {
        return this.reject(error.message, raw, "invalid-envelope");
      }
      try {
        this.dispatch(command);
        return true;
      } catch (error) {
        return this.reject(error.message, command, "rejected-operation");
      }
    }
  }

  return { MobileForthWorkerEngine, TERMINAL, ALLOWED_STATES };
});
