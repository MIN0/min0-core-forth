# frozen_string_literal: true

require "json"
require_relative "constructor_image_fixture"
require_relative "min0_core_forth_linker"
require_relative "min0_core_forth_verify"

def run_service_output_demo(implementation = "ruby")
  vm, dictionary = make_image_system
  Min0CoreForth.install_core_primitives(dictionary)
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
  outer.interpret(': HELLO ." Hello" ;')
  outer.interpret(': GREET HELLO ."  Service" ;')
  outer.interpret(': CORE-OUTPUT 65 EMIT CR -42 . S" ABC" TYPE ;')
  components = {
    code: vm.read_bytes(
      Min0CoreForth::DEFAULT_CODE_BASE,
      outer.code_here - Min0CoreForth::DEFAULT_CODE_BASE
    ),
    dictionary: dictionary.image,
    data: dictionary.body_image
  }
  bases = {
    code: Min0CoreForth::DEFAULT_CODE_BASE,
    dictionary: dictionary.base,
    data: dictionary.body_base
  }
  verification = Min0CoreForth::BytecodeVerifier.verify_image_bytecode(
    components,
    bases,
    Min0CoreForth::Linker.build_manifest(outer.relocation_manifest)
  )
  vm.memory.seal_read_only_region("DATA")
  vm.seal_verified_execution(
    verification, extra_entries: outer.execution_extra_entries
  )
  stack = outer.interpret("GREET CORE-OUTPUT")
  late_registration_rejected = false
  begin
    vm.register_service(99, -> {})
  rescue Min0CoreForth::ServiceRegistrySealed
    late_registration_rejected = true
  end
  data_region = vm.memory.regions.find { |region| region.name == "DATA" }
  code_region = vm.memory.regions.find { |region| region.name == "CODE" }
  {
    implementation: implementation,
    service_id: Min0CoreForth::TERMINAL_TYPE_SERVICE_ID,
    service_id_map: {
      "terminal-type-v0.1" => Min0CoreForth::TERMINAL_TYPE_SERVICE_ID,
      "terminal-emit-v0.1" => Min0CoreForth::TERMINAL_EMIT_SERVICE_ID,
      "terminal-dot-v0.1" => Min0CoreForth::TERMINAL_DOT_SERVICE_ID,
      "terminal-cr-v0.1" => Min0CoreForth::TERMINAL_CR_SERVICE_ID
    },
    service_ids: verification[:service_ids],
    service_addresses: verification[:service_addresses],
    registered_service_ids: vm.registered_service_ids,
    registry_sealed: vm.service_registry_sealed?,
    late_registration_rejected: late_registration_rejected,
    stack: stack,
    output: outer.output,
    terminal_text: outer.terminal_text,
    code_permissions: code_region.permissions,
    data_permissions: data_region.permissions,
    code_here: outer.code_here,
    relocation_kinds: outer.relocation_manifest.map { |record| record[:kind] }
  }
end

puts JSON.generate(run_service_output_demo) if $PROGRAM_NAME == __FILE__
