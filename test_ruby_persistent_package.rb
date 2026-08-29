# frozen_string_literal: true

require_relative "persistent_package_demo"

def persistent_assert_equal(expected, actual, name)
  raise "#{name}: expected #{expected.inspect}, got #{actual.inspect}" unless expected == actual

  puts "#{name}: PASS"
end

result = run_persistent_package_demo
persistent_assert_equal(1, result[:format_version], "persistent format version")
persistent_assert_equal(
  {
    image: {
      bytes: 8356,
      sha256: "571516cbebd7ce8c2f53d4acb5db0fbc3e07871b2e8d9ce8996b0bf954d17f43"
    },
    trust_bundle: {
      bytes: 538,
      sha256: "be731c1b8dcf241c7f96203bbac5d562e9be450da62bfc50f8b69ef20519ba83"
    },
    root_policy_chain: {
      bytes: 1364,
      sha256: "415d92cfb51c5150c9d101745bc166d37aa17e73bf57b1b7eb4b4c7c6d3b4490"
    }
  },
  result[:packages],
  "persistent package vectors"
)
persistent_assert_equal(
  [99, 2, 3, 3, 0, 2, 7, 32_768],
  result[:external_file][:stack],
  "external image execution"
)
persistent_assert_equal(
  {
    root_epoch: 2,
    trust_epoch: 2,
    image_key_id: "fixture-ed25519-01",
    valid: true
  },
  result[:trust_chain],
  "external trust chain"
)
persistent_assert_equal(15, result[:rejected].length, "persistent rejection count")
persistent_assert_equal(true, result[:rejected].values.all?, "persistent rejection matrix")
persistent_assert_equal(
  {
    resealed_container_passes_structure: true,
    image_signature_rejects_resealed_tamper: true,
    unknown_image_metadata_rejected: true
  },
  result[:layering],
  "checksum and authentication layering"
)

puts "PASS: Ruby persistent package tests completed"
