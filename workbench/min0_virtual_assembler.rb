# frozen_string_literal: true

# Independent R0 reference model for the MIN0 virtual assembler.
module Min0VirtualAssembler
  CELL_MASK = 0xFFFF_FFFF
  REGISTERS = %w[V0 V1 V2 V3].freeze
  BINARY_OPS = %w[ADD SUB MUL AND OR XOR].freeze
  SHIFT_OPS = %w[LSL LSR ASR ROL ROR].freeze
  CONDITIONAL_BRANCHES = %w[BEQ BNE BLT BGE BLTU BGEU].freeze

  class Error < StandardError; end
  class ParseError < Error; end
  class VerifyError < Error; end
  class StackUnderflow < Error; end
  class ExecutionError < Error; end

  Instruction = Struct.new(:opcode, :operands, :line, keyword_init: true)

  class CodeDefinition
    attr_reader :name, :inputs, :outputs, :instructions

    def initialize(name, inputs, outputs, instructions)
      @name = name
      @inputs = inputs.freeze
      @outputs = outputs.freeze
      @instructions = instructions.freeze
    end

    def execute(stack, max_steps: 10_000)
      if stack.length < inputs.length
        raise StackUnderflow,
              "#{name} needs #{inputs.length} inputs but stack has #{stack.length}"
      end

      prefix = inputs.empty? ? stack.dup : stack[0...-inputs.length]
      values = inputs.empty? ? [] : stack[-inputs.length, inputs.length]
      entry = inputs.zip(values.map { |value| value & CELL_MASK }).to_h
      registers = {}
      staged = {}
      comparison = nil
      labels = {}
      instructions.each_with_index do |instruction, index|
        labels[instruction.operands[0]] = index if instruction.opcode == "LABEL"
      end

      pc = 0
      steps = 0
      while pc < instructions.length
        steps += 1
        if steps > max_steps
          raise ExecutionError, "#{name} exceeded #{max_steps} virtual instructions"
        end
        instruction = instructions[pc]
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
        when "CMP"
          comparison = [registers.fetch(args[0]), registers.fetch(args[1])]
        when *CONDITIONAL_BRANCHES
          left, right = comparison
          signed_left = Min0VirtualAssembler.signed(left)
          signed_right = Min0VirtualAssembler.signed(right)
          take = case op
                 when "BEQ" then left == right
                 when "BNE" then left != right
                 when "BLT" then signed_left < signed_right
                 when "BGE" then signed_left >= signed_right
                 when "BLTU" then left < right
                 else left >= right
                 end
          if take
            pc = labels.fetch(args[0])
            next
          end
        when "BRA"
          pc = labels.fetch(args[0])
          next
        when "LABEL"
          # No runtime operation.
        else
          raise "unreachable opcode #{op}"
        end
        pc += 1
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
    label_match = /\A@([A-Za-z][A-Za-z0-9_-]*):\z/.match(text)
    if label_match
      return Instruction.new(opcode: "LABEL", operands: [label_match[1]], line: line)
    end
    opcode, operand_text = text.split(/\s+/, 2)
    opcode = opcode.upcase
    operands = operand_text.nil? ? [] : operand_text.split(",").map(&:strip)
    expected = if BINARY_OPS.include?(opcode) || SHIFT_OPS.include?(opcode)
                 2
               else
                 {
                   "NOT" => 1, "IN" => 2, "OUT" => 2, "MOV" => 2,
                   "LIT" => 2, "CMP" => 2, "BRA" => 1, "LABEL" => 1,
                   **CONDITIONAL_BRANCHES.to_h { |branch| [branch, 1] }
                 }[opcode]
               end
    raise ParseError, "line #{line}: unknown opcode #{opcode}" if expected.nil?
    if operands.length != expected || operands.any?(&:empty?)
      raise ParseError, "line #{line}: #{opcode} expects #{expected} operand(s)"
    end
    if CONDITIONAL_BRANCHES.include?(opcode) || opcode == "BRA"
      target = operands[0]
      target = target[1..] if target.start_with?("@")
      operands = [target]
    end
    Instruction.new(opcode: opcode, operands: operands, line: line)
  end

  def verify(definition)
    labels = {}
    definition.instructions.each do |instruction|
      op = instruction.opcode
      args = instruction.operands
      line = instruction.line
      case op
      when "LABEL"
        label(args[0], line)
        raise VerifyError, "line #{line}: duplicate label #{args[0]}" if labels.key?(args[0])
        labels[args[0]] = true
      when *CONDITIONAL_BRANCHES, "BRA"
        label(args[0], line)
      when "IN"
        register(args[0], line)
        raise VerifyError, "line #{line}: unknown input #{args[1]}" unless definition.inputs.include?(args[1])
      when "OUT"
        raise VerifyError, "line #{line}: unknown output #{args[0]}" unless definition.outputs.include?(args[0])
        register(args[1], line)
      when "MOV", "CMP", *BINARY_OPS
        register(args[0], line)
        register(args[1], line)
      when "LIT"
        register(args[0], line)
        parse_number(args[1], line)
      when "NOT"
        register(args[0], line)
      when *SHIFT_OPS
        register(args[0], line)
        begin
          count = Integer(args[1], 10)
        rescue ArgumentError
          raise VerifyError, "line #{line}: invalid shift count #{args[1]}"
        end
        raise VerifyError, "line #{line}: shift count must be 0..31" unless (0..31).cover?(count)
      end
    end
    definition.instructions.each do |instruction|
      next unless CONDITIONAL_BRANCHES.include?(instruction.opcode) || instruction.opcode == "BRA"
      target = instruction.operands[0]
      raise VerifyError, "line #{instruction.line}: unknown label #{target}" unless labels.key?(target)
    end
    verify_paths(definition)
  end

  def verify_paths(definition)
    labels = {}
    definition.instructions.each_with_index do |instruction, index|
      labels[instruction.operands[0]] = index if instruction.opcode == "LABEL"
    end
    pending = [[0, [], [], false]]
    seen = {}
    terminal_seen = false
    until pending.empty?
      pc, initialized, assigned, compared = pending.pop
      key = [pc, initialized, assigned, compared]
      next if seen[key]
      seen[key] = true
      if pc == definition.instructions.length
        terminal_seen = true
        missing = definition.outputs - assigned
        raise VerifyError, "output(s) not assigned: #{missing.join(', ')}" unless missing.empty?
        next
      end

      instruction = definition.instructions[pc]
      op = instruction.opcode
      args = instruction.operands
      line = instruction.line
      next_initialized = initialized.dup
      next_assigned = assigned.dup
      next_compared = compared
      case op
      when "IN"
        next_initialized |= [args[0]]
      when "OUT"
        read_register(args[1], initialized, line)
        if assigned.include?(args[0])
          raise VerifyError, "line #{line}: output #{args[0]} assigned twice on one path"
        end
        next_assigned |= [args[0]]
      when "MOV"
        read_register(args[1], initialized, line)
        next_initialized |= [args[0]]
      when "LIT"
        next_initialized |= [args[0]]
      when *BINARY_OPS
        read_register(args[0], initialized, line)
        read_register(args[1], initialized, line)
      when "NOT", *SHIFT_OPS
        read_register(args[0], initialized, line)
      when "CMP"
        read_register(args[0], initialized, line)
        read_register(args[1], initialized, line)
        next_compared = true
      when *CONDITIONAL_BRANCHES
        raise VerifyError, "line #{line}: #{op} requires CMP on every path" unless compared
        pending << [labels.fetch(args[0]), next_initialized.sort, next_assigned.sort, next_compared]
      when "BRA"
        pending << [labels.fetch(args[0]), next_initialized.sort, next_assigned.sort, next_compared]
        next
      end
      pending << [pc + 1, next_initialized.sort, next_assigned.sort, next_compared]
    end
    raise VerifyError, "CODE definition has no terminating path" unless terminal_seen
  end

  def register(name, line)
    return if REGISTERS.include?(name) && name == name.upcase
    raise VerifyError, "line #{line}: unknown register #{name}"
  end

  def read_register(name, initialized, line)
    register(name, line)
    raise VerifyError, "line #{line}: register #{name} is uninitialized" unless initialized.include?(name)
  end

  def label(name, line)
    return if name.match?(/\A[A-Za-z][A-Za-z0-9_-]*\z/)
    raise VerifyError, "line #{line}: invalid label #{name}"
  end

  def signed(value)
    value < 0x8000_0000 ? value : value - 0x1_0000_0000
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
