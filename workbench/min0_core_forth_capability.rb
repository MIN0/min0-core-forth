# frozen_string_literal: true

require_relative "min0_core_forth_loader"

module Min0CoreForth
  PROFILE_RUNTIME = "runtime"
  PROFILE_MONITOR = "monitor"
  PROFILE_RECOVERY = "recovery"
  PROFILE_PROVISIONER = "provisioner"

  CAPABILITY_PERMISSIONS = {
    PROFILE_RUNTIME => %w[inspect].freeze,
    PROFILE_MONITOR => %w[inspect normal].freeze,
    PROFILE_RECOVERY => %w[inspect normal].freeze,
    PROFILE_PROVISIONER => %w[inspect normal recovery trust root].freeze
  }.freeze

  class CapabilityError < StandardError; end
  class AuthorizationError < CapabilityError; end
  class TransactionOwnerError < CapabilityError; end

  class LoaderSession
    attr_reader :label

    def initialize(authority, serial, label, marker)
      unless authority.valid_session_marker?(marker)
        raise AuthorizationError, "loader sessions must be issued by the authority"
      end

      @authority = authority
      @serial = serial
      @label = label
    end

    def status = @authority.status(self)
    def select_boot = @authority.select_boot(self)
    def stage_root(raw, fail_after: nil) = @authority.stage_root(self, raw, fail_after: fail_after)
    def commit_root(fail_after: nil) = @authority.commit_root(self, fail_after: fail_after)
    def stage_trust(raw, fail_after: nil) = @authority.stage_trust(self, raw, fail_after: fail_after)
    def commit_trust(fail_after: nil) = @authority.commit_trust(self, fail_after: fail_after)

    def stage_image(raw, role:, fail_after: nil)
      @authority.stage_image(self, raw, role: role, fail_after: fail_after)
    end

    def commit_image(role, slot, fail_after: nil)
      @authority.commit_image(self, role, slot, fail_after: fail_after)
    end

    def reject_image(role, slot) = @authority.reject_image(self, role, slot)
    def adopt_pending = @authority.adopt_pending(self)
  end

  class LoaderAuthority
    def initialize(loader)
      @loader = loader
      @profiles = {}.compare_by_identity
      @next_serial = 1
      clear_owner
      @session_marker = Object.new
    end

    def valid_session_marker?(marker) = marker.equal?(@session_marker)

    def issue(profile, label: nil)
      unless CAPABILITY_PERMISSIONS.key?(profile)
        raise AuthorizationError, "unknown loader capability profile"
      end

      session = LoaderSession.new(self, @next_serial, label || profile, @session_marker)
      @next_serial += 1
      @profiles[session] = profile
      session
    end

    def revoke(session)
      profile(session)
      @profiles.delete(session)
      clear_owner if @owner.equal?(session)
      nil
    end

    def status(session)
      require_permission(session, "inspect")
      result = @loader.status
      result[:transaction_owner] = if @owner.nil?
                                     nil
                                   else
                                     {
                                       label: @owner.label,
                                       domain: @owner_domain,
                                       slot: @owner_slot
                                     }
                                   end
      result
    end

    def select_boot(session)
      require_permission(session, "inspect")
      @loader.select_boot
    end

    def stage_root(session, raw, fail_after: nil)
      require_stage_context(session, "root")
      require_unowned
      epoch = @loader.stage_root_package(raw, fail_after: fail_after)
      claim(session, "root")
      epoch
    end

    def commit_root(session, fail_after: nil)
      require_owner(session, "root")
      committed = @loader.commit_root(fail_after: fail_after)
      clear_owner
      committed
    end

    def stage_trust(session, raw, fail_after: nil)
      require_stage_context(session, "trust")
      require_unowned
      epoch = @loader.stage_trust_package(raw, fail_after: fail_after)
      claim(session, "trust")
      epoch
    end

    def commit_trust(session, fail_after: nil)
      require_owner(session, "trust")
      committed = @loader.commit_trust(fail_after: fail_after)
      clear_owner
      committed
    end

    def stage_image(session, raw, role:, fail_after: nil)
      domain = image_domain(role)
      require_stage_context(session, domain)
      require_unowned
      slot = if domain == "normal" && @loader.select_boot[:mode] == "recovery"
               @loader.stage_normal_repair_package(raw, fail_after: fail_after)
             else
               @loader.stage_image_package(raw, role: role, fail_after: fail_after)
             end
      claim(session, domain, slot)
      slot
    end

    def commit_image(session, role, slot, fail_after: nil)
      domain = image_domain(role)
      require_owner(session, domain)
      unless slot == @owner_slot
        raise TransactionOwnerError, "image slot does not match the owned transaction"
      end

      committed = @loader.commit_image(role, slot, fail_after: fail_after)
      clear_owner
      committed
    end

    def reject_image(session, role, slot)
      domain = image_domain(role)
      require_owner(session, domain)
      unless slot == @owner_slot
        raise TransactionOwnerError, "image slot does not match the owned transaction"
      end

      @loader.reject_image(role, slot)
      clear_owner
      nil
    end

    def adopt_pending(session)
      profile(session)
      unless @owner.nil?
        raise TransactionOwnerError, "pending transaction already has an owner"
      end
      phase = @loader.phase
      if phase == "stable"
        raise LoaderOrderError, "there is no persistent transaction to adopt"
      end
      suffix = "-awaiting-commit"
      unless phase.end_with?(suffix)
        raise LoaderOrderError, "unknown persistent loader phase"
      end
      domain = phase.delete_suffix(suffix)
      require_permission(session, domain)
      slot = if %w[normal recovery].include?(domain)
               @loader.installer(domain).select_boot[:slot]
             end
      claim(session, domain, slot)
      { phase: phase, domain: domain, slot: slot }
    end

    private

    def profile(session)
      @profiles.fetch(session)
    rescue KeyError, TypeError
      raise AuthorizationError, "unknown or revoked loader capability"
    end

    def require_permission(session, domain)
      current = profile(session)
      unless CAPABILITY_PERMISSIONS.fetch(current).include?(domain)
        raise AuthorizationError, "#{current} capability cannot operate the #{domain} domain"
      end
      current
    end

    def require_stage_context(session, domain)
      current = require_permission(session, domain)
      if current == PROFILE_MONITOR && @loader.select_boot[:mode] != "normal"
        raise AuthorizationError, "monitor updates require a normal boot context"
      end
      if current == PROFILE_RECOVERY
        unless domain == "normal"
          raise AuthorizationError, "recovery capability can repair only normal images"
        end
        if @loader.select_boot[:mode] != "recovery"
          raise AuthorizationError, "recovery repair requires recovery boot mode"
        end
      end
      current
    end

    def claim(session, domain, slot = nil)
      unless @owner.nil?
        raise TransactionOwnerError, "a loader transaction already has an owner"
      end
      @owner = session
      @owner_domain = domain
      @owner_slot = slot
    end

    def require_unowned
      unless @owner.nil?
        raise TransactionOwnerError, "finish or revoke the owned transaction first"
      end
    end

    def require_owner(session, domain)
      profile(session)
      unless @owner.equal?(session) && @owner_domain == domain
        raise TransactionOwnerError,
              "only the session that owns this transaction may finish it"
      end
    end

    def clear_owner
      @owner = nil
      @owner_domain = nil
      @owner_slot = nil
    end

    def image_domain(role)
      return "normal" if role == IMAGE_ROLE_NORMAL
      return "recovery" if role == IMAGE_ROLE_RECOVERY

      raise AuthorizationError, "unknown image capability domain"
    end
  end
end
