# frozen_string_literal: true

require "digest"
require "json"
require_relative "min0_core_forth_install"

module Min0CoreForth
  ROOT_POLICY_FORMAT = "min0-core-forth-root-policy"
  ROOT_POLICY_VERSION = 1
  ROOT_POLICY_DOMAIN = "MIN0-CORE-FORTH-ROOT-POLICY-R0\0".b
  ROOT_STATE_DOMAIN = "MIN0-CORE-FORTH-ROOT-STATE-R0\0".b
  ROOT_POLICY_INSTALL_STEPS = [
    "erase-inactive-root-state", "write-root-policy-chain", "seal-root-state"
  ].freeze
  ROOT_KEY_ID_PATTERN = /\A[a-z0-9][a-z0-9._-]{0,63}\z/

  class RootPolicyError < StandardError; end
  RootStateSlot = Struct.new(:chain, :checksum, keyword_init: true)

  module RootPolicy
    module_function

    def field(mapping, name)
      return nil unless mapping.respond_to?(:key?)
      return mapping[name] if mapping.key?(name)

      mapping[name.to_s]
    end

    def key_id(value)
      unless value.is_a?(String) && value.match?(ROOT_KEY_ID_PATTERN)
        raise RootPolicyError, "root key_id is malformed"
      end

      value
    end

    def public_key(value)
      unless value.is_a?(String) && value.match?(/\A[0-9a-f]{64}\z/)
        raise RootPolicyError, "root public key must be 32 bytes of lowercase hex"
      end

      [value].pack("H*")
    end

    def signature(value)
      unless value.is_a?(String) && value.match?(/\A[0-9a-f]{128}\z/)
        raise RootPolicyError, "root policy signature must be 64 bytes of lowercase hex"
      end

      [value].pack("H*")
    end

    def normalize_roots(roots)
      raise RootPolicyError, "root entries must be an Array" unless roots.is_a?(Array)

      seen = {}
      normalized = roots.map do |entry|
        raise RootPolicyError, "root entry must be a Hash" unless entry.is_a?(Hash)
        unless entry.keys.map(&:to_s).sort == %w[key_id public_key_hex status]
          raise RootPolicyError, "root entry fields are malformed"
        end
        normalized_id = key_id(field(entry, :key_id))
        raise RootPolicyError, "duplicate root key_id" if seen[normalized_id]

        seen[normalized_id] = true
        normalized_public = public_key(field(entry, :public_key_hex))
        status = field(entry, :status)
        unless %w[active retired].include?(status)
          raise RootPolicyError, "root status must be active or retired"
        end
        {
          key_id: normalized_id,
          public_key_hex: normalized_public.unpack1("H*"),
          status: status
        }
      end
      normalized.sort_by! { |entry| entry[:key_id] }
      unless normalized.any? { |entry| entry[:status] == "active" }
        raise RootPolicyError, "root policy must retain an active root"
      end
      normalized
    end

    def normalize_signatures(signatures)
      unless signatures.is_a?(Array)
        raise RootPolicyError, "root signatures must be an Array"
      end

      seen = {}
      signatures.map do |entry|
        raise RootPolicyError, "root signature entry must be a Hash" unless entry.is_a?(Hash)
        unless entry.keys.map(&:to_s).sort == %w[key_id signature_hex]
          raise RootPolicyError, "root signature entry fields are malformed"
        end
        normalized_id = key_id(field(entry, :key_id))
        raise RootPolicyError, "duplicate root signature key_id" if seen[normalized_id]

        seen[normalized_id] = true
        {
          key_id: normalized_id,
          signature_hex: signature(field(entry, :signature_hex)).unpack1("H*")
        }
      end.sort_by { |entry| entry[:key_id] }
    end

    def payload(policy)
      rows = normalize_roots(field(policy, :roots)).map do |entry|
        [entry[:key_id], entry[:public_key_hex], entry[:status]]
      end
      JSON.generate(
        [
          field(policy, :format), field(policy, :version), field(policy, :epoch),
          field(policy, :previous_policy_sha256), rows
        ]
      )
    end

    def digest(policy)
      Digest::SHA256.hexdigest(payload(policy))
    end

    def message(policy)
      ROOT_POLICY_DOMAIN + [digest(policy)].pack("H*")
    end

    def root_map(roots, status = nil)
      roots.filter_map do |entry|
        next unless status.nil? || entry[:status] == status

        [entry[:key_id], [entry[:public_key_hex]].pack("H*")]
      end.to_h
    end

    def build(epoch, roots, signer_private_keys, previous_policy: nil)
      normalized_epoch = Generation.validate(epoch, "root policy epoch")
      policy = {
        format: ROOT_POLICY_FORMAT,
        version: ROOT_POLICY_VERSION,
        epoch: normalized_epoch,
        previous_policy_sha256: previous_policy.nil? ? nil : digest(previous_policy),
        roots: normalize_roots(roots),
        signatures: []
      }
      policy[:signatures] = signer_private_keys.sort_by { |id, _key| id }.map do |id, key|
        normalized_id = key_id(id)
        begin
          signed = key.sign(nil, message(policy))
        rescue OpenSSL::PKey::PKeyError, TypeError, ArgumentError, NoMethodError => e
          raise RootPolicyError, "invalid root signer private key: #{e.message}"
        end
        { key_id: normalized_id, signature_hex: signed.unpack1("H*") }
      end
      policy
    end

    def validate_shape(policy)
      raise RootPolicyError, "root policy must be a Hash" unless policy.is_a?(Hash)
      unless field(policy, :format) == ROOT_POLICY_FORMAT
        raise RootPolicyError, "unsupported root policy format"
      end
      unless field(policy, :version) == ROOT_POLICY_VERSION
        raise RootPolicyError, "unsupported root policy version"
      end
      epoch = Generation.validate(field(policy, :epoch), "root policy epoch")
      previous = field(policy, :previous_policy_sha256)
      unless previous.nil? || (previous.is_a?(String) && previous.match?(/\A[0-9a-f]{64}\z/))
        raise RootPolicyError, "previous root policy digest is malformed"
      end
      {
        epoch: epoch,
        previous_policy_sha256: previous,
        roots: normalize_roots(field(policy, :roots)),
        signatures: normalize_signatures(field(policy, :signatures)),
        digest: digest(policy)
      }
    end

    def validate_chain(policies, pinned_bootstrap_roots, minimum_epoch: 0)
      unless policies.is_a?(Array) && !policies.empty?
        raise RootPolicyError, "root policy chain must be a nonempty Array"
      end
      raise RootPolicyError, "pinned roots must be a Hash" unless pinned_bootstrap_roots.is_a?(Hash)

      pinned = pinned_bootstrap_roots.to_h do |id, key|
        normalized_id = key_id(id)
        unless key.is_a?(String) && key.bytesize == 32
          raise RootPolicyError, "pinned bootstrap root must be 32 bytes"
        end
        [normalized_id, key.b]
      end
      previous = nil
      policies.each_with_index do |raw_policy, index|
        current = validate_shape(raw_policy)
        current_all = root_map(current[:roots])
        current_active = root_map(current[:roots], "active")
        if index.zero?
          unless current[:previous_policy_sha256].nil?
            raise RootPolicyError, "bootstrap policy must not have a predecessor"
          end
          unless current_active == pinned && current[:roots].length == pinned.length
            raise RootPolicyError, "bootstrap policy disagrees with pinned roots"
          end
          required_signers = pinned.keys
          verification_keys = pinned
        else
          unless current[:epoch] == previous[:epoch] + 1
            raise RootPolicyError, "root policy epoch must increase by exactly one"
          end
          unless current[:previous_policy_sha256] == previous[:digest]
            raise RootPolicyError, "root policy chain digest mismatch"
          end
          previous_all = root_map(previous[:roots])
          previous_active = root_map(previous[:roots], "active")
          previous_all.each do |id, old_key|
            unless current_all[id] == old_key
              raise RootPolicyError, "root key removal or replacement is forbidden"
            end
            old_status = previous[:roots].find { |entry| entry[:key_id] == id }[:status]
            new_status = current[:roots].find { |entry| entry[:key_id] == id }[:status]
            if old_status == "retired" && new_status != "retired"
              raise RootPolicyError, "retired root cannot be reactivated"
            end
          end
          required_signers = (previous_active.keys | current_active.keys)
          verification_keys = previous_all.merge(current_all)
        end
        signatures = current[:signatures].to_h do |entry|
          [entry[:key_id], entry[:signature_hex]]
        end
        unless signatures.keys.sort == required_signers.sort
          raise RootPolicyError, "root policy signatures do not match required signers"
        end
        required_signers.sort.each do |id|
          key = Authentication.ed25519_public_from_bytes(verification_keys.fetch(id))
          signed = [signatures.fetch(id)].pack("H*")
          unless !key.nil? && key.verify(nil, signed, message(raw_policy))
            raise RootPolicyError, "root policy signature is invalid"
          end
        rescue KeyError, OpenSSL::PKey::PKeyError
          raise RootPolicyError, "root policy signature is invalid"
        end
        previous = current
      end
      minimum = Generation.validate(minimum_epoch, "minimum root policy epoch")
      if previous[:epoch] < minimum
        raise RootPolicyError,
              "root policy epoch #{previous[:epoch]} is below minimum #{minimum}"
      end
      previous
    end

    def active_keys(validated_policy)
      root_map(validated_policy[:roots], "active")
    end

    def chain_checksum(chain)
      material = ROOT_STATE_DOMAIN.dup
      chain.each do |policy|
        material << [digest(policy)].pack("H*")
        normalize_signatures(field(policy, :signatures)).each do |signed|
          material << signed[:key_id].b
          material << [signed[:signature_hex]].pack("H*")
        end
      end
      Digest::SHA256.hexdigest(material)
    end
  end

  class RootPolicyStore
    attr_reader :slots, :minimum_epoch, :pinned_bootstrap_roots

    def initialize(bootstrap_policy, pinned_bootstrap_roots)
      bootstrap = Marshal.load(Marshal.dump(bootstrap_policy))
      validated = RootPolicy.validate_chain([bootstrap], pinned_bootstrap_roots)
      @pinned_bootstrap_roots = pinned_bootstrap_roots
      @slots = [
        RootStateSlot.new(chain: [bootstrap], checksum: RootPolicy.chain_checksum([bootstrap])),
        RootStateSlot.new
      ]
      @minimum_epoch = TrustedGenerationJournal.new(validated[:epoch])
    end

    def valid_slots
      @slots.each_with_index.filter_map do |slot, index|
        next if slot.chain.nil?

        begin
          next unless slot.checksum == RootPolicy.chain_checksum(slot.chain)

          validated = RootPolicy.validate_chain(
            slot.chain,
            @pinned_bootstrap_roots,
            minimum_epoch: @minimum_epoch.minimum_accepted
          )
        rescue RootPolicyError, KeyError, TypeError
          next
        end
        [index, validated]
      end
    end

    def current
      valid = valid_slots
      if valid.empty?
        raise RootPolicyError, "no valid root policy chain satisfies minimum epoch"
      end

      index, validated = valid.max_by { |_slot_index, candidate| candidate[:epoch] }
      [index, validated, @slots[index].chain]
    end

    def power_cut(fail_after)
      lambda do |step|
        raise SimulatedPowerLoss, step if step == fail_after
      end
    end

    def install(policy, fail_after: nil)
      after_step = power_cut(fail_after)
      current_index, _validated, chain = current
      candidate_chain = Marshal.load(Marshal.dump(chain))
      candidate_chain << Marshal.load(Marshal.dump(policy))
      RootPolicy.validate_chain(
        candidate_chain,
        @pinned_bootstrap_roots,
        minimum_epoch: @minimum_epoch.minimum_accepted
      )
      target = 1 - current_index
      @slots[target] = RootStateSlot.new
      after_step.call(ROOT_POLICY_INSTALL_STEPS[0])
      @slots[target].chain = candidate_chain
      after_step.call(ROOT_POLICY_INSTALL_STEPS[1])
      @slots[target].checksum = RootPolicy.chain_checksum(candidate_chain)
      after_step.call(ROOT_POLICY_INSTALL_STEPS[2])
      target
    end

    def commit_current(fail_after: nil)
      _index, validated, = current
      @minimum_epoch.commit(validated[:epoch], power_cut(fail_after))
    end
  end
end
