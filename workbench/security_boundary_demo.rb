# frozen_string_literal: true

require "json"
require_relative "image_envelope_demo"

def security_scenario(threat_id, name, result, status)
  { id: threat_id, scenario: name, result: result, status: status }
end

def run_security_boundary_demo(implementation = "ruby")
  components, envelope = build_source_image

  corrupted = components.transform_values(&:dup)
  last = corrupted[:code].bytesize - 1
  corrupted[:code].setbyte(last, 0) # Valid NOP: altered semantics, still valid bytecode.
  corruption = begin
    Min0CoreForth::ImageEnvelope.validate(corrupted, envelope)
    "accepted"
  rescue Min0CoreForth::ImageError
    "blocked"
  end

  manifest_tamper = Marshal.load(Marshal.dump(envelope))
  manifest_tamper[:manifest][:records][0][:kind] += "-tampered"
  manifest_result = begin
    Min0CoreForth::ImageEnvelope.validate(components, manifest_tamper)
    "accepted"
  rescue Min0CoreForth::ImageError
    "blocked"
  end

  rebuilt_envelope = Min0CoreForth::ImageEnvelope.build(
    corrupted,
    SOURCE_BASES,
    SOURCE_LIMITS,
    envelope[:allocator],
    envelope[:manifest],
    generation: envelope[:generation]
  )
  Min0CoreForth::ImageEnvelope.validate(corrupted, rebuilt_envelope)
  malicious_development = "accepted"
  malicious_authenticated = begin
    Min0CoreForth::ImageEnvelope.validate(
      corrupted, rebuilt_envelope, require_authentication: true
    )
    "accepted"
  rescue Min0CoreForth::ImageError
    "blocked"
  end

  old_components, old_envelope = build_source_image(envelope[:generation] - 1)
  rollback_result = begin
    Min0CoreForth::ImageEnvelope.validate(
      old_components, old_envelope, minimum_generation: envelope[:generation]
    )
    "accepted"
  rescue Min0CoreForth::ImageError
    "blocked"
  end

  vm, dictionary = make_image_system
  Min0CoreForth.install_core_primitives(dictionary)
  outer = Min0CoreForth::OuterInterpreter.new(vm, dictionary)
  outer.interpret(": FOREVER BEGIN AGAIN ;")
  forever = dictionary.find("FOREVER")
  execution_limit = begin
    vm.resume(forever.payload, return_to: outer.return_trampoline, max_steps: 20)
    "accepted"
  rescue Min0CoreForth::StepLimitExceeded
    "blocked"
  end

  scenarios = [
    security_scenario("T01", "component-corruption", corruption, "controlled"),
    security_scenario("T02", "manifest-tamper", manifest_result, "controlled"),
    security_scenario("T03", "malicious-rebuild-development", malicious_development, "gap"),
    security_scenario(
      "T04", "malicious-rebuild-authentication-required", malicious_authenticated, "policy-boundary"
    ),
    security_scenario("T05", "rollback-old-valid-image", rollback_result, "controlled"),
    security_scenario("T06", "infinite-execution", execution_limit, "controlled")
  ]
  {
    implementation: implementation,
    authentication: envelope[:authentication][:scheme],
    generation_present: envelope.key?(:generation),
    scenarios: scenarios,
    controlled: scenarios.count { |item| item[:status] == "controlled" },
    gaps: scenarios.select { |item| item[:status] == "gap" }.map { |item| item[:id] }
  }
end

puts JSON.generate(run_security_boundary_demo) if $PROGRAM_NAME == __FILE__
