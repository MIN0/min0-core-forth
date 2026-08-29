# frozen_string_literal: true

require_relative "auth_comparison_demo"

def assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_auth_comparison_demo
assert_equal(
  "d2dea082c439badd51ae464b36775297a2cef9c9184fe08ae621545c916d6573",
  result[:hmac][:tag_hex],
  "HMAC vector"
)
assert_equal(
  "29acbae141bccaf0b22e1a94d34d0bc7361e526d0bfe12c89794bc9322966dd7",
  result[:ed25519][:public_key_hex],
  "Ed25519 public key vector"
)
assert_equal(
  "81fad4a7f388a6355fb1c6e90ab1f838120d27e55acf5e6e3f49857048f5b464" \
  "a62f4e65348b0a5f4f5c70fcbab43f684359921e3fee93564fc895a934ef7601",
  result[:ed25519][:signature_hex],
  "Ed25519 signature vector"
)
assert_equal(
  {
    hmac_valid: true,
    hmac_tampered: false,
    hmac_wrong_key: false,
    ed25519_valid: true,
    ed25519_tampered: false,
    ed25519_wrong_key: false
  },
  result[:verification],
  "authentication verification matrix"
)
assert_equal(true, result[:device_compromise][:hmac_verifier_can_forge], "HMAC verifier secret can forge")
assert_equal(false, result[:device_compromise][:ed25519_verifier_can_forge], "Ed25519 public verifier cannot forge")
assert_equal(32, result[:sizes][:hmac_tag], "HMAC tag bytes")
assert_equal(64, result[:sizes][:ed25519_signature], "Ed25519 signature bytes")
assert_equal(32, result[:sizes][:ed25519_device_public], "Ed25519 device public key bytes")

puts "PASS: Ruby authentication comparison tests completed"
