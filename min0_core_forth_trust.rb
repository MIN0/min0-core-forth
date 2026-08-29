# frozen_string_literal: true

require "digest"
require "json"
require_relative "min0_core_forth_install"

module Min0CoreForth
  TRUST_BUNDLE_FORMAT = "min0-core-forth-trust-bundle"
  TRUST_BUNDLE_VERSION = 1
  TRUST_BUNDLE_DOMAIN = "MIN0-CORE-FORTH-TRUST-BUNDLE-R0\0".b
  TRUST_SLOT_DOMAIN = "MIN0-CORE-FORTH-TRUST-SLOT-R0\0".b
  TRUST_BUNDLE_INSTALL_STEPS = [
    "erase-inactive-trust-slot", "write-trust-bundle", "seal-trust-slot"
  ].freeze
  TRUST_KEY_ID_PATTERN = /\A[a-z0-9][a-z0-9._-]{0,63}\z/

  class TrustError < StandardError; end
  TrustSlot = Struct.new(:bundle, :checksum, keyword_init: true)

  module TrustBundle
    module_function

    def field(mapping, name)
      return nil unless mapping.respond_to?(:key?)
      return mapping[name] if mapping.key?(name)

      mapping[name.to_s]
    end

    def key_id(value, label = "key_id")
      unless value.is_a?(String) && value.match?(TRUST_KEY_ID_PATTERN)
        raise TrustError, "#{label} is malformed"
      end

      value
    end

    def role(value)
      unless [IMAGE_ROLE_NORMAL, IMAGE_ROLE_RECOVERY].include?(value)
        raise TrustError, "trust key role must be normal or recovery"
      end

      value
    end

    def public_key(value)
      unless value.is_a?(String) && value.match?(/\A[0-9a-f]{64}\z/)
        raise TrustError, "trust public key must be 32 bytes of lowercase hex"
      end

      [value].pack("H*")
    end

    def signature(value)
      unless value.is_a?(String) && value.match?(/\A[0-9a-f]{128}\z/)
        raise TrustError, "trust signature must be 64 bytes of lowercase hex"
      end

      [value].pack("H*")
    end

    def normalize_keys(keys)
      raise TrustError, "trust keys must be an Array" unless keys.is_a?(Array)

      seen = {}
      normalized = keys.map do |entry|
        raise TrustError, "trust key entry must be a Hash" unless entry.is_a?(Hash)
        unless entry.keys.map(&:to_s).sort == %w[key_id public_key_hex role status]
          raise TrustError, "trust key entry fields are malformed"
        end
        normalized_key_id = key_id(field(entry, :key_id))
        raise TrustError, "duplicate trust key_id" if seen[normalized_key_id]

        seen[normalized_key_id] = true
        normalized_role = role(field(entry, :role))
        normalized_public = public_key(field(entry, :public_key_hex))
        status = field(entry, :status)
        unless %w[active revoked].include?(status)
          raise TrustError, "trust key status must be active or revoked"
        end
        {
          key_id: normalized_key_id,
          role: normalized_role,
          public_key_hex: normalized_public.unpack1("H*"),
          status: status
        }
      end
      normalized.sort_by { |entry| entry[:key_id] }
    end

    def payload(bundle)
      keys = normalize_keys(field(bundle, :keys))
      rows = keys.map do |entry|
        [entry[:key_id], entry[:role], entry[:public_key_hex], entry[:status]]
      end
      JSON.generate(
        [
          field(bundle, :format), field(bundle, :version), field(bundle, :epoch),
          field(bundle, :root_key_id), rows
        ]
      )
    end

    def message(bundle)
      TRUST_BUNDLE_DOMAIN + Digest::SHA256.digest(payload(bundle))
    end

    def build(epoch, keys, root_key_id:, root_private_key:)
      normalized_epoch = Generation.validate(epoch, "trust epoch")
      normalized_root_id = key_id(root_key_id, "root_key_id")
      bundle = {
        format: TRUST_BUNDLE_FORMAT,
        version: TRUST_BUNDLE_VERSION,
        epoch: normalized_epoch,
        root_key_id: normalized_root_id,
        keys: normalize_keys(keys),
        signature: { scheme: AUTHENTICATION_ED25519 }
      }
      begin
        signed = root_private_key.sign(nil, message(bundle))
      rescue AuthenticationError, OpenSSL::PKey::PKeyError, TypeError, ArgumentError, NoMethodError => e
        raise TrustError, "invalid trust root private key: #{e.message}"
      end
      bundle[:signature][:signature_hex] = signed.unpack1("H*")
      bundle
    end

    def validate(bundle, pinned_root_keys, minimum_epoch: 0)
      raise TrustError, "trust bundle must be a Hash" unless bundle.is_a?(Hash)
      unless field(bundle, :format) == TRUST_BUNDLE_FORMAT
        raise TrustError, "unsupported trust bundle format"
      end
      unless field(bundle, :version) == TRUST_BUNDLE_VERSION
        raise TrustError, "unsupported trust bundle version"
      end
      epoch = Generation.validate(field(bundle, :epoch), "trust epoch")
      minimum = Generation.validate(minimum_epoch, "minimum trust epoch")
      raise TrustError, "trust epoch #{epoch} is below minimum #{minimum}" if epoch < minimum

      root_key_id = key_id(field(bundle, :root_key_id), "root_key_id")
      keys = normalize_keys(field(bundle, :keys))
      signature_block = field(bundle, :signature)
      unless signature_block.is_a?(Hash) &&
             signature_block.keys.map(&:to_s).sort == %w[scheme signature_hex]
        raise TrustError, "trust signature block is malformed"
      end
      unless field(signature_block, :scheme) == AUTHENTICATION_ED25519
        raise TrustError, "unsupported trust signature scheme"
      end
      signed = signature(field(signature_block, :signature_hex))
      unless pinned_root_keys.is_a?(Hash) && pinned_root_keys.key?(root_key_id)
        raise TrustError, "trust root key is not pinned"
      end
      root_public = pinned_root_keys.fetch(root_key_id)
      unless root_public.is_a?(String) && root_public.bytesize == 32
        raise TrustError, "pinned root public key must be 32 bytes"
      end
      root = Authentication.ed25519_public_from_bytes(root_public)
      unless !root.nil? && root.verify(nil, signed, message(bundle))
        raise TrustError, "trust bundle root signature is invalid"
      end
      { epoch: epoch, root_key_id: root_key_id, keys: keys }
    rescue OpenSSL::PKey::PKeyError
      raise TrustError, "trust bundle root signature is invalid"
    end

    def active_keys(validated_bundle, required_role)
      normalized_role = role(required_role)
      validated_bundle[:keys].filter_map do |entry|
        next unless entry[:role] == normalized_role && entry[:status] == "active"

        [entry[:key_id], [entry[:public_key_hex]].pack("H*")]
      end.to_h
    end

    def validate_image(components, envelope, bundle, pinned_root_keys,
                       role:, minimum_generation:, minimum_trust_epoch:)
      validated_bundle = validate(
        bundle, pinned_root_keys, minimum_epoch: minimum_trust_epoch
      )
      ImageEnvelope.validate(
        components,
        envelope,
        require_authentication: true,
        minimum_generation: minimum_generation,
        trusted_public_keys: active_keys(validated_bundle, role),
        required_image_role: role
      )
    end

    def slot_checksum(bundle)
      signature_block = field(bundle, :signature)
      signed = signature(field(signature_block, :signature_hex))
      Digest::SHA256.hexdigest(
        TRUST_SLOT_DOMAIN + Digest::SHA256.digest(payload(bundle)) + signed
      )
    end
  end

  class TrustBundleStore
    attr_reader :slots, :minimum_epoch

    def initialize(initial_bundle, pinned_root_keys)
      @pinned_root_keys = pinned_root_keys
      validated = TrustBundle.validate(initial_bundle, root_keys)
      initial_copy = Marshal.load(Marshal.dump(initial_bundle))
      @slots = [
        TrustSlot.new(bundle: initial_copy, checksum: TrustBundle.slot_checksum(initial_copy)),
        TrustSlot.new
      ]
      @minimum_epoch = TrustedGenerationJournal.new(validated[:epoch])
    end

    def valid_slots
      minimum = @minimum_epoch.minimum_accepted
      @slots.each_with_index.filter_map do |slot, index|
        next if slot.bundle.nil?

        begin
          next unless slot.checksum == TrustBundle.slot_checksum(slot.bundle)

          validated = TrustBundle.validate(
            slot.bundle, root_keys, minimum_epoch: minimum
          )
        rescue TrustError, KeyError, TypeError
          next
        end
        [index, validated]
      end
    end

    def current
      valid = valid_slots
      raise TrustError, "no valid trust bundle satisfies minimum epoch" if valid.empty?

      index, validated = valid.max_by { |_slot_index, candidate| candidate[:epoch] }
      [index, validated, @slots[index].bundle]
    end

    def power_cut(fail_after)
      lambda do |step|
        raise SimulatedPowerLoss, step if step == fail_after
      end
    end

    def install(bundle, fail_after: nil)
      after_step = power_cut(fail_after)
      current_index, current_validated, = current
      candidate = TrustBundle.validate(
        bundle,
        root_keys,
        minimum_epoch: @minimum_epoch.minimum_accepted
      )
      unless candidate[:epoch] > current_validated[:epoch]
        raise TrustError, "new trust bundle epoch must increase"
      end
      target = 1 - current_index
      @slots[target] = TrustSlot.new
      after_step.call(TRUST_BUNDLE_INSTALL_STEPS[0])
      bundle_copy = Marshal.load(Marshal.dump(bundle))
      @slots[target].bundle = bundle_copy
      after_step.call(TRUST_BUNDLE_INSTALL_STEPS[1])
      @slots[target].checksum = TrustBundle.slot_checksum(bundle_copy)
      after_step.call(TRUST_BUNDLE_INSTALL_STEPS[2])
      target
    end

    def commit_current(fail_after: nil)
      _index, validated, = current
      @minimum_epoch.commit(validated[:epoch], power_cut(fail_after))
    end

    def root_keys
      keys = @pinned_root_keys.respond_to?(:call) ? @pinned_root_keys.call : @pinned_root_keys
      raise TrustError, "trust root key provider did not return a Hash" unless keys.is_a?(Hash)

      keys
    end
  end
end
