# frozen_string_literal: true

require_relative "service_output_demo"

def assert_service(condition, name)
  raise name unless condition

  puts "#{name}: PASS"
end

def service_verifier_rejects?(code, records = [])
  components = { code: code.b, dictionary: "".b, data: "".b }
  bases = { code: 0, dictionary: 0x1000, data: 0x2000 }
  Min0CoreForth::BytecodeVerifier.verify_image_bytecode(
    components, bases, Min0CoreForth::Linker.build_manifest(records)
  )
  false
rescue Min0CoreForth::BytecodeVerificationError
  true
end

result = run_service_output_demo
assert_service(result[:service_ids] == [1], "service ID derivation")
assert_service(result[:registered_service_ids] == [1], "trusted service registry")
assert_service(result[:registry_sealed], "service registry seal")
assert_service(result[:late_registration_rejected], "late service rejection")
assert_service(result[:stack] == [], "compiled dot-quote stack")
assert_service(result[:terminal_text] == "Hello Service", "compiled dot-quote output")
assert_service(result[:code_permissions] == "rx", "service CODE seal")
assert_service(result[:data_permissions] == "r", "service DATA seal")

vm = Min0CoreForth::VM.new
calls = []
vm.register_service(7, -> { calls << "called" })
begin
  vm.register_service(7, -> {})
  raise "duplicate service should fail"
rescue Min0CoreForth::ServiceRegistrationError
  puts "duplicate service rejection: PASS"
end
assembler = Min0CoreForth::Assembler.new
assembler.emit(Min0CoreForth::Op::SERVICE, 7)
assembler.emit(Min0CoreForth::Op::HALT)
vm.load(assembler.build)
vm.run
assert_service(calls == ["called"], "registered service execution")

vm = Min0CoreForth::VM.new
vm.load(assembler.build)
begin
  vm.run
  raise "unknown service should fail"
rescue Min0CoreForth::UnknownService
  puts "unknown service rejection: PASS"
end

valid_service = [Min0CoreForth::Op::SERVICE, 1, Min0CoreForth::Op::HALT].pack("CV C")
components = { code: valid_service, dictionary: "".b, data: "".b }
bases = { code: 0, dictionary: 0x1000, data: 0x2000 }
summary = Min0CoreForth::BytecodeVerifier.verify_image_bytecode(
  components, bases, Min0CoreForth::Linker.build_manifest([])
)
assert_service(summary[:service_ids] == [1], "verifier service ID derivation")
assert_service(summary[:service_addresses] == [0], "verifier service address")
assert_service(
  service_verifier_rejects?([Min0CoreForth::Op::SERVICE, 1, 0].pack("C*")),
  "truncated service rejection"
)
assert_service(
  service_verifier_rejects?([Min0CoreForth::Op::SERVICE, 0].pack("CV")),
  "zero service ID rejection"
)
service_relocation = [{
  section: "code", offset: 1, target: "data", width: 4, kind: "string-address"
}]
assert_service(
  service_verifier_rejects?(valid_service, service_relocation),
  "service relocation rejection"
)
branch_into_operand = [
  Min0CoreForth::Op::SERVICE, 1,
  Min0CoreForth::Op::BRANCH, 1,
  Min0CoreForth::Op::HALT
].pack("CV CV C")
branch_relocation = [{
  section: "code", offset: 6, target: "code", width: 4, kind: "branch"
}]
assert_service(
  service_verifier_rejects?(branch_into_operand, branch_relocation),
  "branch into service operand rejection"
)

region = Min0CoreForth::MemoryRegion.new(
  name: "CODE", start: 0, size: 16, permissions: "rwx", programmable: true
)
sealed_vm = Min0CoreForth::VM.new(
  memory_size: 16,
  memory_bus: Min0CoreForth::RegionMemory.new(16, [region])
)
sealed_vm.load(valid_service)
begin
  sealed_vm.seal_verified_execution(summary)
  raise "missing required service should fail"
rescue Min0CoreForth::ExecutionPolicyError
  puts "missing required service rejection: PASS"
end
assert_service(region.permissions == "rwx", "failed seal leaves CODE writable")

puts "PASS: Ruby service-boundary tests completed"
