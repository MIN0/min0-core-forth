# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_outer"

include Min0CoreForth

def defer_outer
  vm = VM.new
  dictionary = RuntimeDictionary.new(vm)
  Min0CoreForth.install_core_primitives(dictionary)
  [vm, dictionary, OuterInterpreter.new(vm, dictionary)]
end

def defer_rejected(*errors)
  yield
  false
rescue *errors
  true
end

def run_defer_source_demo(implementation = "ruby")
  vm, dictionary, outer = defer_outer
  outer.interpret(": OLD-ACTION 10 ; : NEW-ACTION 20 ; DEFER ACTION")
  unassigned_rejected = defer_rejected(UnassignedDefer) { outer.interpret("ACTION") }

  outer.interpret("' OLD-ACTION IS ACTION : USE-ACTION ACTION ; USE-ACTION")
  old_action = dictionary.find("OLD-ACTION")
  action = dictionary.find("ACTION")
  first_value = vm.pop
  outer.interpret("ACTION-OF ACTION")
  first_action_xt = vm.pop

  outer.interpret("' NEW-ACTION IS ACTION USE-ACTION")
  new_action = dictionary.find("NEW-ACTION")
  second_value = vm.pop
  outer.interpret("ACTION-OF ACTION")
  second_action_xt = vm.pop
  relocation = outer.relocation_manifest.find { |record| record[:kind] == "defer-slot" }

  _bad_vm, _bad_dictionary, bad_outer = defer_outer
  bad_outer.interpret(": TARGET 1 ; DEFER D 7 CONSTANT NOT-COLON")
  non_colon_rejected = defer_rejected(DictionaryError) do
    bad_outer.interpret("' NOT-COLON IS D")
  end
  compile_rejected = defer_rejected(CompileStateError) do
    bad_outer.interpret(": BAD ['] TARGET IS D ;")
  end

  {
    implementation: implementation,
    unassigned_rejected: unassigned_rejected,
    first_value: first_value,
    first_action_xt: first_action_xt,
    old_xt: old_action.xt,
    second_value: second_value,
    second_action_xt: second_action_xt,
    new_xt: new_action.xt,
    defer_payload: dictionary.read_defer_target(action),
    non_colon_rejected: non_colon_rejected,
    compile_rejected: compile_rejected,
    relocation: relocation
  }
end

puts JSON.generate(run_defer_source_demo) if $PROGRAM_NAME == __FILE__
