# frozen_string_literal: true

require "json"
require_relative "image_envelope_demo"
require_relative "min0_core_forth_publish"

def w_x_rejected?(*errors)
  yield
  false
rescue *errors
  true
end

def run_w_x_publish_demo(implementation = "ruby")
  components, envelope = build_source_image
  published = Min0CoreForth::RuntimePublisher.publish(components, envelope)
  bases = published.validation[:bases]
  code_base = bases.fetch("code")
  code_region = published.vm.memory.regions.find { |region| region.name == "CODE" }
  staging_code = published.staging_memory.regions.find do |region|
    region.name == "STAGING-CODE"
  end

  staging_execution_rejected = w_x_rejected?(Min0CoreForth::MemoryFault) do
    published.staging_memory.check_fetch(code_base, 1)
  end
  runtime_before = published.vm.read_bytes(code_base, components[:code].bytesize)
  published.staging_memory.write(code_base, "\xFF".b)
  staging_changed = published.staging_memory.read_u8(code_base) == 0xFF
  runtime_unchanged = published.vm.read_bytes(code_base, components[:code].bytesize) == runtime_before
  stack = published.outer.interpret("READ-ANSWER 2 3 +")

  runtime_write_rejected = w_x_rejected?(Min0CoreForth::MemoryFault) do
    published.vm.write_u8(code_base, 0)
  end
  runtime_reprogram_rejected = w_x_rejected?(Min0CoreForth::MemoryFault) do
    published.vm.load("\x00".b, address: code_base)
  end
  tampered = components.dup
  tampered[:code] = components[:code].dup
  tampered[:code].setbyte(0, tampered[:code].getbyte(0) ^ 0xFF)
  tampered_before_publish_rejected = w_x_rejected?(Min0CoreForth::ImageError) do
    Min0CoreForth::RuntimePublisher.publish(tampered, envelope)
  end
  {
    implementation: implementation,
    staging_permissions: staging_code.permissions,
    runtime_permissions: code_region.permissions,
    runtime_programmable: code_region.programmable?,
    runtime_sealed: code_region.sealed?,
    stack: stack,
    staging_changed_after_publish: staging_changed,
    runtime_unchanged_after_staging_change: runtime_unchanged,
    rejected: {
      execute_staging: staging_execution_rejected,
      write_runtime_code: runtime_write_rejected,
      reprogram_runtime_code: runtime_reprogram_rejected,
      tampered_before_publish: tampered_before_publish_rejected
    }
  }
end

puts JSON.generate(run_w_x_publish_demo) if $PROGRAM_NAME == __FILE__
