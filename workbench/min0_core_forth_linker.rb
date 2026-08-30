# frozen_string_literal: true

module Min0CoreForth
  MANIFEST_FORMAT = "min0-core-forth-relocation-manifest"
  MANIFEST_VERSION = 1
  MANIFEST_PROFILE = "reference32-le"
  LINK_SECTIONS = ["code", "dictionary", "data"].freeze
  REFERENCE32_LIMIT = 1 << 32

  class LinkError < StandardError; end

  module Linker
    module_function

    def build_manifest(records)
      {
        format: MANIFEST_FORMAT,
        version: MANIFEST_VERSION,
        profile: MANIFEST_PROFILE,
        records: records.map(&:dup)
      }
    end

    def link_components(components, source_bases, target_bases, manifest)
      images = normalize_components(components)
      old_bases = normalize_bases(source_bases, "source")
      new_bases = normalize_bases(target_bases, "target")
      validate_ranges(images, old_bases, "source")
      validate_ranges(images, new_bases, "target")
      raise LinkError, "manifest must be a Hash" unless manifest.is_a?(Hash)
      unless manifest.keys.map(&:to_s).sort == %w[format profile records version]
        raise LinkError, "relocation manifest fields are malformed"
      end
      unless field(manifest, :format) == MANIFEST_FORMAT
        raise LinkError, "unsupported relocation manifest format"
      end
      unless integer(field(manifest, :version), "manifest version") == MANIFEST_VERSION
        raise LinkError, "unsupported relocation manifest version"
      end
      unless field(manifest, :profile) == MANIFEST_PROFILE
        raise LinkError, "unsupported relocation manifest profile"
      end
      records = field(manifest, :records)
      raise LinkError, "manifest records must be an Array" unless records.is_a?(Array)

      occupied = LINK_SECTIONS.to_h { |section| [section, []] }
      patches = []
      records.each_with_index do |record, index|
        prefix = "relocation record #{index}"
        raise LinkError, "#{prefix} must be a Hash" unless record.is_a?(Hash)
        unless record.keys.map(&:to_s).sort == %w[kind offset section target width]
          raise LinkError, "#{prefix} fields are malformed"
        end
        section = field(record, :section)
        target = field(record, :target)
        raise LinkError, "#{prefix} has unknown patch section" unless LINK_SECTIONS.include?(section)
        raise LinkError, "#{prefix} has unknown target section" unless LINK_SECTIONS.include?(target)

        offset = integer(field(record, :offset), "#{prefix} offset")
        width = integer(field(record, :width), "#{prefix} width")
        kind = field(record, :kind)
        unless kind.is_a?(String) && !kind.empty?
          raise LinkError, "#{prefix} kind must be a nonempty String"
        end
        unless width == 4
          raise LinkError, "#{prefix} width is unsupported for Reference32"
        end
        if offset.negative? || offset + width > images.fetch(section).bytesize
          raise LinkError, "#{prefix} patch is outside its component"
        end
        if section == "dictionary" && ((old_bases.fetch(section) + offset) % 4).nonzero?
          raise LinkError, "#{prefix} dictionary patch is not cell-aligned"
        end
        interval = [offset, offset + width]
        if occupied.fetch(section).any? { |start, finish| interval[0] < finish && start < interval[1] }
          raise LinkError, "#{prefix} overlaps another patch"
        end
        occupied.fetch(section) << interval

        old_value = images.fetch(section).byteslice(offset, width).unpack1("V")
        target_start = old_bases.fetch(target)
        target_end = target_start + images.fetch(target).bytesize
        in_source = if target == "data"
                      old_value.between?(target_start, target_end)
                    else
                      old_value >= target_start && old_value < target_end
                    end
        raise LinkError, "#{prefix} value is outside its source target component" unless in_source

        new_value = old_value + new_bases.fetch(target) - old_bases.fetch(target)
        unless new_value >= 0 && new_value < REFERENCE32_LIMIT
          raise LinkError, "#{prefix} result is outside Reference32"
        end
        moved_end = new_bases.fetch(target) + images.fetch(target).bytesize
        in_target = if target == "data"
                      new_value.between?(new_bases.fetch(target), moved_end)
                    else
                      new_value >= new_bases.fetch(target) && new_value < moved_end
                    end
        raise LinkError, "#{prefix} result is outside its target component" unless in_target

        patches << [section, offset, new_value]
      end

      result = images.transform_values(&:dup)
      patches.each do |section, offset, value|
        result.fetch(section)[offset, 4] = [value].pack("V")
      end
      result
    end

    def field(hash, name)
      hash.key?(name) ? hash[name] : hash[name.to_s]
    end
    private_class_method :field

    def integer(value, label)
      raise LinkError, "#{label} must be an Integer" unless value.is_a?(Integer)

      value
    end
    private_class_method :integer

    def normalize_components(components)
      raise LinkError, "components must be a Hash" unless components.is_a?(Hash)

      LINK_SECTIONS.to_h do |section|
        value = field(components, section.to_sym)
        raise LinkError, "component #{section} must be a String" unless value.is_a?(String)

        [section, value.b]
      end
    end
    private_class_method :normalize_components

    def normalize_bases(bases, label)
      raise LinkError, "#{label} bases must be a Hash" unless bases.is_a?(Hash)

      LINK_SECTIONS.to_h do |section|
        base = integer(field(bases, section.to_sym), "#{label} base #{section}")
        unless base >= 0 && base < REFERENCE32_LIMIT
          raise LinkError, "#{label} base #{section} is outside Reference32"
        end
        [section, base]
      end
    end
    private_class_method :normalize_bases

    def validate_ranges(images, bases, label)
      ranges = LINK_SECTIONS.filter_map do |section|
        start = bases.fetch(section)
        finish = start + images.fetch(section).bytesize
        raise LinkError, "#{label} component #{section} exceeds Reference32" if finish > REFERENCE32_LIMIT

        [start, finish, section] if finish > start
      end.sort
      ranges.each_cons(2) do |previous, current|
        if current[0] < previous[1]
          raise LinkError, "#{label} components #{previous[2]} and #{current[2]} overlap"
        end
      end
    end
    private_class_method :validate_ranges
  end
end
