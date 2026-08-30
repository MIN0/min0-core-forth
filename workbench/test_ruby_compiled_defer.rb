# frozen_string_literal: true

require_relative "compiled_defer_demo"

def assert_compiled_defer(condition, name)
  raise "#{name}: failed" unless condition

  puts "#{name}: PASS"
end

result = run_compiled_defer_demo
assert_compiled_defer(result[:safe_literal_xt] == result[:safe_new_xt], "safe [']")
assert_compiled_defer(result[:safe_current_xt] == result[:safe_old_xt], "safe ACTION-OF")
assert_compiled_defer(result[:safe_compiled_is_rejected], "safe compiled IS rejection")
assert_compiled_defer(result[:safe_target_unchanged], "safe target unchanged")
assert_compiled_defer(result[:build_before_switch] == 10, "build target before IS")
assert_compiled_defer(result[:build_after_switch] == 20, "build target after IS")
assert_compiled_defer(result[:profile_requires_build_vm], "explicit build VM permission")
assert_compiled_defer(result[:monitor_denied_compiled_is], "Monitor disables compiled IS")
assert_compiled_defer(result[:monitor_target_unchanged], "Monitor target unchanged")
puts "PASS: Ruby compiled DEFER tests completed"
