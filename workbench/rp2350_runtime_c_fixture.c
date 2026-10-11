#include <stdio.h>
#include <string.h>

#include "min0_rp2350_runtime.h"

static uint32_t read32(const uint8_t *bytes) {
    uint32_t value;
    memcpy(&value, bytes, 4u);
    return value;
}

static int success_case(void) {
    uint32_t stack[8] = {99u, 10u, 20u, 0x1000u};
    uint8_t memory[16] = {0};
    uint32_t outputs[2];
    uint8_t present[2];
    min0_pending_write pending[2];
    min0_runtime_capability capability = {
        7u, 0x1000u, sizeof(memory),
        MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, memory
    };
    min0_rp2350_execution_context context;
    min0_helper_load_result forwarded;
    min0_helper_status status = min0_runtime_context_init(
        &context, stack, 8u, 4u, 3u, 2u, outputs, present,
        &capability, 1u, pending, 2u
    );
    if (status != MIN0_HELPER_OK) return 1;
    if (min0_runtime_stage_st32(&context, 7u, 0x1000u, 4, 88u) != 0) return 2;
    forwarded = min0_runtime_checked_ld32(&context, 7u, 0x1000u, 4);
    if (forwarded.status != 0u || forwarded.value != 88u || read32(memory + 4) != 0u) return 3;
    if (min0_runtime_result_stage(&context, 0u, 30u) != 0) return 4;
    if (min0_runtime_result_stage(&context, 1u, 40u) != 0) return 5;
    status = min0_runtime_frame_commit(&context, 3u, 2u);
    printf(
        "success status=%u state=%u depth=%zu stack=%u,%u,%u memory=%u forwarded=%u\n",
        (unsigned)status, (unsigned)context.state, context.stack_depth,
        stack[0], stack[1], stack[2], read32(memory + 4), forwarded.value
    );
    return status == 0u ? 0 : 6;
}

static int abort_case(void) {
    uint32_t stack[8] = {99u, 10u, 20u, 0x1000u};
    uint8_t memory[4];
    uint32_t initial = 7u;
    uint32_t outputs[2];
    uint8_t present[2];
    min0_pending_write pending[1];
    min0_runtime_capability capability = {
        7u, 0x1000u, sizeof(memory),
        MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, memory
    };
    min0_rp2350_execution_context context;
    min0_helper_status status;
    memcpy(memory, &initial, 4u);
    if (min0_runtime_context_init(
        &context, stack, 8u, 4u, 3u, 2u, outputs, present,
        &capability, 1u, pending, 1u
    ) != 0) return 10;
    if (min0_runtime_result_stage(&context, 0u, 30u) != 0) return 11;
    if (min0_runtime_stage_st32(&context, 7u, 0x1000u, 0, 88u) != 0) return 12;
    status = min0_runtime_abort_transaction(&context, MIN0_HELPER_ABORTED);
    printf(
        "abort status=%u state=%u depth=%zu stack=%u,%u,%u,%u memory=%u pending=%zu\n",
        (unsigned)status, (unsigned)context.state, context.stack_depth,
        stack[0], stack[1], stack[2], stack[3], read32(memory), context.pending_count
    );
    return status == MIN0_HELPER_ABORTED ? 0 : 13;
}

static int rejection_cases(void) {
    uint32_t stack[4] = {10u, 0x1000u};
    uint8_t memory[4] = {0};
    uint32_t outputs[1];
    uint8_t present[1];
    min0_pending_write pending[1];
    min0_runtime_capability capability = {
        7u, 0x1000u, sizeof(memory), MIN0_CAPABILITY_READ, memory
    };
    min0_rp2350_execution_context context;
    min0_helper_status denied;
    min0_helper_status repeated;
    if (min0_runtime_context_init(
        &context, stack, 4u, 2u, 2u, 1u, outputs, present,
        &capability, 1u, pending, 1u
    ) != 0) return 20;
    denied = min0_runtime_stage_st32(&context, 7u, 0x1000u, 0, 1u);
    min0_runtime_abort_transaction(&context, denied);
    repeated = min0_runtime_abort_transaction(&context, MIN0_HELPER_ABORTED);
    printf(
        "reject denied=%u repeated=%u state=%u depth=%zu memory=%u\n",
        (unsigned)denied, (unsigned)repeated, (unsigned)context.state,
        context.stack_depth, read32(memory)
    );
    return denied == MIN0_HELPER_WRITE_DENIED && repeated == denied ? 0 : 21;
}

static int status_matrix_case(void) {
    uint32_t stack[4] = {10u, 0x1000u};
    uint8_t memory[4] = {0};
    uint32_t outputs[1];
    uint8_t present[1];
    min0_pending_write pending[1];
    min0_runtime_capability capability = {
        7u, 0x1000u, sizeof(memory),
        MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, memory
    };
    min0_rp2350_execution_context context;
    unsigned status[13];
    const unsigned expected[13] = {2u, 3u, 4u, 5u, 6u, 7u, 8u, 9u, 10u, 11u, 12u, 14u, 0u};
    min0_helper_load_result loaded;
    size_t index;

#define RESET(PERMISSIONS, PENDING_CAPACITY) do { \
    capability.permissions = (PERMISSIONS); \
    if (min0_runtime_context_init( \
        &context, stack, 4u, 2u, 2u, 1u, outputs, present, \
        &capability, 1u, pending, (PENDING_CAPACITY) \
    ) != MIN0_HELPER_OK) return 30; \
} while (0)

    RESET(MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, 1u);
    status[0] = min0_runtime_frame_load(&context, 2u).status;
    RESET(MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, 1u);
    status[1] = min0_runtime_result_stage(&context, 1u, 1u);
    RESET(MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, 1u);
    if (min0_runtime_result_stage(&context, 0u, 1u) != 0u) return 31;
    status[2] = min0_runtime_result_stage(&context, 0u, 2u);
    RESET(MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, 1u);
    status[3] = min0_runtime_frame_commit(&context, 2u, 1u);
    RESET(MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, 1u);
    status[4] = min0_runtime_frame_commit(&context, 1u, 1u);
    RESET(MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, 1u);
    status[5] = min0_runtime_checked_ld32(&context, 99u, 0x1000u, 0).status;
    RESET(MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, 1u);
    status[6] = min0_runtime_checked_ld32(&context, 7u, 0xFFFFFFFCu, 4).status;
    RESET(MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, 1u);
    status[7] = min0_runtime_checked_ld32(&context, 7u, 0x1000u, 2).status;
    RESET(MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, 1u);
    status[8] = min0_runtime_checked_ld32(&context, 7u, 0x1000u, 4).status;
    RESET(MIN0_CAPABILITY_WRITE, 1u);
    status[9] = min0_runtime_checked_ld32(&context, 7u, 0x1000u, 0).status;
    RESET(MIN0_CAPABILITY_READ, 1u);
    status[10] = min0_runtime_stage_st32(&context, 7u, 0x1000u, 0, 1u);
    RESET(MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, 0u);
    status[11] = min0_runtime_stage_st32(&context, 7u, 0x1000u, 0, 1u);
    RESET(MIN0_CAPABILITY_READ | MIN0_CAPABILITY_WRITE, 1u);
    loaded = min0_runtime_frame_load(&context, 0u);
    status[12] = loaded.status;

#undef RESET

    printf(
        "matrix statuses=%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u input=%u\n",
        status[0], status[1], status[2], status[3], status[4], status[5],
        status[6], status[7], status[8], status[9], status[10], status[11],
        status[12], loaded.value
    );
    for (index = 0; index < 13u; ++index) {
        if (status[index] != expected[index]) return 32;
    }
    return loaded.value == 10u ? 0 : 33;
}

int main(void) {
    int result = success_case();
    if (result != 0) return result;
    result = abort_case();
    if (result != 0) return result;
    result = rejection_cases();
    if (result != 0) return result;
    result = status_matrix_case();
    if (result != 0) return result;
    return 0;
}
