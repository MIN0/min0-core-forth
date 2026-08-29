# frozen_string_literal: true

require "json"
require_relative "min0_core_forth_capability"
require_relative "loader_state_demo"

def capability_rejected
  yield
  false
rescue Min0CoreForth::CapabilityError, Min0CoreForth::LoaderError
  true
end

def capability_sessions(loader)
  authority = Min0CoreForth::LoaderAuthority.new(loader)
  sessions = {
    runtime: authority.issue(Min0CoreForth::PROFILE_RUNTIME, label: "forth-runtime"),
    monitor: authority.issue(Min0CoreForth::PROFILE_MONITOR, label: "update-monitor"),
    monitor2: authority.issue(Min0CoreForth::PROFILE_MONITOR, label: "second-monitor"),
    recovery: authority.issue(Min0CoreForth::PROFILE_RECOVERY, label: "recovery-console"),
    provisioner: authority.issue(
      Min0CoreForth::PROFILE_PROVISIONER, label: "physical-provisioner"
    )
  }
  [authority, sessions]
end

def capability_advance_to_key_overlap(sessions, packages)
  provisioner = sessions[:provisioner]
  provisioner.stage_root(packages[:root2])
  provisioner.commit_root
  provisioner.stage_trust(packages[:trust2])
  provisioner.commit_trust
end

def run_capability_boundary_demo(implementation = "ruby")
  fixture = loader_fixtures
  packages = fixture[:packages]

  loader = make_loader(fixture)
  authority, sessions = capability_sessions(loader)
  readable = sessions.reject { |name, _session| name == :monitor2 }.to_h do |name, session|
    [name, session.status[:phase] == "stable"]
  end

  denied = {
    runtime_normal_update: capability_rejected do
      sessions[:runtime].stage_image(packages[:normal2], role: Min0CoreForth::IMAGE_ROLE_NORMAL)
    end,
    monitor_root_update: capability_rejected do
      sessions[:monitor].stage_root(packages[:root2])
    end,
    monitor_trust_update: capability_rejected do
      sessions[:monitor].stage_trust(packages[:trust2])
    end,
    monitor_recovery_update: capability_rejected do
      sessions[:monitor].stage_image(packages[:recovery2], role: Min0CoreForth::IMAGE_ROLE_RECOVERY)
    end,
    recovery_repair_while_normal: capability_rejected do
      sessions[:recovery].stage_image(packages[:normal2], role: Min0CoreForth::IMAGE_ROLE_NORMAL)
    end,
    recovery_trust_update: capability_rejected do
      sessions[:recovery].stage_trust(packages[:trust2])
    end,
    profile_string_forgery: capability_rejected do
      authority.status(Min0CoreForth::PROFILE_PROVISIONER)
    end,
    unissued_session: capability_rejected do
      Min0CoreForth::LoaderSession.new(authority, 999, "forged", Object.new)
    end
  }

  capability_advance_to_key_overlap(sessions, packages)
  normal_slot = sessions[:monitor].stage_image(
    packages[:normal2], role: Min0CoreForth::IMAGE_ROLE_NORMAL
  )
  owner_visible = sessions[:runtime].status[:transaction_owner]
  parallel_stage_rejected = capability_rejected do
    sessions[:provisioner].stage_root(packages[:root3])
  end
  cross_session_commit_rejected = capability_rejected do
    sessions[:monitor2].commit_image(Min0CoreForth::IMAGE_ROLE_NORMAL, normal_slot)
  end
  wrong_slot_rejected = capability_rejected do
    sessions[:monitor].commit_image(Min0CoreForth::IMAGE_ROLE_NORMAL, "A")
  end
  sessions[:monitor].commit_image(Min0CoreForth::IMAGE_ROLE_NORMAL, normal_slot)

  recovery_update_by_monitor_rejected = capability_rejected do
    sessions[:monitor].stage_image(packages[:recovery2], role: Min0CoreForth::IMAGE_ROLE_RECOVERY)
  end
  recovery_slot = sessions[:provisioner].stage_image(
    packages[:recovery2], role: Min0CoreForth::IMAGE_ROLE_RECOVERY
  )
  sessions[:provisioner].commit_image(Min0CoreForth::IMAGE_ROLE_RECOVERY, recovery_slot)

  revoked = authority.issue(Min0CoreForth::PROFILE_RUNTIME, label: "temporary-observer")
  authority.revoke(revoked)
  revoked_session_rejected = capability_rejected { revoked.status }

  recovery_loader = make_loader(fixture)
  _recovery_authority, recovery_sessions = capability_sessions(recovery_loader)
  capability_advance_to_key_overlap(recovery_sessions, packages)
  recovery_loader.normal_store.slots.fetch("A").marker = nil
  monitor_blocked_in_recovery = capability_rejected do
    recovery_sessions[:monitor].stage_image(
      packages[:normal2], role: Min0CoreForth::IMAGE_ROLE_NORMAL
    )
  end
  repaired_slot = recovery_sessions[:recovery].stage_image(
    packages[:normal2], role: Min0CoreForth::IMAGE_ROLE_NORMAL
  )
  mode_after_stage = recovery_sessions[:recovery].select_boot[:mode]
  recovery_sessions[:recovery].commit_image(Min0CoreForth::IMAGE_ROLE_NORMAL, repaired_slot)
  repaired_boot = recovery_sessions[:runtime].select_boot

  resume_loader = make_loader(fixture)
  _old_authority, old_sessions = capability_sessions(resume_loader)
  capability_advance_to_key_overlap(old_sessions, packages)
  pending_slot = old_sessions[:monitor].stage_image(
    packages[:normal2], role: Min0CoreForth::IMAGE_ROLE_NORMAL
  )
  _restarted_authority, restarted_sessions = capability_sessions(resume_loader)
  runtime_adoption_rejected = capability_rejected do
    restarted_sessions[:runtime].adopt_pending
  end
  adoption = restarted_sessions[:monitor].adopt_pending
  restarted_sessions[:monitor].commit_image(Min0CoreForth::IMAGE_ROLE_NORMAL, pending_slot)

  {
    implementation: implementation,
    permissions: {
      runtime: ["inspect"],
      monitor: %w[inspect normal],
      recovery: ["inspect", "normal-in-recovery-mode"],
      provisioner: %w[inspect normal recovery trust root]
    },
    readable: readable,
    denied: denied.merge(
      parallel_stage: parallel_stage_rejected,
      cross_session_commit: cross_session_commit_rejected,
      wrong_slot_commit: wrong_slot_rejected,
      monitor_recovery_after_normal_update: recovery_update_by_monitor_rejected,
      revoked_session: revoked_session_rejected,
      monitor_in_recovery_mode: monitor_blocked_in_recovery,
      runtime_pending_adoption: runtime_adoption_rejected
    ),
    ownership: {
      owner_visible: owner_visible,
      normal_slot: normal_slot,
      phase_after_commit: sessions[:runtime].status[:phase]
    },
    recovery_repair: {
      slot: repaired_slot,
      mode_after_stage: mode_after_stage,
      final_mode: repaired_boot[:mode],
      generation: repaired_boot[:generation]
    },
    restart_adoption: adoption.merge(
      final_phase: restarted_sessions[:runtime].status[:phase],
      generation: restarted_sessions[:runtime].status[:normal_generation]
    ),
    final: sessions[:runtime].status
  }
end

puts JSON.generate(run_capability_boundary_demo) if $PROGRAM_NAME == __FILE__
