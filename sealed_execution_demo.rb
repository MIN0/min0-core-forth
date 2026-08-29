# frozen_string_literal: true

require "json"
require_relative "constructor_relocation_demo"
require_relative "min0_core_forth_image"

SEALED_EXECUTION_BASES = { code: 0x1000, dictionary: 0x4000, data: 0x8000 }.freeze
SEALED_EXECUTION_LIMITS = { code: 0x4000, dictionary: 0x8000, data: 0x10000 }.freeze

def sealed_execution_rejected?(*errors)
  yield
  false
rescue *errors
  true
end

def run_sealed_execution_demo(implementation = "ruby")
  code_region = Min0CoreForth::MemoryRegion.new(
    name: "CODE", start: 0, size: 0x4000, permissions: "rwx", programmable: true
  )
  bus = Min0CoreForth::RegionMemory.new(
    0x10000,
    [
      code_region,
      Min0CoreForth::MemoryRegion.new(name: "DICTIONARY", start: 0x4000, size: 0x4000, permissions: "rw"),
      Min0CoreForth::MemoryRegion.new(name: "DATA", start: 0x8000, size: 0x8000, permissions: "rw")
    ]
  )
  vm = Min0CoreForth::VM.new(memory_bus: bus)
  dictionary = Min0CoreForth::RuntimeDictionary.new(
    vm, base: 0x4000, limit: 0x8000, body_base: 0x8000, body_limit: 0x10000
  )
  Min0CoreForth.install_core_primitives(dictionary)
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
  outer.interpret(
    ": SAFE 0x25 ; : TARGET 7 ; " \
    "DEFER ACTION ' TARGET IS ACTION : USE ACTION ; " \
    "VARIABLE CELL : DATA-ROUNDTRIP 123 CELL ! CELL @ ; " \
    ": CODE-WRITE 0x25 0x1000 ! ;"
  )
  safe = dictionary.find("SAFE")
  target = dictionary.find("TARGET")
  use = dictionary.find("USE")
  data_roundtrip = dictionary.find("DATA-ROUNDTRIP")
  code_write = dictionary.find("CODE-WRITE")
  operand_address = safe.payload + 1
  outer.interpret(
    format(": CORRUPT-TARGET 0x%X 0x%X ! ;", operand_address, target.xt + 4)
  )
  corrupt_target = dictionary.find("CORRUPT-TARGET")

  components = {
    code: vm.read_bytes(
      Min0CoreForth::DEFAULT_CODE_BASE,
      outer.code_here - Min0CoreForth::DEFAULT_CODE_BASE
    ),
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
    components,
    SEALED_EXECUTION_BASES,
    SEALED_EXECUTION_LIMITS,
    allocator,
    Min0CoreForth::Linker.build_manifest(records),
    generation: 1
  )
  validated = Min0CoreForth::ImageEnvelope.validate(components, envelope)
  verification = validated[:code_verification]
  before_permissions = code_region.permissions.dup
  vm.seal_verified_execution(
    verification,
    extra_entries: outer.execution_extra_entries
  )

  safe_value = outer.execute(safe).last
  vm.pop
  data_value = outer.execute(data_roundtrip).last
  vm.pop
  defer_value = outer.execute(use).last
  vm.pop
  primitive_value = outer.interpret("2 3 +").last
  vm.pop

  code_before = vm.read_bytes(Min0CoreForth::DEFAULT_CODE_BASE, 4)
  code_store_rejected = sealed_execution_rejected?(Min0CoreForth::MemoryFault) do
    outer.execute(code_write)
  end
  direct_code_write_rejected = sealed_execution_rejected?(Min0CoreForth::MemoryFault) do
    vm.write_cell(Min0CoreForth::DEFAULT_CODE_BASE, 0x25)
  end
  loader_rewrite_rejected = sealed_execution_rejected?(Min0CoreForth::MemoryFault) do
    vm.load("\x00".b, address: Min0CoreForth::DEFAULT_CODE_BASE)
  end
  operand_entry_rejected = sealed_execution_rejected?(Min0CoreForth::InvalidExecutionTarget) do
    vm.resume(operand_address, return_to: outer.return_trampoline)
  end

  outer.execute(corrupt_target)
  corrupted_payload = vm.read_cell(target.xt + 4)
  corrupted_indirect_rejected = sealed_execution_rejected?(Min0CoreForth::InvalidExecutionTarget) do
    outer.execute(use)
  end
  data_execution_rejected = sealed_execution_rejected?(
    Min0CoreForth::InvalidExecutionTarget, Min0CoreForth::MemoryFault
  ) do
    vm.resume(dictionary.body_base)
  end
  reseal_rejected = sealed_execution_rejected?(Min0CoreForth::ExecutionPolicyError) do
    vm.seal_verified_execution(
      verification, extra_entries: outer.execution_extra_entries
    )
  end
  clear_rejected = sealed_execution_rejected?(Min0CoreForth::MemoryFault) do
    bus.clear
  end
  flat_memory_seal_rejected = sealed_execution_rejected?(Min0CoreForth::ExecutionPolicyError) do
    Min0CoreForth::VM.new.seal_verified_execution(verification)
  end
  {
    implementation: implementation,
    before_permissions: before_permissions,
    after_permissions: code_region.permissions,
    code_programmable_after_seal: code_region.programmable?,
    code_sealed: code_region.sealed?,
    verified_boundary_count: vm.verified_boundaries.length,
    values: {
      literal_0x25: safe_value,
      data_roundtrip: data_value,
      defer_before_corruption: defer_value,
      primitive_after_seal: primitive_value
    },
    corrupted_target_payload: corrupted_payload,
    operand_address: operand_address,
    code_unchanged: vm.read_bytes(Min0CoreForth::DEFAULT_CODE_BASE, 4) == code_before,
    rejected: {
      forth_store_to_code: code_store_rejected,
      direct_code_write: direct_code_write_rejected,
      loader_rewrite_after_seal: loader_rewrite_rejected,
      resume_into_operand: operand_entry_rejected,
      corrupted_indirect_target: corrupted_indirect_rejected,
      execute_data: data_execution_rejected,
      second_seal: reseal_rejected,
      clear_sealed_code: clear_rejected,
      flat_memory_cannot_seal: flat_memory_seal_rejected
    }
  }
end

puts JSON.generate(run_sealed_execution_demo) if $PROGRAM_NAME == __FILE__
