# frozen_string_literal: true

require "json"
require_relative "auth_comparison_demo"
require_relative "min0_core_forth_generation"

def rejected_by?(*errors)
  yield
  false
rescue *errors
  true
end

def run_anti_rollback_demo(implementation = "ruby")
  images = {}
  private_key = Min0CoreForth::Authentication.ed25519_private_from_seed(ED25519_TEST_SEED)
  public_key = Min0CoreForth::Authentication.ed25519_public_bytes(private_key)
  [6, 7, 8].each do |generation|
    components, envelope = build_source_image(generation)
    signature = Min0CoreForth::Authentication.ed25519_sign(
      envelope[:identity_sha256], private_key
    )
    images[generation] = [components, envelope, signature]
  end

  trusted = Min0CoreForth::TrustedGeneration.new(7)
  old_components, old_envelope, old_signature = images.fetch(6)
  old_signature_valid = Min0CoreForth::Authentication.ed25519_verify(
    old_envelope[:identity_sha256], public_key, old_signature
  )
  old_rejected = rejected_by?(Min0CoreForth::ImageError) do
    Min0CoreForth::ImageEnvelope.validate(
      old_components,
      old_envelope,
      minimum_generation: trusted.minimum_accepted
    )
  end

  current_components, current_envelope, current_signature = images.fetch(7)
  current_signature_valid = Min0CoreForth::Authentication.ed25519_verify(
    current_envelope[:identity_sha256], public_key, current_signature
  )
  Min0CoreForth::ImageEnvelope.validate(
    current_components,
    current_envelope,
    minimum_generation: trusted.minimum_accepted
  )

  next_components, next_envelope, next_signature = images.fetch(8)
  next_signature_valid = Min0CoreForth::Authentication.ed25519_verify(
    next_envelope[:identity_sha256], public_key, next_signature
  )
  Min0CoreForth::ImageEnvelope.validate(
    next_components,
    next_envelope,
    minimum_generation: trusted.minimum_accepted
  )
  trusted.authorize(next_envelope[:generation])
  before_failed_install = trusted.minimum_accepted
  # An install failure deliberately has no commit call.
  after_failed_install = trusted.minimum_accepted
  after_successful_install = trusted.commit(next_envelope[:generation])
  current_rejected_after_commit = rejected_by?(Min0CoreForth::ImageError) do
    Min0CoreForth::ImageEnvelope.validate(
      current_components,
      current_envelope,
      minimum_generation: trusted.minimum_accepted
    )
  end

  _linked, linked_envelope = Min0CoreForth::ImageEnvelope.link(
    next_components,
    next_envelope,
    TARGET_BASES,
    TARGET_LIMITS,
    minimum_generation: 7
  )

  components, template = build_source_image(0)
  negative_rejected = rejected_by?(Min0CoreForth::ImageError) do
    Min0CoreForth::ImageEnvelope.build(
      components,
      SOURCE_BASES,
      SOURCE_LIMITS,
      template[:allocator],
      template[:manifest],
      generation: -1
    )
  end
  overflow_rejected = rejected_by?(Min0CoreForth::ImageError) do
    Min0CoreForth::ImageEnvelope.build(
      components,
      SOURCE_BASES,
      SOURCE_LIMITS,
      template[:allocator],
      template[:manifest],
      generation: Min0CoreForth::MAX_GENERATION + 1
    )
  end
  lower_commit_rejected = rejected_by?(Min0CoreForth::GenerationError) do
    trusted.commit(7)
  end

  {
    implementation: implementation,
    format_version: next_envelope[:version],
    identities: [6, 7, 8].to_h do |generation|
      [generation.to_s, images.fetch(generation)[1][:identity_sha256]]
    end,
    signatures: [6, 7, 8].to_h do |generation|
      [generation.to_s, images.fetch(generation)[2].unpack1("H*")]
    end,
    signature_valid: {
      old: old_signature_valid,
      current: current_signature_valid,
      next: next_signature_valid
    },
    old_signed_image_rejected: old_rejected,
    trusted_state: {
      before_failed_install: before_failed_install,
      after_failed_install: after_failed_install,
      after_successful_install: after_successful_install
    },
    current_rejected_after_commit: current_rejected_after_commit,
    linked_generation: linked_envelope[:generation],
    bounds: {
      negative_rejected: negative_rejected,
      overflow_rejected: overflow_rejected,
      lower_commit_rejected: lower_commit_rejected
    }
  }
end

puts JSON.generate(run_anti_rollback_demo) if $PROGRAM_NAME == __FILE__
