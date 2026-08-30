# frozen_string_literal: true

require_relative "monitor_control_demo"

def assert_control(condition, name)
  raise "#{name}: failed" unless condition

  puts "#{name}: PASS"
end

result = run_monitor_control_demo
assert_control(result[:denied].values.all?, "forged and observer control rejected")
assert_control(result[:pause][:reason] == Min0CoreForth::STOP_REQUESTED, "requested pause")
assert_control(result[:pause][:data_stack] == [3], "pause preserves data stack")
assert_control(result[:budget][:reason] == Min0CoreForth::STOP_BUDGET, "budget pause")
assert_control(result[:watchdog][:reason] == Min0CoreForth::STOP_WATCHDOG, "watchdog pause")
assert_control(result[:resume_while_latched_rejected], "watchdog latch")
assert_control(result[:final][:reason] == Min0CoreForth::STOP_HALT, "final halt")
assert_control(result[:final][:total_steps] == 6, "no instruction duplicated or skipped")
puts "PASS: Ruby Monitor control tests completed"
