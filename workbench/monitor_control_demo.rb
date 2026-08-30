# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_control"

include Min0CoreForth

def monitor_program
  asm = Assembler.new
  asm.emit(Op::LIT, 1)
  asm.emit(Op::LIT, 2)
  asm.emit(Op::ADD)
  asm.emit(Op::NOP)
  asm.emit(Op::NOP)
  asm.emit(Op::HALT)
  asm.build
end

def control_rejected
  yield
  false
rescue ControlError, ArgumentError
  true
end

def run_monitor_control_demo(implementation = "ruby")
  vm = VM.new
  vm.load(monitor_program)
  authority = MonitorControlAuthority.new(vm)
  observer = authority.issue(CONTROL_PROFILE_OBSERVER, label: "viewer")
  monitor = authority.issue(CONTROL_PROFILE_MONITOR, label: "authenticated-monitor")

  denied = {
    observer_pause: control_rejected { observer.request_pause },
    observer_run: control_rejected { observer.run_slice(budget: 1) },
    profile_string: control_rejected { authority.status(CONTROL_PROFILE_MONITOR) },
    forged_session: control_rejected do
      ControlSession.new(authority, 999, "forged", Object.new)
    end
  }

  pause_points = []
  request_after_add = proc do |point|
    pause_points << {
      slice_steps: point.slice_steps,
      ip: point.ip,
      data_stack: point.data_stack
    }
    monitor.request_pause if point.slice_steps == 3
  end

  paused = monitor.run_slice(budget: 20, on_safe_point: request_after_add)
  budgeted = monitor.run_slice(budget: 1)
  watchdog = monitor.run_slice(
    budget: 20,
    watchdog: proc { |point| point.slice_steps < 1 }
  )
  resume_while_latched_rejected = control_rejected { monitor.run_slice(budget: 1) }
  monitor.clear_watchdog
  final = monitor.run_slice(budget: 20)

  revoked = authority.issue(CONTROL_PROFILE_OBSERVER, label: "temporary-viewer")
  authority.revoke(revoked)
  denied[:revoked_session] = control_rejected { revoked.status }

  {
    implementation: implementation,
    denied: denied,
    pause: paused.as_json,
    budget: budgeted.as_json,
    watchdog: watchdog.as_json,
    resume_while_latched_rejected: resume_while_latched_rejected,
    final: final.as_json,
    observer_status: observer.status,
    pause_points: pause_points
  }
end

puts JSON.generate(run_monitor_control_demo) if $PROGRAM_NAME == __FILE__
