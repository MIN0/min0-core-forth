# frozen_string_literal: true

require "digest"
require_relative "min0_core_forth_generation"

module Min0CoreForth
  TRUSTED_RECORD_DOMAIN = "MIN0-CORE-FORTH-TRUSTED-GENERATION-R0\0".b
  SLOT_MARKER_DOMAIN = "MIN0-CORE-FORTH-SLOT-COMPLETE-R0\0".b
  INSTALL_STEPS = [
    "erase-inactive-slot", "write-code", "write-dictionary", "write-data",
    "write-envelope", "verify-staged-image", "write-complete-marker-body",
    "seal-complete-marker"
  ].freeze
  TRUST_COMMIT_STEPS = [
    "erase-next-trusted-record", "write-next-trusted-record", "seal-next-trusted-record"
  ].freeze

  class InstallError < StandardError; end
  class BootError < InstallError; end
  class SimulatedPowerLoss < InstallError
    attr_reader :step

    def initialize(step)
      @step = step
      super("simulated power loss after #{step}")
    end
  end

  TrustedRecord = Struct.new(:sequence, :generation, :checksum, keyword_init: true)
  CompleteMarker = Struct.new(:sequence, :identity, :checksum, keyword_init: true)
  ImageSlot = Struct.new(:components, :envelope, :marker, keyword_init: true) do
    def initialize(components: {}, envelope: nil, marker: nil)
      super
    end
  end

  def self.trusted_record_checksum(sequence, generation)
    Digest::SHA256.hexdigest(TRUSTED_RECORD_DOMAIN + "#{sequence}:#{generation}")
  end

  def self.slot_marker_checksum(slot_name, sequence, identity)
    Digest::SHA256.hexdigest(SLOT_MARKER_DOMAIN + "#{slot_name}:#{sequence}:#{identity}")
  end

  class TrustedGenerationJournal
    attr_reader :records

    def initialize(generation)
      normalized = Generation.validate(generation, "trusted generation")
      @records = [
        TrustedRecord.new(
          sequence: 1,
          generation: normalized,
          checksum: Min0CoreForth.trusted_record_checksum(1, normalized)
        ),
        nil
      ]
    end

    def valid_records
      @records.each_with_index.filter_map do |record, index|
        next if record.nil?

        begin
          generation = Generation.validate(record.generation)
        rescue GenerationError
          next
        end
        next unless record.sequence.is_a?(Integer) && record.sequence.positive?
        next unless record.checksum == Min0CoreForth.trusted_record_checksum(record.sequence, generation)

        [index, record]
      end
    end

    def current
      valid = valid_records
      raise BootError, "no valid trusted-generation record" if valid.empty?

      index, record = valid.max_by { |_record_index, candidate| candidate.sequence }
      [index, record.sequence, record.generation]
    end

    def minimum_accepted
      current[2]
    end

    def commit(generation, after_step = nil)
      candidate = Generation.validate(generation)
      current_index, sequence, current_generation = current
      if candidate < current_generation
        raise GenerationError,
              "generation #{candidate} is below trusted minimum #{current_generation}"
      end
      return current_generation if candidate == current_generation

      target_index = 1 - current_index
      @records[target_index] = nil
      after_step&.call(TRUST_COMMIT_STEPS[0])
      next_sequence = sequence + 1
      @records[target_index] = TrustedRecord.new(
        sequence: next_sequence, generation: candidate
      )
      after_step&.call(TRUST_COMMIT_STEPS[1])
      @records[target_index].checksum = Min0CoreForth.trusted_record_checksum(
        next_sequence, candidate
      )
      after_step&.call(TRUST_COMMIT_STEPS[2])
      minimum_accepted
    end
  end

  class PersistentABStore
    attr_reader :slots, :trusted

    def initialize(initial_components, initial_envelope, trusted_generation)
      @slots = { "A" => ImageSlot.new, "B" => ImageSlot.new }
      @trusted = TrustedGenerationJournal.new(trusted_generation)
      write_initial("A", initial_components, initial_envelope)
    end

    def fetch_component(components, name)
      return components[name] if components.key?(name)

      components.fetch(name.to_sym)
    end

    def write_initial(slot_name, components, envelope)
      identity = envelope[:identity_sha256] || envelope["identity_sha256"]
      raise InstallError, "initial envelope identity is malformed" unless identity.is_a?(String)

      @slots[slot_name] = ImageSlot.new(
        components: %w[code dictionary data].to_h do |name|
          [name, fetch_component(components, name).dup.b]
        end,
        envelope: Marshal.load(Marshal.dump(envelope)),
        marker: CompleteMarker.new(
          sequence: 1,
          identity: identity,
          checksum: Min0CoreForth.slot_marker_checksum(slot_name, 1, identity)
        )
      )
    end
  end

  class TransactionalInstaller
    attr_reader :store

    def initialize(store, trusted_public_keys, required_image_role: IMAGE_ROLE_NORMAL,
                   runtime_profile: EXECUTION_PROFILE_SAFE_RUNTIME)
      @store = store
      @trusted_public_keys = trusted_public_keys
      @required_image_role = required_image_role
      @runtime_profile = runtime_profile
    end

    def power_cut(fail_after)
      lambda do |step|
        raise SimulatedPowerLoss, step if fail_after == step
      end
    end

    def envelope_field(envelope, name)
      return envelope[name] if envelope.key?(name)

      envelope[name.to_sym]
    end

    def component_field(components, name)
      return components[name] if components.key?(name)

      components[name.to_sym]
    end

    def marker_valid?(slot_name, slot)
      marker = slot.marker
      envelope = slot.envelope
      return false if marker.nil? || !envelope.is_a?(Hash)

      identity = envelope_field(envelope, "identity_sha256")
      marker.sequence.is_a?(Integer) && marker.sequence.positive? &&
        identity.is_a?(String) && identity.match?(/\A[0-9a-f]{64}\z/) &&
        marker.identity == identity &&
        marker.checksum == Min0CoreForth.slot_marker_checksum(
          slot_name, marker.sequence, marker.identity
        )
    end

    def select_boot
      minimum = @store.trusted.minimum_accepted
      candidates = @store.slots.filter_map do |slot_name, slot|
        next unless marker_valid?(slot_name, slot)

        begin
          validated = ImageEnvelope.validate(
            slot.components,
            slot.envelope,
            require_authentication: true,
            minimum_generation: minimum,
            trusted_public_keys: @trusted_public_keys,
            required_image_role: @required_image_role,
            runtime_profile: @runtime_profile
          )
        rescue ImageError
          next
        end
        [
          validated[:generation], slot.marker.sequence, slot_name,
          envelope_field(slot.envelope, "identity_sha256")
        ]
      end
      raise BootError, "no complete authenticated slot satisfies policy" if candidates.empty?

      generation, sequence, slot_name, identity = candidates.max
      {
        slot: slot_name,
        generation: generation,
        sequence: sequence,
        identity: identity,
        trusted_generation: minimum
      }
    end

    def install(components, envelope, fail_after: nil)
      after_step = power_cut(fail_after)
      ImageEnvelope.validate(
        components,
        envelope,
        require_authentication: true,
        minimum_generation: @store.trusted.minimum_accepted,
        trusted_public_keys: @trusted_public_keys,
        required_image_role: @required_image_role,
        runtime_profile: @runtime_profile
      )
      active = select_boot[:slot]
      inactive = active == "A" ? "B" : "A"
      write_candidate(inactive, components, envelope, after_step)
      inactive
    end

    def repair_install(components, envelope, target_slot:, fail_after: nil)
      unless @store.slots.key?(target_slot)
        raise InstallError, "repair target slot must be A or B"
      end
      ImageEnvelope.validate(
        components,
        envelope,
        require_authentication: true,
        minimum_generation: @store.trusted.minimum_accepted,
        trusted_public_keys: @trusted_public_keys,
        required_image_role: @required_image_role,
        runtime_profile: @runtime_profile
      )
      write_candidate(target_slot, components, envelope, power_cut(fail_after))
      target_slot
    end

    def write_candidate(target_slot, components, envelope, after_step)
      slot = ImageSlot.new
      @store.slots[target_slot] = slot
      after_step.call(INSTALL_STEPS[0])
      %w[code dictionary data].each_with_index do |section, index|
        image = component_field(components, section)
        raise InstallError, "component #{section} must be a String" unless image.is_a?(String)

        slot.components[section] = image.dup.b
        after_step.call(INSTALL_STEPS[index + 1])
      end
      slot.envelope = Marshal.load(Marshal.dump(envelope))
      after_step.call(INSTALL_STEPS[4])
      ImageEnvelope.validate(
        slot.components,
        slot.envelope,
        require_authentication: true,
        minimum_generation: @store.trusted.minimum_accepted,
        trusted_public_keys: @trusted_public_keys,
        required_image_role: @required_image_role,
        runtime_profile: @runtime_profile
      )
      after_step.call(INSTALL_STEPS[5])
      sequences = @store.slots.filter_map do |name, candidate|
        candidate.marker.sequence if marker_valid?(name, candidate)
      end
      sequence = (sequences.max || 0) + 1
      identity = envelope_field(slot.envelope, "identity_sha256")
      slot.marker = CompleteMarker.new(sequence: sequence, identity: identity)
      after_step.call(INSTALL_STEPS[6])
      slot.marker.checksum = Min0CoreForth.slot_marker_checksum(target_slot, sequence, identity)
      after_step.call(INSTALL_STEPS[7])
    end

    def report_boot_success(slot_name, fail_after: nil)
      selected = select_boot
      unless selected[:slot] == slot_name
        raise InstallError, "boot success does not describe the selected slot"
      end

      @store.trusted.commit(selected[:generation], power_cut(fail_after))
    end

    def report_boot_failure(slot_name)
      selected = select_boot
      unless selected[:slot] == slot_name
        raise InstallError, "boot failure does not describe the selected slot"
      end

      @store.slots[slot_name].marker = nil
    end
  end
end
