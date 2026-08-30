import unittest

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_linker import build_manifest
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_verify import BytecodeVerificationError, verify_image_bytecode
from min0_core_forth_vm import (
    Assembler,
    ExecutionPolicyError,
    MemoryFault,
    MemoryRegion,
    Min0CoreForthVM,
    Op,
    RegionMemory,
    ServiceRegistrationError,
    ServiceRegistrySealed,
    UnknownService,
)
from service_output_demo import run_demo


def components(code: bytes) -> dict[str, bytes]:
    return {"code": code, "dictionary": b"", "data": b""}


BASES = {"code": 0, "dictionary": 0x1000, "data": 0x2000}


class ServiceBoundaryTests(unittest.TestCase):
    def test_registered_service_executes_and_unknown_id_is_rejected(self) -> None:
        vm = Min0CoreForthVM()
        calls: list[str] = []
        vm.register_service(7, lambda: calls.append("called"))
        with self.assertRaises(ServiceRegistrationError):
            vm.register_service(7, lambda: None)
        assembler = Assembler()
        assembler.emit(Op.SERVICE, 7)
        assembler.emit(Op.HALT)
        vm.load(assembler.build())
        self.assertEqual(vm.run(), [])
        self.assertEqual(calls, ["called"])

        vm = Min0CoreForthVM()
        assembler = Assembler()
        assembler.emit(Op.SERVICE, 7)
        assembler.emit(Op.HALT)
        vm.load(assembler.build())
        with self.assertRaises(UnknownService):
            vm.run()

    def test_terminal_service_fault_is_atomic_and_zero_length_is_safe(self) -> None:
        vm = Min0CoreForthVM()
        dictionary = RuntimeDictionary(vm)
        install_core_primitives(dictionary)
        outer = OuterInterpreter(vm, dictionary)
        outer.interpret("65 EMIT")
        assembler = Assembler()
        assembler.emit(Op.SERVICE, 1)
        assembler.emit(Op.HALT)
        program = assembler.build()
        vm.load(program)
        vm.data_stack[:] = [65534, 4]
        with self.assertRaises(MemoryFault):
            vm.run()
        self.assertEqual(vm.data_stack, [65534, 4])
        self.assertEqual(outer.output, ["A"])

        vm.load(program)
        vm.data_stack[:] = [0xFFFFFFFF, 0]
        self.assertEqual(vm.run(), [])
        self.assertEqual(outer.output, ["A"])

    def test_verifier_derives_service_ids_and_protects_operand_bytes(self) -> None:
        valid = bytes([Op.SERVICE]) + (1).to_bytes(4, "little") + bytes([Op.HALT])
        summary = verify_image_bytecode(components(valid), BASES, build_manifest([]))
        self.assertEqual(summary["service_ids"], [1])
        self.assertEqual(summary["service_addresses"], [0])
        self.assertEqual(summary["boundaries"], [0, 5])

        with self.assertRaises(BytecodeVerificationError):
            verify_image_bytecode(
                components(bytes([Op.SERVICE, 1, 0])), BASES, build_manifest([])
            )
        with self.assertRaises(BytecodeVerificationError):
            verify_image_bytecode(
                components(bytes([Op.SERVICE]) + (0).to_bytes(4, "little")),
                BASES,
                build_manifest([]),
            )
        with self.assertRaises(BytecodeVerificationError):
            verify_image_bytecode(
                components(valid),
                BASES,
                build_manifest(
                    [{
                        "section": "code", "offset": 1, "target": "data",
                        "width": 4, "kind": "string-address",
                    }]
                ),
            )

        branch_into_operand = (
            bytes([Op.SERVICE])
            + (1).to_bytes(4, "little")
            + bytes([Op.BRANCH])
            + (1).to_bytes(4, "little")
            + bytes([Op.HALT])
        )
        with self.assertRaises(BytecodeVerificationError):
            verify_image_bytecode(
                components(branch_into_operand),
                BASES,
                build_manifest(
                    [{
                        "section": "code", "offset": 6, "target": "code",
                        "width": 4, "kind": "branch",
                    }]
                ),
            )

    def test_seal_requires_services_and_makes_registry_immutable(self) -> None:
        code = bytes([Op.SERVICE]) + (1).to_bytes(4, "little") + bytes([Op.HALT])
        summary = verify_image_bytecode(components(code), BASES, build_manifest([]))

        code_region = MemoryRegion("CODE", 0, 16, "rwx", programmable=True)
        bus = RegionMemory(16, [code_region])
        vm = Min0CoreForthVM(memory_size=16, memory_bus=bus)
        vm.load(code)
        calls: list[int] = []
        vm.register_service(1, lambda: calls.append(1))
        vm.seal_verified_execution(summary)
        self.assertTrue(vm.service_registry_sealed)
        self.assertEqual(vm.run(), [])
        self.assertEqual(calls, [1])
        with self.assertRaises(ServiceRegistrySealed):
            vm.register_service(2, lambda: None)

        missing_region = MemoryRegion("CODE", 0, 16, "rwx", programmable=True)
        missing_bus = RegionMemory(16, [missing_region])
        missing_vm = Min0CoreForthVM(memory_size=16, memory_bus=missing_bus)
        missing_vm.load(code)
        with self.assertRaises(ExecutionPolicyError):
            missing_vm.seal_verified_execution(summary)
        self.assertEqual(missing_region.permissions, "rwx")

    def test_compiled_dot_quote_runs_with_code_and_data_sealed(self) -> None:
        result = run_demo()
        self.assertEqual(result["service_ids"], [1])
        self.assertEqual(result["registered_service_ids"], [1])
        self.assertTrue(result["registry_sealed"])
        self.assertTrue(result["late_registration_rejected"])
        self.assertEqual(result["stack"], [])
        self.assertEqual(result["terminal_text"], "Hello Service")
        self.assertEqual(result["code_permissions"], "rx")
        self.assertEqual(result["data_permissions"], "r")


if __name__ == "__main__":
    unittest.main(verbosity=2)
