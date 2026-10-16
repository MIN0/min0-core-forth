(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Min0MobileMonitor = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const STATES = Object.freeze({
    IDLE: "idle",
    RUNNING: "running",
    PAUSE_REQUESTED: "pause-requested",
    PAUSED: "paused",
    STEPPING: "stepping",
    WAITING_INPUT: "waiting-input",
    STOP_REQUESTED: "stop-requested",
    STOPPED: "stopped",
    ABORT_REQUESTED: "abort-requested",
    ABORTED: "aborted",
    COMPLETED: "completed",
    FAILED: "failed",
  });

  class MonitorTransitionError extends Error {}

  function clone(value) {
    return value === null || value === undefined ? value : JSON.parse(JSON.stringify(value));
  }

  class MonitorExecutionControl {
    constructor() {
      this.state = STATES.IDLE;
      this.initialSnapshot = null;
      this.currentSnapshot = null;
      this.stopReason = null;
      this.sequence = 0;
      this.transitions = [];
      this.inputResumeState = null;
    }

    record(action, from, to, details = {}) {
      this.sequence += 1;
      this.transitions.push({ sequence: this.sequence, action, from, to, ...clone(details) });
    }

    require(allowed, action) {
      if (!allowed.includes(this.state)) {
        throw new MonitorTransitionError(`${action} is not allowed while ${this.state}`);
      }
    }

    move(action, nextState, details = {}) {
      const previous = this.state;
      this.state = nextState;
      this.record(action, previous, nextState, details);
    }

    start(initialSnapshot) {
      this.require([STATES.IDLE], "start");
      this.initialSnapshot = clone(initialSnapshot);
      this.currentSnapshot = clone(initialSnapshot);
      this.stopReason = null;
      this.move("start", STATES.RUNNING);
      return this.status();
    }

    requestPause() {
      this.require([STATES.RUNNING, STATES.WAITING_INPUT], "requestPause");
      if (this.state === STATES.WAITING_INPUT) {
        this.inputResumeState = null;
        this.stopReason = "pause";
        this.move("pause-at-input-boundary", STATES.PAUSED, { boundary: true });
        return this.status();
      }
      this.move("request-pause", STATES.PAUSE_REQUESTED);
      return this.status();
    }

    continueExecution() {
      this.require([STATES.PAUSED], "continueExecution");
      this.stopReason = null;
      this.move("continue", STATES.RUNNING);
      return this.status();
    }

    step() {
      this.require([STATES.PAUSED], "step");
      this.stopReason = null;
      this.move("step", STATES.STEPPING);
      return this.status();
    }

    requestStop() {
      this.require([STATES.RUNNING, STATES.PAUSE_REQUESTED, STATES.STEPPING, STATES.WAITING_INPUT, STATES.PAUSED], "requestStop");
      if ([STATES.PAUSED, STATES.WAITING_INPUT].includes(this.state)) {
        this.inputResumeState = null;
        this.stopReason = "stop";
        this.move("stop-at-paused-boundary", STATES.STOPPED);
      } else {
        this.move("request-stop", STATES.STOP_REQUESTED);
      }
      return this.status();
    }

    requestAbort() {
      this.require([STATES.RUNNING, STATES.PAUSE_REQUESTED, STATES.STEPPING, STATES.WAITING_INPUT, STATES.PAUSED, STATES.STOPPED, STATES.FAILED, STATES.COMPLETED], "requestAbort");
      if ([STATES.WAITING_INPUT, STATES.PAUSED, STATES.STOPPED, STATES.FAILED, STATES.COMPLETED].includes(this.state)) {
        this.inputResumeState = null;
        this.currentSnapshot = clone(this.initialSnapshot);
        this.stopReason = "abort-rollback";
        this.move("abort-at-safe-boundary", STATES.ABORTED, { rollback: true });
      } else {
        this.move("request-abort", STATES.ABORT_REQUESTED);
      }
      return this.status();
    }

    confirmRollback(snapshot) {
      this.require([STATES.ABORTED], "confirmRollback");
      this.currentSnapshot = clone(snapshot);
      this.record("confirm-rollback", this.state, this.state, { boundary: true });
      return this.status();
    }

    waitForInput(snapshot) {
      this.require([STATES.RUNNING, STATES.STEPPING], "waitForInput");
      this.currentSnapshot = clone(snapshot);
      this.inputResumeState = this.state;
      this.stopReason = "input-empty";
      this.move("wait-for-input", STATES.WAITING_INPUT, { boundary: true, resumeState: this.inputResumeState });
      return this.status();
    }

    inputAvailable(snapshot) {
      this.require([STATES.WAITING_INPUT], "inputAvailable");
      this.currentSnapshot = clone(snapshot);
      const next = this.inputResumeState || STATES.RUNNING;
      this.inputResumeState = null;
      this.stopReason = null;
      this.move("input-available", next, { boundary: true });
      return this.status();
    }

    observe(snapshot, action = "observe") {
      this.currentSnapshot = clone(snapshot);
      this.record(action, this.state, this.state, { boundary: true });
      return this.status();
    }

    atInstructionBoundary(snapshot) {
      this.require([STATES.RUNNING, STATES.PAUSE_REQUESTED, STATES.STEPPING, STATES.STOP_REQUESTED, STATES.ABORT_REQUESTED], "atInstructionBoundary");
      this.currentSnapshot = clone(snapshot);
      if (this.state === STATES.PAUSE_REQUESTED) {
        this.stopReason = "pause";
        this.move("accept-pause", STATES.PAUSED, { boundary: true });
        return "paused";
      }
      if (this.state === STATES.STEPPING) {
        this.stopReason = "step-complete";
        this.move("complete-step", STATES.PAUSED, { boundary: true });
        return "paused";
      }
      if (this.state === STATES.STOP_REQUESTED) {
        this.stopReason = "stop";
        this.move("accept-stop", STATES.STOPPED, { boundary: true });
        return "stopped";
      }
      if (this.state === STATES.ABORT_REQUESTED) {
        this.currentSnapshot = clone(this.initialSnapshot);
        this.stopReason = "abort-rollback";
        this.move("accept-abort", STATES.ABORTED, { boundary: true, rollback: true });
        return "aborted";
      }
      this.record("instruction-boundary", this.state, this.state, { boundary: true });
      return "continue";
    }

    complete(snapshot) {
      this.require([STATES.RUNNING, STATES.STEPPING], "complete");
      this.currentSnapshot = clone(snapshot);
      this.stopReason = "completed";
      this.move("complete", STATES.COMPLETED, { boundary: true });
      return this.status();
    }

    fail(snapshot, error) {
      this.require([STATES.RUNNING, STATES.PAUSE_REQUESTED, STATES.STEPPING, STATES.STOP_REQUESTED, STATES.ABORT_REQUESTED], "fail");
      this.currentSnapshot = clone(snapshot);
      this.stopReason = "error";
      this.move("fail", STATES.FAILED, { boundary: true, error: clone(error) });
      return this.status();
    }

    status() {
      return {
        state: this.state,
        stopReason: this.stopReason,
        initialSnapshot: clone(this.initialSnapshot),
        currentSnapshot: clone(this.currentSnapshot),
        transitions: clone(this.transitions),
        inputResumeState: this.inputResumeState,
      };
    }
  }

  return { STATES, MonitorTransitionError, MonitorExecutionControl };
});
