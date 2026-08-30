# frozen_string_literal: true

require "json"
require_relative "auth_comparison_demo"

SIGNED_IMAGE_KEY_ID = "fixture-ed25519-01"

def signed_from_template(components, template, key_id,
                         private_key: nil, image_role: Min0CoreForth::IMAGE_ROLE_NORMAL)
  private_key ||= Min0CoreForth::Authentication.ed25519_private_from_seed(ED25519_TEST_SEED)
  sections = %w[code dictionary data]
  bases = sections.to_h { |name| [name, template[:components][name][:base]] }
  limits = sections.to_h { |name| [name, template[:components][name][:limit]] }
  Min0CoreForth::ImageEnvelope.build_ed25519(
    components,
    bases,
    limits,
    template[:allocator],
    template[:manifest],
    generation: template[:generation],
    key_id: key_id,
    private_key: private_key,
    image_role: image_role
  )
end

def signed_image_rejected(name)
  yield
  raise "#{name} was accepted"
rescue Min0CoreForth::ImageError
  name
end

def run_signed_image_demo(implementation = "ruby")
  components, unsigned = build_source_image(7)
  signed = signed_from_template(components, unsigned, SIGNED_IMAGE_KEY_ID)
  private_key = Min0CoreForth::Authentication.ed25519_private_from_seed(ED25519_TEST_SEED)
  public_key = Min0CoreForth::Authentication.ed25519_public_bytes(private_key)
  wrong_public_key = Min0CoreForth::Authentication.ed25519_public_bytes(
    Min0CoreForth::Authentication.ed25519_private_from_seed(WRONG_ED25519_TEST_SEED)
  )
  trusted = { SIGNED_IMAGE_KEY_ID => public_key }
  validated = Min0CoreForth::ImageEnvelope.validate(
    components,
    signed,
    require_authentication: true,
    minimum_generation: 7,
    trusted_public_keys: trusted
  )

  corrupted = components.transform_values(&:dup)
  last = corrupted[:code].bytesize - 1
  corrupted[:code].setbyte(last, corrupted[:code].getbyte(last) ^ 1)

  signature_tamper = Marshal.load(Marshal.dump(signed))
  original = signature_tamper[:authentication][:signature_hex]
  signature_tamper[:authentication][:signature_hex] =
    (original[0] == "0" ? "1" : "0") + original[1..]
  malformed_signature = Marshal.load(Marshal.dump(signed))
  malformed_signature[:authentication][:signature_hex] = "00"
  key_id_tamper = Marshal.load(Marshal.dump(signed))
  key_id_tamper[:authentication][:key_id] = "attacker-key"
  unknown_scheme = Marshal.load(Marshal.dump(signed))
  unknown_scheme[:authentication][:scheme] = "unknown-signature"
  extra_authentication_field = Marshal.load(Marshal.dump(signed))
  extra_authentication_field[:authentication][:public_key_hex] = public_key.unpack1("H*")
  unknown_signed = signed_from_template(components, unsigned, "unknown-key-01")

  rejected = [
    signed_image_rejected("component-tamper") do
      Min0CoreForth::ImageEnvelope.validate(corrupted, signed, trusted_public_keys: trusted)
    end,
    signed_image_rejected("signature-tamper") do
      Min0CoreForth::ImageEnvelope.validate(components, signature_tamper, trusted_public_keys: trusted)
    end,
    signed_image_rejected("malformed-signature") do
      Min0CoreForth::ImageEnvelope.validate(components, malformed_signature, trusted_public_keys: trusted)
    end,
    signed_image_rejected("key-id-tamper") do
      Min0CoreForth::ImageEnvelope.validate(components, key_id_tamper, trusted_public_keys: trusted)
    end,
    signed_image_rejected("unknown-scheme") do
      Min0CoreForth::ImageEnvelope.validate(components, unknown_scheme, trusted_public_keys: trusted)
    end,
    signed_image_rejected("extra-authentication-field") do
      Min0CoreForth::ImageEnvelope.validate(
        components, extra_authentication_field, trusted_public_keys: trusted
      )
    end,
    signed_image_rejected("unknown-key") do
      Min0CoreForth::ImageEnvelope.validate(components, unknown_signed, trusted_public_keys: trusted)
    end,
    signed_image_rejected("wrong-public-key") do
      Min0CoreForth::ImageEnvelope.validate(
        components, signed, trusted_public_keys: { SIGNED_IMAGE_KEY_ID => wrong_public_key }
      )
    end,
    signed_image_rejected("missing-trust-store") do
      Min0CoreForth::ImageEnvelope.validate(components, signed)
    end,
    signed_image_rejected("unsigned-secure-mode") do
      Min0CoreForth::ImageEnvelope.validate(components, unsigned, require_authentication: true)
    end,
    signed_image_rejected("signed-rollback") do
      Min0CoreForth::ImageEnvelope.validate(
        components, signed, minimum_generation: 8, trusted_public_keys: trusted
      )
    end,
    signed_image_rejected("signed-relocation-without-resigning") do
      Min0CoreForth::ImageEnvelope.link(
        components, signed, TARGET_BASES, TARGET_LIMITS, trusted_public_keys: trusted
      )
    end
  ]

  linked, linked_unsigned = Min0CoreForth::ImageEnvelope.link(
    components, unsigned, TARGET_BASES, TARGET_LIMITS
  )
  linked_signed = signed_from_template(linked, linked_unsigned, SIGNED_IMAGE_KEY_ID)
  Min0CoreForth::ImageEnvelope.validate(
    linked,
    linked_signed,
    require_authentication: true,
    minimum_generation: 7,
    trusted_public_keys: trusted
  )

  {
    implementation: implementation,
    format_version: signed[:version],
    scheme: validated[:authentication][:scheme],
    image_role: validated[:image_role],
    key_id: signed[:authentication][:key_id],
    identity: signed[:identity_sha256],
    signature_hex: signed[:authentication][:signature_hex],
    generation: validated[:generation],
    rejected: rejected,
    target_signed: {
      identity: linked_signed[:identity_sha256],
      generation: linked_signed[:generation],
      valid: true
    }
  }
end

puts JSON.generate(run_signed_image_demo) if $PROGRAM_NAME == __FILE__
