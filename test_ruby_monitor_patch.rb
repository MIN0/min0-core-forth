# frozen_string_literal: true

require_relative "monitor_patch_demo"

def assert_patch(condition, name)
  raise "#{name}: failed" unless condition

  puts "#{name}: PASS"
end

result = run_monitor_patch_demo
assert_patch(result[:first][:data_stack] == [10], "old target before pause")
assert_patch(result[:final_stack] == [10, 20], "new target after resume")
assert_patch(result[:snapshot_copy_isolated], "snapshot is a copy")
assert_patch(result[:denied].values.all?, "unauthorized changes rejected")
assert_patch(result[:audit][:from] == "OLD-SERVICE", "audit old target")
assert_patch(result[:audit][:to] == "NEW-SERVICE", "audit new target")
assert_patch(result[:audit_visible_to_observer] == [result[:audit]], "audit visible")
assert_patch(result[:defer_relocation][:target] == "dictionary", "typed relocation")
puts "PASS: Ruby Monitor patch tests completed"
