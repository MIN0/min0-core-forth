# frozen_string_literal: true

require "digest"
require "json"
require_relative "min0_core_forth_auth"
require_relative "image_envelope_demo"

# Public, deterministic test fixtures only. Never use these keys in deployment.
HMAC_TEST_KEY = (0...32).to_a.pack("C*").freeze
ED25519_TEST_SEED = (32...64).to_a.pack("C*").freeze
WRONG_HMAC_TEST_KEY = (0...32).to_a.reverse.pack("C*").freeze
WRONG_ED25519_TEST_SEED = ([0xA5] * 32).pack("C*").freeze

def tamper_identity(identity)
  replacement = identity[0] == "0" ? "1" : "0"
  replacement + identity[1..]
end

def benchmark_auth(identity, hmac_tag, public_key, signature)
  hmac_iterations = 2000
  ed_iterations = 300
  start = Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond)
  hmac_iterations.times do
    Min0CoreForth::Authentication.hmac_verify(identity, HMAC_TEST_KEY, hmac_tag)
  end
  hmac_us = (Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond) - start).fdiv(hmac_iterations * 1000)

  private_key = Min0CoreForth::Authentication.ed25519_private_from_seed(ED25519_TEST_SEED)
  start = Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond)
  ed_iterations.times do
    Min0CoreForth::Authentication.ed25519_sign(identity, private_key)
  end
  ed_sign_us = (Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond) - start).fdiv(ed_iterations * 1000)

  start = Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond)
  ed_iterations.times do
    Min0CoreForth::Authentication.ed25519_verify(identity, public_key, signature)
  end
  ed_verify_us = (Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond) - start).fdiv(ed_iterations * 1000)
  {
    hmac_verify_us: hmac_us.round(3),
    ed25519_sign_us: ed_sign_us.round(3),
    ed25519_verify_us: ed_verify_us.round(3),
    note: "host measurement only; not a target estimate"
  }
end

def run_auth_comparison_demo(implementation = "ruby")
  _components, envelope = build_source_image
  identity = envelope[:identity_sha256]
  tampered = tamper_identity(identity)

  hmac_tag = Min0CoreForth::Authentication.hmac_sign(identity, HMAC_TEST_KEY)
  forged_tag = Min0CoreForth::Authentication.hmac_sign(tampered, HMAC_TEST_KEY)

  private_key = Min0CoreForth::Authentication.ed25519_private_from_seed(ED25519_TEST_SEED)
  public_key = Min0CoreForth::Authentication.ed25519_public_bytes(private_key)
  wrong_public_key = Min0CoreForth::Authentication.ed25519_public_bytes(
    Min0CoreForth::Authentication.ed25519_private_from_seed(WRONG_ED25519_TEST_SEED)
  )
  signature = Min0CoreForth::Authentication.ed25519_sign(identity, private_key)
  public_object = Min0CoreForth::Authentication.ed25519_public_from_bytes(public_key)
  public_can_sign = begin
    public_object.sign(nil, Min0CoreForth::Authentication.message(identity))
    true
  rescue OpenSSL::PKey::PKeyError
    false
  end

  {
    implementation: implementation,
    identity: identity,
    message_bytes: Min0CoreForth::Authentication.message(identity).bytesize,
    hmac: {
      scheme: "hmac-sha256",
      key_id: "fixture-hmac-01",
      tag_hex: hmac_tag.unpack1("H*")
    },
    ed25519: {
      scheme: "ed25519",
      key_id: Digest::SHA256.hexdigest(public_key)[0, 16],
      public_key_hex: public_key.unpack1("H*"),
      signature_hex: signature.unpack1("H*")
    },
    sizes: {
      hmac_device_secret: HMAC_TEST_KEY.bytesize,
      hmac_tag: hmac_tag.bytesize,
      ed25519_signer_seed: ED25519_TEST_SEED.bytesize,
      ed25519_device_public: public_key.bytesize,
      ed25519_signature: signature.bytesize
    },
    verification: {
      hmac_valid: Min0CoreForth::Authentication.hmac_verify(identity, HMAC_TEST_KEY, hmac_tag),
      hmac_tampered: Min0CoreForth::Authentication.hmac_verify(tampered, HMAC_TEST_KEY, hmac_tag),
    hmac_wrong_key: Min0CoreForth::Authentication.hmac_verify(identity, WRONG_HMAC_TEST_KEY, hmac_tag),
      ed25519_valid: Min0CoreForth::Authentication.ed25519_verify(identity, public_key, signature),
      ed25519_tampered: Min0CoreForth::Authentication.ed25519_verify(tampered, public_key, signature),
      ed25519_wrong_key: Min0CoreForth::Authentication.ed25519_verify(identity, wrong_public_key, signature)
    },
    device_compromise: {
      hmac_verifier_can_forge: Min0CoreForth::Authentication.hmac_verify(tampered, HMAC_TEST_KEY, forged_tag),
      ed25519_verifier_can_forge: public_can_sign
    },
    timing: benchmark_auth(identity, hmac_tag, public_key, signature)
  }
end

puts JSON.generate(run_auth_comparison_demo) if $PROGRAM_NAME == __FILE__
