# frozen_string_literal: true

require_relative "min0_core_forth_compiler"
require_relative "min0_core_forth_dictionary"
require_relative "min0_core_forth_relocation"
require_relative "min0_core_forth_trace"

module Min0CoreForth
  STATE_INTERPRET = 0
  STATE_COMPILE = 1
  STATE_DIRECT_CONTROL = 2
  STATE_DIRECT_LOOP = STATE_DIRECT_CONTROL
  SOURCE_PROFILE_SAFE_RUNTIME = "safe-runtime"
  SOURCE_PROFILE_STANDARD_BUILD = "standard-build"
  DEFAULT_CODE_BASE = 0x1000
  PRIMITIVE_DISPATCH_SLOT_BYTES = 2
  TERMINAL_TYPE_SERVICE_ID = 1
  TERMINAL_EMIT_SERVICE_ID = 2
  TERMINAL_DOT_SERVICE_ID = 3
  TERMINAL_CR_SERVICE_ID = 4
  DEFAULT_DIRECT_TOKEN_LIMIT = 4096
  DEFAULT_DIRECT_EXECUTION_LIMIT = 100_000
  CONTROL_WORDS = [
    "IF", "ELSE", "THEN", "BEGIN", "UNTIL", "AGAIN", "WHILE", "REPEAT",
    "DO", "?DO", "LOOP", "+LOOP", "FOR", "NEXT", "LEAVE", "DOES>", "[']"
  ].freeze
  DIRECT_CONTROL_OPENERS = ["IF", "BEGIN", "DO", "?DO", "FOR"].freeze
  DIRECT_CONTROL_CLOSERS = [
    "ELSE", "THEN", "UNTIL", "AGAIN", "WHILE", "REPEAT", "LOOP", "+LOOP", "NEXT"
  ].freeze
  DATA_WORDS = [
    "HERE", ",", "C,", "ALLOT", "ALIGN", "CONSTANT", "VARIABLE", "CREATE",
    "DEFER", "'", "IS", "ACTION-OF"
  ].freeze
  HOST_WORDS = [".", "EMIT", "CR", "TYPE", "WORDS", 'S"', '."'].freeze
  COMMENT_WORDS = ["(", "\\"].freeze
  WORD_LIST_STARTUP_WORDS = (
    [":", ";"] + CONTROL_WORDS + DATA_WORDS + HOST_WORDS + COMMENT_WORDS
  ).uniq.freeze
  WORD_LIST_USER_HEADING =
    "--- ここから先はユーザーが : で定義したワードなどです ---"
  WORD_LIST_LINE_WIDTH = 72

  class OuterInterpreterError < StandardError; end
  class UnknownWord < OuterInterpreterError; end
  class InvalidExecutionToken < OuterInterpreterError; end
  class CompileStateError < OuterInterpreterError; end

  DirectControlCollection = Struct.new(
    :opener, :operands, :tokens, :structures, :data_before, :loops_before
  )
  DirectNode = Struct.new(
    :kind, :body, :alternate, :token, :terminator, keyword_init: true
  )
  class DirectLeave < StandardError; end

  class OuterInterpreter
    attr_reader :vm, :dictionary, :primitive_trampoline, :return_trampoline,
                :code_here, :code_limit, :state, :current_definition,
                :control_stack, :trace, :trace_failures, :code_base, :source_profile,
                :output

    def initialize(
      vm, dictionary, code_base: DEFAULT_CODE_BASE, trace: nil,
      source_profile: SOURCE_PROFILE_SAFE_RUNTIME,
      direct_token_limit: DEFAULT_DIRECT_TOKEN_LIMIT,
      direct_execution_limit: DEFAULT_DIRECT_EXECUTION_LIMIT
    )
      @vm = vm
      @dictionary = dictionary
      @trace = trace
      @trace_failures = []
      @output = []
      unless direct_token_limit.positive? && direct_execution_limit.positive?
        raise OuterInterpreterError, "direct-control limits must be positive"
      end
      @direct_token_limit = direct_token_limit
      @direct_execution_limit = direct_execution_limit
      @direct_control = nil
      @startup_dictionary_entries = dictionary.entries(include_hidden: false)
                                              .map(&:header_address).to_h { |address| [address, true] }
      unless [SOURCE_PROFILE_SAFE_RUNTIME, SOURCE_PROFILE_STANDARD_BUILD].include?(source_profile)
        raise OuterInterpreterError, "unknown source profile #{source_profile.inspect}"
      end
      if source_profile == SOURCE_PROFILE_STANDARD_BUILD && !vm.allow_defer_store?
        raise OuterInterpreterError,
              "standard-build profile requires a build VM with DEFER store enabled"
      end
      @source_profile = source_profile
      primitive_opcodes = PRIMITIVES.values.uniq.sort
      if (primitive_opcodes & Op::OPERAND_OPS).any?
        raise OuterInterpreterError,
              "fixed primitive dispatch only supports operand-free opcodes"
      end
      dispatch_size = primitive_opcodes.length * PRIMITIVE_DISPATCH_SLOT_BYTES
      if dictionary.base <= dispatch_size
        raise OuterInterpreterError, "dictionary base leaves no dispatch-table space"
      end

      @return_trampoline = dictionary.base - 1
      @primitive_trampoline = return_trampoline - dispatch_size
      @primitive_dispatch = primitive_opcodes.each_with_index.to_h do |opcode, index|
        [opcode, primitive_trampoline + index * PRIMITIVE_DISPATCH_SLOT_BYTES]
      end
      unless code_base >= 0 && code_base < primitive_trampoline
        raise OuterInterpreterError, "code base is outside the executable region"
      end

      @code_base = code_base
      @code_here = code_base
      @code_limit = primitive_trampoline
      @state = STATE_INTERPRET
      @current_definition = nil
      @control_stack = []
      @saved_dictionary_here = dictionary.here
      @saved_data_here = dictionary.data_here
      @saved_latest = dictionary.latest
      @saved_code_here = code_base
      @saved_relocation_count = 0
      @definer_create_seen = false
      @definer_behavior_address = nil
      @definer_steps = []
      @definer_segment_start = nil
      @relocation_records = []
      dispatch = primitive_opcodes.flat_map { |opcode| [opcode, Op::HALT] }
      dispatch << Op::HALT
      vm.memory.program(primitive_trampoline, dispatch.pack("C*"))
      vm.register_service(TERMINAL_TYPE_SERVICE_ID, method(:service_type))
      vm.register_service(TERMINAL_EMIT_SERVICE_ID, method(:service_emit))
      vm.register_service(TERMINAL_DOT_SERVICE_ID, method(:service_dot))
      vm.register_service(TERMINAL_CR_SERVICE_ID, method(:service_cr))
    end

    def relocation_manifest
      @relocation_records.map(&:to_h)
    end

    def terminal_text
      output.join
    end

    def awaiting_direct_control? = !@direct_control.nil?

    def awaiting_direct_loop? = awaiting_direct_control?

    def finish_input
      collection = @direct_control
      return if collection.nil?

      expected = direct_expected_closer(collection.structures[-1])
      opener = collection.opener
      abort_direct_control
      raise CompileStateError,
            "#{opener} is missing its matching #{expected} at end of input"
    end

    def execution_extra_entries
      entries = []
      @primitive_dispatch.sort.each do |opcode, address|
        expected = [opcode, Op::HALT].pack("C*")
        unless vm.read_bytes(address, 2) == expected
          raise OuterInterpreterError, "fixed primitive dispatch was modified"
        end
        entries.concat([address, address + 1])
      end
      unless vm.read_u8(return_trampoline) == Op::HALT
        raise OuterInterpreterError, "return trampoline was modified"
      end
      entries << return_trampoline
      entries
    end

    def interpret(source)
      index = 0
      input_data_before = vm.data_stack.dup
      begin
        tokens = Compiler.tokenize(source)
        if state == STATE_DIRECT_CONTROL
          trailing = collect_direct_control(tokens)
          return vm.data_stack.dup if trailing.nil?

          tokens = trailing
          input_data_before = vm.data_stack.dup
        end
        while index < tokens.length
          token = tokens[index]
          if token.is_a?(QuotedText)
            if state == STATE_COMPILE
              compile_quoted_text(token)
              index += 1
              next
            end
            unless state == STATE_INTERPRET
              raise CompileStateError, "#{token.word.inspect} is interpret-only in v0.1"
            end
            byte_count = interpret_quoted_text(token)
            index += 1
            next
          end
          if state == STATE_INTERPRET && DIRECT_CONTROL_OPENERS.include?(token)
            operands = consume_direct_control_operands(token)
            begin_direct_control(token, operands, input_data_before)
            trailing = collect_direct_control(tokens[(index + 1)..] || [])
            return vm.data_stack.dup if trailing.nil?

            tokens = trailing
            index = 0
            input_data_before = vm.data_stack.dup
            next
          end
          if state == STATE_INTERPRET && ["DEFER", "'", "IS", "ACTION-OF"].include?(token)
            if index + 1 >= tokens.length
              raise CompileStateError, "#{token.inspect} requires a word name in the same input"
            end
            name = tokens[index + 1]
            unless name.is_a?(String)
              raise CompileStateError, "#{token.inspect} requires an ordinary unquoted word name"
            end
            interpret_defer_word(token, name)
            index += 2
            next
          end
          if state == STATE_INTERPRET && ["CONSTANT", "VARIABLE", "CREATE"].include?(token)
            if index + 1 >= tokens.length
              raise CompileStateError, "#{token.inspect} requires a name in the same input"
            end
            name = tokens[index + 1]
            unless name.is_a?(String)
              raise CompileStateError, "#{token.inspect} requires an ordinary unquoted word name"
            end
            case token
            when "CONSTANT" then define_constant(name)
            when "VARIABLE" then define_variable(name)
            else define_created(name)
            end
            index += 2
            next
          end
          if state == STATE_INTERPRET && token == ":"
            if index + 1 >= tokens.length
              raise CompileStateError, "':' requires a word name in the same input"
            end
            name = tokens[index + 1]
            unless name.is_a?(String)
              raise CompileStateError, "':' requires an ordinary unquoted word name"
            end
            begin_definition(name)
            index += 2
            next
          end
          if state == STATE_COMPILE
            if token == ":"
              raise CompileStateError, "nested ':' definition is not allowed"
            elsif ["[']", "ACTION-OF", "IS"].include?(token)
              if index + 1 >= tokens.length
                raise CompileStateError, "#{token.inspect} requires a word name in the same input"
              end
              name = tokens[index + 1]
              unless name.is_a?(String)
                raise CompileStateError, "#{token.inspect} requires an ordinary unquoted word name"
              end
              compile_defer_source_word(token, name)
              index += 2
              next
            elsif token == ";"
              finish_definition
            else
              compile_token(token)
            end
            index += 1
            next
          end
          raise CompileStateError, "';' outside a definition" if token == ";"
          if CONTROL_WORDS.include?(token)
            vm.data_stack.replace(input_data_before)
            if ["LOOP", "+LOOP"].include?(token)
              raise CompileStateError,
                    "#{token.inspect} requires an unmatched direct DO or ?DO"
            elsif token == "NEXT"
              raise CompileStateError, "NEXT requires an unmatched direct FOR"
            elsif DIRECT_CONTROL_CLOSERS.include?(token)
              raise CompileStateError,
                    "#{token.inspect} has no matching direct control opener"
            end
            raise CompileStateError, "#{token.inspect} is compile-only"
          end

          if Compiler.parse_number(token).nil?
            entry = dictionary.find(token)
            if !entry.nil? && entry.kind == KIND_DEFINER
              if index + 1 >= tokens.length
                raise CompileStateError,
                      "defining word #{token.inspect} requires a child name in the same input"
              end
              child_name = tokens[index + 1]
              unless child_name.is_a?(String)
                raise CompileStateError,
                      "defining word #{token.inspect} requires an ordinary unquoted child name"
              end
              execute_definer(entry, child_name)
              index += 2
              next
            end
          end

          interpret_token(token)
          index += 1
        end
      rescue StandardError
        abort_definition if state == STATE_COMPILE
        abort_direct_control if state == STATE_DIRECT_CONTROL
        raise
      end
      vm.data_stack.dup
    end

    def execute(entry)
      data_before = vm.data_stack.dup
      return_depth = vm.return_stack.length
      loop_depth = vm.loop_stack.length
      begin
        case entry.kind
        when KIND_PRIMITIVE
          address = @primitive_dispatch[entry.payload]
          if address.nil?
            raise InvalidExecutionToken,
                  format("primitive opcode 0x%02X has no fixed dispatch entry", entry.payload)
          end
          vm.resume(address)
        when KIND_COLON
          vm.resume(entry.payload, return_to: return_trampoline)
        when KIND_CONSTANT, KIND_VARIABLE, KIND_CREATED
          vm.push(entry.payload)
          vm.data_stack.dup
        when KIND_DOES
          body_address, code_address = dictionary.read_does_descriptor(entry)
          trace_event(
            "does.execute.begin",
            word: entry.name, body: body_address, behavior: code_address
          )
          vm.push(body_address)
          result = vm.resume(code_address, return_to: return_trampoline)
          trace_event(
            "does.execute.end",
            word: entry.name, body: body_address, behavior: code_address
          )
          result
        when KIND_DEFER
          target_xt = dictionary.read_defer_target(entry)
          if target_xt.zero?
            raise UnassignedDefer, "DEFER word #{entry.name.inspect} is unassigned"
          end
          target = dictionary.entry_for_xt(target_xt)
          vm.resume(target.payload, return_to: return_trampoline)
        when KIND_DEFINER
          raise InvalidExecutionToken,
                "a defining word requires a child name from the outer interpreter"
        else
          raise InvalidExecutionToken, "unknown XT kind #{entry.kind}"
        end
      rescue StandardError
        vm.data_stack.replace(data_before)
        vm.return_stack.slice!(return_depth..)
        vm.loop_stack.slice!(loop_depth..)
        raise
      end
    end

    private

    def consume_direct_control_operands(opener)
      required = if ["DO", "?DO"].include?(opener)
                   2
                 elsif ["IF", "FOR"].include?(opener)
                   1
                 else
                   0
                 end
      if vm.data_stack.length < required
        raise StackUnderflow, "data stack underflow in direct #{opener}"
      end
      return [] if required.zero?
      return [vm.pop] if required == 1

      start = vm.pop
      limit = vm.pop
      [limit, start]
    end

    def begin_direct_control(opener, operands, data_before)
      @direct_control = DirectControlCollection.new(
        opener, operands.dup, [], [opener], data_before.dup,
        vm.loop_stack.map(&:dup)
      )
      @state = STATE_DIRECT_CONTROL
    end

    def collect_direct_control(tokens)
      collection = @direct_control
      raise CompileStateError, "direct-control collection is not active" if collection.nil?

      tokens.each_with_index do |token, index|
        if token.is_a?(String)
          advance_direct_structure(collection.structures, token)
          if collection.structures.empty?
            trailing = tokens[(index + 1)..] || []
            @direct_control = nil
            @state = STATE_INTERPRET
            begin
              program = [collection.opener, *collection.tokens, token]
              nodes = parse_direct_program(program)
              validate_direct_nodes(nodes)
              collection.operands.each { |operand| vm.push(operand) }
              execute_direct_nodes(nodes, [@direct_execution_limit])
        rescue StandardError
          vm.data_stack.replace(collection.data_before)
          vm.loop_stack.replace(collection.loops_before)
          raise
            end
            return trailing
          end
        end
        if collection.tokens.length >= @direct_token_limit
          abort_direct_control
          raise CompileStateError,
                "direct control body exceeds #{@direct_token_limit} tokens"
        end
        collection.tokens << token
      end
      nil
    end

    def advance_direct_structure(structures, token)
      if DIRECT_CONTROL_OPENERS.include?(token)
        structures << token
      elsif token == "ELSE"
        unless structures[-1] == "IF"
          raise CompileStateError, "ELSE requires an unmatched direct IF"
        end
        structures[-1] = "IF-ELSE"
      elsif token == "THEN"
        unless ["IF", "IF-ELSE"].include?(structures[-1])
          raise CompileStateError, "THEN requires an unmatched direct IF"
        end
        structures.pop
      elsif token == "WHILE"
        unless structures[-1] == "BEGIN"
          raise CompileStateError, "WHILE requires an unmatched direct BEGIN"
        end
        structures[-1] = "BEGIN-WHILE"
      elsif ["UNTIL", "AGAIN"].include?(token)
        unless structures[-1] == "BEGIN"
          raise CompileStateError, "#{token} requires an unmatched direct BEGIN"
        end
        structures.pop
      elsif token == "REPEAT"
        unless structures[-1] == "BEGIN-WHILE"
          raise CompileStateError, "REPEAT requires matching direct BEGIN and WHILE"
        end
        structures.pop
      elsif ["LOOP", "+LOOP"].include?(token)
        unless ["DO", "?DO"].include?(structures[-1])
          raise CompileStateError, "#{token} requires an unmatched direct DO or ?DO"
        end
        structures.pop
      elsif token == "NEXT"
        unless structures[-1] == "FOR"
          raise CompileStateError, "NEXT requires an unmatched direct FOR"
        end
        structures.pop
      end
    end

    def direct_expected_closer(structure)
      {
        "IF" => "THEN",
        "IF-ELSE" => "THEN",
        "BEGIN" => "UNTIL, AGAIN, or WHILE ... REPEAT",
        "BEGIN-WHILE" => "REPEAT",
        "DO" => "LOOP or +LOOP",
        "?DO" => "LOOP or +LOOP",
        "FOR" => "NEXT"
      }.fetch(structure)
    end

    def abort_direct_control
      collection = @direct_control
      unless collection.nil?
        vm.data_stack.replace(collection.data_before)
        vm.loop_stack.replace(collection.loops_before)
      end
      @direct_control = nil
      @state = STATE_INTERPRET
    end

    def parse_direct_program(tokens)
      nodes, index, terminator = parse_direct_sequence(tokens, 0, [])
      if !terminator.nil? || index != tokens.length
        raise CompileStateError, "unexpected direct-control terminator"
      end
      nodes
    end

    def parse_direct_sequence(tokens, start, stops)
      nodes = []
      index = start
      while index < tokens.length
        token = tokens[index]
        return [nodes, index + 1, token] if token.is_a?(String) && stops.include?(token)
        if token.is_a?(String) && DIRECT_CONTROL_CLOSERS.include?(token)
          raise CompileStateError, "unexpected #{token} in direct control structure"
        end
        if token == "IF"
          body, index, closer = parse_direct_sequence(tokens, index + 1, ["ELSE", "THEN"])
          alternate = []
          if closer == "ELSE"
            alternate, index, closer = parse_direct_sequence(tokens, index, ["THEN"])
          end
          nodes << DirectNode.new(kind: "IF", body: body, alternate: alternate)
          next
        elsif token == "BEGIN"
          body, index, closer = parse_direct_sequence(
            tokens, index + 1, ["UNTIL", "AGAIN", "WHILE"]
          )
          alternate = nil
          if closer == "WHILE"
            alternate, index, closer = parse_direct_sequence(tokens, index, ["REPEAT"])
          end
          nodes << DirectNode.new(
            kind: "BEGIN", body: body, alternate: alternate, terminator: closer
          )
          next
        elsif ["DO", "?DO"].include?(token)
          body, index, closer = parse_direct_sequence(tokens, index + 1, ["LOOP", "+LOOP"])
          nodes << DirectNode.new(
            kind: "DO", body: body, token: token, terminator: closer
          )
          next
        elsif token == "FOR"
          body, index, = parse_direct_sequence(tokens, index + 1, ["NEXT"])
          nodes << DirectNode.new(kind: "FOR", body: body)
          next
        end
        nodes << DirectNode.new(kind: "TOKEN", body: [], token: token)
        index += 1
      end
      unless stops.empty?
        raise CompileStateError,
              "direct control structure is missing #{stops.sort.join(', ')}"
      end
      [nodes, index, nil]
    end

    def validate_direct_nodes(nodes, loop_depth = 0)
      nodes.each do |node|
        if node.kind == "IF" || node.kind == "BEGIN"
          validate_direct_nodes(node.body, loop_depth)
          validate_direct_nodes(node.alternate || [], loop_depth)
          next
        elsif ["DO", "FOR"].include?(node.kind)
          validate_direct_nodes(node.body, loop_depth + 1)
          next
        end
        token = node.token
        if token.is_a?(QuotedText)
          if token.word == 'S"'
            raise CompileStateError, 'S" is not supported inside direct control input'
          end
          next
        end
        if token == "LEAVE"
          if loop_depth.zero?
            raise CompileStateError, "LEAVE requires a direct DO, ?DO, or FOR"
          end
          next
        end
        if CONTROL_WORDS.include?(token)
          raise CompileStateError, "#{token.inspect} is not valid in direct control input"
        end
        if DATA_WORDS.include?(token) || [":", ";", "UNLOOP"].include?(token)
          raise CompileStateError,
                "#{token.inspect} is not supported inside direct control input"
        end
        next unless Compiler.parse_number(token).nil? && !HOST_WORDS.include?(token)

        entry = dictionary.find(token)
        raise UnknownWord, "unknown word #{token.inspect} in direct control input" if entry.nil?
        if entry.kind == KIND_DEFINER
          raise CompileStateError,
                "defining word #{token.inspect} is not supported inside direct control input"
        end
      end
    end

    def execute_direct_nodes(nodes, budget)
      nodes.each do |node|
        consume_direct_budget(budget)
        if node.kind == "IF"
          flag = peek_data("IF")
          vm.pop
          execute_direct_nodes(flag.zero? ? node.alternate || [] : node.body, budget)
        elsif node.kind == "BEGIN"
          run_direct_begin(node, budget)
        elsif node.kind == "FOR"
          count = peek_data("FOR")
          vm.pop
          run_direct_for(count, node.body, budget)
        elsif node.kind == "DO"
          if vm.data_stack.length < 2
            raise StackUnderflow, "data stack underflow in direct #{node.token}"
          end
          start = vm.pop
          limit = vm.pop
          run_direct_do(
            limit, start, node.body,
            conditional: node.token == "?DO",
            plus: node.terminator == "+LOOP",
            budget: budget
          )
        elsif node.token.is_a?(QuotedText)
          interpret_quoted_text(node.token)
        elsif node.token == "LEAVE"
          raise DirectLeave
        else
          interpret_token(node.token)
        end
      end
    end

    def run_direct_begin(node, budget)
      loop do
        consume_direct_budget(budget)
        execute_direct_nodes(node.body, budget)
        if node.terminator == "UNTIL"
          flag = peek_data("UNTIL")
          vm.pop
          return unless flag.zero?
        elsif node.terminator == "AGAIN"
          next
        else
          flag = peek_data("WHILE")
          vm.pop
          return if flag.zero?

          execute_direct_nodes(node.alternate || [], budget)
        end
      end
    end

    def run_direct_for(count, nodes, budget)
      return if count.zero?

      require_direct_loop_capacity
      loop_depth = vm.loop_stack.length
      frame = LoopFrame.new(Min0CoreForth.cell(count), 0)
      vm.loop_stack << frame
      begin
        count.times do |index|
          consume_direct_budget(budget)
          frame.index = Min0CoreForth.cell(index)
          begin
            execute_direct_nodes(nodes, budget)
          rescue DirectLeave
            return
          end
          require_unchanged_direct_loop(loop_depth, frame)
        end
      ensure
        vm.loop_stack.slice!(loop_depth..)
      end
    end

    def run_direct_do(limit, start, nodes, conditional:, plus:, budget:)
      return if conditional && start == limit

      require_direct_loop_capacity
      loop_depth = vm.loop_stack.length
      frame = LoopFrame.new(Min0CoreForth.cell(limit), Min0CoreForth.cell(start))
      vm.loop_stack << frame
      begin
        loop do
          consume_direct_budget(budget)
          begin
            execute_direct_nodes(nodes, budget)
          rescue DirectLeave
            return
          end
          require_unchanged_direct_loop(loop_depth, frame)
          if plus
            increment = Min0CoreForth.signed(peek_data("+LOOP"))
            vm.pop
            old_delta = Min0CoreForth.signed(frame.index - frame.limit)
            frame.index = Min0CoreForth.cell(frame.index + increment)
            new_delta = Min0CoreForth.signed(frame.index - frame.limit)
            crossed = (increment.positive? && old_delta.negative? && new_delta >= 0) ||
                      (increment.negative? && old_delta.positive? && new_delta <= 0)
            return if crossed
          else
            frame.index = Min0CoreForth.cell(frame.index + 1)
            return if frame.index == frame.limit
          end
        end
      ensure
        vm.loop_stack.slice!(loop_depth..)
      end
    end

    def require_direct_loop_capacity
      if vm.loop_stack.length >= vm.max_loop_depth
        raise LoopStackOverflow,
              "loop stack limit #{vm.max_loop_depth} frame(s) exceeded"
      end
    end

    def require_unchanged_direct_loop(loop_depth, frame)
      return if vm.loop_stack.length == loop_depth + 1 && vm.loop_stack[loop_depth].equal?(frame)

      raise CompileStateError, "direct body changed its active loop frame"
    end

    def consume_direct_budget(budget)
      unless budget[0].positive?
        raise CompileStateError, "direct control execution limit exceeded"
      end

      budget[0] -= 1
    end

    def interpret_defer_word(token, name)
      if token == "DEFER"
        validate_data_name(name)
        dictionary.add_defer(name)
        return
      end
      entry = dictionary.find(name)
      raise UnknownWord, "unknown word #{name.inspect}" if entry.nil?
      if token == "'"
        vm.push(entry.xt)
      elsif token == "ACTION-OF"
        target_xt = dictionary.read_defer_target(entry)
        if target_xt.zero?
          raise UnassignedDefer, "DEFER word #{entry.name.inspect} is unassigned"
        end
        vm.push(target_xt)
      elsif token == "IS"
        target_xt = peek_data("IS")
        target = dictionary.entry_for_xt(target_xt)
        dictionary.set_defer(entry, target)
        vm.pop
      else
        raise token
      end
    end

    def interpret_token(token)
      if token == "."
        service_dot
        return
      elsif token == "EMIT"
        service_emit
        return
      elsif token == "CR"
        service_cr
        return
      elsif token == "TYPE"
        service_type
        return
      elsif token == "WORDS"
        output << word_listing
        return
      elsif token == "HERE"
        vm.push(dictionary.data_here)
        return
      elsif token == ","
        value = peek_data(",")
        dictionary.comma(value)
        vm.pop
        return
      elsif token == "C,"
        value = peek_data("C,")
        dictionary.c_comma(value)
        vm.pop
        return
      elsif token == "ALLOT"
        count = Min0CoreForth.signed(peek_data("ALLOT"))
        dictionary.allot(count)
        vm.pop
        return
      elsif token == "ALIGN"
        dictionary.align_here
        return
      end
      number = Compiler.parse_number(token)
      unless number.nil?
        vm.push(number)
        return
      end
      entry = dictionary.find(token)
      raise UnknownWord, "unknown word #{token.inspect}" if entry.nil?

      execute(entry)
    end

    def word_listing
      active_entries = {}
      dictionary.entries(include_hidden: false).each do |entry|
        active_entries[entry.name] ||= entry
      end

      startup_names = WORD_LIST_STARTUP_WORDS.to_h { |name| [name, true] }
      user_names = {}
      active_entries.each do |name, entry|
        next if WORD_LIST_STARTUP_WORDS.include?(name)

        if @startup_dictionary_entries.key?(entry.header_address)
          startup_names[name] = true
        else
          user_names[name] = true
        end
      end

      [
        "起動時から使えるワード",
        format_word_names(startup_names.keys),
        "",
        WORD_LIST_USER_HEADING,
        user_names.empty? ? "（まだありません）" : format_word_names(user_names.keys),
        ""
      ].join("\n")
    end

    def format_word_names(names)
      lines = []
      current = ""
      names.sort.each do |name|
        candidate = current.empty? ? name : "#{current} #{name}"
        if !current.empty? && candidate.length > WORD_LIST_LINE_WIDTH
          lines << current
          current = name
        else
          current = candidate
        end
      end
      lines << current unless current.empty?
      lines.join("\n")
    end

    def interpret_quoted_text(token)
      raw = encode_quoted_text(token)
      if token.word == '."'
        output << token.text
        return raw.bytesize
      end
      raise token.word unless token.word == 'S"'
      if vm.data_stack.length + 2 > vm.max_data_depth
        raise DataStackOverflow, "data stack limit #{vm.max_data_depth} cell(s) exceeded"
      end

      address = dictionary.data_here
      vm.memory.check_write(address, raw.bytesize) unless raw.empty?
      allocated = dictionary.allot(raw.bytesize)
      vm.write_bytes(allocated, raw) unless raw.empty?
      vm.push(allocated)
      vm.push(raw.bytesize)
      raw.bytesize
    end

    def compile_quoted_text(token)
      raw = encode_quoted_text(token)
      raise token.word unless ['S"', '."'].include?(token.word)
      if raw.empty?
        address = dictionary.body_base
      else
        address = dictionary.data_here
        vm.memory.check_write(address, raw.bytesize)
        address = dictionary.allot(raw.bytesize)
        vm.write_bytes(address, raw)
      end
      emit_opcode(Op::LIT)
      emit_reference(address, TARGET_DATA, "string-address")
      emit_opcode(Op::LIT)
      emit_cell(raw.bytesize)
      if token.word == '."'
        emit_opcode(Op::SERVICE)
        emit_cell(TERMINAL_TYPE_SERVICE_ID)
      end
      raw.bytesize
    end

    def service_type
      if vm.data_stack.length < 2
        raise StackUnderflow,
              "data stack needs 2 cell(s) for TYPE, has #{vm.data_stack.length}"
      end
      address = vm.data_stack[-2]
      length = vm.data_stack[-1]
      if length.zero?
        vm.data_stack.slice!(-2, 2)
        return
      end
      raw = vm.read_bytes(address, length)
      text = raw.bytes.map { |byte| byte.chr(Encoding::UTF_8) }.join
      output << text
      vm.data_stack.slice!(-2, 2)
    end

    def service_emit
      value = peek_data("EMIT")
      output << (value & 0xFF).chr(Encoding::UTF_8)
      vm.pop
    end

    def service_dot
      value = peek_data(".")
      output << Min0CoreForth.signed(value).to_s
      vm.pop
    end

    def service_cr
      output << "\n"
    end

    def encode_quoted_text(token)
      unless token.text.codepoints.all? { |codepoint| codepoint <= 0xFF }
        raise CompileStateError,
              "#{token.word} supports only byte characters U+0000..U+00FF"
      end
      token.text.codepoints.pack("C*").b
    end

    def begin_definition(name)
      if [":", ";"].include?(name) || DATA_WORDS.include?(name) || HOST_WORDS.include?(name)
        raise CompileStateError, "invalid definition name #{name.inspect}"
      end

      @saved_dictionary_here = dictionary.here
      @saved_data_here = dictionary.data_here
      @saved_latest = dictionary.latest
      @saved_code_here = code_here
      @saved_relocation_count = @relocation_records.length
      @current_definition = dictionary.add_colon(name, code_here, hidden: true)
      @state = STATE_COMPILE
      control_stack.clear
      @definer_create_seen = false
      @definer_behavior_address = nil
      @definer_steps.clear
      @definer_segment_start = nil
    end

    def finish_definition
      raise CompileStateError, "no current definition" if current_definition.nil?
      unless control_stack.empty?
        kind, = control_stack.last
        raise CompileStateError, "unresolved #{kind.inspect} before ';'"
      end

      if @definer_create_seen
        if @definer_behavior_address.nil?
          finish_constructor_plan
        else
          emit_opcode(Op::EXIT)
        end
        @current_definition = dictionary.set_definer(
          current_definition,
          @definer_steps,
          @definer_behavior_address || 0
        )
      else
        emit_opcode(Op::EXIT)
      end
      @current_definition = dictionary.set_hidden(current_definition, false)
      if @definer_create_seen
        plan_address, behavior_address = dictionary.read_definer_descriptor(current_definition)
        trace_event(
          "definer.compile.complete",
          word: current_definition.name,
          plan: plan_address,
          behavior: behavior_address,
          step_count: @definer_steps.length
        )
      end
      @current_definition = nil
      control_stack.clear
      @definer_create_seen = false
      @definer_behavior_address = nil
      @definer_steps.clear
      @definer_segment_start = nil
      @state = STATE_INTERPRET
    end

    def abort_definition
      vm.fill_bytes(@saved_code_here, code_here - @saved_code_here)
      @code_here = @saved_code_here
      @relocation_records.slice!(@saved_relocation_count..)
      dictionary.restore(
        here: @saved_dictionary_here,
        latest: @saved_latest,
        data_here: @saved_data_here
      )
      @current_definition = nil
      control_stack.clear
      @definer_create_seen = false
      @definer_behavior_address = nil
      @definer_steps.clear
      @definer_segment_start = nil
      @state = STATE_INTERPRET
    end

    def compile_defer_source_word(token, name)
      entry = dictionary.find(name)
      raise UnknownWord, "unknown word #{name.inspect} while compiling #{token}" if entry.nil?

      if token == "[']"
        emit_opcode(Op::LIT)
        emit_reference(entry.xt, TARGET_DICTIONARY, "xt-literal")
      else
        raise CompileStateError, "#{token} requires a DEFER word" unless entry.kind == KIND_DEFER

        if token == "ACTION-OF"
          emit_opcode(Op::LIT)
          emit_reference(entry.xt + CELL_BYTES, TARGET_DICTIONARY, "action-of-slot")
          emit_opcode(Op::FETCH)
        elsif token == "IS"
          unless source_profile == SOURCE_PROFILE_STANDARD_BUILD
            raise CompileStateError, "compiled IS is disabled in the safe-runtime profile"
          end
          emit_opcode(Op::DSET)
          emit_reference(entry.xt + CELL_BYTES, TARGET_DICTIONARY, "defer-store-slot")
        else
          raise token
        end
      end
    end

    def compile_token(token)
      if token == "CREATE"
        compile_create
        return
      elsif token == "DOES>"
        compile_does
        return
      end
      if @definer_create_seen && @definer_behavior_address.nil?
        if token == ","
          compile_constructor_action(CONSTRUCTOR_ACTION_COMMA)
          return
        elsif token == "C,"
          compile_constructor_action(CONSTRUCTOR_ACTION_C_COMMA)
          return
        elsif token == "ALLOT"
          compile_constructor_action(CONSTRUCTOR_ACTION_ALLOT)
          return
        elsif token == "ALIGN"
          compile_constructor_action(CONSTRUCTOR_ACTION_ALIGN)
          return
        end
      end
      if token == "TYPE"
        emit_opcode(Op::SERVICE)
        emit_cell(TERMINAL_TYPE_SERVICE_ID)
        return
      elsif token == "EMIT"
        emit_opcode(Op::SERVICE)
        emit_cell(TERMINAL_EMIT_SERVICE_ID)
        return
      elsif token == "."
        emit_opcode(Op::SERVICE)
        emit_cell(TERMINAL_DOT_SERVICE_ID)
        return
      elsif token == "CR"
        emit_opcode(Op::SERVICE)
        emit_cell(TERMINAL_CR_SERVICE_ID)
        return
      end
      raise CompileStateError, "#{token.inspect} is interpret-only in v0.1" if DATA_WORDS.include?(token)

      if token == "IF"
        compile_if
        return
      elsif token == "ELSE"
        compile_else
        return
      elsif token == "THEN"
        compile_then
        return
      elsif token == "BEGIN"
        compile_begin
        return
      elsif token == "UNTIL"
        compile_until
        return
      elsif token == "AGAIN"
        compile_again
        return
      elsif token == "WHILE"
        compile_while
        return
      elsif token == "REPEAT"
        compile_repeat
        return
      elsif token == "DO"
        compile_do
        return
      elsif token == "?DO"
        compile_do(conditional: true)
        return
      elsif token == "LOOP"
        compile_loop
        return
      elsif token == "+LOOP"
        compile_loop(plus: true)
        return
      elsif token == "FOR"
        compile_for
        return
      elsif token == "NEXT"
        compile_next
        return
      elsif token == "LEAVE"
        compile_leave
        return
      end

      number = Compiler.parse_number(token)
      unless number.nil?
        emit_opcode(Op::LIT)
        emit_cell(number)
        return
      end

      entry = dictionary.find(token)
      raise UnknownWord, "unknown word #{token.inspect} while compiling" if entry.nil?

      if entry.immediate?
        execute(entry)
      elsif entry.kind == KIND_PRIMITIVE
        emit_opcode(entry.payload)
      elsif entry.kind == KIND_COLON
        emit_opcode(Op::CALL)
        emit_reference(entry.payload, TARGET_CODE, "call")
      elsif entry.kind == KIND_CONSTANT
        emit_opcode(Op::LIT)
        emit_cell(entry.payload)
      elsif [KIND_VARIABLE, KIND_CREATED].include?(entry.kind)
        emit_opcode(Op::LIT)
        emit_reference(entry.payload, TARGET_DATA, "data-literal")
      elsif entry.kind == KIND_DOES
        body_address, code_address = dictionary.read_does_descriptor(entry)
        emit_opcode(Op::LIT)
        emit_reference(body_address, TARGET_DATA, "does-body")
        emit_opcode(Op::CALL)
        emit_reference(code_address, TARGET_CODE, "does-call")
      elsif entry.kind == KIND_DEFER
        emit_opcode(Op::ICALL)
        emit_reference(entry.xt + CELL_BYTES, TARGET_DICTIONARY, "defer-slot")
      elsif entry.kind == KIND_DEFINER
        raise CompileStateError, "defining word #{token.inspect} is interpret-only in v0.1"
      else
        raise InvalidExecutionToken, "unknown XT kind #{entry.kind}"
      end
    end

    def emit_opcode(opcode)
      reserve_code(1)
      vm.write_u8(code_here, Integer(opcode))
      @code_here += 1
    end

    def emit_cell(value)
      reserve_code(CELL_BYTES)
      vm.write_cell(code_here, value)
      @code_here += CELL_BYTES
    end

    def emit_reference(value, target, kind)
      patch_address = code_here
      emit_cell(value)
      @relocation_records << RelocationRecord.new(
        section: SECTION_CODE,
        offset: patch_address - code_base,
        target: target,
        width: REFERENCE32_WIDTH,
        kind: kind
      )
    end

    def reserve_code(size)
      raise CompileStateError, "compiled code region is full" if code_here + size > code_limit
    end

    def compile_if
      emit_opcode(Op::ZBRANCH)
      patch_address = code_here
      emit_reference(0, TARGET_CODE, "zbranch")
      control_stack << ["IF", patch_address]
    end

    def compile_else
      unless !control_stack.empty? && control_stack.last.first == "IF"
        raise CompileStateError, "ELSE requires an unmatched IF"
      end

      _kind, if_patch = control_stack.pop
      emit_opcode(Op::BRANCH)
      else_patch = code_here
      emit_reference(0, TARGET_CODE, "branch")
      vm.write_cell(if_patch, code_here)
      control_stack << ["ELSE", else_patch]
    end

    def compile_then
      unless !control_stack.empty? && ["IF", "ELSE"].include?(control_stack.last.first)
        raise CompileStateError, "THEN requires an unmatched IF or ELSE"
      end

      _kind, patch_address = control_stack.pop
      vm.write_cell(patch_address, code_here)
    end

    def compile_begin
      control_stack << ["BEGIN", code_here]
    end

    def compile_until
      begin_address = pop_begin("UNTIL")
      emit_opcode(Op::ZBRANCH)
      emit_reference(begin_address, TARGET_CODE, "zbranch")
    end

    def compile_again
      begin_address = pop_begin("AGAIN")
      emit_opcode(Op::BRANCH)
      emit_reference(begin_address, TARGET_CODE, "branch")
    end

    def compile_while
      unless !control_stack.empty? && control_stack.last.first == "BEGIN"
        raise CompileStateError, "WHILE requires an unmatched BEGIN"
      end

      emit_opcode(Op::ZBRANCH)
      patch_address = code_here
      emit_reference(0, TARGET_CODE, "zbranch")
      control_stack << ["WHILE", patch_address]
    end

    def compile_repeat
      unless control_stack.length >= 2 &&
             control_stack[-1].first == "WHILE" &&
             control_stack[-2].first == "BEGIN"
        raise CompileStateError, "REPEAT requires matching BEGIN and WHILE"
      end

      _while_kind, while_patch = control_stack.pop
      _begin_kind, begin_address = control_stack.pop
      emit_opcode(Op::BRANCH)
      emit_reference(begin_address, TARGET_CODE, "branch")
      vm.write_cell(while_patch, code_here)
    end

    def pop_begin(word)
      unless !control_stack.empty? && control_stack.last.first == "BEGIN"
        raise CompileStateError, "#{word} requires an unmatched BEGIN"
      end

      _kind, begin_address = control_stack.pop
      begin_address
    end

    def compile_do(conditional: false)
      exit_patches = []
      if conditional
        emit_opcode(Op::QDO)
        exit_patches << code_here
        emit_reference(0, TARGET_CODE, "qdo")
      else
        emit_opcode(Op::DO)
      end
      control_stack << ["DO", code_here, exit_patches]
    end

    def compile_loop(plus: false)
      unless !control_stack.empty? && control_stack.last.first == "DO"
        word = plus ? "+LOOP" : "LOOP"
        raise CompileStateError, "#{word} requires an unmatched DO or ?DO"
      end

      _kind, loop_address, exit_patches = control_stack.pop
      emit_opcode(plus ? Op::PLOOP : Op::LOOP)
      emit_reference(loop_address, TARGET_CODE, plus ? "ploop" : "loop")
      exit_patches.each { |patch_address| vm.write_cell(patch_address, code_here) }
    end

    def compile_for
      emit_opcode(Op::LIT)
      emit_cell(0)
      emit_opcode(Op::QDO)
      exit_patch = code_here
      emit_reference(0, TARGET_CODE, "for-exit")
      control_stack << ["FOR", code_here, [exit_patch]]
    end

    def compile_next
      unless !control_stack.empty? && control_stack.last.first == "FOR"
        raise CompileStateError, "NEXT requires an unmatched FOR"
      end

      _kind, loop_address, exit_patches = control_stack.pop
      emit_opcode(Op::LOOP)
      emit_reference(loop_address, TARGET_CODE, "next")
      exit_patches.each { |patch_address| vm.write_cell(patch_address, code_here) }
    end

    def compile_leave
      mark = control_stack.reverse.find { |item| ["DO", "FOR"].include?(item.first) }
      if mark.nil?
        raise CompileStateError, "LEAVE requires an unmatched DO, ?DO, or FOR"
      end

      emit_opcode(Op::LEAVE)
      patch_address = code_here
      emit_reference(0, TARGET_CODE, "leave")
      mark[2] << patch_address
    end

    def compile_create
      raise CompileStateError, "CREATE requires a current definition" if current_definition.nil?
      if @definer_create_seen
        raise CompileStateError, "only one CREATE is allowed in a defining word"
      end
      if code_here != current_definition.payload || !control_stack.empty?
        raise CompileStateError,
              "v0.1 defining words require CREATE as the first body token"
      end

      @definer_create_seen = true
      @definer_segment_start = current_definition.payload
    end

    def compile_does
      raise CompileStateError, "DOES> requires an earlier CREATE" unless @definer_create_seen
      unless @definer_behavior_address.nil?
        raise CompileStateError, "only one DOES> is allowed in a defining word"
      end
      unless control_stack.empty?
        kind, = control_stack.last
        raise CompileStateError, "unresolved #{kind.inspect} before 'DOES>'"
      end

      finish_constructor_plan
      @definer_behavior_address = code_here
    end

    def compile_constructor_action(action)
      unless control_stack.empty?
        kind, = control_stack.last
        raise CompileStateError,
              "constructor action inside unresolved #{kind.inspect} is not supported"
      end
      if @definer_segment_start.nil?
        raise CompileStateError, "constructor plan has no active code segment"
      end

      emit_opcode(Op::EXIT)
      @definer_steps << [@definer_segment_start, action]
      @definer_segment_start = code_here
    end

    def finish_constructor_plan
      if @definer_segment_start.nil?
        raise CompileStateError, "constructor plan has no active code segment"
      end

      emit_opcode(Op::EXIT)
      @definer_steps << [@definer_segment_start, CONSTRUCTOR_ACTION_END]
      @definer_segment_start = nil
    end

    def execute_definer(entry, child_name)
      validate_data_name(child_name)
      _plan_address, behavior_address = dictionary.read_definer_descriptor(entry)
      constructor_steps = dictionary.read_constructor_plan(entry)
      saved_here = dictionary.here
      saved_data_here = dictionary.data_here
      saved_latest = dictionary.latest
      data_before = vm.data_stack.dup
      return_depth = vm.return_stack.length
      loop_depth = vm.loop_stack.length
      trace_event("definer.execute.begin", word: entry.name, child: child_name)
      begin
        child = dictionary.add_created(child_name, hidden: true)
        trace_event(
          "child.create.hidden",
          word: entry.name, child: child.name, body: child.payload, header: child.header_address
        )
        constructor_steps.each do |code_address, action|
          trace_event(
            "constructor.segment.begin",
            word: entry.name, child: child.name, code_address: code_address, action: action
          )
          vm.resume(code_address, return_to: return_trampoline)
          trace_event(
            "constructor.segment.end",
            word: entry.name, child: child.name, code_address: code_address, action: action
          )
          if action == CONSTRUCTOR_ACTION_COMMA
            value = peek_data(",")
            address = dictionary.comma(value)
            vm.pop
            trace_event(
              "constructor.comma",
              word: entry.name, child: child.name, address: address,
              value: value, data_here_after: dictionary.data_here
            )
          elsif action == CONSTRUCTOR_ACTION_C_COMMA
            value = peek_data("C,")
            address = dictionary.c_comma(value)
            vm.pop
            trace_event(
              "constructor.c_comma",
              word: entry.name, child: child.name, address: address,
              value: value & 0xFF, data_here_after: dictionary.data_here
            )
          elsif action == CONSTRUCTOR_ACTION_ALLOT
            count = Min0CoreForth.signed(peek_data("ALLOT"))
            address = dictionary.allot(count)
            vm.pop
            trace_event(
              "constructor.allot",
              word: entry.name, child: child.name, address: address,
              count: count, data_here_after: dictionary.data_here
            )
          elsif action == CONSTRUCTOR_ACTION_ALIGN
            address_before = dictionary.data_here
            address_after = dictionary.align_here
            trace_event(
              "constructor.align",
              word: entry.name, child: child.name, address_before: address_before,
              padding: address_after - address_before, data_here_after: address_after
            )
          elsif action != CONSTRUCTOR_ACTION_END
            raise InvalidExecutionToken, "unknown constructor action #{action}"
          end
        end
        unless behavior_address.zero?
          child = dictionary.set_does(child, behavior_address)
          body_address, code_address = dictionary.read_does_descriptor(child)
          trace_event(
            "child.does.attach",
            word: entry.name, child: child.name, body: body_address,
            behavior: code_address, descriptor: child.payload
          )
        end
        child = dictionary.set_hidden(child, false)
        trace_event(
          "child.publish",
          word: entry.name, child: child.name, header: child.header_address, kind: child.kind
        )
        trace_event("definer.execute.end", word: entry.name, child: child.name)
        vm.data_stack.dup
      rescue StandardError => error
        vm.data_stack.replace(data_before)
        vm.return_stack.slice!(return_depth..)
        vm.loop_stack.slice!(loop_depth..)
        dictionary.restore(here: saved_here, latest: saved_latest, data_here: saved_data_here)
        trace_event(
          "definer.execute.rollback",
          word: entry.name, child: child_name, error: error.class.name.split("::").last
        )
        raise
      end
    end

    def trace_event(event, **details)
      return if trace.nil?

      trace.emit(vm, dictionary, event, **details)
    rescue StandardError => error
      trace_failures << "#{error.class.name}: #{error.message}"
    end

    def define_constant(name)
      validate_data_name(name)
      value = peek_data("CONSTANT")
      dictionary.add_constant(name, value)
      vm.pop
    end

    def define_variable(name)
      validate_data_name(name)
      dictionary.add_variable(name)
    end

    def define_created(name)
      validate_data_name(name)
      dictionary.add_created(name)
    end

    def validate_data_name(name)
      return unless [":", ";"].include?(name) || DATA_WORDS.include?(name)

      raise CompileStateError, "invalid data definition name #{name.inspect}"
    end

    def peek_data(word)
      raise StackUnderflow, "data stack underflow in #{word}" if vm.data_stack.empty?

      vm.data_stack.last
    end
  end

  def self.install_core_primitives(dictionary)
    PRIMITIVES.each { |name, opcode| dictionary.add_primitive(name, opcode) }
  end
end
