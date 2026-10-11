#ifndef MIN0_RP2350_RUNTIME_H
#define MIN0_RP2350_RUNTIME_H

#include <stddef.h>
#include <stdint.h>

#define MIN0_RP2350_HELPER_ABI_VERSION "min0-rp2350-helper-abi/0.2"

typedef enum {
    MIN0_HELPER_OK = 0,
    MIN0_HELPER_INVALID_STATE = 1,
    MIN0_HELPER_INPUT_INDEX = 2,
    MIN0_HELPER_OUTPUT_INDEX = 3,
    MIN0_HELPER_OUTPUT_DUPLICATE = 4,
    MIN0_HELPER_OUTPUT_MISSING = 5,
    MIN0_HELPER_CONTRACT_MISMATCH = 6,
    MIN0_HELPER_UNKNOWN_CAPABILITY = 7,
    MIN0_HELPER_ADDRESS_OVERFLOW = 8,
    MIN0_HELPER_UNALIGNED_ADDRESS = 9,
    MIN0_HELPER_ADDRESS_RANGE = 10,
    MIN0_HELPER_READ_DENIED = 11,
    MIN0_HELPER_WRITE_DENIED = 12,
    MIN0_HELPER_ABORTED = 13,
    MIN0_HELPER_PENDING_FULL = 14
} min0_helper_status;

typedef enum {
    MIN0_TRANSACTION_ACTIVE = 0,
    MIN0_TRANSACTION_COMMITTED = 1,
    MIN0_TRANSACTION_ABORTED = 2
} min0_transaction_state;

enum {
    MIN0_CAPABILITY_READ = 1u,
    MIN0_CAPABILITY_WRITE = 2u
};

typedef struct {
    uint32_t identifier;
    uint32_t logical_base;
    uint32_t size;
    uint32_t permissions;
    uint8_t *bytes;
} min0_runtime_capability;

typedef struct {
    uint32_t capability_id;
    uint32_t address;
    uint32_t value;
} min0_pending_write;

typedef struct {
    uint32_t status;
    uint32_t value;
} min0_helper_load_result;

typedef struct {
    uint32_t *data_stack;
    size_t stack_capacity;
    size_t stack_depth;
    size_t original_depth;
    size_t input_count;
    size_t output_count;
    uint32_t *staged_outputs;
    uint8_t *output_present;
    const min0_runtime_capability *capabilities;
    size_t capability_count;
    min0_pending_write *pending_writes;
    size_t pending_capacity;
    size_t pending_count;
    min0_helper_status status;
    min0_transaction_state state;
} min0_rp2350_execution_context;

min0_helper_status min0_runtime_context_init(
    min0_rp2350_execution_context *context,
    uint32_t *data_stack,
    size_t stack_capacity,
    size_t stack_depth,
    size_t input_count,
    size_t output_count,
    uint32_t *staged_outputs,
    uint8_t *output_present,
    const min0_runtime_capability *capabilities,
    size_t capability_count,
    min0_pending_write *pending_writes,
    size_t pending_capacity
);

min0_helper_load_result min0_runtime_frame_load(
    min0_rp2350_execution_context *context, uint32_t input_index
);
min0_helper_status min0_runtime_result_stage(
    min0_rp2350_execution_context *context,
    uint32_t output_index,
    uint32_t value
);
min0_helper_load_result min0_runtime_checked_ld32(
    min0_rp2350_execution_context *context,
    uint32_t capability_id,
    uint32_t base,
    int32_t offset
);
min0_helper_status min0_runtime_stage_st32(
    min0_rp2350_execution_context *context,
    uint32_t capability_id,
    uint32_t base,
    int32_t offset,
    uint32_t value
);
min0_helper_status min0_runtime_frame_commit(
    min0_rp2350_execution_context *context,
    uint32_t input_count,
    uint32_t output_count
);
min0_helper_status min0_runtime_abort_transaction(
    min0_rp2350_execution_context *context,
    min0_helper_status status
);

/*
 * These portable bodies define transaction semantics.  The final RP2350
 * symbols min0_frame_load, min0_stage_st32, min0_abort_transaction, and their
 * peers require target veneers that implement the private register and tail
 * ABI before generated machine code may call them.
 */

#endif
