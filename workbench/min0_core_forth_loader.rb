# frozen_string_literal: true

require_relative "min0_core_forth_persistent"
require_relative "min0_core_forth_root"
require_relative "min0_core_forth_trust"

module Min0CoreForth
  class LoaderError < StandardError; end
  class LoaderOrderError < LoaderError; end

  class Loader
    attr_reader :root_store, :trust_store, :normal_store, :recovery_store, :history

    def initialize(bootstrap_policy, pinned_bootstrap_roots, initial_trust_bundle,
                   normal_components, normal_envelope,
                   recovery_components, recovery_envelope,
                   runtime_profile: EXECUTION_PROFILE_SAFE_RUNTIME)
      @runtime_profile = runtime_profile
      @root_store = RootPolicyStore.new(bootstrap_policy, pinned_bootstrap_roots)
      @trust_store = TrustBundleStore.new(
        initial_trust_bundle, -> { active_root_keys }
      )
      normal_generation = Generation.validate(
        field(normal_envelope, :generation), "initial normal generation"
      )
      recovery_generation = Generation.validate(
        field(recovery_envelope, :generation), "initial recovery generation"
      )
      @normal_store = PersistentABStore.new(
        normal_components, normal_envelope, normal_generation
      )
      @recovery_store = PersistentABStore.new(
        recovery_components, recovery_envelope, recovery_generation
      )
      @history = []
      validate_current_images
      record("initialized")
    end

    def active_root_keys
      _slot, validated, = @root_store.current
      RootPolicy.active_keys(validated)
    end

    def current_trust
      _slot, validated, bundle = @trust_store.current
      [validated, bundle]
    end

    def image_keys(role)
      validated, = current_trust
      TrustBundle.active_keys(validated, role)
    end

    def store(role)
      return @normal_store if role == IMAGE_ROLE_NORMAL
      return @recovery_store if role == IMAGE_ROLE_RECOVERY

      raise LoaderOrderError, "loader image role must be normal or recovery"
    end

    def installer(role)
      TransactionalInstaller.new(
        store(role), image_keys(role), required_image_role: role,
        runtime_profile: @runtime_profile
      )
    end

    def selected_image(role)
      selected = installer(role).select_boot
      slot = store(role).slots.fetch(selected[:slot])
      raise LoaderError, "selected image slot has no envelope" if slot.envelope.nil?

      [selected, slot.envelope]
    end

    def validate_current_images(validated_trust = nil)
      validated_trust, = current_trust if validated_trust.nil?
      [IMAGE_ROLE_NORMAL, IMAGE_ROLE_RECOVERY].each do |role|
        selected, envelope = selected_image(role)
        slot = store(role).slots.fetch(selected[:slot])
        ImageEnvelope.validate(
          slot.components,
          envelope,
          require_authentication: true,
          minimum_generation: store(role).trusted.minimum_accepted,
          trusted_public_keys: TrustBundle.active_keys(validated_trust, role),
          required_image_role: role,
          runtime_profile: @runtime_profile
        )
      end
    end

    def pending_domains
      pending = []
      _slot, root, = @root_store.current
      if root[:epoch] > @root_store.minimum_epoch.minimum_accepted
        pending << "root"
      end
      trust, = current_trust
      if trust[:epoch] > @trust_store.minimum_epoch.minimum_accepted
        pending << "trust"
      end
      [IMAGE_ROLE_NORMAL, IMAGE_ROLE_RECOVERY].each do |role|
        selected = begin
          installer(role).select_boot
        rescue BootError
          raise unless role == IMAGE_ROLE_NORMAL

          nil
        end
        next if selected.nil?

        if selected[:generation] > store(role).trusted.minimum_accepted
          pending << role
        end
      end
      pending
    end

    def phase
      pending = pending_domains
      return "stable" if pending.empty?
      if pending.length != 1
        raise LoaderOrderError, "multiple uncommitted loader domains are visible"
      end

      "#{pending.first}-awaiting-commit"
    end

    def status
      _root_slot, root, = @root_store.current
      trust, = current_trust
      normal = begin
        installer(IMAGE_ROLE_NORMAL).select_boot
      rescue BootError
        nil
      end
      recovery = installer(IMAGE_ROLE_RECOVERY).select_boot
      boot = if normal.nil?
               { mode: "recovery", **recovery }
             else
               { mode: "normal", **normal }
             end
      {
        phase: phase,
        runtime_profile: @runtime_profile,
        root_epoch: root[:epoch],
        minimum_root_epoch: @root_store.minimum_epoch.minimum_accepted,
        trust_epoch: trust[:epoch],
        minimum_trust_epoch: @trust_store.minimum_epoch.minimum_accepted,
        normal_generation: normal&.fetch(:generation),
        minimum_normal_generation: @normal_store.trusted.minimum_accepted,
        recovery_generation: recovery[:generation],
        minimum_recovery_generation: @recovery_store.trusted.minimum_accepted,
        boot: boot
      }
    end

    def record(action)
      @history << { action: action, phase: phase }
    end

    def require_stable
      return if phase == "stable"

      raise LoaderOrderError, "finish or reject the visible transaction first"
    end

    def stage_root_package(raw, fail_after: nil)
      require_stable
      candidate_chain = PersistentPackage.decode_root_policy_chain(raw)
      _slot, _current, current_chain = @root_store.current
      unless candidate_chain.length == current_chain.length + 1
        raise LoaderOrderError, "root package must append exactly one policy"
      end
      current_chain.zip(candidate_chain[0...-1]).each do |saved, candidate|
        unless PersistentPackage.canonical_json(saved) == PersistentPackage.canonical_json(candidate)
          raise LoaderOrderError, "root package history does not match installed chain"
        end
      end
      validated_candidate = RootPolicy.validate_chain(
        candidate_chain,
        @root_store.pinned_bootstrap_roots,
        minimum_epoch: @root_store.minimum_epoch.minimum_accepted
      )
      _trust, current_bundle = current_trust
      TrustBundle.validate(
        current_bundle,
        RootPolicy.active_keys(validated_candidate),
        minimum_epoch: @trust_store.minimum_epoch.minimum_accepted
      )
      @root_store.install(candidate_chain[-1], fail_after: fail_after)
      record("stage-root")
      validated_candidate[:epoch]
    end

    def commit_root(fail_after: nil)
      unless phase == "root-awaiting-commit"
        raise LoaderOrderError, "no root policy is awaiting commit"
      end
      _slot, root, = @root_store.current
      _trust, bundle = current_trust
      TrustBundle.validate(
        bundle,
        RootPolicy.active_keys(root),
        minimum_epoch: @trust_store.minimum_epoch.minimum_accepted
      )
      committed = @root_store.commit_current(fail_after: fail_after)
      record("commit-root")
      committed
    end

    def stage_trust_package(raw, fail_after: nil)
      require_stable
      bundle = PersistentPackage.decode_trust_bundle(raw)
      candidate = TrustBundle.validate(
        bundle,
        active_root_keys,
        minimum_epoch: @trust_store.minimum_epoch.minimum_accepted
      )
      validate_current_images(candidate)
      @trust_store.install(bundle, fail_after: fail_after)
      record("stage-trust")
      candidate[:epoch]
    end

    def commit_trust(fail_after: nil)
      unless phase == "trust-awaiting-commit"
        raise LoaderOrderError, "no trust bundle is awaiting commit"
      end
      trust, = current_trust
      validate_current_images(trust)
      committed = @trust_store.commit_current(fail_after: fail_after)
      record("commit-trust")
      committed
    end

    def stage_image_package(raw, role:, fail_after: nil)
      require_stable
      components, envelope = PersistentPackage.decode_image(raw)
      generation = Generation.validate(
        field(envelope, :generation), "candidate image generation"
      )
      if generation <= store(role).trusted.minimum_accepted
        raise LoaderOrderError, "candidate image generation must increase"
      end
      slot = installer(role).install(components, envelope, fail_after: fail_after)
      record("stage-#{role}")
      slot
    end

    def stage_normal_repair_package(raw, target_slot: nil, fail_after: nil)
      require_stable
      unless select_boot[:mode] == "recovery"
        raise LoaderOrderError, "normal repair requires recovery boot mode"
      end
      components, envelope = PersistentPackage.decode_image(raw)
      generation = Generation.validate(
        field(envelope, :generation), "candidate normal repair generation"
      )
      if generation <= @normal_store.trusted.minimum_accepted
        raise LoaderOrderError, "normal repair generation must increase"
      end
      if target_slot.nil?
        empty = @normal_store.slots.select { |_name, slot| slot.envelope.nil? }.keys
        target_slot = empty.empty? ? "B" : empty.first
      end
      installer(IMAGE_ROLE_NORMAL).repair_install(
        components,
        envelope,
        target_slot: target_slot,
        fail_after: fail_after
      )
      record("stage-normal")
      target_slot
    end

    def commit_image(role, slot, fail_after: nil)
      unless phase == "#{role}-awaiting-commit"
        raise LoaderOrderError, "no #{role} image is awaiting commit"
      end
      committed = installer(role).report_boot_success(slot, fail_after: fail_after)
      record("commit-#{role}")
      committed
    end

    def reject_image(role, slot)
      unless phase == "#{role}-awaiting-commit"
        raise LoaderOrderError, "no #{role} image is awaiting rejection"
      end
      installer(role).report_boot_failure(slot)
      record("reject-#{role}")
      nil
    end

    def select_boot
      { mode: "normal", **installer(IMAGE_ROLE_NORMAL).select_boot }
    rescue BootError
      begin
        { mode: "recovery", **installer(IMAGE_ROLE_RECOVERY).select_boot }
      rescue BootError => e
        raise LoaderError, "normal and recovery boot both failed: #{e.message}"
      end
    end

    def field(mapping, name)
      return mapping[name] if mapping.key?(name)

      mapping[name.to_s]
    end
  end
end
