# frozen_string_literal: true

require "digest"
require "json"

module Min0CoreForth
  PERSISTENT_MAGIC = "FCPKG0\r\n".b
  PERSISTENT_VERSION = 1
  PERSISTENT_HEADER_SIZE = 32
  PERSISTENT_DIRECTORY_ENTRY_SIZE = 32
  PERSISTENT_TRAILER_SIZE = 32
  PERSISTENT_KIND_CODES = {
    "image" => 1, "trust-bundle" => 2, "root-policy-chain" => 3
  }.freeze
  PERSISTENT_CODE_KINDS = PERSISTENT_KIND_CODES.invert.freeze
  PERSISTENT_KIND_SECTIONS = {
    "image" => %w[envelope code dictionary data],
    "trust-bundle" => ["trust-bundle"],
    "root-policy-chain" => ["root-chain"]
  }.freeze
  PERSISTENT_SECTION_NAME_PATTERN = /\A[a-z][a-z0-9-]{0,14}\z/
  PERSISTENT_MAX_JSON_DEPTH = 32
  PERSISTENT_MAX_JSON_STRING = 4096
  PERSISTENT_MAX_JSON_NUMBER_DIGITS = 20
  PERSISTENT_MAX_JSON_NODES = 20_000

  class PersistentFormatError < StandardError; end

  class ParserLimits
    attr_reader :max_file_bytes, :max_sections, :max_payload_bytes,
                :max_section_bytes, :max_metadata_bytes

    def initialize(max_file_bytes: 1_048_576, max_sections: 8,
                   max_payload_bytes: 786_432, max_section_bytes: 524_288,
                   max_metadata_bytes: 262_144)
      @max_file_bytes = max_file_bytes
      @max_sections = max_sections
      @max_payload_bytes = max_payload_bytes
      @max_section_bytes = max_section_bytes
      @max_metadata_bytes = max_metadata_bytes
      values = [
        @max_file_bytes, @max_sections, @max_payload_bytes,
        @max_section_bytes, @max_metadata_bytes
      ]
      unless values.all? { |value| value.is_a?(Integer) && value.positive? }
        raise PersistentFormatError, "parser limits must be positive integers"
      end
      if @max_sections > 0xFFFF
        raise PersistentFormatError, "max_sections exceeds container field"
      end
      if @max_payload_bytes > @max_file_bytes
        raise PersistentFormatError, "payload limit exceeds file limit"
      end
      if @max_metadata_bytes > @max_section_bytes
        raise PersistentFormatError, "metadata limit exceeds section limit"
      end
      freeze
    end
  end

  PERSISTENT_DEFAULT_LIMITS = ParserLimits.new

  class DuplicateJsonKeyError < StandardError; end

  class DuplicateRejectHash < Hash
    def []=(key, value)
      raise DuplicateJsonKeyError, "duplicate JSON key #{key}" if key?(key)

      super
    end
  end

  module PersistentPackage
    module_function

    def normalize_json(value, depth: 0, counter: nil)
      counter ||= [0]
      counter[0] += 1
      if counter[0] > PERSISTENT_MAX_JSON_NODES
        raise PersistentFormatError, "metadata contains too many JSON values"
      end
      if depth > PERSISTENT_MAX_JSON_DEPTH
        raise PersistentFormatError, "metadata nesting is too deep"
      end
      case value
      when nil, true, false
        value
      when Integer
        if value.abs.to_s.length > PERSISTENT_MAX_JSON_NUMBER_DIGITS
          raise PersistentFormatError, "metadata integer is too long"
        end
        value
      when Float
        raise PersistentFormatError, "floating-point metadata is forbidden"
      when String
        if value.length > PERSISTENT_MAX_JSON_STRING
          raise PersistentFormatError, "metadata string is too long"
        end
        value
      when Array
        value.map do |item|
          normalize_json(item, depth: depth + 1, counter: counter)
        end
      when Hash
        normalized = {}
        value.each do |raw_key, item|
          unless raw_key.is_a?(String) || raw_key.is_a?(Symbol)
            raise PersistentFormatError, "metadata object keys must be strings"
          end
          key = raw_key.to_s
          if key.length > PERSISTENT_MAX_JSON_STRING
            raise PersistentFormatError, "metadata object key is too long"
          end
          if normalized.key?(key)
            raise PersistentFormatError, "metadata contains duplicate normalized keys"
          end
          normalized[key] = normalize_json(
            item, depth: depth + 1, counter: counter
          )
        end
        normalized.keys.sort.to_h { |key| [key, normalized.fetch(key)] }
      else
        raise PersistentFormatError, "metadata contains an unsupported JSON value"
      end
    end

    def canonical_json(value)
      JSON.generate(normalize_json(value)).b
    rescue JSON::GeneratorError, EncodingError => e
      raise PersistentFormatError, "metadata cannot be encoded canonically: #{e.message}"
    end

    def preflight_json(text)
      chars = text.each_char.to_a
      depth = 0
      in_string = false
      escaped = false
      string_length = 0
      index = 0
      while index < chars.length
        char = chars[index]
        if in_string
          if escaped
            escaped = false
          elsif char == "\\"
            escaped = true
          elsif char == '"'
            in_string = false
          else
            string_length += 1
            if string_length > PERSISTENT_MAX_JSON_STRING
              raise PersistentFormatError, "metadata string is too long"
            end
          end
          index += 1
          next
        end
        case char
        when '"'
          in_string = true
          string_length = 0
        when "[", "{"
          depth += 1
          if depth > PERSISTENT_MAX_JSON_DEPTH
            raise PersistentFormatError, "metadata nesting is too deep"
          end
        when "]", "}"
          depth -= 1
          raise PersistentFormatError, "metadata nesting is malformed" if depth.negative?
        else
          if char == "-" || char.match?(/[0-9]/)
            cursor = index + (char == "-" ? 1 : 0)
            start = cursor
            cursor += 1 while cursor < chars.length && chars[cursor].match?(/[0-9]/)
            if cursor - start > PERSISTENT_MAX_JSON_NUMBER_DIGITS
              raise PersistentFormatError, "metadata number is too long"
            end
            index = cursor - 1
          end
        end
        index += 1
      end
      if in_string || escaped || !depth.zero?
        raise PersistentFormatError, "metadata JSON is incomplete"
      end
    end

    def decode_canonical_json(raw, limits: PERSISTENT_DEFAULT_LIMITS)
      unless raw.is_a?(String)
        raise PersistentFormatError, "metadata section must be a String"
      end
      if raw.bytesize > limits.max_metadata_bytes
        raise PersistentFormatError, "metadata section exceeds configured limit"
      end
      text = raw.dup.force_encoding(Encoding::UTF_8)
      raise PersistentFormatError, "metadata is not valid UTF-8" unless text.valid_encoding?
      raise PersistentFormatError, "metadata contains NUL" if text.include?("\0")

      preflight_json(text)
      begin
        value = JSON.parse(
          text,
          object_class: DuplicateRejectHash,
          array_class: Array,
          create_additions: false,
          max_nesting: PERSISTENT_MAX_JSON_DEPTH
        )
      rescue DuplicateJsonKeyError, JSON::ParserError, JSON::NestingError, ArgumentError => e
        raise PersistentFormatError, "metadata JSON is malformed: #{e.message}"
      end
      normalized = normalize_json(value)
      unless canonical_json(normalized) == raw.b
        raise PersistentFormatError, "metadata JSON is not canonical"
      end
      normalized
    end

    def section_name_bytes(name)
      unless name.is_a?(String) && name.match?(PERSISTENT_SECTION_NAME_PATTERN)
        raise PersistentFormatError, "section name is malformed"
      end
      encoded = name.b
      encoded + ("\0" * (16 - encoded.bytesize)).b
    end

    def decode_section_name(raw)
      prefix = raw.split("\0".b, 2).first
      name = prefix.dup.force_encoding(Encoding::US_ASCII)
      raise PersistentFormatError, "section name is not ASCII" unless name.valid_encoding?
      unless section_name_bytes(name) == raw
        raise PersistentFormatError, "section name padding is malformed"
      end
      name
    end

    def encode(kind, sections, limits: PERSISTENT_DEFAULT_LIMITS)
      unless PERSISTENT_KIND_CODES.key?(kind)
        raise PersistentFormatError, "persistent package kind is unsupported"
      end
      expected_names = PERSISTENT_KIND_SECTIONS.fetch(kind)
      unless sections.is_a?(Hash) && sections.keys.map(&:to_s).sort == expected_names.sort
        raise PersistentFormatError, "persistent package sections do not match kind"
      end
      if expected_names.length > limits.max_sections
        raise PersistentFormatError, "section count exceeds configured limit"
      end
      normalized = expected_names.to_h do |name|
        value = sections.key?(name) ? sections[name] : sections[name.to_sym]
        raise PersistentFormatError, "section #{name} must be a String" unless value.is_a?(String)

        encoded = value.b
        section_limit = metadata_section?(name) ? limits.max_metadata_bytes : limits.max_section_bytes
        if encoded.bytesize > section_limit
          raise PersistentFormatError, "section #{name} exceeds configured limit"
        end
        [name, encoded]
      end
      payload_bytes = expected_names.sum { |name| normalized.fetch(name).bytesize }
      if payload_bytes > limits.max_payload_bytes
        raise PersistentFormatError, "package payload exceeds configured limit"
      end
      directory_bytes = expected_names.length * PERSISTENT_DIRECTORY_ENTRY_SIZE
      file_bytes = PERSISTENT_HEADER_SIZE + directory_bytes + payload_bytes + PERSISTENT_TRAILER_SIZE
      if file_bytes > limits.max_file_bytes
        raise PersistentFormatError, "package exceeds configured file limit"
      end
      header = [
        PERSISTENT_MAGIC, PERSISTENT_VERSION, PERSISTENT_KIND_CODES.fetch(kind),
        expected_names.length, 0, directory_bytes, payload_bytes, file_bytes, 0
      ].pack("a8S<S<S<S<L<L<L<L<")
      directory = +"".b
      offset = 0
      expected_names.each do |name|
        data = normalized.fetch(name)
        directory << [section_name_bytes(name), offset, data.bytesize, 0, 0].pack("a16L<L<L<L<")
        offset += data.bytesize
      end
      payload = expected_names.map { |name| normalized.fetch(name) }.join.b
      body = header + directory + payload
      body + Digest::SHA256.digest(body)
    end

    def decode(raw, limits: PERSISTENT_DEFAULT_LIMITS)
      raise PersistentFormatError, "persistent package must be a String" unless raw.is_a?(String)

      encoded = raw.b
      if encoded.bytesize > limits.max_file_bytes
        raise PersistentFormatError, "package exceeds configured file limit"
      end
      if encoded.bytesize < PERSISTENT_HEADER_SIZE + PERSISTENT_TRAILER_SIZE
        raise PersistentFormatError, "package is shorter than fixed framing"
      end
      begin
        magic, version, kind_code, section_count, flags, directory_bytes,
          payload_bytes, file_bytes, reserved = encoded.byteslice(0, PERSISTENT_HEADER_SIZE)
                                                    .unpack("a8S<S<S<S<L<L<L<L<")
      rescue StandardError => e
        raise PersistentFormatError, "package header is incomplete: #{e.message}"
      end
      raise PersistentFormatError, "package magic is unsupported" unless magic == PERSISTENT_MAGIC
      raise PersistentFormatError, "package version is unsupported" unless version == PERSISTENT_VERSION
      unless PERSISTENT_CODE_KINDS.key?(kind_code)
        raise PersistentFormatError, "package kind is unsupported"
      end
      kind = PERSISTENT_CODE_KINDS.fetch(kind_code)
      expected_names = PERSISTENT_KIND_SECTIONS.fetch(kind)
      unless section_count.positive? && section_count <= limits.max_sections
        raise PersistentFormatError, "package section count is invalid"
      end
      unless section_count == expected_names.length
        raise PersistentFormatError, "package section count disagrees with kind"
      end
      unless flags.zero? && reserved.zero?
        raise PersistentFormatError, "package header contains unsupported flags"
      end
      expected_directory_bytes = section_count * PERSISTENT_DIRECTORY_ENTRY_SIZE
      unless directory_bytes == expected_directory_bytes
        raise PersistentFormatError, "package directory length is invalid"
      end
      if payload_bytes > limits.max_payload_bytes
        raise PersistentFormatError, "package payload exceeds configured limit"
      end
      expected_file_bytes = PERSISTENT_HEADER_SIZE + directory_bytes + payload_bytes + PERSISTENT_TRAILER_SIZE
      unless file_bytes == expected_file_bytes && file_bytes == encoded.bytesize
        raise PersistentFormatError, "package file length is inconsistent"
      end
      payload_start = PERSISTENT_HEADER_SIZE + directory_bytes
      payload_end = payload_start + payload_bytes
      body = encoded.byteslice(0, payload_end)
      trailer = encoded.byteslice(payload_end, PERSISTENT_TRAILER_SIZE)
      unless Digest::SHA256.digest(body) == trailer
        raise PersistentFormatError, "package checksum mismatch"
      end
      sections = {}
      expected_offset = 0
      expected_names.each_with_index do |expected_name, index|
        directory_offset = PERSISTENT_HEADER_SIZE + index * PERSISTENT_DIRECTORY_ENTRY_SIZE
        raw_name, offset, length, entry_flags, entry_reserved =
          encoded.byteslice(directory_offset, PERSISTENT_DIRECTORY_ENTRY_SIZE)
                 .unpack("a16L<L<L<L<")
        name = decode_section_name(raw_name)
        unless name == expected_name
          raise PersistentFormatError, "package sections are duplicate, missing, or reordered"
        end
        unless entry_flags.zero? && entry_reserved.zero?
          raise PersistentFormatError, "section contains unsupported flags"
        end
        unless offset == expected_offset
          raise PersistentFormatError, "section ranges overlap or contain a gap"
        end
        section_limit = metadata_section?(name) ? limits.max_metadata_bytes : limits.max_section_bytes
        if length > section_limit || offset + length > payload_bytes
          raise PersistentFormatError, "section #{name} length is invalid"
        end
        sections[name] = encoded.byteslice(payload_start + offset, length)
        expected_offset += length
      end
      unless expected_offset == payload_bytes
        raise PersistentFormatError, "package payload contains unclaimed bytes"
      end
      { kind: kind, sections: sections, sha256: Digest::SHA256.hexdigest(body) }
    end

    def read_file(path, limits: PERSISTENT_DEFAULT_LIMITS)
      raw = File.open(path, "rb") { |stream| stream.read(limits.max_file_bytes + 1) }
      if raw.bytesize > limits.max_file_bytes
        raise PersistentFormatError, "package exceeds configured file limit"
      end
      decode(raw, limits: limits)
    rescue SystemCallError => e
      raise PersistentFormatError, "cannot read persistent package: #{e.message}"
    end

    def write_file(path, kind, sections, limits: PERSISTENT_DEFAULT_LIMITS)
      raw = encode(kind, sections, limits: limits)
      File.binwrite(path, raw)
      { bytes: raw.bytesize, sha256: Digest::SHA256.hexdigest(raw) }
    rescue SystemCallError => e
      raise PersistentFormatError, "cannot write persistent package: #{e.message}"
    end

    def encode_image(components, envelope, limits: PERSISTENT_DEFAULT_LIMITS)
      encode(
        "image",
        {
          "envelope" => canonical_json(envelope),
          "code" => field(components, "code"),
          "dictionary" => field(components, "dictionary"),
          "data" => field(components, "data")
        },
        limits: limits
      )
    end

    def decode_image(raw, limits: PERSISTENT_DEFAULT_LIMITS)
      package = decode(raw, limits: limits)
      decode_image_sections(package, limits: limits)
    end

    def decode_image_sections(package, limits: PERSISTENT_DEFAULT_LIMITS)
      raise PersistentFormatError, "persistent package is not an image" unless package[:kind] == "image"

      sections = package[:sections]
      envelope = decode_canonical_json(sections.fetch("envelope"), limits: limits)
      unless envelope.is_a?(Hash)
        raise PersistentFormatError, "image envelope metadata must be an object"
      end
      [
        %w[code dictionary data].to_h { |name| [name, sections.fetch(name)] },
        envelope
      ]
    end

    def write_image_file(path, components, envelope, limits: PERSISTENT_DEFAULT_LIMITS)
      write_file(
        path,
        "image",
        {
          "envelope" => canonical_json(envelope),
          "code" => field(components, "code"),
          "dictionary" => field(components, "dictionary"),
          "data" => field(components, "data")
        },
        limits: limits
      )
    end

    def read_image_file(path, limits: PERSISTENT_DEFAULT_LIMITS)
      decode_image_sections(read_file(path, limits: limits), limits: limits)
    end

    def encode_trust_bundle(bundle, limits: PERSISTENT_DEFAULT_LIMITS)
      encode(
        "trust-bundle",
        { "trust-bundle" => canonical_json(bundle) },
        limits: limits
      )
    end

    def decode_trust_bundle(raw, limits: PERSISTENT_DEFAULT_LIMITS)
      package = decode(raw, limits: limits)
      unless package[:kind] == "trust-bundle"
        raise PersistentFormatError, "persistent package is not a trust bundle"
      end
      value = decode_canonical_json(
        package[:sections].fetch("trust-bundle"), limits: limits
      )
      raise PersistentFormatError, "trust bundle metadata must be an object" unless value.is_a?(Hash)

      value
    end

    def encode_root_policy_chain(chain, limits: PERSISTENT_DEFAULT_LIMITS)
      encode(
        "root-policy-chain",
        { "root-chain" => canonical_json(chain) },
        limits: limits
      )
    end

    def decode_root_policy_chain(raw, limits: PERSISTENT_DEFAULT_LIMITS)
      package = decode(raw, limits: limits)
      unless package[:kind] == "root-policy-chain"
        raise PersistentFormatError, "persistent package is not a root policy chain"
      end
      value = decode_canonical_json(
        package[:sections].fetch("root-chain"), limits: limits
      )
      unless value.is_a?(Array)
        raise PersistentFormatError, "root policy chain metadata must be an array"
      end
      value
    end

    def field(mapping, name)
      return mapping[name] if mapping.key?(name)

      mapping[name.to_sym]
    end

    def metadata_section?(name)
      %w[envelope trust-bundle root-chain].include?(name)
    end
  end
end
