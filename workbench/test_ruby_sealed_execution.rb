# frozen_string_literal: true

require_relative "sealed_execution_demo"

result = run_sealed_execution_demo
raise "build permissions mismatch" unless result[:before_permissions] == "rwx"
raise "runtime permissions mismatch" unless result[:after_permissions] == "rx"
raise "CODE remains programmable" if result[:code_programmable_after_seal]
raise "CODE did not seal" unless result[:code_sealed]
unless result[:values] == {
  literal_0x25: 0x25,
  data_roundtrip: 123,
  defer_before_corruption: 7,
  primitive_after_seal: 5
}
  raise "sealed execution changed valid behavior"
end
raise "CODE changed after rejected write" unless result[:code_unchanged]
raise "sealed rejection matrix failed" unless result[:rejected].values.all?

puts "one-way rwx to rx seal: PASS"
puts "safe CODE/DATA/DEFER execution: PASS"
puts "write and invalid-target rejection: PASS"
puts "PASS: Ruby sealed execution tests completed"
