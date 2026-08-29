# frozen_string_literal: true

# Independent Ruby implementation of the MIN0 CORE FORTH VM v0.1 experiment.
module Min0CoreForth
  CELL_BITS = 32
  CELL_BYTES = 4
  CELL_MASK = 0xFFFF_FFFF
  SIGN_BIT = 0x8000_0000
  DEFAULT_MEMORY_SIZE = 64 * 1024
  DEFAULT_DATA_STACK_DEPTH = 256
  DEFAULT_RETURN_STACK_DEPTH = 256
  DEFAULT_LOOP_STACK_DEPTH = 32
  MINIMUM_CONFORMING_LOOP_DEPTH = 8

  module Op
    NOP = 0x00
    LIT = 0x01
    CALL = 0x02
    EXIT = 0x03
    BRANCH = 0x04
    ZBRANCH = 0x05
    FETCH = 0x06
    STORE = 0x07
    DROP = 0x08
    DUP = 0x09
    SWAP = 0x0A
    OVER = 0x0B
    ADD = 0x0C
    SUB = 0x0D
    MUL = 0x0E
    AND = 0x0F
    OR = 0x10
    XOR = 0x11
    LESS = 0x12
    EQUAL = 0x13
    HALT = 0x14
    DO = 0x15
    LOOP = 0x16
    I = 0x17
    UNLOOP = 0x18
    PLOOP = 0x19
    J = 0x1A
    QDO = 0x1B
    LEAVE = 0x1C
    CELL_PLUS = 0x1D
    CELLS = 0x1E
    ALIGNED = 0x1F
    C_FETCH = 0x20
    C_STORE = 0x21
    CHAR_PLUS = 0x22
    CHARS = 0x23
    ICALL = 0x24
    DSET = 0x25
    SERVICE = 0x26

    OPERAND_OPS = [LIT, CALL, ICALL, DSET, BRANCH, ZBRANCH, LOOP, PLOOP, QDO, LEAVE, SERVICE].freeze
    ALL = constants(false).filter_map do |name|
      value = const_get(name)
      value if value.is_a?(Integer)
    end.freeze
  end

  class VMError < StandardError; end
  class StackUnderflow < VMError; end
  class StackOverflow < VMError; end
  class DataStackOverflow < StackOverflow; end
  class ReturnStackOverflow < StackOverflow; end
  class LoopStackOverflow < StackOverflow; end
  class LoopStackUnderflow < StackUnderflow; end
  class MemoryFault < VMError; end
  class InvalidOpcode < VMError; end
  class StepLimitExceeded < VMError; end
  class UnassignedDefer < VMError; end
  class InvalidIndirectCall < VMError; end
  class DeferStoreDenied < VMError; end
  class InvalidExecutionTarget < VMError; end
  class ExecutionPolicyError < VMError; end
  class UnknownService < VMError; end
  class ServiceRegistrationError < VMError; end
  class ServiceRegistrySealed < ServiceRegistrationError; end

  class FlatMemory
    attr_reader :size

    def initialize(size)
      raise ArgumentError, "memory size must be positive" unless size.positive?

      @size = size
      @data = ("\x00" * size).b
    end

    alias bytesize size

    def check_read(address, length) = check_range(address, length)
    def check_write(address, length) = check_range(address, length)
    def check_fetch(address, length) = check_range(address, length)

    def read(address, length)
      check_read(address, length)
      @data.byteslice(address, length)
    end

    def write(address, bytes)
      bytes = bytes.b
      check_write(address, bytes.bytesize)
      @data[address, bytes.bytesize] = bytes
    end

    def program(address, bytes)
      write(address, bytes)
    end

    def fetch(address, length)
      check_fetch(address, length)
      @data.byteslice(address, length)
    end

    def read_u8(address)
      check_read(address, 1)
      @data.getbyte(address)
    end

    def write_u8(address, value)
      check_write(address, 1)
      @data.setbyte(address, value & 0xFF)
    end

    def fetch_u8(address)
      check_fetch(address, 1)
      @data.getbyte(address)
    end

    def clear
      @data.replace(("\x00" * size).b)
    end

    # Temporary String compatibility for dictionary/compiler migration.
    def getbyte(address) = @data.getbyte(address)
    def setbyte(address, value) = @data.setbyte(address, value)
    def byteslice(*args) = @data.byteslice(*args)
    def [](*args) = @data[*args]
    def []=(*args)
      @data.send(:[]=, *args)
    end
    def replace(bytes) = @data.replace(bytes)

    private

    def check_range(address, length)
      return if address >= 0 && length >= 0 && address + length <= size

      raise MemoryFault,
            format("memory range 0x%08X..0x%08X is invalid", address, address + length)
    end
  end

  class MemoryRegion
    attr_reader :name, :start, :size, :permissions, :data

    def initialize(name:, start:, size:, permissions:, programmable: false)
      raise ArgumentError, "memory region name must not be empty" if name.to_s.empty?
      raise ArgumentError, "memory region start/size is invalid" if start.negative? || !size.positive?
      chars = permissions.chars
      unless !chars.empty? && (chars - %w[r w x]).empty? && chars.uniq.length == chars.length
        raise ArgumentError, "memory region permissions must use unique r, w, and/or x"
      end

      @name = name.to_s
      @start = start
      @size = size
      @permissions = permissions
      @programmable = programmable
      @sealed = false
      @read_only_sealed = false
      @write_protected = false
      @write_authorities = []
      @data = ("\x00" * size).b
    end

    def end_address = start + size
    def programmable? = @programmable
    def sealed? = @sealed
    def read_only_sealed? = @read_only_sealed
    def write_protected? = @write_protected

    def protect_writes!(authorities)
      raise MemoryFault, "memory region #{name.inspect} writes are already protected" if write_protected?
      raise MemoryFault, "memory region #{name.inspect} is not writable" unless permissions.include?("w")

      raise ArgumentError, "write authority must not be null" if authorities.any?(&:nil?)
      tokens = authorities.uniq(&:object_id)
      raise ArgumentError, "at least one write authority is required" if tokens.empty?

      @write_authorities = tokens
      @write_protected = true
    end

    def permits_write_authority?(authority)
      @write_authorities.any? { |token| token.equal?(authority) }
    end

    def seal_executable!
      return if sealed?

      @permissions = permissions.include?("r") ? "rx" : "x"
      @programmable = false
      @sealed = true
    end

    def seal_read_only!
      return if read_only_sealed?
      raise MemoryFault, "memory region #{name.inspect} is not readable" unless permissions.include?("r")

      @permissions = "r"
      @programmable = false
      @read_only_sealed = true
    end
  end

  class RegionMemory
    attr_reader :size, :regions

    def initialize(size, regions)
      raise ArgumentError, "memory size must be positive" unless size.positive?

      @size = size
      @regions = regions.sort_by(&:start)
      @active_write_authorities = []
      raise ArgumentError, "at least one memory region is required" if @regions.empty?
      unless @regions.map(&:name).uniq.length == @regions.length
        raise ArgumentError, "memory region names must be unique"
      end
      previous_end = 0
      @regions.each_with_index do |region, index|
        raise ArgumentError, "memory region #{region.name.inspect} is outside the map" if region.end_address > size
        raise ArgumentError, "memory regions must not overlap" if index.positive? && region.start < previous_end

        previous_end = region.end_address
      end
    end

    alias bytesize size

    def check_read(address, length) = resolve(address, length, "r")
    def check_write(address, length)
      region = resolve(address, length, "w")
      check_write_authority(address, length, region)
      region
    end
    def check_fetch(address, length) = resolve(address, length, "x")

    def read(address, length)
      region = resolve(address, length, "r")
      return "".b if region.nil?

      region.data.byteslice(address - region.start, length)
    end

    def write(address, bytes)
      bytes = bytes.b
      region = resolve(address, bytes.bytesize, "w")
      return if region.nil?

      check_write_authority(address, bytes.bytesize, region)
      region.data[address - region.start, bytes.bytesize] = bytes
    end

    def program(address, bytes)
      bytes = bytes.b
      region = resolve_containing(address, bytes.bytesize)
      return if region.nil?
      unless region.permissions.include?("w") || region.programmable?
        permission_fault(address, bytes.bytesize, region, "program")
      end

      check_write_authority(address, bytes.bytesize, region)
      region.data[address - region.start, bytes.bytesize] = bytes
    end

    def protect_region_writes(name, authorities)
      region = regions.find { |item| item.name == name.to_s }
      raise MemoryFault, "memory region #{name.inspect} does not exist" if region.nil?

      region.protect_writes!(authorities)
    end

    def with_authorized_writes(name, authority)
      region = regions.find { |item| item.name == name.to_s }
      raise MemoryFault, "memory region #{name.inspect} does not exist" if region.nil?
      unless region.write_protected? && region.permits_write_authority?(authority)
        raise MemoryFault, "memory region #{name.inspect} rejects write authority"
      end

      marker = [region, authority]
      @active_write_authorities << marker
      begin
        yield
      ensure
        unless @active_write_authorities.last.equal?(marker)
          raise "authorized write scope is unbalanced"
        end
        @active_write_authorities.pop
      end
    end

    def seal_executable_region(name)
      region = regions.find { |item| item.name == name }
      raise MemoryFault, "memory region #{name.inspect} does not exist" if region.nil?

      region.seal_executable!
    end

    def seal_read_only_region(name)
      region = regions.find { |item| item.name == name.to_s }
      raise MemoryFault, "memory region #{name.inspect} does not exist" if region.nil?

      region.seal_read_only!
    end

    def fetch(address, length)
      region = resolve(address, length, "x")
      return "".b if region.nil?

      region.data.byteslice(address - region.start, length)
    end

    def read_u8(address) = read(address, 1).getbyte(0)
    def write_u8(address, value) = write(address, [value & 0xFF].pack("C"))
    def fetch_u8(address) = fetch(address, 1).getbyte(0)

    def clear
      sealed = regions.find(&:sealed?)
      unless sealed.nil?
        raise MemoryFault, "sealed region #{sealed.name.inspect} cannot be cleared"
      end
      read_only = regions.find(&:read_only_sealed?)
      unless read_only.nil?
        raise MemoryFault, "read-only region #{read_only.name.inspect} cannot be cleared"
      end
      protected = regions.find(&:write_protected?)
      unless protected.nil?
        raise MemoryFault, "protected region #{protected.name.inspect} cannot be cleared"
      end
      regions.each { |region| region.data.replace(("\x00" * region.size).b) }
    end

    def region_bytes(name)
      region = regions.find { |candidate| candidate.name == name.to_s }
      raise KeyError, name if region.nil?

      region.data.dup
    end

    # Temporary String compatibility for dictionary/compiler migration.
    def getbyte(address) = read_u8(address)
    def setbyte(address, value) = write_u8(address, value)
    def byteslice(address, length) = read(address, length)

    def [](*args)
      return read_u8(args[0]) if args.length == 1
      return read(args[0], args[1]) if args.length == 2

      raise ArgumentError, "invalid memory index"
    end

    def []=(*args)
      if args.length == 2
        write_u8(args[0], args[1])
      elsif args.length == 3
        address, length, bytes = args
        bytes = bytes.b
        raise ArgumentError, "memory slice assignment cannot resize a region" unless bytes.bytesize == length

        write(address, bytes)
      else
        raise ArgumentError, "invalid memory assignment"
      end
    end

    private

    def resolve(address, length, permission)
      region = resolve_containing(address, length)
      unless region.nil? || region.permissions.include?(permission)
        operation = { "r" => "read", "w" => "write", "x" => "fetch" }.fetch(permission)
        permission_fault(address, length, region, operation)
      end
      region
    end

    def resolve_containing(address, length)
      check_logical_range(address, length)
      return nil if length.zero?

      finish = address + length
      region = regions.find { |candidate| address >= candidate.start && finish <= candidate.end_address }
      return region unless region.nil?

      raise MemoryFault,
            format("memory range 0x%08X..0x%08X is unmapped or crosses a region", address, finish)
    end

    def check_logical_range(address, length)
      return if address >= 0 && length >= 0 && address + length <= size

      raise MemoryFault,
            format("memory range 0x%08X..0x%08X is invalid", address, address + length)
    end

    def check_write_authority(address, length, region)
      return if region.nil? || !region.write_protected?

      authorized = @active_write_authorities.any? do |active_region, authority|
        active_region.equal?(region) && region.permits_write_authority?(authority)
      end
      permission_fault(address, length, region, "protected write") unless authorized
    end

    def permission_fault(address, length, region, operation)
      raise MemoryFault,
            format("memory region %p denies %s at 0x%08X..0x%08X",
                   region.name, operation, address, address + length)
    end
  end

  LoopFrame = Struct.new(:limit, :index)

  def self.cell(value)
    value & CELL_MASK
  end

  def self.signed(value)
    value = cell(value)
    (value & SIGN_BIT).zero? ? value : value - (1 << CELL_BITS)
  end

  class VM
    attr_reader :memory, :memory_size, :ip, :data_stack, :return_stack, :loop_stack, :steps,
                :max_data_depth, :max_return_depth, :max_loop_depth,
                :verified_boundaries, :verified_code_start, :verified_code_end

    def initialize(
      memory_size: DEFAULT_MEMORY_SIZE,
      max_data_depth: DEFAULT_DATA_STACK_DEPTH,
      max_return_depth: DEFAULT_RETURN_STACK_DEPTH,
      max_loop_depth: DEFAULT_LOOP_STACK_DEPTH,
      allow_defer_store: false,
      memory_bus: nil
    )
      raise ArgumentError, "memory size must be positive" unless memory_size.positive?
      unless [max_data_depth, max_return_depth, max_loop_depth].all?(&:positive?)
        raise ArgumentError, "stack depths must be positive"
      end

      @memory_size = memory_size
      @max_data_depth = max_data_depth
      @max_return_depth = max_return_depth
      @max_loop_depth = max_loop_depth
      @allow_defer_store = allow_defer_store
      @verified_boundaries = nil
      @verified_code_start = nil
      @verified_code_end = nil
      @service_registry_sealed = false
      @allowed_service_ids = nil
      @service_handlers = {}
      @memory = memory_bus || FlatMemory.new(memory_size)
      unless @memory.size == memory_size
        raise ArgumentError, "memory bus size does not match memory_size"
      end
      reset
    end

    def reset(clear_memory: false)
      @ip = 0
      @data_stack = []
      @return_stack = []
      @loop_stack = []
      @halted = false
      @steps = 0
      @memory.clear if clear_memory
    end

    def load(program, address: 0)
      program = program.b
      @memory.program(address, program)
      @ip = address
    end

    def halted? = @halted
    def allow_defer_store? = @allow_defer_store
    def lock_defer_store = @allow_defer_store = false
    def service_registry_sealed? = @service_registry_sealed
    def registered_service_ids = @service_handlers.keys.sort.freeze

    def register_service(service_id, handler = nil, &block)
      if service_registry_sealed? || !verified_boundaries.nil?
        raise ServiceRegistrySealed, "service registry is sealed"
      end
      unless service_id.is_a?(Integer) && service_id.between?(1, CELL_MASK)
        raise ServiceRegistrationError, "service id must be a nonzero Reference32 integer"
      end
      callable = handler || block
      unless callable.respond_to?(:call)
        raise ServiceRegistrationError, "service handler must be callable"
      end
      if @service_handlers.key?(service_id)
        raise ServiceRegistrationError, "service id #{service_id} is already registered"
      end

      @service_handlers[service_id] = callable
    end

    def seal_verified_execution(verification, code_region: "CODE", extra_entries: [])
      unless verified_boundaries.nil?
        raise ExecutionPolicyError, "verified execution policy is already sealed"
      end
      unless verification.is_a?(Hash)
        raise ExecutionPolicyError, "verification summary must be a Hash"
      end
      field = lambda do |name|
        verification.key?(name) ? verification[name] : verification[name.to_s]
      end
      boundaries_raw = field.call(:boundaries)
      code_start = field.call(:code_start)
      code_end = field.call(:code_end)
      boundary_count = field.call(:boundary_count)
      service_ids_raw = field.call(:service_ids) || []
      unless boundaries_raw.is_a?(Array) && code_start.is_a?(Integer) &&
             code_end.is_a?(Integer) && code_end >= code_start &&
             boundary_count == boundaries_raw.length
        raise ExecutionPolicyError, "verification summary is malformed"
      end
      valid_service_ids = service_ids_raw.is_a?(Array) && service_ids_raw.all? do |service_id|
        service_id.is_a?(Integer) && service_id.between?(1, CELL_MASK)
      end
      unless valid_service_ids
        raise ExecutionPolicyError, "verified service IDs are malformed"
      end
      if service_ids_raw.uniq.length != service_ids_raw.length
        raise ExecutionPolicyError, "verified service IDs contain duplicates"
      end
      missing_services = service_ids_raw.reject { |service_id| @service_handlers.key?(service_id) }
      unless missing_services.empty?
        raise ExecutionPolicyError,
              "required service id #{missing_services.min} is not registered"
      end
      boundaries = {}
      boundaries_raw.each do |address|
        unless address.is_a?(Integer) && address >= code_start && address < code_end
          raise ExecutionPolicyError, "verified boundary is outside CODE"
        end
        boundaries[address] = true
      end
      if boundaries.length != boundaries_raw.length
        raise ExecutionPolicyError, "verified boundaries contain duplicates"
      end
      extra_entries.each do |address|
        raise ExecutionPolicyError, "extra execution entry must be an Integer" unless address.is_a?(Integer)

        memory.check_fetch(address, 1)
        boundaries[address] = true
      end
      unless memory.respond_to?(:seal_executable_region)
        raise ExecutionPolicyError,
              "verified execution sealing requires protected RegionMemory"
      end
      memory.seal_executable_region(code_region)
      @verified_boundaries = boundaries.freeze
      @verified_code_start = code_start
      @verified_code_end = code_end
      @allowed_service_ids = service_ids_raw.to_h { |service_id| [service_id, true] }.freeze
      @service_registry_sealed = true
    end

    def run(max_steps: 100_000)
      start_steps = @steps
      until @halted
        if @steps - start_steps >= max_steps
          raise StepLimitExceeded, "step limit #{max_steps} exceeded"
        end

        step
      end
      @data_stack.dup
    end

    def resume(address, return_to: nil, max_steps: 100_000)
      jump(address)
      unless return_to.nil?
        check_execution_target(return_to)
        @memory.check_fetch(return_to, 1)
        push_return(return_to)
      end
      @halted = false
      run(max_steps: max_steps)
    end

    def step
      opcode_address = @ip
      check_execution_target(opcode_address)
      op = read_opcode_u8
      unless Op::ALL.include?(op)
        raise InvalidOpcode, format("invalid opcode 0x%02X at 0x%08X", op, opcode_address)
      end

      @steps += 1

      case op
      when Op::NOP then nil
      when Op::LIT then push(read_immediate_cell)
      when Op::CALL
        target = read_immediate_cell
        push_return(@ip)
        jump(target)
      when Op::ICALL
        slot_address = read_immediate_cell
        target_xt = read_cell(slot_address)
        if target_xt.zero?
          raise UnassignedDefer, format("unassigned DEFER slot at 0x%08X", slot_address)
        end
        target_kind = read_cell(target_xt)
        unless target_kind == 1
          raise InvalidIndirectCall, format("indirect XT 0x%08X is not a colon word", target_xt)
        end
        target = read_cell(target_xt + CELL_BYTES)
        push_return(@ip)
        jump(target)
      when Op::DSET
        slot_address = read_immediate_cell
        unless @allow_defer_store
          raise DeferStoreDenied, "compiled IS is disabled in this VM profile"
        end
        require_data(1)
        if slot_address < CELL_BYTES || read_cell(slot_address - CELL_BYTES) != 7
          raise InvalidIndirectCall, format("DEFER store slot 0x%08X is invalid", slot_address)
        end
        target_xt = @data_stack[-1]
        if target_xt.zero? || read_cell(target_xt) != 1
          raise InvalidIndirectCall,
                format("DEFER target XT 0x%08X is not a colon word", target_xt)
        end
        target = read_cell(target_xt + CELL_BYTES)
        check_execution_target(target)
        @memory.check_fetch(target, 1)
        @memory.check_write(slot_address, CELL_BYTES)
        pop
        write_cell(slot_address, target_xt)
      when Op::SERVICE
        invoke_service(read_immediate_cell)
      when Op::EXIT
        raise StackUnderflow, "return stack underflow in EXIT" if @return_stack.empty?

        jump(@return_stack.pop)
      when Op::BRANCH then jump(read_immediate_cell)
      when Op::ZBRANCH
        target = read_immediate_cell
        jump(target) if pop.zero?
      when Op::FETCH
        require_data(1)
        value = read_cell(@data_stack[-1])
        pop
        push(value)
      when Op::STORE
        require_data(2)
        address = @data_stack[-1]
        @memory.check_write(address, CELL_BYTES)
        address = pop
        value = pop
        write_cell(address, value)
      when Op::DROP then pop
      when Op::DUP
        require_data(1)
        push(@data_stack[-1])
      when Op::SWAP
        require_data(2)
        @data_stack[-1], @data_stack[-2] = @data_stack[-2], @data_stack[-1]
      when Op::OVER
        require_data(2)
        push(@data_stack[-2])
      when Op::ADD then binary { |left, right| left + right }
      when Op::SUB then binary { |left, right| left - right }
      when Op::MUL then binary { |left, right| left * right }
      when Op::AND then binary { |left, right| left & right }
      when Op::OR then binary { |left, right| left | right }
      when Op::XOR then binary { |left, right| left ^ right }
      when Op::LESS
        binary { |left, right| Min0CoreForth.signed(left) < Min0CoreForth.signed(right) ? CELL_MASK : 0 }
      when Op::EQUAL then binary { |left, right| left == right ? CELL_MASK : 0 }
      when Op::HALT then @halted = true
      when Op::DO
        require_data(2)
        require_loop_capacity
        start = pop
        limit = pop
        push_loop(limit, start)
      when Op::LOOP
        target = read_immediate_cell
        frame = current_loop
        frame.index = Min0CoreForth.cell(frame.index + 1)
        if frame.index == frame.limit
          @loop_stack.pop
        else
          jump(target)
        end
      when Op::I then push(current_loop.index)
      when Op::UNLOOP
        current_loop
        @loop_stack.pop
      when Op::PLOOP
        target = read_immediate_cell
        require_data(1)
        frame = current_loop
        increment = Min0CoreForth.signed(pop)
        old_delta = Min0CoreForth.signed(frame.index - frame.limit)
        frame.index = Min0CoreForth.cell(frame.index + increment)
        new_delta = Min0CoreForth.signed(frame.index - frame.limit)
        crossed = (increment.positive? && old_delta.negative? && new_delta >= 0) ||
                  (increment.negative? && old_delta.positive? && new_delta <= 0)
        if crossed
          @loop_stack.pop
        else
          jump(target)
        end
      when Op::J
        raise LoopStackUnderflow, "J requires two active loop frames" if @loop_stack.length < 2

        push(@loop_stack[-2].index)
      when Op::QDO
        target = read_immediate_cell
        require_data(2)
        start = @data_stack[-1]
        limit = @data_stack[-2]
        require_loop_capacity unless start == limit
        start = pop
        limit = pop
        if start == limit
          jump(target)
        else
          push_loop(limit, start)
        end
      when Op::LEAVE
        target = read_immediate_cell
        current_loop
        @loop_stack.pop
        jump(target)
      when Op::CELL_PLUS then push(pop + CELL_BYTES)
      when Op::CELLS then push(pop * CELL_BYTES)
      when Op::ALIGNED then push((pop + CELL_BYTES - 1) & ~(CELL_BYTES - 1))
      when Op::C_FETCH
        require_data(1)
        address = @data_stack[-1]
        @memory.check_read(address, 1)
        value = @memory.read_u8(address)
        pop
        push(value)
      when Op::C_STORE
        require_data(2)
        address = @data_stack[-1]
        @memory.check_write(address, 1)
        address = pop
        value = pop
        @memory.write_u8(address, value)
      when Op::CHAR_PLUS then push(pop + 1)
      when Op::CHARS then require_data(1)
      end
    end

    def push(value)
      if @data_stack.length >= max_data_depth
        raise DataStackOverflow, "data stack limit #{max_data_depth} cell(s) exceeded"
      end
      @data_stack << Min0CoreForth.cell(value)
    end

    def pop
      require_data(1)
      @data_stack.pop
    end

    def read_cell(address)
      @memory.read(address, CELL_BYTES).unpack1("V")
    end

    def write_cell(address, value)
      @memory.write(address, [Min0CoreForth.cell(value)].pack("V"))
    end

    def read_u8(address)
      @memory.read_u8(address)
    end

    def write_u8(address, value)
      @memory.write_u8(address, value)
    end

    def read_bytes(address, length)
      @memory.read(address, length)
    end

    def write_bytes(address, bytes)
      @memory.write(address, bytes)
    end

    def fill_bytes(address, length, value = 0)
      raise ArgumentError, "fill byte must be in range 0..255" unless value.between?(0, 0xFF)

      @memory.write(address, ([value].pack("C") * length).b)
    end

    private

    def binary
      require_data(2)
      right = pop
      left = pop
      push(yield(left, right))
    end

    def read_opcode_u8
      value = @memory.fetch_u8(@ip)
      @ip += 1
      value
    end

    def read_immediate_cell
      value = @memory.fetch(@ip, CELL_BYTES).unpack1("V")
      @ip += CELL_BYTES
      value
    end

    def jump(address)
      check_execution_target(address)
      @memory.check_fetch(address, 1)
      @ip = address
    end

    def check_execution_target(address)
      return if verified_boundaries.nil?
      return if verified_boundaries.key?(address)

      raise InvalidExecutionTarget,
            format("address 0x%08X is not a verified instruction boundary", address)
    end

    def invoke_service(service_id)
      if service_registry_sealed? && !@allowed_service_ids.key?(service_id)
        raise UnknownService, "service id #{service_id} is not allowed by verified CODE"
      end
      handler = @service_handlers[service_id]
      raise UnknownService, "service id #{service_id} is not registered" if handler.nil?

      handler.call
    end

    def require_data(count)
      return if @data_stack.length >= count

      raise StackUnderflow, "data stack needs #{count} cell(s), has #{@data_stack.length}"
    end

    def push_return(value)
      if @return_stack.length >= max_return_depth
        raise ReturnStackOverflow, "return stack limit #{max_return_depth} cell(s) exceeded"
      end
      @return_stack << Min0CoreForth.cell(value)
    end

    def push_loop(limit, index)
      require_loop_capacity
      @loop_stack << LoopFrame.new(Min0CoreForth.cell(limit), Min0CoreForth.cell(index))
    end

    def require_loop_capacity
      return if @loop_stack.length < max_loop_depth

      raise LoopStackOverflow, "loop stack limit #{max_loop_depth} frame(s) exceeded"
    end

    def current_loop
      raise LoopStackUnderflow, "loop stack is empty" if @loop_stack.empty?

      @loop_stack.last
    end

    def check_range(address, size)
      @memory.check_read(address, size)
    end
  end

  class Assembler
    attr_reader :labels

    def initialize
      @code = +"".b
      @labels = {}
      @fixups = []
    end

    def address
      @code.bytesize
    end

    def label(name)
      raise ArgumentError, "duplicate label #{name.inspect}" if @labels.key?(name)

      @labels[name] = address
    end

    def emit(op, operand = :absent)
      @code << [op].pack("C")
      if operand == :absent
        raise ArgumentError, "opcode 0x#{op.to_s(16)} requires an operand" if Op::OPERAND_OPS.include?(op)
        return
      end

      unless Op::OPERAND_OPS.include?(op)
        raise ArgumentError, "opcode 0x#{op.to_s(16)} does not accept an operand"
      end

      if operand.is_a?(String) || operand.is_a?(Symbol)
        @fixups << [address, operand.to_s]
        value = 0
      else
        value = operand
      end
      @code << [Min0CoreForth.cell(value)].pack("V")
    end

    def build
      result = @code.dup
      @fixups.each do |offset, name|
        raise ArgumentError, "unknown label #{name.inspect}" unless @labels.key?(name)

        result[offset, CELL_BYTES] = [@labels.fetch(name)].pack("V")
      end
      result
    end
  end
end
