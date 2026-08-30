# frozen_string_literal: true

require "json"
require_relative "code_relocation_demo"
require_relative "constructor_relocation_demo"
require_relative "min0_core_forth_image"

SOURCE_BASES = { code: 0x1000, dictionary: 0x4000, data: 0x8000 }.freeze
SOURCE_LIMITS = { code: 0x4000, dictionary: 0x8000, data: 0x10000 }.freeze
TARGET_BASES = { code: 0x2000, dictionary: 0x5000, data: 0x9000 }.freeze
TARGET_LIMITS = { code: 0x5000, dictionary: 0x9000, data: 0x11000 }.freeze
SOURCE_GENERATION = 7

def build_source_image(generation = SOURCE_GENERATION)
  vm, dictionary = make_image_system
  Min0CoreForth.install_core_primitives(dictionary)
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
  outer.interpret(SOURCE)
  components = {
    code: vm.read_bytes(Min0CoreForth::DEFAULT_CODE_BASE, outer.code_here - Min0CoreForth::DEFAULT_CODE_BASE),
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
  manifest = Min0CoreForth::Linker.build_manifest(records)
  envelope = Min0CoreForth::ImageEnvelope.build(
    components, SOURCE_BASES, SOURCE_LIMITS, allocator, manifest,
    generation: generation
  )
  [components, envelope]
end

def expect_image_rejection(name)
  yield
  raise "#{name} was accepted"
rescue Min0CoreForth::ImageError, Min0CoreForth::ImageAuthenticationError
  name
end

def run_image_envelope_demo(implementation = "ruby")
  components, envelope = build_source_image
  Min0CoreForth::ImageEnvelope.validate(components, envelope)
  linked, linked_envelope = Min0CoreForth::ImageEnvelope.link(
    components, envelope, TARGET_BASES, TARGET_LIMITS
  )

  bus = Min0CoreForth::RegionMemory.new(
    0x11000,
    [
      Min0CoreForth::MemoryRegion.new(name: "CODE", start: 0, size: 0x5000, permissions: "rwx", programmable: true),
      Min0CoreForth::MemoryRegion.new(name: "DICTIONARY", start: 0x5000, size: 0x4000, permissions: "rw"),
      Min0CoreForth::MemoryRegion.new(name: "DATA", start: 0x9000, size: 0x8000, permissions: "rw")
    ]
  )
  moved_vm = Min0CoreForth::VM.new(memory_size: 0x11000, memory_bus: bus)
  moved_vm.load(linked.fetch("code"), address: TARGET_BASES.fetch(:code))
  moved_dictionary = Min0CoreForth::RuntimeDictionary.new(
    moved_vm,
    base: TARGET_BASES.fetch(:dictionary),
    limit: TARGET_LIMITS.fetch(:dictionary),
    body_base: TARGET_BASES.fetch(:data),
    body_limit: TARGET_LIMITS.fetch(:data)
  )
  moved_allocator = linked_envelope.fetch(:allocator)
  moved_dictionary.load_images(
    linked.fetch("dictionary"),
    latest: moved_allocator.fetch("latest"),
    body_image: linked.fetch("data")
  )
  moved_outer = Min0CoreForth::OuterInterpreter.new(
    moved_vm, moved_dictionary, code_base: moved_allocator.fetch("code_here")
  )
  stack = moved_outer.interpret(
    "0 CHOOSE 1 CHOOSE 0 SPIN SUM SKIP STEP READ-ANSWER SLOT-ADDR"
  )

  different_components = components.transform_values(&:dup)
  different_components[:code].setbyte(
    different_components[:code].bytesize - 1,
    0 # Valid NOP; keep the alternate image structurally decodable.
  )
  different_envelope = Min0CoreForth::ImageEnvelope.build(
    different_components,
    SOURCE_BASES,
    SOURCE_LIMITS,
    envelope.fetch(:allocator),
    envelope.fetch(:manifest),
    generation: envelope.fetch(:generation)
  )
  allocator_tamper = Marshal.load(Marshal.dump(envelope))
  allocator_tamper[:allocator]["latest"] -= 4
  manifest_tamper = Marshal.load(Marshal.dump(envelope))
  manifest_tamper[:manifest][:records][0][:kind] += "-changed"
  rejected = [
    expect_image_rejection("different-image") do
      Min0CoreForth::ImageEnvelope.validate(different_components, envelope)
    end,
    expect_image_rejection("different-envelope") do
      Min0CoreForth::ImageEnvelope.validate(components, different_envelope)
    end,
    expect_image_rejection("allocator-metadata") do
      Min0CoreForth::ImageEnvelope.validate(components, allocator_tamper)
    end,
    expect_image_rejection("manifest-digest") do
      Min0CoreForth::ImageEnvelope.validate(components, manifest_tamper)
    end,
    expect_image_rejection("authentication-required") do
      Min0CoreForth::ImageEnvelope.validate(components, envelope, require_authentication: true)
    end
  ]
  {
    implementation: implementation,
    record_count: envelope[:manifest][:records].length,
    source_identity: envelope[:identity_sha256],
    linked_identity: linked_envelope[:identity_sha256],
    different_identity: different_envelope[:identity_sha256],
    identity_changed: envelope[:identity_sha256] != linked_envelope[:identity_sha256],
    authentication: envelope[:authentication][:scheme],
    generation: envelope[:generation],
    linked_generation: linked_envelope[:generation],
    source_allocator: envelope[:allocator],
    linked_allocator: linked_envelope[:allocator],
    stack: stack,
    rejected: rejected
  }
end

puts JSON.generate(run_image_envelope_demo) if $PROGRAM_NAME == __FILE__
