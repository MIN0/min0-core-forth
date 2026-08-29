# frozen_string_literal: true

require_relative "bytecode_verifier_demo"

result = run_bytecode_verifier_demo
raise "literal 0x25 was misclassified" unless result[:literal_0x25_capabilities] == []
raise "literal instruction count mismatch" unless result[:literal_instruction_count] == 2
unless result[:dset_capabilities] == ["compiled-defer-store"] && result[:dset_addresses] == [0x1000]
  raise "DSET capability mismatch"
end
raise "verifier rejection matrix failed" unless result[:rejected].values.all?

puts "literal 0x25 boundary: PASS"
puts "DSET capability derivation: PASS"
puts "structural and typed-reference rejection: PASS"
puts "PASS: Ruby bytecode verifier tests completed"
