# frozen_string_literal: true

require "json"
require_relative "auth_comparison_demo"
require_relative "constructor_relocation_demo"
require_relative "min0_core_forth_install"
require_relative "signed_image_demo"

EXECUTION_PROFILE_BASES = { code: 0x1000, dictionary: 0x4000, data: 0x8000 }.freeze
EXECUTION_PROFILE_LIMITS = { code: 0x4000, dictionary: 0x8000, data: 0x10000 }.freeze

def build_execution_profile_candidate(standard_build:, generation:, private_key:)
  bus = Min0CoreForth::RegionMemory.new(
    0x10000,
    [
      Min0CoreForth::MemoryRegion.new(name: "CODE", start: 0, size: 0x4000, permissions: "rwx", programmable: true),
      Min0CoreForth::MemoryRegion.new(name: "DICTIONARY", start: 0x4000, size: 0x4000, permissions: "rw"),
      Min0CoreForth::MemoryRegion.new(name: "DATA", start: 0x8000, size: 0x8000, permissions: "rw")
    ]
  )
  vm = Min0CoreForth::VM.new(memory_bus: bus, allow_defer_store: standard_build)
  dictionary = Min0CoreForth::RuntimeDictionary.new(
    vm, base: 0x4000, limit: 0x8000, body_base: 0x8000, body_limit: 0x10000
  )
  Min0CoreForth.install_core_primitives(dictionary)
  options = standard_build ? { source_profile: Min0CoreForth::SOURCE_PROFILE_STANDARD_BUILD } : {}
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary, **options)
  outer.interpret(
    ": OLD-ACTION 10 ; : NEW-ACTION 20 ; " \
    "DEFER ACTION ' OLD-ACTION IS ACTION"
  )
  if standard_build
    outer.interpret(": SWITCH ['] NEW-ACTION IS ACTION ;")
  else
    outer.interpret(": USE-ACTION ACTION ;")
  end
  components = {
    code: vm.read_bytes(
      Min0CoreForth::DEFAULT_CODE_BASE,
      outer.code_here - Min0CoreForth::DEFAULT_CODE_BASE
    ),
    dictionary: dictionary.image,
    data: dictionary.body_image
  }
  allocator = {
    code_here: outer.code_here,
    header_here: dictionary.here,
    data_here: dictionary.data_here,
    latest: dictionary.latest
  }
  records = outer.relocation_manifest + collect_dictionary_relocations(vm, dictionary)
  envelope = Min0CoreForth::ImageEnvelope.build_ed25519(
    components,
    EXECUTION_PROFILE_BASES,
    EXECUTION_PROFILE_LIMITS,
    allocator,
    Min0CoreForth::Linker.build_manifest(records),
    generation: generation,
    key_id: SIGNED_IMAGE_KEY_ID,
    private_key: private_key
  )
  [components, envelope]
end

def execution_profile_rejected?
  yield
  false
rescue Min0CoreForth::ImageError
  true
end

def run_image_execution_profile_demo(implementation = "ruby")
  private_key = Min0CoreForth::Authentication.ed25519_private_from_seed(ED25519_TEST_SEED)
  trusted = {
    SIGNED_IMAGE_KEY_ID => Min0CoreForth::Authentication.ed25519_public_bytes(private_key)
  }
  safe_components, safe_envelope = build_execution_profile_candidate(
    standard_build: false, generation: 1, private_key: private_key
  )
  build_components, build_envelope = build_execution_profile_candidate(
    standard_build: true, generation: 2, private_key: private_key
  )
  validated_safe = Min0CoreForth::ImageEnvelope.validate(
    safe_components,
    safe_envelope,
    require_authentication: true,
    trusted_public_keys: trusted,
    runtime_profile: Min0CoreForth::EXECUTION_PROFILE_SAFE_RUNTIME
  )
  validated_build = Min0CoreForth::ImageEnvelope.validate(
    build_components,
    build_envelope,
    require_authentication: true,
    trusted_public_keys: trusted,
    runtime_profile: Min0CoreForth::EXECUTION_PROFILE_STANDARD_BUILD
  )

  store = Min0CoreForth::PersistentABStore.new(safe_components, safe_envelope, 1)
  safe_installer = Min0CoreForth::TransactionalInstaller.new(store, trusted)
  rejected_before_write = execution_profile_rejected? do
    safe_installer.install(build_components, build_envelope)
  end
  inactive = store.slots.fetch("B")
  inactive_untouched = inactive.components.empty? && inactive.envelope.nil?
  build_installer = Min0CoreForth::TransactionalInstaller.new(
    store,
    trusted,
    runtime_profile: Min0CoreForth::EXECUTION_PROFILE_STANDARD_BUILD
  )
  installed_slot = build_installer.install(build_components, build_envelope)

  profile_tamper = Marshal.load(Marshal.dump(build_envelope))
  profile_tamper[:execution_profile] = Min0CoreForth::EXECUTION_PROFILE_SAFE_RUNTIME
  tamper_rejected = execution_profile_rejected? do
    Min0CoreForth::ImageEnvelope.validate(
      build_components,
      profile_tamper,
      require_authentication: true,
      trusted_public_keys: trusted,
      runtime_profile: Min0CoreForth::EXECUTION_PROFILE_SAFE_RUNTIME
    )
  end
  recovery_rejected = execution_profile_rejected? do
    Min0CoreForth::ImageEnvelope.build_ed25519(
      build_components,
      EXECUTION_PROFILE_BASES,
      EXECUTION_PROFILE_LIMITS,
      build_envelope[:allocator],
      build_envelope[:manifest],
      generation: 2,
      key_id: SIGNED_IMAGE_KEY_ID,
      private_key: private_key,
      image_role: Min0CoreForth::IMAGE_ROLE_RECOVERY
    )
  end
  {
    implementation: implementation,
    safe_image_profile: validated_safe[:execution_profile],
    build_image_profile: validated_build[:execution_profile],
    safe_verified_capabilities: validated_safe[:code_verification][:capabilities],
    build_verified_capabilities: validated_build[:code_verification][:capabilities],
    build_verified_instruction_count: validated_build[:code_verification][:instruction_count],
    build_has_defer_store_record: build_envelope[:manifest][:records].any? do |record|
      record[:kind] == "defer-store-slot"
    end,
    safe_loader_rejected_before_write: rejected_before_write,
    inactive_slot_untouched: inactive_untouched,
    standard_build_installed_slot: installed_slot,
    profile_tamper_rejected: tamper_rejected,
    standard_build_recovery_rejected: recovery_rejected
  }
end

puts JSON.generate(run_image_execution_profile_demo) if $PROGRAM_NAME == __FILE__
