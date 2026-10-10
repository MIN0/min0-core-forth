# frozen_string_literal: true

# Independent R0 reference model for the MIN0 virtual assembler.
module Min0VirtualAssembler
  CELL_MASK = 0xFFFF_FFFF
  REGISTERS = %w[V0 V1 V2 V3].freeze
  BINARY_OPS = %w[ADD SUB MUL AND OR XOR].freeze
  SHIFT_OPS = %w[LSL LSR ASR ROL ROR].freeze

  class Error < StandardError; end
  class ParseError < Error; end
  class VerifyError < Error; end
  class StackUnderflow < Error; end

  Instruction = Struct.new(:opcode, :operands, :line, keyword_init: true)

  class CodeDefinition
    attr_reader :name, :inputs, :outputs, :instructions

    def initialize(name, inputs, outputs, instructions)
      @name = name
      @inputs = inputs.freeze
      @outputs = outputs.freeze
      @instructions = instructions.freeze
    end

    def execute(stack)
      if stack.length < inputs.length
        raise StackUnderflow,
              "#{name} needs #{inputs.length} inputs but stack has #{stack.length}"
      end

      prefix = inputs.empty? ? stack.dup : stack[0...-inputs.length]
      values = inputs.empty? ? [] : stack[-inputs.length, inputs.length]
      entry = inputs.zip(values.map { |value| value & CELL_MASK }).to_h
      registers = {}
      staged = {}

      instructions.each do |instruction|
        op = instruction.opcode
        args = instruction.operands
        case op
        when "IN"
          registers[args[0]] = entry.fetch(args[1])
        when "OUT"
          staged[args[0]] = registers.fetch(args[1])
        when "MOV"
          registers[args[0]] = registers.fetch(args[1])
        when "LIT"
          registers[args[0]] = Min0VirtualAssembler.parse_number(args[1], instruction.line)
        when *BINARY_OPS
          left = registers.fetch(args[0])
          right = registers.fetch(args[1])
          result = case op
                   when "ADD" then left + right
                   when "SUB" then left - right
                   when "MUL" then left * right
                   when "AND" then left & right
                   when "OR" then left | right
                   else left ^ right
                   end
          registers[args[0]] = result & CELL_MASK
        when "NOT"
          registers[args[0]] = (~registers.fetch(args[0])) & CELL_MASK
        when *SHIFT_OPS
          register = args[0]
          count = Integer(args[1], 10)
          value = registers.fetch(register)
          result = case op
                   when "LSL" then value << count
                   when "LSR" then value >> count
                   when "ASR"
                     signed = value < 0x8000_0000 ? value : value - 0x1_0000_0000
                     signed >> count
                   when "ROL"
                     count.zero? ? value : (value << count) | (value >> (32 - count))
                   else
                     count.zero? ? value : (value >> count) | (value << (32 - count))
                   end
          registers[register] = result & CELL_MASK
        else
          raise "unreachable opcode #{op}"
        end
      end

      prefix + outputs.map { |output| staged.fetch(output) }
    end
  end

  HEADER = /^\s*CODE:\s+([A-Za-z][A-Za-z0-9_-]*)\s*\(\s*(.*?)\s*--\s*(.*?)\s*\)\s*$/i

  module_function

  def compile_code(source)
    meaningful = source.lines.each_with_index.filter_map do |line, index|
      [index + 1, line.chomp] unless line.strip.empty?
    end
    raise ParseError, "empty source" if meaningful.empty?

    header_line, header_text = meaningful.first
    match = HEADER.match(header_text)
    raise ParseError, "line #{header_line}: invalid CODE header" unless match

    name = match[1].upcase
    inputs = names(match[2], "input", header_line)
    outputs = names(match[3], "output", header_line)
    instructions = []
    ended = false
    meaningful.drop(1).each do |line_number, raw_line|
      line = raw_line.split("\\", 2).first.strip
      next if line.empty?
      if line.upcase == ";CODE"
        ended = true
        break
      end
      instructions << parse_instruction(line, line_number)
    end
    raise ParseError, "missing ;CODE" unless ended

    definition = CodeDefinition.new(name, inputs, outputs, instructions)
    verify(definition)
    definition
  end

  def names(text, role, line)
    result = text.split
    result.each do |name|
      raise ParseError, "line #{line}: invalid #{role} name #{name.inspect}" unless name.match?(/\A[A-Za-z][A-Za-z0-9_-]*\z/)
    end
    raise VerifyError, "line #{line}: duplicate #{role} name" unless result.uniq.length == result.length
    result
  end

  def parse_instruction(text, line)
    opcode, operand_text = text.split(/\s+/, 2)
    opcode = opcode.upcase
    operands = operand_text.nil? ? [] : operand_text.split(",").map(&:strip)
    expected = if BINARY_OPS.include?(opcode) || SHIFT_OPS.include?(opcode)
                 2
               else
                 { "NOT" => 1, "IN" => 2, "OUT" => 2, "MOV" => 2, "LIT" => 2 }[opcode]
               end
    raise ParseError, "line #{line}: unknown opcode #{opcode}" if expected.nil?
    if operands.length != expected || operands.any?(&:empty?)
      raise ParseError, "line #{line}: #{opcode} expects #{expected} operand(s)"
    end
    Instruction.new(opcode: opcode, operands: operands, line: line)
  end

  def verify(definition)
    initialized = []
    assigned_outputs = []
    definition.instructions.each do |instruction|
      op = instruction.opcode
      args = instruction.operands
      line = instruction.line
      case op
      when "IN"
        register(args[0], line)
        raise VerifyError, "line #{line}: unknown input #{args[1]}" unless definition.inputs.include?(args[1])
        initialized << args[0] unless initialized.include?(args[0])
      when "OUT"
        raise VerifyError, "line #{line}: unknown output #{args[0]}" unless definition.outputs.include?(args[0])
        read_register(args[1], initialized, line)
        raise VerifyError, "line #{line}: output #{args[0]} assigned twice" if assigned_outputs.include?(args[0])
        assigned_outputs << args[0]
      when "MOV"
        register(args[0], line)
        read_register(args[1], initialized, line)
        initialized << args[0] unless initialized.include?(args[0])
      when "LIT"
        register(args[0], line)
        parse_number(args[1], line)
        initialized << args[0] unless initialized.include?(args[0])
      when *BINARY_OPS
        read_register(args[0], initialized, line)
        read_register(args[1], initialized, line)
      when "NOT"
        read_register(args[0], initialized, line)
      when *SHIFT_OPS
        read_register(args[0], initialized, line)
        begin
          count = Integer(args[1], 10)
        rescue ArgumentError
          raise VerifyError, "line #{line}: invalid shift count #{args[1]}"
        end
        raise VerifyError, "line #{line}: shift count must be 0..31" unless (0..31).cover?(count)
      end
    end
    missing = definition.outputs - assigned_outputs
    raise VerifyError, "output(s) not assigned: #{missing.join(', ')}" unless missing.empty?
  end

  def register(name, line)
    return if REGISTERS.include?(name) && name == name.upcase
    raise VerifyError, "line #{line}: unknown register #{name}"
  end

  def read_register(name, initialized, line)
    register(name, line)
    raise VerifyError, "line #{line}: register #{name} is uninitialized" unless initialized.include?(name)
  end

  def parse_number(text, line)
    value = if text.match?(/\A-?0[xX][0-9A-Fa-f]+\z/)
              sign = text.start_with?("-") ? -1 : 1
              digits = sign.negative? ? text[3..] : text[2..]
              sign * Integer(digits, 16)
            elsif text.match?(/\A-?[0-9]+\z/)
              Integer(text, 10)
            else
              raise ArgumentError, text
            end
    raise VerifyError, "line #{line}: literal outside 32-bit cell" unless (-(1 << 31)..CELL_MASK).cover?(value)
    value & CELL_MASK
  rescue ArgumentError
    raise VerifyError, "line #{line}: invalid number #{text}"
  end
end
