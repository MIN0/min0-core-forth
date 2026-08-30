# frozen_string_literal: true

require_relative "min0_core_forth_vm"

module Min0CoreForth
  DICTIONARY_BASE = 0x8000
  DICTIONARY_ALIGNMENT = 4
  MAX_NAME_BYTES = 31

  FLAG_IMMEDIATE = 0x01
  FLAG_HIDDEN = 0x02

  KIND_PRIMITIVE = 0
  KIND_COLON = 1
  KIND_CONSTANT = 2
  KIND_VARIABLE = 3
  KIND_CREATED = 4
  KIND_DOES = 5
  KIND_DEFINER = 6
  KIND_DEFER = 7

  DOES_DESCRIPTOR_BYTES = 8
  DEFINER_DESCRIPTOR_BYTES = 8
  CONSTRUCTOR_PLAN_MAGIC = 0x4E4C5043
  CONSTRUCTOR_PLAN_VERSION = 1
  CONSTRUCTOR_ACTION_END = 0
  CONSTRUCTOR_ACTION_COMMA = 1
  CONSTRUCTOR_ACTION_C_COMMA = 2
  CONSTRUCTOR_ACTION_ALLOT = 3
  CONSTRUCTOR_ACTION_ALIGN = 4
  CONSTRUCTOR_ACTIONS = [
    CONSTRUCTOR_ACTION_END, CONSTRUCTOR_ACTION_COMMA, CONSTRUCTOR_ACTION_C_COMMA,
    CONSTRUCTOR_ACTION_ALLOT, CONSTRUCTOR_ACTION_ALIGN
  ].freeze

  class DictionaryError < StandardError; end
  class DictionaryFull < DictionaryError; end
  class InvalidDictionary < DictionaryError; end

  DictionaryEntry = Data.define(
    :header_address,
    :link,
    :flags,
    :name,
    :xt,
    :kind,
    :payload
  ) do
    def immediate?
      (flags & FLAG_IMMEDIATE) != 0
    end

    def hidden?
      (flags & FLAG_HIDDEN) != 0
    end
  end

  class RuntimeDictionary
    attr_reader :vm, :base, :limit, :body_base, :body_limit, :here, :latest

    def initialize(vm, base: DICTIONARY_BASE, limit: nil, body_base: nil, body_limit: nil)
      @vm = vm
      @base = base
      @limit = limit || vm.memory_size
      unless base.positive? && (base % DICTIONARY_ALIGNMENT).zero?
        raise DictionaryError, "dictionary base must be nonzero and 4-byte aligned"
      end
      if @limit < base || @limit > vm.memory_size
        raise DictionaryError, "dictionary limit is outside VM memory"
      end

      @here = base
      @split_body = !body_base.nil?
      if @split_body
        @body_base = body_base
        @body_limit = body_limit || vm.memory_size
        unless body_base >= 0 && (body_base % DICTIONARY_ALIGNMENT).zero?
          raise DictionaryError, "body base must be 4-byte aligned"
        end
        if @body_limit < body_base || @body_limit > vm.memory_size
          raise DictionaryError, "body limit is outside VM memory"
        end
        unless @body_limit <= base || body_base >= @limit
          raise DictionaryError, "dictionary header and body ranges overlap"
        end
        @body_here = body_base
      else
        raise DictionaryError, "body_limit requires body_base" unless body_limit.nil?

        @body_base = base
        @body_limit = @limit
        @body_here = base
      end
      @latest = 0
      @defer_authority = nil
      @runtime_structure_sealed = false
      @dictionary_region_name = nil
      @defer_write_authority = nil
    end

    def split_body? = @split_body
    def data_here = split_body? ? @body_here : here

    def add_primitive(name, opcode, immediate: false, hidden: false)
      require_structure_mutable
      value = Integer(opcode)
      raise DictionaryError, format("invalid primitive opcode 0x%02X", value) unless Op::ALL.include?(value)

      add(name, kind: KIND_PRIMITIVE, payload: value, immediate: immediate, hidden: hidden)
    end

    def add_colon(name, code_address, immediate: false, hidden: false)
      require_structure_mutable
      unless code_address >= 0 && code_address < vm.memory_size
        raise DictionaryError, "colon code address is outside VM memory"
      end

      add(name, kind: KIND_COLON, payload: code_address, immediate: immediate, hidden: hidden)
    end

    def add_constant(name, value, immediate: false, hidden: false)
      require_structure_mutable
      add(name, kind: KIND_CONSTANT, payload: value, immediate: immediate, hidden: hidden)
    end

    def add_defer(name, target = nil, immediate: false, hidden: false)
      require_structure_mutable
      require_defer_authority(nil)
      target_xt = target.nil? ? 0 : defer_xt_target(target)
      add(
        name, kind: KIND_DEFER, payload: target_xt,
        immediate: immediate, hidden: hidden
      )
    end

    def set_defer(entry, target, authorization: nil)
      require_defer_authority(authorization)
      current = read_entry(entry.header_address)
      raise DictionaryError, "IS requires a DEFER word" unless current.kind == KIND_DEFER

      target_xt = defer_xt_target(target)
      if runtime_structure_sealed?
        vm.memory.with_authorized_writes(@dictionary_region_name, @defer_write_authority) do
          vm.memory.check_write(current.xt + 4, CELL_BYTES)
          vm.write_cell(current.xt + 4, target_xt)
        end
      else
        vm.memory.check_write(current.xt + 4, CELL_BYTES)
        vm.write_cell(current.xt + 4, target_xt)
      end
      read_entry(current.header_address)
    end

    def runtime_structure_sealed? = @runtime_structure_sealed

    def seal_runtime_structure(region_name = "DICTIONARY")
      if runtime_structure_sealed?
        raise DictionaryError, "runtime dictionary structure is already sealed"
      end
      memory = vm.memory
      unless memory.respond_to?(:protect_region_writes) &&
             memory.respond_to?(:with_authorized_writes) && memory.respond_to?(:regions)
        raise DictionaryError, "runtime dictionary sealing requires protected RegionMemory"
      end
      region = memory.regions.find { |item| item.name == region_name.to_s }
      if region.nil? || base < region.start || limit > region.end_address
        raise DictionaryError, "dictionary allocator is outside protected region"
      end
      token = Object.new
      memory.protect_region_writes(region_name, [token])
      @dictionary_region_name = region_name.to_s
      @defer_write_authority = token
      @runtime_structure_sealed = true
    end

    def lock_defer_updates(authorization)
      raise DictionaryError, "DEFER authorization marker must not be null" if authorization.nil?
      raise DictionaryError, "DEFER updates are already controlled" unless @defer_authority.nil?

      @defer_authority = authorization
    end

    def read_defer_target(entry)
      current = read_entry(entry.header_address)
      raise DictionaryError, "word is not DEFERred" unless current.kind == KIND_DEFER

      unless current.payload.zero?
        target = entry_for_xt(current.payload)
        unless target.kind == KIND_COLON
          raise InvalidDictionary, "DEFER target XT is not a colon word"
        end
        begin
          vm.memory.check_fetch(target.payload, 1)
        rescue StandardError
          raise InvalidDictionary, "DEFER target is not executable"
        end
      end
      current.payload
    end

    def entry_for_xt(xt)
      entry = entries(include_hidden: true).find { |candidate| candidate.xt == xt }
      raise InvalidDictionary, format("unknown execution token 0x%08X", xt) if entry.nil?

      entry
    end

    def add_variable(name, immediate: false, hidden: false)
      require_structure_mutable
      saved_here = here
      saved_data_here = data_here
      saved_latest = latest
      begin
        data_address = split_body? ? align_here : data_field_address(name)
        entry = add(
          name,
          kind: KIND_VARIABLE,
          payload: data_address,
          immediate: immediate,
          hidden: hidden
        )
        raise "variable data-field address mismatch" unless comma(0) == data_address

        entry
      rescue StandardError
        restore(here: saved_here, latest: saved_latest, data_here: saved_data_here)
        raise
      end
    end

    def add_created(name, immediate: false, hidden: false)
      require_structure_mutable
      saved_here = here
      saved_data_here = data_here
      saved_latest = latest
      begin
        payload = split_body? ? align_here : data_field_address(name)
        add(
          name,
          kind: KIND_CREATED,
          payload: payload,
          immediate: immediate,
          hidden: hidden
        )
      rescue StandardError
        restore(here: saved_here, latest: saved_latest, data_here: saved_data_here)
        raise
      end
    end

    def set_does(entry, code_address)
      require_structure_mutable
      current = read_entry(entry.header_address)
      unless current.kind == KIND_CREATED
        raise DictionaryError, "DOES behavior requires a CREATEd word"
      end
      unless code_address >= 0 && code_address < vm.memory_size
        raise DictionaryError, "DOES code address is outside VM memory"
      end
      begin
        vm.memory.check_fetch(code_address, 1)
      rescue StandardError => error
        raise DictionaryError, "DOES code address is not executable", cause: error
      end

      descriptor = self.class.align(here)
      next_here = descriptor + DOES_DESCRIPTOR_BYTES
      if next_here > limit
        raise DictionaryFull, format("DOES descriptor exceeds limit 0x%08X", limit)
      end

      vm.memory.check_write(here, next_here - here)
      vm.memory.check_write(current.xt, 8)
      old_here = here
      old_xt = vm.read_bytes(current.xt, 8)
      old_descriptor = vm.read_bytes(old_here, next_here - old_here)
      begin
        vm.fill_bytes(old_here, descriptor - old_here)
        vm.write_cell(descriptor, current.payload)
        vm.write_cell(descriptor + 4, code_address)
        vm.write_cell(current.xt, KIND_DOES)
        vm.write_cell(current.xt + 4, descriptor)
        @here = next_here
        read_entry(current.header_address)
      rescue StandardError
        vm.write_bytes(current.xt, old_xt)
        vm.write_bytes(old_here, old_descriptor)
        @here = old_here
        raise
      end
    end

    def read_does_descriptor(entry)
      current = read_entry(entry.header_address)
      raise DictionaryError, "word has no DOES descriptor" unless current.kind == KIND_DOES

      descriptor = current.payload
      unless descriptor >= base && (descriptor % DICTIONARY_ALIGNMENT).zero? &&
             descriptor + DOES_DESCRIPTOR_BYTES <= here
        raise InvalidDictionary, "invalid DOES descriptor address"
      end
      body_address = vm.read_cell(descriptor)
      code_address = vm.read_cell(descriptor + 4)
      begin
        vm.memory.check_fetch(code_address, 1)
      rescue StandardError => error
        raise InvalidDictionary, "DOES code address is not executable", cause: error
      end
      [body_address, code_address]
    end

    def set_definer(entry, constructor_steps, behavior_address = 0)
      require_structure_mutable
      current = read_entry(entry.header_address)
      unless current.kind == KIND_COLON
        raise DictionaryError, "defining-word metadata requires a colon word"
      end
      steps = if constructor_steps.is_a?(Integer)
                [[constructor_steps, CONSTRUCTOR_ACTION_END]]
              else
                constructor_steps.map(&:dup)
              end
      raise DictionaryError, "constructor plan must contain at least one step" if steps.empty?
      steps.each_with_index do |(address, action), index|
        unless address >= 0 && address < vm.memory_size
          raise DictionaryError, "constructor code address is outside VM memory"
        end
        begin
          vm.memory.check_fetch(address, 1)
        rescue StandardError => error
          raise DictionaryError, "constructor code address is not executable", cause: error
        end
        raise DictionaryError, "unknown constructor action #{action}" unless CONSTRUCTOR_ACTIONS.include?(action)
        unless (action == CONSTRUCTOR_ACTION_END) == (index == steps.length - 1)
          raise DictionaryError, "constructor END must be the final plan action"
        end
      end
      unless behavior_address.zero?
        unless behavior_address >= 0 && behavior_address < vm.memory_size
          raise DictionaryError, "definer behavior address is outside VM memory"
        end
        begin
          vm.memory.check_fetch(behavior_address, 1)
        rescue StandardError => error
          raise DictionaryError, "definer behavior address is not executable", cause: error
        end
      end

      plan = self.class.align(here)
      plan_bytes = 12 + steps.length * 8
      descriptor = self.class.align(plan + plan_bytes)
      next_here = descriptor + DEFINER_DESCRIPTOR_BYTES
      if next_here > limit
        raise DictionaryFull, format("constructor plan exceeds limit 0x%08X", limit)
      end
      vm.memory.check_write(here, next_here - here)
      vm.memory.check_write(current.xt, 8)
      old_here = here
      old_xt = vm.read_bytes(current.xt, 8)
      old_metadata = vm.read_bytes(old_here, next_here - old_here)
      begin
        vm.fill_bytes(old_here, plan - old_here)
        vm.write_cell(plan, CONSTRUCTOR_PLAN_MAGIC)
        vm.write_cell(plan + 4, CONSTRUCTOR_PLAN_VERSION)
        vm.write_cell(plan + 8, steps.length)
        cursor = plan + 12
        steps.each do |code_address, action|
          vm.write_cell(cursor, code_address)
          vm.write_cell(cursor + 4, action)
          cursor += 8
        end
        vm.fill_bytes(cursor, descriptor - cursor)
        vm.write_cell(descriptor, plan)
        vm.write_cell(descriptor + 4, behavior_address)
        vm.write_cell(current.xt, KIND_DEFINER)
        vm.write_cell(current.xt + 4, descriptor)
        @here = next_here
        read_entry(current.header_address)
      rescue StandardError
        vm.write_bytes(current.xt, old_xt)
        vm.write_bytes(old_here, old_metadata)
        @here = old_here
        raise
      end
    end

    def read_definer_descriptor(entry)
      current = read_entry(entry.header_address)
      raise DictionaryError, "word has no definer descriptor" unless current.kind == KIND_DEFINER

      descriptor = current.payload
      unless descriptor >= base && (descriptor % DICTIONARY_ALIGNMENT).zero? &&
             descriptor + DEFINER_DESCRIPTOR_BYTES <= here
        raise InvalidDictionary, "invalid definer descriptor address"
      end
      plan_address = vm.read_cell(descriptor)
      behavior_address = vm.read_cell(descriptor + 4)
      read_constructor_plan_at(plan_address, descriptor)
      unless behavior_address.zero?
        begin
          vm.memory.check_fetch(behavior_address, 1)
        rescue StandardError => error
          raise InvalidDictionary, "definer behavior address is not executable", cause: error
        end
      end
      [plan_address, behavior_address]
    end

    def read_constructor_plan(entry)
      current = read_entry(entry.header_address)
      raise DictionaryError, "word has no constructor plan" unless current.kind == KIND_DEFINER

      descriptor = current.payload
      unless descriptor >= base && (descriptor % DICTIONARY_ALIGNMENT).zero? &&
             descriptor + DEFINER_DESCRIPTOR_BYTES <= here
        raise InvalidDictionary, "invalid definer descriptor address"
      end
      read_constructor_plan_at(vm.read_cell(descriptor), descriptor)
    end

    def comma(value)
      address = self.class.align(data_here)
      reserve_to(address + CELL_BYTES)
      vm.write_cell(address, value)
      address
    end

    def c_comma(value)
      address = data_here
      reserve_to(data_here + 1)
      vm.write_u8(address, value)
      address
    end

    def allot(byte_count)
      raise DictionaryError, "ALLOT byte count must be nonnegative in v0.1" if byte_count.negative?

      address = data_here
      reserve_to(data_here + byte_count)
      address
    end

    def align_here
      address = self.class.align(data_here)
      reserve_to(address)
      address
    end

    def find(name, include_hidden: false)
      wanted = encode_name(name)
      address = latest
      visited = {}
      until address.zero?
        raise InvalidDictionary, "dictionary link cycle detected" if visited.key?(address)

        visited[address] = true
        entry = read_entry(address)
        return entry if (include_hidden || !entry.hidden?) && entry.name.b == wanted

        address = entry.link
      end
      nil
    end

    def entries(include_hidden: true)
      result = []
      address = latest
      visited = {}
      until address.zero?
        raise InvalidDictionary, "dictionary link cycle detected" if visited.key?(address)

        visited[address] = true
        entry = read_entry(address)
        result << entry if include_hidden || !entry.hidden?
        address = entry.link
      end
      result
    end

    def read_entry(address)
      unless address >= base && address + 8 <= here && (address % DICTIONARY_ALIGNMENT).zero?
        raise InvalidDictionary, format("invalid dictionary header 0x%08X", address)
      end

      link = vm.read_cell(address)
      flags = vm.read_u8(address + 4)
      name_length = vm.read_u8(address + 5)
      reserved = vm.read_bytes(address + 6, 2).unpack1("v")
      raise InvalidDictionary, "dictionary reserved field is not zero" unless reserved.zero?
      unless name_length.positive? && name_length <= MAX_NAME_BYTES
        raise InvalidDictionary, "invalid dictionary name length #{name_length}"
      end

      name_end = address + 8 + name_length
      xt = self.class.align(name_end)
      raise InvalidDictionary, "dictionary entry extends beyond HERE" if xt + 8 > here

      raw_name = vm.read_bytes(address + 8, name_length)
      raise InvalidDictionary, "dictionary name is not ASCII" unless raw_name.ascii_only?

      name = raw_name.force_encoding(Encoding::US_ASCII)
      kind = vm.read_cell(xt)
      payload = vm.read_cell(xt + 4)
      unless [
        KIND_PRIMITIVE, KIND_COLON, KIND_CONSTANT, KIND_VARIABLE, KIND_CREATED,
        KIND_DOES, KIND_DEFINER, KIND_DEFER
      ].include?(kind)
        raise InvalidDictionary, "unknown dictionary kind #{kind}"
      end

      DictionaryEntry.new(address, link, flags, name, xt, kind, payload)
    end

    def image
      vm.read_bytes(base, here - base)
    end

    def body_image
      vm.read_bytes(body_base, data_here - body_base)
    end

    def load_images(header_image, latest:, body_image: "".b)
      require_structure_mutable
      unless here == base && self.latest.zero? && data_here == body_base
        raise DictionaryError, "dictionary image loading requires an empty dictionary"
      end
      headers = header_image.b
      body = body_image.b
      next_here = base + headers.bytesize
      raise InvalidDictionary, "dictionary image exceeds header limit" if next_here > limit
      if headers.empty? == !latest.zero?
        raise InvalidDictionary, "dictionary image and LATEST disagree"
      end
      if !latest.zero? && !(latest >= base && latest < next_here && (latest % DICTIONARY_ALIGNMENT).zero?)
        raise InvalidDictionary, "dictionary image has invalid LATEST"
      end
      if split_body?
        next_data_here = body_base + body.bytesize
        raise InvalidDictionary, "dictionary image exceeds body limit" if next_data_here > body_limit
      else
        raise InvalidDictionary, "flat dictionary cannot load a separate body image" unless body.empty?

        next_data_here = next_here
      end

      vm.memory.check_write(base, headers.bytesize)
      vm.memory.check_write(body_base, body.bytesize) if split_body?
      old_headers = vm.read_bytes(base, headers.bytesize)
      old_body = split_body? ? vm.read_bytes(body_base, body.bytesize) : "".b
      begin
        vm.write_bytes(base, headers)
        vm.write_bytes(body_base, body) if split_body?
        @here = next_here
        @latest = latest
        @body_here = next_data_here if split_body?
        entries.each do |entry|
          if entry.kind == KIND_DEFINER
            read_definer_descriptor(entry)
          elsif entry.kind == KIND_DOES
            read_does_descriptor(entry)
          elsif entry.kind == KIND_DEFER
            read_defer_target(entry)
          end
        end
      rescue StandardError
        vm.write_bytes(base, old_headers)
        if split_body?
          vm.write_bytes(body_base, old_body)
          @body_here = body_base
        end
        @here = base
        @latest = 0
        raise
      end
    end

    def set_hidden(entry, hidden)
      require_structure_mutable
      current = read_entry(entry.header_address)
      flags = hidden ? current.flags | FLAG_HIDDEN : current.flags & ~FLAG_HIDDEN
      vm.write_u8(current.header_address + 4, flags)
      read_entry(current.header_address)
    end

    def restore(here:, latest:, data_here: nil)
      require_structure_mutable
      unless here >= base && here <= @here
        raise DictionaryError, "invalid dictionary rollback HERE"
      end
      if latest != 0 && !(latest >= base && latest < here && (latest % DICTIONARY_ALIGNMENT).zero?)
        raise DictionaryError, "invalid dictionary rollback LATEST"
      end
      if split_body?
        raise DictionaryError, "split dictionary rollback requires data HERE" if data_here.nil?
        unless data_here >= body_base && data_here <= self.data_here
          raise DictionaryError, "invalid dictionary rollback data HERE"
        end
      end

      vm.fill_bytes(here, @here - here)
      if split_body?
        vm.fill_bytes(data_here, self.data_here - data_here)
        @body_here = data_here
      end
      @here = here
      @latest = latest
    end

    def self.align(address)
      (address + DICTIONARY_ALIGNMENT - 1) & ~(DICTIONARY_ALIGNMENT - 1)
    end

    private

    def read_constructor_plan_at(plan_address, descriptor_address)
      unless plan_address >= base && (plan_address % DICTIONARY_ALIGNMENT).zero? &&
             plan_address + 12 <= descriptor_address
        raise InvalidDictionary, "invalid constructor plan address"
      end
      unless vm.read_cell(plan_address) == CONSTRUCTOR_PLAN_MAGIC
        raise InvalidDictionary, "invalid constructor plan magic"
      end
      unless vm.read_cell(plan_address + 4) == CONSTRUCTOR_PLAN_VERSION
        raise InvalidDictionary, "unsupported constructor plan version"
      end
      count = vm.read_cell(plan_address + 8)
      if count.zero? || plan_address + 12 + count * 8 > descriptor_address
        raise InvalidDictionary, "invalid constructor plan length"
      end
      result = []
      cursor = plan_address + 12
      count.times do |index|
        code_address = vm.read_cell(cursor)
        action = vm.read_cell(cursor + 4)
        begin
          vm.memory.check_fetch(code_address, 1)
        rescue StandardError => error
          raise InvalidDictionary, "constructor code address is not executable", cause: error
        end
        unless CONSTRUCTOR_ACTIONS.include?(action)
          raise InvalidDictionary, "unknown constructor action #{action}"
        end
        unless (action == CONSTRUCTOR_ACTION_END) == (index == count - 1)
          raise InvalidDictionary, "constructor END must be the final plan action"
        end
        result << [code_address, action]
        cursor += 8
      end
      result
    end

    def add(name, kind:, payload:, immediate:, hidden:)
      require_structure_mutable
      encoded_name = encode_name(name)
      header = self.class.align(here)
      xt = self.class.align(header + 8 + encoded_name.bytesize)
      next_here = xt + 8
      if next_here > limit
        raise DictionaryFull,
              format("dictionary entry %p exceeds limit 0x%08X", encoded_name, limit)
      end

      flags = (immediate ? FLAG_IMMEDIATE : 0) | (hidden ? FLAG_HIDDEN : 0)
      vm.fill_bytes(here, header - here)
      vm.write_cell(header, latest)
      vm.write_u8(header + 4, flags)
      vm.write_u8(header + 5, encoded_name.bytesize)
      vm.fill_bytes(header + 6, 2)
      vm.write_bytes(header + 8, encoded_name)
      padding_start = header + 8 + encoded_name.bytesize
      vm.fill_bytes(padding_start, xt - padding_start)
      vm.write_cell(xt, kind)
      vm.write_cell(xt + 4, payload)
      @here = next_here
      @latest = header
      read_entry(header)
    end

    def defer_xt_target(target)
      current = read_entry(target.header_address)
      unless current.kind == KIND_COLON
        raise DictionaryError, "DEFER R0 target must be a colon word"
      end
      begin
        vm.memory.check_fetch(current.payload, 1)
      rescue StandardError
        raise DictionaryError, "DEFER target is not executable"
      end
      current.xt
    end

    def require_defer_authority(authorization)
      if runtime_structure_sealed? && @defer_authority.nil?
        raise DictionaryError, "DEFER update requires Monitor authorization"
      end
      return if @defer_authority.nil? || authorization.equal?(@defer_authority)

      raise DictionaryError, "DEFER update requires Monitor authorization"
    end

    def require_structure_mutable
      raise DictionaryError, "runtime dictionary structure is sealed" if runtime_structure_sealed?
    end

    def reserve_to(next_here)
      require_structure_mutable
      current = data_here
      data_limit = split_body? ? body_limit : limit
      if next_here > data_limit
        raise DictionaryFull, format("dictionary data exceeds limit 0x%08X", data_limit)
      end

      vm.fill_bytes(current, next_here - current)
      if split_body?
        @body_here = next_here
      else
        @here = next_here
      end
    end

    def data_field_address(name)
      encoded_name = encode_name(name)
      header = self.class.align(here)
      xt = self.class.align(header + 8 + encoded_name.bytesize)
      xt + 8
    end

    def encode_name(name)
      canonical = name.upcase
      unless canonical.ascii_only?
        raise DictionaryError, "v0.1 dictionary names must be ASCII"
      end

      encoded = canonical.encode(Encoding::US_ASCII).b
      if encoded.empty? || encoded.bytesize > MAX_NAME_BYTES || encoded.match?(/\s/)
        raise DictionaryError, "dictionary name must contain 1..31 non-space ASCII bytes"
      end
      encoded
    end
  end
end
