import copy
import unittest

from constructor_image_fixture import (
    IMAGE_VERSION,
    build_envelope,
    load_envelope,
    make_system,
)
from min0_core_forth_dictionary import DictionaryError, InvalidDictionary


class ConstructorImageTests(unittest.TestCase):
    def test_python_envelope_round_trip_executes_record(self) -> None:
        result = load_envelope(build_envelope())
        self.assertEqual(result["plan_version"], 1)
        self.assertEqual(result["actions"], [2, 3, 4, 0])
        self.assertEqual(result["stack"], [0x8000])
        self.assertEqual(result["body_hex"], "ab000000")
        self.assertEqual(result["data_here"], 0x8004)

    def test_transport_version_is_rejected(self) -> None:
        envelope = build_envelope()
        envelope["version"] = IMAGE_VERSION + 1
        with self.assertRaisesRegex(ValueError, "version"):
            load_envelope(envelope)

    def test_embedded_plan_version_is_rejected(self) -> None:
        envelope = build_envelope()
        headers = bytearray.fromhex(envelope["dictionary_hex"])
        offset = envelope["record_plan"] - envelope["dictionary_base"] + 4
        headers[offset : offset + 4] = (2).to_bytes(4, "little")
        envelope["dictionary_hex"] = headers.hex()
        with self.assertRaisesRegex(InvalidDictionary, "plan version"):
            load_envelope(envelope)

    def test_component_loader_rolls_back_rejected_dictionary(self) -> None:
        envelope = build_envelope()
        headers = bytearray.fromhex(envelope["dictionary_hex"])
        offset = envelope["record_plan"] - envelope["dictionary_base"] + 4
        headers[offset : offset + 4] = (2).to_bytes(4, "little")
        vm, dictionary = make_system()
        vm.load(bytes.fromhex(envelope["code_hex"]), envelope["code_base"])

        with self.assertRaises(InvalidDictionary):
            dictionary.load_images(
                headers,
                latest=envelope["latest"],
                body_image=bytes.fromhex(envelope["body_hex"]),
            )

        self.assertEqual(dictionary.here, dictionary.base)
        self.assertEqual(dictionary.latest, 0)
        self.assertEqual(dictionary.data_here, dictionary.body_base)
        self.assertEqual(vm.read_bytes(dictionary.base, len(headers)), bytes(len(headers)))

    def test_component_loader_requires_empty_dictionary(self) -> None:
        envelope = build_envelope()
        _vm, dictionary = make_system()
        dictionary.add_created("EXISTING")
        with self.assertRaisesRegex(DictionaryError, "empty dictionary"):
            dictionary.load_images(
                bytes.fromhex(envelope["dictionary_hex"]),
                latest=envelope["latest"],
            )

    def test_hex_and_allocator_lengths_are_validated(self) -> None:
        bad_hex = build_envelope()
        bad_hex["code_hex"] = "0Z"
        with self.assertRaisesRegex(ValueError, "hex"):
            load_envelope(bad_hex)

        bad_length = copy.deepcopy(build_envelope())
        bad_length["header_here"] += 1
        with self.assertRaisesRegex(ValueError, "DICTIONARY length"):
            load_envelope(bad_length)


if __name__ == "__main__":
    unittest.main(verbosity=2)
