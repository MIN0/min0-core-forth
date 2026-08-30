# frozen_string_literal: true

require_relative "min0_core_forth_image"

module Min0CoreForth
  class GenerationError < StandardError; end

  module Generation
    module_function

    def validate(value, label = "generation")
      raise GenerationError, "#{label} must be an Integer" unless value.is_a?(Integer)
      unless value.between?(0, MAX_GENERATION)
        raise GenerationError, "#{label} must be an unsigned 64-bit integer"
      end

      value
    end
  end

  class TrustedGeneration
    attr_reader :minimum_accepted

    def initialize(minimum_accepted = 0)
      @minimum_accepted = Generation.validate(
        minimum_accepted, "minimum accepted generation"
      )
    end

    def authorize(generation)
      candidate = Generation.validate(generation)
      if candidate < @minimum_accepted
        raise GenerationError,
              "generation #{candidate} is below trusted minimum #{@minimum_accepted}"
      end

      candidate
    end

    def commit(generation)
      candidate = authorize(generation)
      @minimum_accepted = candidate if candidate > @minimum_accepted
      @minimum_accepted
    end
  end
end
