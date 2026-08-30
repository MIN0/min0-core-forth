# frozen_string_literal: true

require "digest"
require "json"
require "tmpdir"
require_relative "min0_core_forth_persistent"
require_relative "min0_core_forth_root"
require_relative "min0_core_forth_trust"
require_relative "signed_image_demo"
require_relative "root_rotation_demo"

PERSISTENT_EXECUTION_SOURCE =
  "0 CHOOSE 1 CHOOSE 0 SPIN SUM SKIP STEP READ-ANSWER SLOT-ADDR"

def persistent_root_entry(key_id, public_key)
  {
    key_id: key_id,
    public_key_hex: public_key.unpack1("H*"),
    status: "active"
  }
end

def persistent_rejected(*errors)
  yield
  false
rescue *errors
  true
end

def persistent_reseal(raw)
  changed = raw.dup.b
  changed[-32, 32] = Digest::SHA256.digest(changed.byteslice(0, changed.bytesize - 32))
  changed
end

def persistent_with_metadata(metadata, components)
  Min0CoreForth::PersistentPackage.encode(
    "image",
    {
      "envelope" => metadata,
      "code" => components[:code],
      "dictionary" => components[:dictionary],
      "data" => components[:data]
    }
  )
end

def persistent_execute(components, validated)
  vm, dictionary = make_image_system
  allocator = validated[:allocator]
  vm.load(components.fetch("code"), address: validated[:bases].fetch("code"))
  dictionary.load_images(
    components.fetch("dictionary"),
    latest: allocator.fetch("latest"),
    body_image: components.fetch("data")
  )
  outer = Min0CoreForth::OuterInterpreter.new(
    vm, dictionary, code_base: allocator.fetch("code_here")
  )
  outer.interpret(PERSISTENT_EXECUTION_SOURCE)
end

def run_persistent_package_demo(implementation = "ruby")
  image_private = Min0CoreForth::Authentication.ed25519_private_from_seed(ED25519_TEST_SEED)
  image_public = Min0CoreForth::Authentication.ed25519_public_bytes(image_private)
  source_components, unsigned = build_source_image(7)
  signed = signed_from_template(
    source_components,
    unsigned,
    SIGNED_IMAGE_KEY_ID,
    private_key: image_private
  )

  old_private = Min0CoreForth::Authentication.ed25519_private_from_seed(ROOT_ROTATE_OLD_TEST_SEED)
  new_private = Min0CoreForth::Authentication.ed25519_private_from_seed(ROOT_ROTATE_NEW_TEST_SEED)
  old_public = Min0CoreForth::Authentication.ed25519_public_bytes(old_private)
  new_public = Min0CoreForth::Authentication.ed25519_public_bytes(new_private)
  pinned = { ROOT_ROTATE_OLD_ID => old_public }
  roots1 = [persistent_root_entry(ROOT_ROTATE_OLD_ID, old_public)]
  roots2 = [
    persistent_root_entry(ROOT_ROTATE_OLD_ID, old_public),
    persistent_root_entry(ROOT_ROTATE_NEW_ID, new_public)
  ]
  policy1 = Min0CoreForth::RootPolicy.build(
    1, roots1, { ROOT_ROTATE_OLD_ID => old_private }
  )
  policy2 = Min0CoreForth::RootPolicy.build(
    2,
    roots2,
    { ROOT_ROTATE_OLD_ID => old_private, ROOT_ROTATE_NEW_ID => new_private },
    previous_policy: policy1
  )
  root_package = Min0CoreForth::PersistentPackage.encode_root_policy_chain([policy1, policy2])
  loaded_chain = Min0CoreForth::PersistentPackage.decode_root_policy_chain(root_package)
  validated_root = Min0CoreForth::RootPolicy.validate_chain(
    loaded_chain, pinned, minimum_epoch: 2
  )

  trust_entries = [
    {
      key_id: SIGNED_IMAGE_KEY_ID,
      role: Min0CoreForth::IMAGE_ROLE_NORMAL,
      public_key_hex: image_public.unpack1("H*"),
      status: "active"
    }
  ]
  trust_bundle = Min0CoreForth::TrustBundle.build(
    2,
    trust_entries,
    root_key_id: ROOT_ROTATE_NEW_ID,
    root_private_key: new_private
  )
  trust_package = Min0CoreForth::PersistentPackage.encode_trust_bundle(trust_bundle)
  loaded_bundle = Min0CoreForth::PersistentPackage.decode_trust_bundle(trust_package)
  validated_trust = Min0CoreForth::TrustBundle.validate(
    loaded_bundle,
    Min0CoreForth::RootPolicy.active_keys(validated_root),
    minimum_epoch: 2
  )
  trusted_image_keys = Min0CoreForth::TrustBundle.active_keys(
    validated_trust, Min0CoreForth::IMAGE_ROLE_NORMAL
  )

  image_package = Min0CoreForth::PersistentPackage.encode_image(source_components, signed)
  write_result = nil
  loaded_components = nil
  loaded_envelope = nil
  validated_image = nil
  stack = nil
  oversized_file_rejected_before_parse = nil
  Dir.mktmpdir("min0-core-forth-persistent-") do |directory|
    image_path = File.join(directory, "signed-image.fcp")
    write_result = Min0CoreForth::PersistentPackage.write_image_file(
      image_path, source_components, signed
    )
    loaded_components, loaded_envelope =
      Min0CoreForth::PersistentPackage.read_image_file(image_path)
    validated_image = Min0CoreForth::ImageEnvelope.validate(
      loaded_components,
      loaded_envelope,
      require_authentication: true,
      minimum_generation: 7,
      trusted_public_keys: trusted_image_keys,
      required_image_role: Min0CoreForth::IMAGE_ROLE_NORMAL
    )
    stack = persistent_execute(loaded_components, validated_image)

    oversized_path = File.join(directory, "oversized.fcp")
    File.binwrite(
      oversized_path,
      "X".b * (Min0CoreForth::PERSISTENT_DEFAULT_LIMITS.max_file_bytes + 1)
    )
    oversized_file_rejected_before_parse = persistent_rejected(
      Min0CoreForth::PersistentFormatError
    ) do
      Min0CoreForth::PersistentPackage.read_image_file(oversized_path)
    end
  end

  truncated = image_package.byteslice(0, image_package.bytesize - 1)
  trailing = image_package + "\0".b
  checksum_tamper = image_package.dup
  checksum_tamper.setbyte(checksum_tamper.bytesize - 33, checksum_tamper.getbyte(-33) ^ 1)

  declared_length_bomb = image_package.dup
  declared_length_bomb[20, 4] = [0xFFFFFFFF].pack("L<")
  section_count_bomb = image_package.dup
  section_count_bomb[12, 2] = [0xFFFF].pack("S<")
  unknown_version = image_package.dup
  unknown_version[8, 2] = [99].pack("S<")
  unknown_kind = image_package.dup
  unknown_kind[10, 2] = [99].pack("S<")

  duplicate_section = image_package.dup
  second_entry = Min0CoreForth::PERSISTENT_HEADER_SIZE + Min0CoreForth::PERSISTENT_DIRECTORY_ENTRY_SIZE
  duplicate_section[second_entry, 16] = "envelope".b + ("\0".b * 8)
  duplicate_section = persistent_reseal(duplicate_section)

  overlap = image_package.dup
  overlap[second_entry + 16, 4] = [0].pack("L<")
  overlap = persistent_reseal(overlap)

  section_length_bomb = image_package.dup
  section_length_bomb[second_entry + 20, 4] = [0xFFFFFFFF].pack("L<")
  section_length_bomb = persistent_reseal(section_length_bomb)

  duplicate_json = persistent_with_metadata('{"a":1,"a":2}'.b, source_components)
  noncanonical_json = persistent_with_metadata('{"a": 1}'.b, source_components)
  deep_json = persistent_with_metadata(
    ("[".b * 33) + "0".b + ("]".b * 33), source_components
  )
  long_integer_json = persistent_with_metadata(
    '{"a":123456789012345678901}'.b, source_components
  )

  resealed_component_tamper = image_package.dup
  header = resealed_component_tamper.byteslice(0, Min0CoreForth::PERSISTENT_HEADER_SIZE)
                                      .unpack("a8S<S<S<S<L<L<L<L<")
  directory_size = header[5]
  first_entry = resealed_component_tamper
                .byteslice(Min0CoreForth::PERSISTENT_HEADER_SIZE,
                           Min0CoreForth::PERSISTENT_DIRECTORY_ENTRY_SIZE)
                .unpack("a16L<L<L<L<")
  envelope_length = first_entry[2]
  code_start = Min0CoreForth::PERSISTENT_HEADER_SIZE + directory_size + envelope_length
  resealed_component_tamper.setbyte(
    code_start, resealed_component_tamper.getbyte(code_start) ^ 1
  )
  resealed_component_tamper = persistent_reseal(resealed_component_tamper)
  tampered_components, tampered_envelope =
    Min0CoreForth::PersistentPackage.decode_image(resealed_component_tamper)
  resealed_container_passes_structure = true
  image_signature_rejects_resealed_tamper = persistent_rejected(Min0CoreForth::ImageError) do
    Min0CoreForth::ImageEnvelope.validate(
      tampered_components,
      tampered_envelope,
      require_authentication: true,
      trusted_public_keys: trusted_image_keys
    )
  end
  extra_metadata_envelope = Marshal.load(Marshal.dump(signed))
  extra_metadata_envelope[:"attacker-note"] = "not covered by image identity"
  extra_metadata_package = Min0CoreForth::PersistentPackage.encode_image(
    source_components, extra_metadata_envelope
  )
  extra_metadata_components, extra_metadata_loaded =
    Min0CoreForth::PersistentPackage.decode_image(extra_metadata_package)
  unknown_image_metadata_rejected = persistent_rejected(Min0CoreForth::ImageError) do
    Min0CoreForth::ImageEnvelope.validate(
      extra_metadata_components,
      extra_metadata_loaded,
      require_authentication: true,
      trusted_public_keys: trusted_image_keys
    )
  end

  rejected = {
    truncated: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(truncated)
    end,
    trailing_data: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(trailing)
    end,
    checksum_tamper: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(checksum_tamper)
    end,
    declared_length_bomb: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(declared_length_bomb)
    end,
    section_count_bomb: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(section_count_bomb)
    end,
    unknown_version: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(unknown_version)
    end,
    unknown_kind: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(unknown_kind)
    end,
    duplicate_section: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(duplicate_section)
    end,
    overlapping_sections: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(overlap)
    end,
    section_length_bomb: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(section_length_bomb)
    end,
    duplicate_json_key: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(duplicate_json)
    end,
    noncanonical_json: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(noncanonical_json)
    end,
    deep_json: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(deep_json)
    end,
    long_json_integer: persistent_rejected(Min0CoreForth::PersistentFormatError) do
      Min0CoreForth::PersistentPackage.decode_image(long_integer_json)
    end,
    oversized_file: oversized_file_rejected_before_parse
  }

  {
    implementation: implementation,
    format_version: 1,
    limits: {
      max_file_bytes: Min0CoreForth::PERSISTENT_DEFAULT_LIMITS.max_file_bytes,
      max_sections: Min0CoreForth::PERSISTENT_DEFAULT_LIMITS.max_sections,
      max_metadata_bytes: Min0CoreForth::PERSISTENT_DEFAULT_LIMITS.max_metadata_bytes
    },
    packages: {
      image: {
        bytes: image_package.bytesize,
        sha256: Digest::SHA256.hexdigest(image_package)
      },
      trust_bundle: {
        bytes: trust_package.bytesize,
        sha256: Digest::SHA256.hexdigest(trust_package)
      },
      root_policy_chain: {
        bytes: root_package.bytesize,
        sha256: Digest::SHA256.hexdigest(root_package)
      }
    },
    external_file: {
      write_bytes: write_result[:bytes],
      write_sha256: write_result[:sha256],
      identity: loaded_envelope.fetch("identity_sha256"),
      generation: validated_image[:generation],
      stack: stack
    },
    trust_chain: {
      root_epoch: validated_root[:epoch],
      trust_epoch: validated_trust[:epoch],
      image_key_id: SIGNED_IMAGE_KEY_ID,
      valid: true
    },
    layering: {
      resealed_container_passes_structure: resealed_container_passes_structure,
      image_signature_rejects_resealed_tamper: image_signature_rejects_resealed_tamper,
      unknown_image_metadata_rejected: unknown_image_metadata_rejected
    },
    rejected: rejected
  }
end

puts JSON.generate(run_persistent_package_demo) if $PROGRAM_NAME == __FILE__
