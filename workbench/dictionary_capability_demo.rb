# frozen_string_literal: true

require "json"
require_relative "constructor_image_fixture"
require_relative "constructor_relocation_demo"
require_relative "min0_core_forth_control"
require_relative "min0_core_forth_image"
require_relative "min0_core_forth_publish"

DICTIONARY_CAPABILITY_BASES = { code: 0x1000, dictionary: 0x4000, data: 0x8000 }.freeze
DICTIONARY_CAPABILITY_LIMITS = { code: 0x4000, dictionary: 0x8000, data: 0x10000 }.freeze
DICTIONARY_CAPABILITY_SOURCE = ": TARGET-A 7 ; : TARGET-B 9 ; " \
                               "DEFER ACTION ' TARGET-A IS ACTION : USE ACTION ; VARIABLE CELL"

def dictionary_capability_rejected?(*errors)
  yield
  false
rescue *errors
  true
end

def build_dictionary_capability_image
  vm, dictionary = make_image_system
  Min0CoreForth.install_core_primitives(dictionary)
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
  outer.interpret(DICTIONARY_CAPABILITY_SOURCE)
  components = {
    code: vm.read_bytes(Min0CoreForth::DEFAULT_CODE_BASE, outer.code_here - Min0CoreForth::DEFAULT_CODE_BASE),
    dictionary: dictionary.image,
    data: dictionary.body_image
  }
  allocator = {
    code_here: outer.code_here,
    header_here: dictionary.here,
    data_here: dictionary.data_here,
    latest: dictionary.latest
  }
  records = outer.relocation_manifest + collect_dictionary_relocations(vm, dictionary)
  envelope = Min0CoreForth::ImageEnvelope.build(
    components, DICTIONARY_CAPABILITY_BASES, DICTIONARY_CAPABILITY_LIMITS,
    allocator, Min0CoreForth::Linker.build_manifest(records), generation: 1
  )
  [components, envelope]
end

def run_dictionary_capability_demo(implementation = "ruby")
  components, envelope = build_dictionary_capability_image
  published = Min0CoreForth::RuntimePublisher.publish(components, envelope)
  vm = published.vm
  dictionary = published.dictionary
  outer = published.outer
  dictionary_region = vm.memory.regions.find { |region| region.name == "DICTIONARY" }
  action = dictionary.find("ACTION")
  target_b = dictionary.find("TARGET-B")
  use = dictionary.find("USE")

  data_value = outer.interpret("123 CELL ! CELL @").last
  vm.data_stack.clear
  dictionary_before_attacks = dictionary.image
  raw_header_store_rejected = dictionary_capability_rejected?(Min0CoreForth::MemoryFault) do
    outer.interpret(format("0 0x%X !", dictionary.latest))
  end
  vm.data_stack.clear
  raw_defer_store_rejected = dictionary_capability_rejected?(Min0CoreForth::MemoryFault) do
    outer.interpret(format("0 0x%X !", action.xt + 4))
  end
  vm.data_stack.clear
  definition_rejected = dictionary_capability_rejected?(Min0CoreForth::DictionaryError) do
    outer.interpret(": INTRUDER 1 ;")
  end
  allocator_rejected = dictionary_capability_rejected?(Min0CoreForth::DictionaryError) do
    outer.interpret("1 ,")
  end
  vm.data_stack.clear
  ordinary_is_rejected = dictionary_capability_rejected?(Min0CoreForth::DictionaryError) do
    outer.interpret("' TARGET-B IS ACTION")
  end
  vm.data_stack.clear
  loader_program_rejected = dictionary_capability_rejected?(Min0CoreForth::MemoryFault) do
    vm.load("\x00".b, address: dictionary.latest)
  end
  second_structure_seal_rejected = dictionary_capability_rejected?(Min0CoreForth::DictionaryError) do
    dictionary.seal_runtime_structure
  end
  flat_dictionary = Min0CoreForth::RuntimeDictionary.new(Min0CoreForth::VM.new)
  flat_memory_seal_rejected = dictionary_capability_rejected?(Min0CoreForth::DictionaryError) do
    flat_dictionary.seal_runtime_structure
  end
  forged_scope_rejected = dictionary_capability_rejected?(Min0CoreForth::MemoryFault) do
    vm.memory.with_authorized_writes("DICTIONARY", Object.new) {}
  end
  attacks_left_dictionary_unchanged = dictionary.image == dictionary_before_attacks

  vm.reset(clear_memory: false)
  authority = Min0CoreForth::MonitorControlAuthority.new(vm, dictionary)
  observer = authority.issue(Min0CoreForth::CONTROL_PROFILE_OBSERVER)
  monitor = authority.issue(Min0CoreForth::CONTROL_PROFILE_MONITOR)
  observer_switch_rejected = dictionary_capability_rejected?(Min0CoreForth::ControlAuthorizationError) do
    observer.switch_defer("ACTION", "TARGET-B")
  end
  audit = monitor.switch_defer("ACTION", "TARGET-B")
  defer_value = outer.execute(use).last
  vm.pop

  dictionary_after_monitor = dictionary.image
  changed_offsets = dictionary_before_attacks.bytes.zip(dictionary_after_monitor.bytes).each_index.filter_map do |index|
    index if dictionary_before_attacks.getbyte(index) != dictionary_after_monitor.getbyte(index)
  end
  defer_offset = action.xt + 4 - dictionary.base
  monitor_changed_only_defer_slot = !changed_offsets.empty? && changed_offsets.all? do |offset|
    offset >= defer_offset && offset < defer_offset + 4
  end
  {
    implementation: implementation,
    dictionary_permissions: dictionary_region.permissions,
    dictionary_write_protected: dictionary_region.write_protected?,
    runtime_structure_sealed: dictionary.runtime_structure_sealed?,
    data_value: data_value,
    defer_value_after_monitor: defer_value,
    monitor_audit_operation: audit[:operation],
    attacks_left_dictionary_unchanged: attacks_left_dictionary_unchanged,
    monitor_changed_only_defer_slot: monitor_changed_only_defer_slot,
    rejected: {
      raw_header_store: raw_header_store_rejected,
      raw_defer_store: raw_defer_store_rejected,
      new_definition: definition_rejected,
      allocator_comma: allocator_rejected,
      ordinary_is: ordinary_is_rejected,
      loader_program: loader_program_rejected,
      second_structure_seal: second_structure_seal_rejected,
      flat_memory_seal: flat_memory_seal_rejected,
      forged_write_scope: forged_scope_rejected,
      observer_switch: observer_switch_rejected
    }
  }
end

puts JSON.generate(run_dictionary_capability_demo) if $PROGRAM_NAME == __FILE__
