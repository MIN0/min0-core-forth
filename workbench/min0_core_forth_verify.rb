# frozen_string_literal: true

require_relative "min0_core_forth_linker"
require_relative "min0_core_forth_vm"

module Min0CoreForth
  class BytecodeVerificationError < StandardError; end

  module BytecodeVerifier
    module_function

    OPERAND_OPS = [
      Op::LIT, Op::CALL, Op::ICALL, Op::DSET, Op::BRANCH, Op::ZBRANCH,
      Op::LOOP, Op::PLOOP, Op::QDO, Op::LEAVE, Op::SERVICE
    ].freeze
    REQUIRED_CODE_RELOCATIONS = {
      Op::CALL => ["code", %w[call does-call]],
      Op::ICALL => ["dictionary", %w[defer-slot]],
      Op::DSET => ["dictionary", %w[defer-store-slot]],
      Op::BRANCH => ["code", %w[branch]],
      Op::ZBRANCH => ["code", %w[zbranch]],
      Op::LOOP => ["code", %w[loop]],
      Op::PLOOP => ["code", %w[ploop]],
      Op::QDO => ["code", %w[qdo]],
      Op::LEAVE => ["code", %w[leave]]
    }.freeze
    OPTIONAL_LITERAL_RELOCATIONS = [
      ["dictionary", "xt-literal"],
      ["dictionary", "action-of-slot"],
      ["data", "data-literal"],
      ["data", "does-body"],
      ["data", "string-address"]
    ].freeze
    DIRECT_CODE_OPS = [
      Op::CALL, Op::BRANCH, Op::ZBRANCH, Op::LOOP, Op::PLOOP, Op::QDO, Op::LEAVE
    ].freeze

    def field(hash, name)
      return nil unless hash.respond_to?(:key?)
      return hash[name] if hash.key?(name)

      hash[name.to_s]
    end
    private_class_method :field

    def integer(value, label)
      raise BytecodeVerificationError, "#{label} must be an Integer" unless value.is_a?(Integer)

      value
    end
    private_class_method :integer

    def verify_image_bytecode(components, bases, manifest)
      raise BytecodeVerificationError, "components must be a Hash" unless components.is_a?(Hash)
      raise BytecodeVerificationError, "component bases must be a Hash" unless bases.is_a?(Hash)

      images = {}
      normalized_bases = {}
      LINK_SECTIONS.each do |section|
        image = field(components, section.to_sym)
        raise BytecodeVerificationError, "component #{section} must be a String" unless image.is_a?(String)

        images[section] = image.b
        normalized_bases[section] = integer(field(bases, section.to_sym), "base #{section}")
      end
      raise BytecodeVerificationError, "manifest must be a Hash" unless manifest.is_a?(Hash)

      records = field(manifest, :records)
      raise BytecodeVerificationError, "manifest records must be an Array" unless records.is_a?(Array)

      code_records = {}
      records.each_with_index do |record, index|
        raise BytecodeVerificationError, "relocation record #{index} must be a Hash" unless record.is_a?(Hash)
        next unless field(record, :section) == "code"

        offset = integer(field(record, :offset), "relocation record #{index} offset")
        if code_records.key?(offset)
          raise BytecodeVerificationError, "multiple CODE relocations at offset #{offset}"
        end
        code_records[offset] = record
      end

      code = images.fetch("code")
      code_base = normalized_bases.fetch("code")
      boundaries = {}
      instructions = []
      consumed = {}
      service_ids = {}
      service_addresses = []
      offset = 0
      while offset < code.bytesize
        boundaries[code_base + offset] = true
        raw_opcode = code.getbyte(offset)
        unless Op::ALL.include?(raw_opcode)
          raise BytecodeVerificationError,
                format("invalid opcode 0x%02X at CODE+0x%X", raw_opcode, offset)
        end
        op = raw_opcode
        instruction_offset = offset
        offset += 1
        operand = nil
        if OPERAND_OPS.include?(op)
          if offset + CELL_BYTES > code.bytesize
            raise BytecodeVerificationError,
                  format("truncated operand at CODE+0x%X", instruction_offset)
          end
          operand = code.byteslice(offset, CELL_BYTES).unpack1("V")
          record = code_records[offset]
          if op == Op::LIT
            unless record.nil?
              pair = [field(record, :target), field(record, :kind)]
              unless OPTIONAL_LITERAL_RELOCATIONS.include?(pair)
                raise BytecodeVerificationError,
                      format("LIT at CODE+0x%X has incompatible relocation", instruction_offset)
              end
              consumed[offset] = true
            end
          elsif op == Op::SERVICE
            unless record.nil?
              raise BytecodeVerificationError,
                    format("SERVICE at CODE+0x%X must not have relocation", instruction_offset)
            end
            if operand.zero?
              raise BytecodeVerificationError,
                    format("SERVICE at CODE+0x%X uses reserved id zero", instruction_offset)
            end
            service_ids[operand] = true
            service_addresses << code_base + instruction_offset
          else
            expected_target, expected_kinds = REQUIRED_CODE_RELOCATIONS.fetch(op)
            if record.nil?
              raise BytecodeVerificationError,
                    format("opcode 0x%02X at CODE+0x%X lacks typed relocation", op, instruction_offset)
            end
            unless field(record, :target) == expected_target &&
                   expected_kinds.include?(field(record, :kind)) && field(record, :width) == 4
              raise BytecodeVerificationError,
                    format("opcode 0x%02X at CODE+0x%X has incompatible relocation", op, instruction_offset)
            end
            consumed[offset] = true
          end
          offset += CELL_BYTES
        end
        instructions << [instruction_offset, op, operand]
      end

      unexpected = (code_records.keys - consumed.keys).sort
      unless unexpected.empty?
        raise BytecodeVerificationError,
              "CODE relocation at offset #{unexpected.first} is not an instruction operand"
      end

      instructions.each do |instruction_offset, op, operand|
        next unless DIRECT_CODE_OPS.include?(op)
        next if boundaries.key?(operand)

        raise BytecodeVerificationError,
              format("opcode 0x%02X at CODE+0x%X targets non-boundary 0x%08X", op, instruction_offset, operand)
      end

      records.each_with_index do |record, index|
        next unless field(record, :target) == "code"

        section = field(record, :section)
        next unless LINK_SECTIONS.include?(section)

        patch_offset = integer(field(record, :offset), "relocation record #{index} offset")
        image = images.fetch(section)
        next if patch_offset.negative? || patch_offset + CELL_BYTES > image.bytesize

        target = image.byteslice(patch_offset, CELL_BYTES).unpack1("V")
        unless boundaries.key?(target)
          raise BytecodeVerificationError,
                format("relocation record %d targets non-boundary 0x%08X", index, target)
        end
      end

      dset_addresses = instructions.filter_map do |instruction_offset, op, _operand|
        code_base + instruction_offset if op == Op::DSET
      end
      {
        instruction_count: instructions.length,
        code_start: code_base,
        code_end: code_base + code.bytesize,
        boundary_count: boundaries.length,
        boundaries: boundaries.keys.sort,
        capabilities: dset_addresses.empty? ? [] : ["compiled-defer-store"],
        dset_addresses: dset_addresses,
        service_ids: service_ids.keys.sort,
        service_addresses: service_addresses
      }
    end
  end
end
