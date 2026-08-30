# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_control"
require_relative "min0_core_forth_outer"

include Min0CoreForth

def patch_system
  vm = VM.new
  dictionary = RuntimeDictionary.new(vm)
  Min0CoreForth.install_core_primitives(dictionary)
  outer = OuterInterpreter.new(vm, dictionary)
  outer.interpret(": OLD-SERVICE 10 ; : NEW-SERVICE 20 ;")
  dictionary.add_defer("SERVICE", dictionary.find("OLD-SERVICE"))
  outer.interpret(": APPLICATION SERVICE ;")
  dictionary.add_constant("NOT-CODE", 7)
  application = dictionary.find("APPLICATION")

  wrapper = Assembler.new
  wrapper.emit(Op::CALL, application.payload)
  wrapper.emit(Op::CALL, application.payload)
  wrapper.emit(Op::HALT)
  vm.load(wrapper.build, address: 0x200)
  [vm, dictionary, outer]
end

def patch_rejected
  yield
  false
rescue ControlError, DictionaryError, ArgumentError
  true
end

def patch_tamper_rejected
  vm, dictionary, = patch_system
  authority = MonitorControlAuthority.new(vm, dictionary)
  monitor = authority.issue(CONTROL_PROFILE_MONITOR)
  monitor.request_pause
  monitor.run_slice(budget: 10)
  vm.data_stack << 0xBAD
  begin
    monitor.run_slice(budget: 1)
  rescue ControlInvariantError
    return true
  end
  false
end

def patch_ordinary_source_switch_rejected
  vm, dictionary, outer = patch_system
  authority = MonitorControlAuthority.new(vm, dictionary)
  monitor = authority.issue(CONTROL_PROFILE_MONITOR)
  deferred = dictionary.find("SERVICE")
  before = dictionary.read_defer_target(deferred)
  rejected = patch_rejected { outer.interpret("' NEW-SERVICE IS SERVICE") }
  unchanged = dictionary.read_defer_target(deferred) == before
  invariant_blocked = patch_rejected { monitor.run_slice(budget: 1) }
  rejected && unchanged && invariant_blocked
end

def run_monitor_patch_demo(implementation = "ruby")
  vm, dictionary, outer = patch_system
  authority = MonitorControlAuthority.new(vm, dictionary)
  observer = authority.issue(CONTROL_PROFILE_OBSERVER, label: "viewer")
  monitor = authority.issue(CONTROL_PROFILE_MONITOR, label: "authenticated-monitor")

  stop_between_calls = proc do |point|
    monitor.request_pause if point.slice_steps == 5
  end
  first = monitor.run_slice(budget: 30, on_safe_point: stop_between_calls)
  inspection = observer.inspect_paused
  service_before = inspection[:dictionary].find { |item| item[:name] == "SERVICE" }
  begin
    inspection[:data_stack] << 999
  rescue FrozenError
    # Ruby exposes the copied VM stack as an immutable observation.
  end
  snapshot_copy_isolated = vm.data_stack == [10]

  denied = {
    observer_switch: patch_rejected do
      observer.apply_forth_control("' NEW-SERVICE IS SERVICE")
    end,
    non_defer_source: patch_rejected { monitor.switch_defer("OLD-SERVICE", "NEW-SERVICE") },
    non_colon_target: patch_rejected { monitor.switch_defer("SERVICE", "NOT-CODE") },
    out_of_band_stack_tamper: patch_tamper_rejected,
    ordinary_source_after_lock: patch_ordinary_source_switch_rejected
  }
  audit = monitor.apply_forth_control("' NEW-SERVICE IS SERVICE")
  action_of = observer.apply_forth_control("ACTION-OF SERVICE")
  inspection_after = observer.inspect_paused
  service_after = inspection_after[:dictionary].find { |item| item[:name] == "SERVICE" }
  final = monitor.run_slice(budget: 30)
  defer_relocation = outer.relocation_manifest.find { |record| record[:kind] == "defer-slot" }

  {
    implementation: implementation,
    first: first.as_json,
    service_before: service_before,
    snapshot_copy_isolated: snapshot_copy_isolated,
    denied: denied,
    audit: audit,
    action_of: action_of,
    service_after: service_after,
    final: final.as_json,
    final_stack: vm.data_stack,
    audit_visible_to_observer: inspection_after[:audit],
    defer_relocation: defer_relocation
  }
end

puts JSON.generate(run_monitor_patch_demo) if $PROGRAM_NAME == __FILE__
