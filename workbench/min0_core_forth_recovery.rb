# frozen_string_literal: true

require_relative "min0_core_forth_install"

module Min0CoreForth
  class ProtectedRecoveryStore
    attr_reader :components, :envelope, :trusted

    def initialize(components, envelope, trusted_generation)
      @components = %w[code dictionary data].to_h do |name|
        image = components.key?(name) ? components[name] : components.fetch(name.to_sym)
        [name, image.dup.b]
      end
      @envelope = Marshal.load(Marshal.dump(envelope))
      @trusted = TrustedGenerationJournal.new(trusted_generation)
    end
  end

  class RecoveryBootManager
    attr_reader :normal_installer, :recovery_store

    def initialize(normal_installer, recovery_store, recovery_public_keys)
      @normal_installer = normal_installer
      @recovery_store = recovery_store
      @recovery_public_keys = recovery_public_keys
    end

    def select_boot
      normal = begin
        @normal_installer.select_boot
      rescue BootError
        nil
      end
      return { mode: "normal", **normal } unless normal.nil?

      begin
        validated = ImageEnvelope.validate(
          @recovery_store.components,
          @recovery_store.envelope,
          require_authentication: true,
          minimum_generation: @recovery_store.trusted.minimum_accepted,
          trusted_public_keys: @recovery_public_keys,
          required_image_role: IMAGE_ROLE_RECOVERY
        )
      rescue ImageError => e
        raise BootError, "normal and recovery boot both failed: #{e.message}"
      end
      {
        mode: "recovery",
        slot: "R",
        generation: validated[:generation],
        identity: @recovery_store.envelope[:identity_sha256],
        trusted_generation: @recovery_store.trusted.minimum_accepted
      }
    end

    def repair_normal(components, envelope, target_slot:, fail_after: nil)
      unless select_boot[:mode] == "recovery"
        raise InstallError, "normal repair is allowed only from recovery mode"
      end

      @normal_installer.repair_install(
        components,
        envelope,
        target_slot: target_slot,
        fail_after: fail_after
      )
    end
  end
end
