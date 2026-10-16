(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./mobile-monitor-state.js"));
  } else {
    root.Min0MobileForthScheduler = factory(root.Min0MobileMonitor);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (monitor) {
  "use strict";

  if (!monitor) throw new Error("Mobile Monitor state module is required");

  const { STATES } = monitor;
  const RUNNABLE = new Set([
    STATES.RUNNING,
    STATES.PAUSE_REQUESTED,
    STATES.STEPPING,
    STATES.STOP_REQUESTED,
    STATES.ABORT_REQUESTED,
  ]);

  class MobileForthScheduler {
    constructor(session, options = {}) {
      if (!session || typeof session.advance !== "function") throw new TypeError("a MobileForthSession is required");
      this.session = session;
      this.chunkSize = options.chunkSize === undefined ? 100 : Number(options.chunkSize);
      if (!Number.isSafeInteger(this.chunkSize) || this.chunkSize < 1) throw new RangeError("chunkSize must be a positive safe integer");
      this.schedule = options.schedule || (callback => setTimeout(callback, 0));
      this.onUpdate = options.onUpdate || (() => {});
      this.started = false;
      this.scheduled = false;
      this.chunkSequence = 0;
      this.totalBoundaries = 0;
    }

    isRunnable() { return RUNNABLE.has(this.session.state); }

    update(kind, executed = 0) {
      const event = {
        kind,
        chunkSequence: this.chunkSequence,
        executed,
        totalBoundaries: this.totalBoundaries,
        scheduled: this.scheduled,
        status: this.session.status(),
        diagnostics: this.isRunnable() ? null : this.session.diagnostics(),
      };
      this.onUpdate(event);
      return event;
    }

    start() {
      if (this.started) throw new Error("scheduler has already started");
      this.started = true;
      this.update("start");
      this.scheduleNext();
    }

    scheduleNext() {
      if (!this.started || this.scheduled || !this.isRunnable()) return false;
      this.scheduled = true;
      this.schedule(() => {
        this.scheduled = false;
        this.runChunk();
      });
      return true;
    }

    runChunk() {
      if (!this.started || !this.isRunnable()) return this.update("idle-chunk");
      this.chunkSequence += 1;
      let executed = 0;
      while (executed < this.chunkSize && this.isRunnable()) {
        this.session.advance();
        executed += 1;
      }
      this.totalBoundaries += executed;
      const event = this.update("chunk", executed);
      this.scheduleNext();
      return event;
    }

    requestPause() {
      this.session.requestPause();
      const event = this.update("pause-requested");
      this.scheduleNext();
      return event;
    }

    continueExecution() {
      this.session.continueExecution();
      const event = this.update("continued");
      this.scheduleNext();
      return event;
    }

    step() {
      this.session.step();
      const event = this.update("step-requested");
      this.scheduleNext();
      return event;
    }

    requestStop() {
      this.session.requestStop();
      const event = this.update("stop-requested");
      this.scheduleNext();
      return event;
    }

    requestAbort() {
      this.session.requestAbort();
      const event = this.update("abort-requested");
      this.scheduleNext();
      return event;
    }

    enqueueInput(text) {
      const count = this.session.enqueueInput(text);
      const event = this.update("input-enqueued");
      this.scheduleNext();
      return { count, event };
    }
  }

  return { MobileForthScheduler, RUNNABLE };
});
