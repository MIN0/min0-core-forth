# frozen_string_literal: true

require_relative "min0_core_forth_vm"

module Min0CoreForth
  class CompileError < StandardError; end

  PRIMITIVES = {
    "NOP" => Op::NOP,
    "@" => Op::FETCH,
    "!" => Op::STORE,
    "DROP" => Op::DROP,
    "DUP" => Op::DUP,
    "SWAP" => Op::SWAP,
    "OVER" => Op::OVER,
    "+" => Op::ADD,
    "-" => Op::SUB,
    "*" => Op::MUL,
    "AND" => Op::AND,
    "OR" => Op::OR,
    "XOR" => Op::XOR,
    "<" => Op::LESS,
    "=" => Op::EQUAL,
    "I" => Op::I,
    "J" => Op::J,
    "UNLOOP" => Op::UNLOOP,
    "CELL+" => Op::CELL_PLUS,
    "CELLS" => Op::CELLS,
    "ALIGNED" => Op::ALIGNED,
    "C@" => Op::C_FETCH,
    "C!" => Op::C_STORE,
    "CHAR+" => Op::CHAR_PLUS,
    "CHARS" => Op::CHARS
  }.freeze

  Definition = Data.define(:name, :body)
  ParsedSource = Data.define(:definitions, :main)
  QuotedText = Data.define(:word, :text)

  class Compiler
    def self.tokenize(source)
      tokens = []
      index = 0
      while index < source.length
        character = source[index]
        if character.match?(/\s/)
          index += 1
          next
        end
        if character == "\\"
          index += 1 while index < source.length && !["\r", "\n"].include?(source[index])
          next
        end

        introducer = source[index, 2].upcase
        if ['S"', '."'].include?(introducer)
          index += 2
          index += 1 if index < source.length && [" ", "\t"].include?(source[index])
          start = index
          while index < source.length && source[index] != '"'
            if ["\r", "\n"].include?(source[index])
              raise CompileError, "#{introducer} string is missing closing quote"
            end
            index += 1
          end
          raise CompileError, "#{introducer} string is missing closing quote" if index >= source.length

          tokens << QuotedText.new(introducer, source[start...index])
          index += 1
          next
        end

        start = index
        while index < source.length && !source[index].match?(/\s/) && source[index] != "\\"
          index += 1
        end
        tokens << source[start...index].upcase
      end
      tokens
    end

    def self.parse(source)
      tokens = tokenize(source)
      definitions = []
      main = []
      names = {}
      index = 0

      while index < tokens.length
        token = tokens[index]
        if token.is_a?(QuotedText)
          raise CompileError,
                "#{token.word} is supported by the runtime outer interpreter, not the raw v0.1 compiler"
        end
        if token == ":"
          raise CompileError, "':' requires a word name" if index + 1 >= tokens.length

          name = tokens[index + 1]
          unless name.is_a?(String)
            raise CompileError, "':' requires an ordinary unquoted word name"
          end
          raise CompileError, "invalid word name #{name.inspect}" if [":", ";"].include?(name)
          raise CompileError, "cannot redefine primitive #{name.inspect} in v0.1" if PRIMITIVES.key?(name)
          raise CompileError, "duplicate definition #{name.inspect}" if names.key?(name)

          index += 2
          body = []
          while index < tokens.length && tokens[index] != ";"
            if tokens[index].is_a?(QuotedText)
              quoted = tokens[index]
              raise CompileError,
                    "#{quoted.word} is supported by the runtime outer interpreter, not the raw v0.1 compiler"
            end
            raise CompileError, "nested ':' definition is not allowed" if tokens[index] == ":"

            body << tokens[index]
            index += 1
          end
          raise CompileError, "definition #{name.inspect} is missing ';'" if index >= tokens.length

          definitions << Definition.new(name, body.freeze)
          names[name] = true
          index += 1
        elsif token == ";"
          raise CompileError, "';' outside a definition"
        else
          main << token
          index += 1
        end
      end

      ParsedSource.new(definitions.freeze, main.freeze)
    end

    def self.parse_number(token)
      if token.start_with?("-0X", "+0X")
        sign = token.start_with?("-") ? -1 : 1
        return sign * Integer(token[3..], 16)
      end
      Integer(token, 0)
    rescue ArgumentError
      nil
    end

    def self.compile(source)
      parsed = parse(source)
      user_words = parsed.definitions.to_h { |definition| [definition.name, true] }
      assembler = Assembler.new

      compile_tokens(assembler, parsed.main, user_words, context: "main")
      assembler.emit(Op::HALT)

      parsed.definitions.each do |definition|
        assembler.label(word_label(definition.name))
        compile_tokens(assembler, definition.body, user_words, context: definition.name)
        assembler.emit(Op::EXIT)
      end
      assembler.build
    end

    def self.compile_tokens(assembler, tokens, user_words, context:)
      tokens.each do |token|
        number = parse_number(token)
        if number
          assembler.emit(Op::LIT, number)
        elsif PRIMITIVES.key?(token)
          assembler.emit(PRIMITIVES.fetch(token))
        elsif user_words.key?(token)
          assembler.emit(Op::CALL, word_label(token))
        else
          raise CompileError, "unknown word #{token.inspect} in #{context.inspect}"
        end
      end
    end
    private_class_method :compile_tokens

    def self.word_label(name)
      "word:#{name}"
    end
    private_class_method :word_label
  end
end
