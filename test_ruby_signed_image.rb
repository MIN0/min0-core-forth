# frozen_string_literal: true

require_relative "signed_image_demo"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_signed_image_demo
assert_equal(5, result[:format_version], "image envelope v5")
assert_equal("ed25519", result[:scheme], "authentication scheme")
assert_equal("normal", result[:image_role], "normal image role")
assert_equal("fixture-ed25519-01", result[:key_id], "trusted key id")
assert_equal(
  "ac47aa6417ba1356b28daf3e7254343b5a56503ca2f633ba60384f17e0843274",
  result[:identity],
  "signed identity"
)
assert_equal(
  [
    "component-tamper", "signature-tamper", "malformed-signature", "key-id-tamper",
    "unknown-scheme", "extra-authentication-field", "unknown-key", "wrong-public-key",
    "missing-trust-store", "unsigned-secure-mode",
    "signed-rollback", "signed-relocation-without-resigning"
  ],
  result[:rejected],
  "fail-closed matrix"
)
assert_equal(7, result[:generation], "signed generation")
assert_equal(true, result[:target_signed][:valid], "resigned target validates")
assert_equal(7, result[:target_signed][:generation], "resigned target generation")

puts "PASS: Ruby signed image tests completed"
