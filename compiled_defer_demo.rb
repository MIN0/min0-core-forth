# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_control"
require_relative "min0_core_forth_outer"

include Min0CoreForth

def compiled_defer_system(standard_build: false)
  vm = VM.new(allow_defer_store: standard_build)
  dictionary = RuntimeDictionary.new(vm)
  Min0CoreForth.install_core_primitives(dictionary)
  options = standard_build ? { source_profile: SOURCE_PROFILE_STANDARD_BUILD } : {}
  outer = OuterInterpreter.new(vm, dictionary, **options)
  outer.interpret(
    ": OLD-ACTION 10 ; : NEW-ACTION 20 ; " \
    "DEFER ACTION ' OLD-ACTION IS ACTION"
  )
  [vm, dictionary, outer]
end

def compiled_defer_rejected(*errors)
  yield
  false
rescue *errors
  true
end

def monitor_disables_compiled_is
  vm, dictionary, outer = compiled_defer_system(standard_build: true)
  outer.interpret(": SWITCH ['] NEW-ACTION IS ACTION ;")
  deferred = dictionary.find("ACTION")
  before = dictionary.read_defer_target(deferred)
  MonitorControlAuthority.new(vm, dictionary)
  denied = compiled_defer_rejected(DeferStoreDenied) { outer.interpret("SWITCH") }
  [denied, dictionary.read_defer_target(deferred) == before]
end

def run_compiled_defer_demo(implementation = "ruby")
  safe_vm, safe_dictionary, safe_outer = compiled_defer_system
  safe_outer.interpret(": XT-OF-NEW ['] NEW-ACTION ;")
  safe_outer.interpret(": CURRENT-ACTION ACTION-OF ACTION ;")
  new_action = safe_dictionary.find("NEW-ACTION")
  old_action = safe_dictionary.find("OLD-ACTION")
  action = safe_dictionary.find("ACTION")
  safe_outer.interpret("XT-OF-NEW CURRENT-ACTION")
  safe_current_xt = safe_vm.pop
  safe_literal_xt = safe_vm.pop
  safe_compiled_is_rejected = compiled_defer_rejected(CompileStateError) do
    safe_outer.interpret(": FORBIDDEN ['] NEW-ACTION IS ACTION ;")
  end
  safe_target_unchanged = safe_dictionary.read_defer_target(action) == old_action.xt
  safe_relocations = safe_outer.relocation_manifest
                               .select { |record| ["xt-literal", "action-of-slot"].include?(record[:kind]) }
                               .to_h { |record| [record[:kind], record] }

  build_vm, build_dictionary, build_outer = compiled_defer_system(standard_build: true)
  build_outer.interpret(": USE-ACTION ACTION ; : SWITCH ['] NEW-ACTION IS ACTION ;")
  build_outer.interpret("USE-ACTION")
  before_switch = build_vm.pop
  build_outer.interpret("SWITCH USE-ACTION")
  after_switch = build_vm.pop
  build_action = build_dictionary.find("ACTION")
  build_new = build_dictionary.find("NEW-ACTION")
  build_target_xt = build_dictionary.read_defer_target(build_action)
  store_relocation = build_outer.relocation_manifest.find do |record|
    record[:kind] == "defer-store-slot"
  end

  profile_requires_build_vm = compiled_defer_rejected(OuterInterpreterError) do
    wrong_vm = VM.new
    OuterInterpreter.new(
      wrong_vm, RuntimeDictionary.new(wrong_vm),
      source_profile: SOURCE_PROFILE_STANDARD_BUILD
    )
  end
  monitor_denied, monitor_target_unchanged = monitor_disables_compiled_is

  {
    implementation: implementation,
    safe_literal_xt: safe_literal_xt,
    safe_new_xt: new_action.xt,
    safe_current_xt: safe_current_xt,
    safe_old_xt: old_action.xt,
    safe_compiled_is_rejected: safe_compiled_is_rejected,
    safe_target_unchanged: safe_target_unchanged,
    safe_relocations: safe_relocations,
    build_before_switch: before_switch,
    build_after_switch: after_switch,
    build_target_xt: build_target_xt,
    build_new_xt: build_new.xt,
    store_relocation: store_relocation,
    profile_requires_build_vm: profile_requires_build_vm,
    monitor_denied_compiled_is: monitor_denied,
    monitor_target_unchanged: monitor_target_unchanged
  }
end

puts JSON.generate(run_compiled_defer_demo) if $PROGRAM_NAME == __FILE__
