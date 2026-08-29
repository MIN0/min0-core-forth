# frozen_string_literal: true

require_relative "security_boundary_demo"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_security_boundary_demo
by_id = result[:scenarios].to_h { |item| [item[:id], item] }
assert_equal("blocked", by_id.fetch("T01")[:result], "component corruption blocked")
assert_equal("blocked", by_id.fetch("T02")[:result], "manifest tamper blocked")
assert_equal("blocked", by_id.fetch("T06")[:result], "infinite execution blocked")
assert_equal(4, result[:controlled], "current controlled count")
assert_equal("accepted", by_id.fetch("T03")[:result], "malicious rebuild gap visible")
assert_equal("blocked", by_id.fetch("T05")[:result], "rollback blocked")
assert_equal(["T03"], result[:gaps], "explicit threat gaps")
assert_equal(true, result[:generation_present], "generation present")
assert_equal("none", result[:authentication], "authentication absent")
assert_equal("blocked", by_id.fetch("T04")[:result], "authenticated policy fail-closed")

puts "PASS: Ruby security boundary tests completed"
