# frozen_string_literal: true

require_relative "defer_source_demo"

def assert_defer(condition, name)
  raise "#{name}: failed" unless condition

  puts "#{name}: PASS"
end

result = run_defer_source_demo
assert_defer(result[:first_value] == 10, "old source action")
assert_defer(result[:second_value] == 20, "new source action")
assert_defer(result[:first_action_xt] == result[:old_xt], "first ACTION-OF XT")
assert_defer(result[:second_action_xt] == result[:new_xt], "second ACTION-OF XT")
assert_defer(result[:unassigned_rejected], "unassigned DEFER rejected")
assert_defer(result[:non_colon_rejected], "non-colon IS rejected")
assert_defer(result[:compile_rejected], "safe compiled IS restriction")
puts "PASS: Ruby DEFER source tests completed"
