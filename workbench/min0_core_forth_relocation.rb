# frozen_string_literal: true

module Min0CoreForth
  SECTION_CODE = "code"
  TARGET_CODE = "code"
  TARGET_DICTIONARY = "dictionary"
  TARGET_DATA = "data"
  REFERENCE32_WIDTH = 4

  RelocationRecord = Data.define(:section, :offset, :target, :width, :kind) do
    def to_h
      {
        section: section,
        offset: offset,
        target: target,
        width: width,
        kind: kind
      }
    end
  end
end
