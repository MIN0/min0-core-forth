# frozen_string_literal: true

require "digest"
require "json"
require_relative "min0_core_forth_auth"
require_relative "min0_core_forth_linker"
require_relative "min0_core_forth_verify"

module Min0CoreForth
  IMAGE_FORMAT = "min0-core-forth-image-envelope"
  IMAGE_VERSION = 5
  DIGEST_ALGORITHM = "sha256"
  AUTHENTICATION_NONE = "none"
  AUTHENTICATION_ED25519 = "ed25519"
  MAX_GENERATION = (1 << 64) - 1
  IMAGE_ROLE_NORMAL = "normal"
  IMAGE_ROLE_RECOVERY = "recovery"
  EXECUTION_PROFILE_SAFE_RUNTIME = "safe-runtime"
  EXECUTION_PROFILE_STANDARD_BUILD = "standard-build"
  KEY_ID_PATTERN = /\A[a-z0-9][a-z0-9._-]{0,63}\z/

  class ImageError < StandardError; end
  class ImageAuthenticationError < ImageError; end
  class ImageRollbackError < ImageError; end

  module ImageEnvelope
    module_function

    def build(components, bases, limits, allocator, manifest,
              generation:, image_role: IMAGE_ROLE_NORMAL)
      build_with_authentication(
        components, bases, limits, allocator, manifest,
        generation: generation, image_role: image_role,
        authentication: { scheme: AUTHENTICATION_NONE }
      )
    end

    def build_ed25519(components, bases, limits, allocator, manifest,
                      generation:, key_id:, private_key:, image_role: IMAGE_ROLE_NORMAL)
      normalized_key_id = key_id_value(key_id)
      envelope = build_with_authentication(
        components, bases, limits, allocator, manifest,
        generation: generation, image_role: image_role,
        authentication: { scheme: AUTHENTICATION_ED25519, key_id: normalized_key_id }
      )
      begin
        signature = Authentication.ed25519_sign(envelope[:identity_sha256], private_key)
      rescue AuthenticationError, OpenSSL::PKey::PKeyError, TypeError, ArgumentError, NoMethodError => e
        raise ImageAuthenticationError, "invalid Ed25519 private key: #{e.message}"
      end
      envelope[:authentication][:signature_hex] = signature.unpack1("H*")
      envelope
    end

    def build_with_authentication(components, bases, limits, allocator, manifest,
                                  generation:, image_role:, authentication:)
      images = {}
      normalized_bases = {}
      normalized_limits = {}
      LINK_SECTIONS.each do |section|
        image = field(components, section.to_sym)
        raise ImageError, "component #{section} must be a String" unless image.is_a?(String)

        images[section] = image.b
        normalized_bases[section] = integer(field(bases, section.to_sym), "base #{section}")
        normalized_limits[section] = integer(field(limits, section.to_sym), "limit #{section}")
      end
      normalized_allocator = allocator_names.to_h do |name|
        [name.to_s, integer(field(allocator, name), "allocator #{name}")]
      end
      validate_layout(images, normalized_bases, normalized_limits, normalized_allocator)
      manifest_copy = Marshal.load(Marshal.dump(manifest))
      begin
        Linker.link_components(images, normalized_bases, normalized_bases, manifest_copy)
        code_verification = BytecodeVerifier.verify_image_bytecode(
          images, normalized_bases, manifest_copy
        )
      rescue LinkError, BytecodeVerificationError => e
        raise ImageError, "image manifest is invalid: #{e.message}"
      end
      manifest_sha256 = sha256(manifest_payload(manifest_copy))
      normalized_generation = generation_value(generation)
      normalized_role = image_role_value(image_role)
      execution_profile = required_execution_profile(code_verification)
      if normalized_role == IMAGE_ROLE_RECOVERY &&
         execution_profile != EXECUTION_PROFILE_SAFE_RUNTIME
        raise ImageError, "recovery image must use safe-runtime execution profile"
      end
      envelope = {
        format: IMAGE_FORMAT,
        version: IMAGE_VERSION,
        profile: MANIFEST_PROFILE,
        digest_algorithm: DIGEST_ALGORITHM,
        generation: normalized_generation,
        image_role: normalized_role,
        execution_profile: execution_profile,
        components: LINK_SECTIONS.to_h do |section|
          [
            section,
            {
              base: normalized_bases.fetch(section),
              size: images.fetch(section).bytesize,
              limit: normalized_limits.fetch(section),
              sha256: sha256(images.fetch(section))
            }
          ]
        end,
        allocator: normalized_allocator,
        manifest: manifest_copy,
        manifest_sha256: manifest_sha256,
        authentication: authentication.dup
      }
      envelope[:identity_sha256] = sha256(identity_payload(envelope))
      envelope
    end
    private_class_method :build_with_authentication

    def validate(components, envelope, require_authentication: false, minimum_generation: 0,
                 trusted_public_keys: nil, required_image_role: nil, runtime_profile: nil)
      raise ImageError, "image envelope must be a Hash" unless envelope.is_a?(Hash)
      expected_envelope_fields = %w[
        allocator authentication components digest_algorithm format generation identity_sha256
        execution_profile image_role manifest manifest_sha256 profile version
      ]
      unless envelope.keys.map(&:to_s).sort == expected_envelope_fields.sort
        raise ImageError, "image envelope fields are malformed"
      end
      raise ImageError, "unsupported image envelope format" unless field(envelope, :format) == IMAGE_FORMAT
      unless integer(field(envelope, :version), "image version") == IMAGE_VERSION
        raise ImageError, "unsupported image envelope version"
      end
      raise ImageError, "unsupported image profile" unless field(envelope, :profile) == MANIFEST_PROFILE
      unless field(envelope, :digest_algorithm) == DIGEST_ALGORITHM
        raise ImageError, "unsupported image digest algorithm"
      end
      generation = generation_value(field(envelope, :generation))
      image_role = image_role_value(field(envelope, :image_role))
      execution_profile = execution_profile_value(field(envelope, :execution_profile))
      if !required_image_role.nil? && image_role != image_role_value(required_image_role)
        raise ImageError,
              "image role #{image_role} does not satisfy required role #{required_image_role}"
      end
      check_execution_compatibility(execution_profile, runtime_profile)
      minimum = generation_value(minimum_generation, "minimum generation")
      authentication = field(envelope, :authentication)
      raise ImageError, "image authentication metadata is malformed" unless authentication.is_a?(Hash)

      scheme = field(authentication, :scheme)
      key_id = nil
      signature = nil
      if scheme == AUTHENTICATION_NONE
        unless authentication.keys.map(&:to_s).sort == ["scheme"]
          raise ImageAuthenticationError, "none authentication block contains unexpected fields"
        end
      elsif scheme == AUTHENTICATION_ED25519
        unless authentication.keys.map(&:to_s).sort == ["key_id", "scheme", "signature_hex"]
          raise ImageAuthenticationError, "Ed25519 authentication block is malformed"
        end
        key_id = key_id_value(field(authentication, :key_id))
        signature = signature_value(field(authentication, :signature_hex))
      else
        raise ImageAuthenticationError, "unsupported image authentication scheme"
      end
      if require_authentication && scheme == AUTHENTICATION_NONE
        raise ImageAuthenticationError, "authenticated image is required"
      end

      descriptors = field(envelope, :components)
      allocator_raw = field(envelope, :allocator)
      manifest = field(envelope, :manifest)
      unless descriptors.is_a?(Hash) && allocator_raw.is_a?(Hash)
        raise ImageError, "image metadata is malformed"
      end
      raise ImageError, "image manifest is malformed" unless manifest.is_a?(Hash)
      unless descriptors.keys.map(&:to_s).sort == LINK_SECTIONS.sort
        raise ImageError, "image component descriptor fields are malformed"
      end
      unless allocator_raw.keys.map(&:to_s).sort == %w[code_here data_here header_here latest]
        raise ImageError, "image allocator fields are malformed"
      end

      images = {}
      bases = {}
      limits = {}
      LINK_SECTIONS.each do |section|
        image = field(components, section.to_sym)
        descriptor = field(descriptors, section.to_sym)
        raise ImageError, "component #{section} must be a String" unless image.is_a?(String)
        unless descriptor.is_a?(Hash)
          raise ImageError, "component descriptor #{section} is malformed"
        end
        unless descriptor.keys.map(&:to_s).sort == %w[base limit sha256 size]
          raise ImageError, "component descriptor #{section} fields are malformed"
        end
        images[section] = image.b
        bases[section] = integer(field(descriptor, :base), "base #{section}")
        limits[section] = integer(field(descriptor, :limit), "limit #{section}")
        size = integer(field(descriptor, :size), "size #{section}")
        raise ImageError, "component #{section} size mismatch" unless size == images.fetch(section).bytesize
        unless field(descriptor, :sha256) == sha256(images.fetch(section))
          raise ImageError, "component #{section} digest mismatch"
        end
      end
      allocator = allocator_names.to_h do |name|
        [name.to_s, integer(field(allocator_raw, name), "allocator #{name}")]
      end
      validate_layout(images, bases, limits, allocator)
      unless field(manifest, :format) == MANIFEST_FORMAT
        raise ImageError, "image contains unsupported manifest format"
      end
      unless integer(field(manifest, :version), "manifest version") == MANIFEST_VERSION
        raise ImageError, "image contains unsupported manifest version"
      end
      begin
        Linker.link_components(images, bases, bases, manifest)
        code_verification = BytecodeVerifier.verify_image_bytecode(images, bases, manifest)
      rescue LinkError, BytecodeVerificationError => e
        raise ImageError, "image manifest is invalid: #{e.message}"
      end
      derived_execution_profile = required_execution_profile(code_verification)
      unless execution_profile == derived_execution_profile
        raise ImageError, "image execution profile disagrees with relocation requirements"
      end
      if image_role == IMAGE_ROLE_RECOVERY &&
         execution_profile != EXECUTION_PROFILE_SAFE_RUNTIME
        raise ImageError, "recovery image must use safe-runtime execution profile"
      end
      unless field(envelope, :manifest_sha256) == sha256(manifest_payload(manifest))
        raise ImageError, "manifest digest mismatch"
      end
      unless field(envelope, :identity_sha256) == sha256(identity_payload(envelope))
        raise ImageError, "image identity digest mismatch"
      end
      if scheme == AUTHENTICATION_ED25519
        unless trusted_public_keys.is_a?(Hash) && trusted_public_keys.key?(key_id)
          raise ImageAuthenticationError, "authentication key_id is not trusted"
        end
        public_key = trusted_public_keys.fetch(key_id)
        raise ImageAuthenticationError, "trusted Ed25519 public key must be a String" unless public_key.is_a?(String)
        unless Authentication.ed25519_verify(
          field(envelope, :identity_sha256), public_key.b, signature
        )
          raise ImageAuthenticationError, "Ed25519 image signature is invalid"
        end
      end
      if generation < minimum
        raise ImageRollbackError,
              "image generation #{generation} is below trusted minimum #{minimum}"
      end
      {
        components: images,
        bases: bases,
        limits: limits,
        allocator: allocator,
        manifest: manifest,
        generation: generation,
        authentication: { scheme: scheme, key_id: key_id },
        image_role: image_role,
        execution_profile: execution_profile,
        code_verification: code_verification
      }
    end

    def link(components, envelope, target_bases, target_limits,
             require_authentication: false, minimum_generation: 0, trusted_public_keys: nil,
             required_image_role: nil, runtime_profile: nil)
      validated = validate(
        components, envelope, require_authentication: require_authentication,
        minimum_generation: minimum_generation, trusted_public_keys: trusted_public_keys,
        required_image_role: required_image_role, runtime_profile: runtime_profile
      )
      unless validated[:authentication][:scheme] == AUTHENTICATION_NONE
        raise ImageAuthenticationError,
              "authenticated image relocation requires build-host re-signing"
      end
      new_bases = LINK_SECTIONS.to_h do |section|
        [section, integer(field(target_bases, section.to_sym), "target base #{section}")]
      end
      new_limits = LINK_SECTIONS.to_h do |section|
        [section, integer(field(target_limits, section.to_sym), "target limit #{section}")]
      end
      linked = Linker.link_components(
        validated[:components], validated[:bases], new_bases, validated[:manifest]
      )
      old_allocator = validated[:allocator]
      new_allocator = {
        "code_here" => new_bases.fetch("code") + linked.fetch("code").bytesize,
        "header_here" => new_bases.fetch("dictionary") + linked.fetch("dictionary").bytesize,
        "data_here" => new_bases.fetch("data") + linked.fetch("data").bytesize,
        "latest" => if old_allocator.fetch("latest").zero?
                      0
                    else
                      old_allocator.fetch("latest") + new_bases.fetch("dictionary") -
                        validated[:bases].fetch("dictionary")
                    end
      }
      linked_envelope = build(
        linked, new_bases, new_limits, new_allocator, validated[:manifest],
        generation: validated[:generation], image_role: validated[:image_role]
      )
      [linked, linked_envelope]
    end

    def allocator_names
      [:code_here, :header_here, :data_here, :latest]
    end
    private_class_method :allocator_names

    def field(hash, name)
      return nil unless hash.respond_to?(:key?)
      return hash[name] if hash.key?(name)

      hash[name.to_s]
    end
    private_class_method :field

    def integer(value, label)
      raise ImageError, "#{label} must be an Integer" unless value.is_a?(Integer)

      value
    end
    private_class_method :integer

    def generation_value(value, label = "image generation")
      generation = integer(value, label)
      unless generation.between?(0, MAX_GENERATION)
        raise ImageError, "#{label} must be an unsigned 64-bit integer"
      end

      generation
    end
    private_class_method :generation_value

    def key_id_value(value)
      unless value.is_a?(String) && value.match?(KEY_ID_PATTERN)
        raise ImageAuthenticationError,
              "authentication key_id must be 1..64 lowercase identifier characters"
      end

      value
    end
    private_class_method :key_id_value

    def image_role_value(value)
      unless [IMAGE_ROLE_NORMAL, IMAGE_ROLE_RECOVERY].include?(value)
        raise ImageError, "image role must be normal or recovery"
      end

      value
    end
    private_class_method :image_role_value

    def execution_profile_value(value, label = "image execution profile")
      unless [EXECUTION_PROFILE_SAFE_RUNTIME, EXECUTION_PROFILE_STANDARD_BUILD].include?(value)
        raise ImageError, "#{label} must be safe-runtime or standard-build"
      end

      value
    end
    private_class_method :execution_profile_value

    def required_execution_profile(verification)
      capabilities = field(verification, :capabilities)
      return EXECUTION_PROFILE_SAFE_RUNTIME if capabilities == []
      return EXECUTION_PROFILE_STANDARD_BUILD if capabilities == ["compiled-defer-store"]

      raise ImageError, "bytecode verifier returned unsupported capabilities"
    end
    private_class_method :required_execution_profile

    def check_execution_compatibility(image_profile, runtime_profile)
      return if runtime_profile.nil?

      runtime = execution_profile_value(runtime_profile, "loader execution profile")
      if runtime == EXECUTION_PROFILE_SAFE_RUNTIME &&
         image_profile != EXECUTION_PROFILE_SAFE_RUNTIME
        raise ImageError,
              "image execution profile #{image_profile} is incompatible with loader profile #{runtime}"
      end
    end
    private_class_method :check_execution_compatibility

    def signature_value(value)
      unless value.is_a?(String) && value.match?(/\A[0-9a-f]{128}\z/)
        raise ImageAuthenticationError,
              "Ed25519 signature must be 64 bytes of lowercase hex"
      end

      [value].pack("H*")
    end
    private_class_method :signature_value

    def sha256(data)
      Digest::SHA256.hexdigest(data)
    end
    private_class_method :sha256

    def manifest_payload(manifest)
      records = field(manifest, :records)
      raise ImageError, "manifest records must be an Array" unless records.is_a?(Array)

      rows = records.each_with_index.map do |record, index|
        raise ImageError, "manifest record #{index} must be a Hash" unless record.is_a?(Hash)

        [
          field(record, :section), field(record, :offset), field(record, :target),
          field(record, :width), field(record, :kind)
        ]
      end
      JSON.generate(
        [field(manifest, :format), field(manifest, :version), field(manifest, :profile), rows]
      )
    end
    private_class_method :manifest_payload

    def identity_payload(envelope)
      descriptors = field(envelope, :components)
      allocator = field(envelope, :allocator)
      authentication = field(envelope, :authentication)
      unless descriptors.is_a?(Hash) && allocator.is_a?(Hash)
        raise ImageError, "image identity metadata is malformed"
      end
      unless authentication.is_a?(Hash)
        raise ImageError, "image authentication metadata is malformed"
      end
      component_rows = LINK_SECTIONS.map do |section|
        descriptor = field(descriptors, section.to_sym)
        unless descriptor.is_a?(Hash)
          raise ImageError, "component descriptor #{section} is malformed"
        end
        [
          section, field(descriptor, :base), field(descriptor, :size),
          field(descriptor, :limit), field(descriptor, :sha256)
        ]
      end
      JSON.generate(
        [
          field(envelope, :format), field(envelope, :version), field(envelope, :profile),
          field(envelope, :digest_algorithm), field(envelope, :generation),
          field(envelope, :image_role), field(envelope, :execution_profile), component_rows,
          allocator_names.map { |name| field(allocator, name) },
          field(envelope, :manifest_sha256),
          [field(authentication, :scheme), field(authentication, :key_id)]
        ]
      )
    end
    private_class_method :identity_payload

    def validate_layout(images, bases, limits, allocator)
      ranges = LINK_SECTIONS.map do |section|
        base = bases.fetch(section)
        limit = limits.fetch(section)
        unless base >= 0 && base < REFERENCE32_LIMIT
          raise ImageError, "component #{section} base is outside Reference32"
        end
        unless limit > base && limit <= REFERENCE32_LIMIT
          raise ImageError, "component #{section} limit is invalid"
        end
        if base + images.fetch(section).bytesize > limit
          raise ImageError, "component #{section} exceeds its region limit"
        end
        [base, limit, section]
      end.sort
      ranges.each_cons(2) do |previous, current|
        if current[0] < previous[1]
          raise ImageError, "component regions #{previous[2]} and #{current[2]} overlap"
        end
      end
      expected_here = {
        "code_here" => bases.fetch("code") + images.fetch("code").bytesize,
        "header_here" => bases.fetch("dictionary") + images.fetch("dictionary").bytesize,
        "data_here" => bases.fetch("data") + images.fetch("data").bytesize
      }
      expected_here.each do |name, expected|
        unless allocator.fetch(name) == expected
          raise ImageError, "allocator #{name} disagrees with component length"
        end
      end
      latest = allocator.fetch("latest")
      unless latest.zero? || latest.between?(bases.fetch("dictionary"), allocator.fetch("header_here") - 1)
        raise ImageError, "allocator latest is outside used DICTIONARY"
      end
      raise ImageError, "allocator latest is not cell-aligned" unless (latest % 4).zero?
    end
    private_class_method :validate_layout
  end
end
