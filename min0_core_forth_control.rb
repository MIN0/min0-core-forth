# frozen_string_literal: true

# Safe-point execution control around the independent Ruby VM.
require_relative "min0_core_forth_vm"
require_relative "min0_core_forth_compiler"
require "digest"

module Min0CoreForth
  CONTROL_PROFILE_OBSERVER = "observer"
  CONTROL_PROFILE_MONITOR = "monitor"

  CONTROL_STATE_PAUSED = "paused"
  CONTROL_STATE_RUNNING = "running"
  CONTROL_STATE_WATCHDOG = "watchdog-latched"
  CONTROL_STATE_HALTED = "halted"
  CONTROL_STATE_FAULTED = "faulted"

  STOP_REQUESTED = "pause-requested"
  STOP_BUDGET = "budget-exhausted"
  STOP_WATCHDOG = "watchdog-expired"
  STOP_HALT = "halted"

  class ControlError < StandardError; end
  class ControlAuthorizationError < ControlError; end
  class ControlStateError < ControlError; end
  class ControlInvariantError < ControlStateError; end

  SafePoint = Struct.new(
    :slice_steps, :total_steps, :ip, :data_stack, :return_stack, :loop_stack,
    keyword_init: true
  )

  RunResult = Struct.new(
    :reason, :executed, :total_steps, :ip, :data_stack, :return_stack, :loop_stack,
    keyword_init: true
  ) do
    def as_json
      {
        reason: reason,
        executed: executed,
        total_steps: total_steps,
        ip: ip,
        data_stack: data_stack,
        return_stack: return_stack,
        loop_stack: loop_stack
      }
    end
  end

  class ControlSession
    attr_reader :serial, :label

    def initialize(authority, serial, label, marker)
      unless authority.valid_session_marker?(marker)
        raise ControlAuthorizationError, "control sessions must be issued by the authority"
      end

      @authority = authority
      @serial = serial
      @label = label
    end

    def status = @authority.status(self)
    def request_pause = @authority.request_pause(self)

    def run_slice(budget:, watchdog: nil, on_safe_point: nil)
      @authority.run_slice(
        self, budget: budget, watchdog: watchdog, on_safe_point: on_safe_point
      )
    end

    def clear_watchdog = @authority.clear_watchdog(self)
    def inspect_paused = @authority.inspect_paused(self)
    def switch_defer(defer_name, target_name) = @authority.switch_defer(self, defer_name, target_name)
    def apply_forth_control(source) = @authority.apply_forth_control(self, source)
  end

  class MonitorControlAuthority
    attr_reader :vm

    def initialize(vm, dictionary = nil)
      @vm = vm
      @dictionary = dictionary
      @vm.lock_defer_store
      @defer_authorization = Object.new
      @dictionary.lock_defer_updates(@defer_authorization) unless @dictionary.nil?
      @marker = Object.new
      @profiles = {}
      @next_serial = 1
      @pause_requested = false
      @watchdog_latched = false
      @state = vm.halted? ? CONTROL_STATE_HALTED : CONTROL_STATE_PAUSED
      @last_stop = vm.halted? ? STOP_HALT : nil
      @audit = []
      @seal = control_fingerprint
    end

    def valid_session_marker?(marker) = marker.equal?(@marker)

    def issue(profile, label: nil)
      unless [CONTROL_PROFILE_OBSERVER, CONTROL_PROFILE_MONITOR].include?(profile)
        raise ArgumentError, "unknown control profile #{profile.inspect}"
      end

      session = ControlSession.new(self, @next_serial, label || profile, @marker)
      @next_serial += 1
      @profiles[session] = profile
      session
    end

    def revoke(session)
      profile(session)
      @profiles.delete(session)
    end

    def status(session)
      profile(session)
      point = safe_point(0)
      {
        state: @state,
        last_stop: @last_stop,
        pause_requested: @pause_requested,
        watchdog_latched: @watchdog_latched,
        total_steps: point.total_steps,
        ip: point.ip,
        data_stack: point.data_stack,
        return_stack: point.return_stack,
        loop_stack: point.loop_stack
      }
    end

    def request_pause(session)
      require_monitor(session)
      @pause_requested = true
      nil
    end

    def inspect_paused(session)
      profile(session)
      unless [CONTROL_STATE_PAUSED, CONTROL_STATE_WATCHDOG, CONTROL_STATE_HALTED].include?(@state)
        raise ControlStateError, "inspection requires a stopped VM"
      end
      verify_resume_invariants
      result = status(session)
      result[:dictionary] = if @dictionary.nil?
                              []
                            else
                              @dictionary.entries(include_hidden: false).map do |entry|
                                {
                                  name: entry.name, kind: entry.kind,
                                  xt: entry.xt, payload: entry.payload
                                }
                              end
                            end
      result[:audit] = @audit.map(&:dup)
      result
    end

    def switch_defer(session, defer_name, target_name)
      require_monitor(session)
      if @state != CONTROL_STATE_PAUSED || @watchdog_latched
        raise ControlStateError, "DEFER switching requires an acknowledged pause"
      end
      raise ControlStateError, "no runtime dictionary is attached" if @dictionary.nil?

      verify_resume_invariants
      deferred = @dictionary.find(defer_name)
      target = @dictionary.find(target_name)
      raise ControlStateError, "unknown DEFER word #{defer_name.inspect}" if deferred.nil?
      raise ControlStateError, "unknown DEFER target #{target_name.inspect}" if target.nil?

      old_xt = @dictionary.read_defer_target(deferred)
      old_name = colon_name_for(old_xt)
      updated = @dictionary.set_defer(
        deferred, target, authorization: @defer_authorization
      )
      record = {
        sequence: @audit.length + 1,
        operation: "defer-switch",
        defer: updated.name,
        from: old_name,
        to: target.name,
        old_xt: old_xt,
        new_xt: updated.payload,
        total_steps: vm.steps,
        ip: vm.ip
      }
      @audit << record
      @seal = control_fingerprint
      record.dup
    end

    def apply_forth_control(session, source)
      tokens = Compiler.tokenize(source)
      if tokens.length == 4 && tokens[0] == "'" && tokens[2] == "IS"
        return switch_defer(session, tokens[3], tokens[1])
      end
      profile(session)
      if tokens.length == 2 && tokens[0] == "ACTION-OF"
        raise ControlStateError, "no runtime dictionary is attached" if @dictionary.nil?

        deferred = @dictionary.find(tokens[1])
        raise ControlStateError, "unknown DEFER word #{tokens[1].inspect}" if deferred.nil?

        target_xt = @dictionary.read_defer_target(deferred)
        return {
          operation: "action-of", defer: deferred.name,
          target: colon_name_for(target_xt), target_xt: target_xt
        }
      end
      raise ControlStateError,
            "control source must be: ' target IS defer, or ACTION-OF defer"
    end

    def clear_watchdog(session)
      require_monitor(session)
      raise ControlStateError, "watchdog is not latched" unless @watchdog_latched

      @watchdog_latched = false
      @state = CONTROL_STATE_PAUSED
      nil
    end

    def run_slice(session, budget:, watchdog: nil, on_safe_point: nil)
      require_monitor(session)
      unless budget.is_a?(Integer) && budget.positive?
        raise ArgumentError, "instruction budget must be a positive integer"
      end
      if @watchdog_latched
        raise ControlStateError, "watchdog must be explicitly cleared before execution resumes"
      end
      raise ControlStateError, "faulted execution cannot be resumed" if @state == CONTROL_STATE_FAULTED
      verify_resume_invariants
      if vm.halted?
        @state = CONTROL_STATE_HALTED
        return result(STOP_HALT, 0)
      end

      @state = CONTROL_STATE_RUNNING
      executed = 0
      loop do
        point = safe_point(executed)
        on_safe_point.call(point) unless on_safe_point.nil?
        if @pause_requested
          @pause_requested = false
          @state = CONTROL_STATE_PAUSED
          return result(STOP_REQUESTED, executed)
        end
        if executed >= budget
          @state = CONTROL_STATE_PAUSED
          return result(STOP_BUDGET, executed)
        end
        unless watchdog.nil? || watchdog.call(point)
          @watchdog_latched = true
          @state = CONTROL_STATE_WATCHDOG
          return result(STOP_WATCHDOG, executed)
        end

        vm.step
        executed += 1
        if vm.halted?
          @state = CONTROL_STATE_HALTED
          return result(STOP_HALT, executed)
        end
      end
    rescue VMError
      @state = CONTROL_STATE_FAULTED
      raise
    end

    private

    def profile(session)
      @profiles.fetch(session)
    rescue KeyError, TypeError
      raise ControlAuthorizationError, "unknown, forged, or revoked control session"
    end

    def require_monitor(session)
      return if profile(session) == CONTROL_PROFILE_MONITOR

      raise ControlAuthorizationError, "monitor control authority is required"
    end

    def safe_point(slice_steps)
      SafePoint.new(
        slice_steps: slice_steps,
        total_steps: vm.steps,
        ip: vm.ip,
        data_stack: vm.data_stack.dup.freeze,
        return_stack: vm.return_stack.dup.freeze,
        loop_stack: vm.loop_stack.map { |frame| [frame.limit, frame.index].freeze }.freeze
      )
    end

    def result(reason, executed)
      @last_stop = reason
      point = safe_point(executed)
      value = RunResult.new(
        reason: reason,
        executed: executed,
        total_steps: point.total_steps,
        ip: point.ip,
        data_stack: point.data_stack,
        return_stack: point.return_stack,
        loop_stack: point.loop_stack
      )
      @seal = control_fingerprint
      value
    end

    def colon_name_for(target_xt)
      return "<unassigned>" if target_xt.zero?

      entry = @dictionary.entries(include_hidden: false).find do |candidate|
        candidate.kind == KIND_COLON && candidate.xt == target_xt
      end
      entry.nil? ? format("0x%08X", target_xt) : entry.name
    end

    def control_fingerprint
      dictionary_state = if @dictionary.nil?
                           nil
                         else
                           [
                             @dictionary.here, @dictionary.data_here, @dictionary.latest,
                             Digest::SHA256.digest(@dictionary.image)
                           ]
                         end
      [
        vm.ip, vm.steps, vm.halted?, vm.allow_defer_store?,
        vm.data_stack.dup, vm.return_stack.dup,
        vm.loop_stack.map { |frame| [frame.limit, frame.index] }, dictionary_state
      ]
    end

    def verify_resume_invariants
      if vm.allow_defer_store?
        raise ControlInvariantError,
              "compiled DEFER store must remain disabled under Monitor control"
      end
      if vm.data_stack.length > vm.max_data_depth
        raise ControlInvariantError, "DATA stack exceeds its configured limit"
      end
      if vm.return_stack.length > vm.max_return_depth
        raise ControlInvariantError, "RETURN stack exceeds its configured limit"
      end
      if vm.loop_stack.length > vm.max_loop_depth
        raise ControlInvariantError, "LOOP stack exceeds its configured limit"
      end
      begin
        vm.memory.check_fetch(vm.ip, 1) unless vm.halted?
        vm.return_stack.each { |address| vm.memory.check_fetch(address, 1) }
        unless @dictionary.nil?
          @dictionary.entries.each do |entry|
            @dictionary.read_defer_target(entry) if entry.kind == KIND_DEFER
          end
        end
      rescue StandardError
        raise ControlInvariantError, "control-state structure is invalid"
      end
      return if control_fingerprint == @seal

      raise ControlInvariantError,
            "control-critical state changed outside an authorized operation"
    end
  end
end
