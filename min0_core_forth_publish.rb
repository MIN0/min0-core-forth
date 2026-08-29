# frozen_string_literal: true

require_relative "min0_core_forth_image"
require_relative "min0_core_forth_outer"

module Min0CoreForth
  class PublishError < ImageError; end

  PublishedRuntime = Data.define(:vm, :dictionary, :outer, :staging_memory, :validation)

  module RuntimePublisher
    module_function

    def publish(
      components, envelope, require_authentication: false, minimum_generation: 0,
      trusted_public_keys: nil, required_image_role: nil
    )
      validation_options = {
        require_authentication: require_authentication,
        minimum_generation: minimum_generation,
        trusted_public_keys: trusted_public_keys,
        required_image_role: required_image_role,
        runtime_profile: EXECUTION_PROFILE_SAFE_RUNTIME
      }
      first = ImageEnvelope.validate(components, envelope, **validation_options)
      bases = first[:bases]
      limits = first[:limits]
      memory_size = r0_layout(bases, limits)

      staging = RegionMemory.new(
        memory_size,
        [
          MemoryRegion.new(
            name: "STAGING-CODE", start: bases["code"],
            size: limits["code"] - bases["code"], permissions: "rw"
          ),
          MemoryRegion.new(
            name: "STAGING-DICTIONARY", start: bases["dictionary"],
            size: limits["dictionary"] - bases["dictionary"], permissions: "rw"
          ),
          MemoryRegion.new(
            name: "STAGING-DATA", start: bases["data"],
            size: limits["data"] - bases["data"], permissions: "rw"
          )
        ]
      )
      %w[code dictionary data].each do |section|
        staging.write(bases.fetch(section), first[:components].fetch(section))
      end
      staged_components = %w[code dictionary data].to_h do |section|
        image = first[:components].fetch(section)
        [section, staging.read(bases.fetch(section), image.bytesize)]
      end
      validated = ImageEnvelope.validate(
        staged_components, envelope, **validation_options
      )

      code_region = MemoryRegion.new(
        name: "CODE", start: 0, size: limits["code"],
        permissions: "rx", programmable: true
      )
      runtime_memory = RegionMemory.new(
        memory_size,
        [
          code_region,
          MemoryRegion.new(
            name: "DICTIONARY", start: bases["dictionary"],
            size: limits["dictionary"] - bases["dictionary"], permissions: "rw"
          ),
          MemoryRegion.new(
            name: "DATA", start: bases["data"],
            size: limits["data"] - bases["data"], permissions: "rw"
          )
        ]
      )
      vm = VM.new(memory_size: memory_size, memory_bus: runtime_memory)
      vm.load(staged_components.fetch("code"), address: bases.fetch("code"))
      dictionary = RuntimeDictionary.new(
        vm,
        base: bases.fetch("dictionary"), limit: limits.fetch("dictionary"),
        body_base: bases.fetch("data"), body_limit: limits.fetch("data")
      )
      allocator = validated[:allocator]
      dictionary.load_images(
        staged_components.fetch("dictionary"),
        latest: allocator.fetch("latest"),
        body_image: staged_components.fetch("data")
      )
      outer = OuterInterpreter.new(
        vm, dictionary, code_base: allocator.fetch("code_here")
      )
      dictionary.seal_runtime_structure
      vm.seal_verified_execution(
        validated[:code_verification], extra_entries: outer.execution_extra_entries
      )
      PublishedRuntime.new(vm, dictionary, outer, staging, validated)
    end

    def r0_layout(bases, limits)
      valid = bases["code"].positive? && bases["code"] < limits["code"] &&
              limits["code"] == bases["dictionary"] &&
              bases["dictionary"] < limits["dictionary"] &&
              limits["dictionary"] == bases["data"] &&
              bases["data"] < limits["data"]
      unless valid
        raise PublishError,
              "R0 publication requires contiguous CODE, DICTIONARY, and DATA limits"
      end
      limits["data"]
    end
    private_class_method :r0_layout
  end
end
