#include "min0_rp2350_runtime.h"

#include <limits.h>
#include <string.h>

typedef struct {
    const min0_runtime_capability *capability;
    uint32_t address;
} checked_address;

static min0_helper_status fail(
    min0_rp2350_execution_context *context, min0_helper_status status
) {
    if (context->status == MIN0_HELPER_OK) {
        context->status = status;
    }
    return context->status;
}

static min0_helper_status active_status(
    min0_rp2350_execution_context *context
) {
    if (context == NULL) {
        return MIN0_HELPER_INVALID_STATE;
    }
    if (context->state != MIN0_TRANSACTION_ACTIVE) {
        return context->status != MIN0_HELPER_OK
            ? context->status : MIN0_HELPER_INVALID_STATE;
    }
    return context->status;
}

static const min0_runtime_capability *find_capability(
    const min0_rp2350_execution_context *context, uint32_t identifier
) {
    size_t index;
    for (index = 0; index < context->capability_count; ++index) {
        if (context->capabilities[index].identifier == identifier) {
            return &context->capabilities[index];
        }
    }
    return NULL;
}

static min0_helper_status check_address(
    min0_rp2350_execution_context *context,
    uint32_t capability_id,
    uint32_t base,
    int32_t offset,
    uint32_t permission,
    checked_address *result
) {
    const min0_runtime_capability *capability =
        find_capability(context, capability_id);
    int64_t address;
    uint64_t window_end;
    if (capability == NULL) {
        return fail(context, MIN0_HELPER_UNKNOWN_CAPABILITY);
    }
    address = (int64_t)(uint64_t)base + (int64_t)offset;
    if (address < 0 || (uint64_t)address > (uint64_t)UINT32_MAX - 3u) {
        return fail(context, MIN0_HELPER_ADDRESS_OVERFLOW);
    }
    if (((uint32_t)address & 3u) != 0u) {
        return fail(context, MIN0_HELPER_UNALIGNED_ADDRESS);
    }
    window_end = (uint64_t)capability->logical_base + capability->size;
    if ((uint64_t)address < capability->logical_base ||
        (uint64_t)address + 4u > window_end) {
        return fail(context, MIN0_HELPER_ADDRESS_RANGE);
    }
    if ((capability->permissions & permission) == 0u) {
        return fail(
            context,
            permission == MIN0_CAPABILITY_READ
                ? MIN0_HELPER_READ_DENIED : MIN0_HELPER_WRITE_DENIED
        );
    }
    result->capability = capability;
    result->address = (uint32_t)address;
    return MIN0_HELPER_OK;
}

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
) {
    size_t left;
    size_t right;
    if (context == NULL ||
        (stack_capacity != 0u && data_stack == NULL) ||
        stack_depth > stack_capacity ||
        input_count > stack_depth ||
        output_count > stack_capacity - (stack_depth - input_count) ||
        (output_count != 0u &&
         (staged_outputs == NULL || output_present == NULL)) ||
        (capability_count != 0u && capabilities == NULL) ||
        (pending_capacity != 0u && pending_writes == NULL)) {
        return MIN0_HELPER_INVALID_STATE;
    }
    for (left = 0; left < capability_count; ++left) {
        uint64_t end = (uint64_t)capabilities[left].logical_base +
            capabilities[left].size;
        if (capabilities[left].bytes == NULL || end > UINT64_C(0x100000000)) {
            return MIN0_HELPER_INVALID_STATE;
        }
        for (right = left + 1u; right < capability_count; ++right) {
            if (capabilities[left].identifier == capabilities[right].identifier) {
                return MIN0_HELPER_INVALID_STATE;
            }
        }
    }
    memset(context, 0, sizeof(*context));
    context->data_stack = data_stack;
    context->stack_capacity = stack_capacity;
    context->stack_depth = stack_depth;
    context->original_depth = stack_depth;
    context->input_count = input_count;
    context->output_count = output_count;
    context->staged_outputs = staged_outputs;
    context->output_present = output_present;
    context->capabilities = capabilities;
    context->capability_count = capability_count;
    context->pending_writes = pending_writes;
    context->pending_capacity = pending_capacity;
    context->status = MIN0_HELPER_OK;
    context->state = MIN0_TRANSACTION_ACTIVE;
    if (output_count != 0u) {
        memset(output_present, 0, output_count);
    }
    return MIN0_HELPER_OK;
}

min0_helper_load_result min0_runtime_frame_load(
    min0_rp2350_execution_context *context, uint32_t input_index
) {
    min0_helper_load_result result = {MIN0_HELPER_INVALID_STATE, 0u};
    min0_helper_status status = active_status(context);
    if (status != MIN0_HELPER_OK) {
        result.status = status;
        return result;
    }
    if ((size_t)input_index >= context->input_count) {
        result.status = fail(context, MIN0_HELPER_INPUT_INDEX);
        return result;
    }
    result.status = MIN0_HELPER_OK;
    result.value = context->data_stack[
        context->original_depth - context->input_count + input_index
    ];
    return result;
}

min0_helper_status min0_runtime_result_stage(
    min0_rp2350_execution_context *context,
    uint32_t output_index,
    uint32_t value
) {
    min0_helper_status status = active_status(context);
    if (status != MIN0_HELPER_OK) {
        return status;
    }
    if ((size_t)output_index >= context->output_count) {
        return fail(context, MIN0_HELPER_OUTPUT_INDEX);
    }
    if (context->output_present[output_index] != 0u) {
        return fail(context, MIN0_HELPER_OUTPUT_DUPLICATE);
    }
    context->staged_outputs[output_index] = value;
    context->output_present[output_index] = 1u;
    return MIN0_HELPER_OK;
}

min0_helper_load_result min0_runtime_checked_ld32(
    min0_rp2350_execution_context *context,
    uint32_t capability_id,
    uint32_t base,
    int32_t offset
) {
    min0_helper_load_result result = {MIN0_HELPER_INVALID_STATE, 0u};
    checked_address checked;
    min0_helper_status status = active_status(context);
    size_t index;
    size_t byte_offset;
    if (status != MIN0_HELPER_OK) {
        result.status = status;
        return result;
    }
    status = check_address(
        context, capability_id, base, offset, MIN0_CAPABILITY_READ, &checked
    );
    if (status != MIN0_HELPER_OK) {
        result.status = status;
        return result;
    }
    for (index = context->pending_count; index > 0u; --index) {
        const min0_pending_write *pending = &context->pending_writes[index - 1u];
        if (pending->capability_id == capability_id &&
            pending->address == checked.address) {
            result.status = MIN0_HELPER_OK;
            result.value = pending->value;
            return result;
        }
    }
    byte_offset = (size_t)(checked.address - checked.capability->logical_base);
    memcpy(&result.value, checked.capability->bytes + byte_offset, 4u);
    result.status = MIN0_HELPER_OK;
    return result;
}

min0_helper_status min0_runtime_stage_st32(
    min0_rp2350_execution_context *context,
    uint32_t capability_id,
    uint32_t base,
    int32_t offset,
    uint32_t value
) {
    checked_address checked;
    min0_helper_status status = active_status(context);
    size_t index;
    if (status != MIN0_HELPER_OK) {
        return status;
    }
    status = check_address(
        context, capability_id, base, offset, MIN0_CAPABILITY_WRITE, &checked
    );
    if (status != MIN0_HELPER_OK) {
        return status;
    }
    for (index = 0; index < context->pending_count; ++index) {
        min0_pending_write *pending = &context->pending_writes[index];
        if (pending->capability_id == capability_id &&
            pending->address == checked.address) {
            pending->value = value;
            return MIN0_HELPER_OK;
        }
    }
    if (context->pending_count >= context->pending_capacity) {
        return fail(context, MIN0_HELPER_PENDING_FULL);
    }
    context->pending_writes[context->pending_count].capability_id = capability_id;
    context->pending_writes[context->pending_count].address = checked.address;
    context->pending_writes[context->pending_count].value = value;
    ++context->pending_count;
    return MIN0_HELPER_OK;
}

min0_helper_status min0_runtime_frame_commit(
    min0_rp2350_execution_context *context,
    uint32_t input_count,
    uint32_t output_count
) {
    min0_helper_status status = active_status(context);
    size_t index;
    size_t prefix_depth;
    if (status != MIN0_HELPER_OK) {
        return status;
    }
    if ((size_t)input_count != context->input_count ||
        (size_t)output_count != context->output_count) {
        return fail(context, MIN0_HELPER_CONTRACT_MISMATCH);
    }
    for (index = 0; index < context->output_count; ++index) {
        if (context->output_present[index] == 0u) {
            return fail(context, MIN0_HELPER_OUTPUT_MISSING);
        }
    }
    for (index = 0; index < context->pending_count; ++index) {
        const min0_pending_write *pending = &context->pending_writes[index];
        const min0_runtime_capability *capability =
            find_capability(context, pending->capability_id);
        size_t byte_offset;
        if (capability == NULL) {
            return fail(context, MIN0_HELPER_INVALID_STATE);
        }
        byte_offset = (size_t)(pending->address - capability->logical_base);
        memcpy(capability->bytes + byte_offset, &pending->value, 4u);
    }
    prefix_depth = context->original_depth - context->input_count;
    for (index = 0; index < context->output_count; ++index) {
        context->data_stack[prefix_depth + index] = context->staged_outputs[index];
    }
    context->stack_depth = prefix_depth + context->output_count;
    context->pending_count = 0u;
    context->state = MIN0_TRANSACTION_COMMITTED;
    return MIN0_HELPER_OK;
}

min0_helper_status min0_runtime_abort_transaction(
    min0_rp2350_execution_context *context,
    min0_helper_status status
) {
    if (context == NULL || context->state == MIN0_TRANSACTION_COMMITTED) {
        return MIN0_HELPER_INVALID_STATE;
    }
    if (context->state == MIN0_TRANSACTION_ABORTED) {
        return context->status;
    }
    if (context->status == MIN0_HELPER_OK) {
        context->status = status == MIN0_HELPER_OK ? MIN0_HELPER_ABORTED : status;
    }
    context->pending_count = 0u;
    if (context->output_count != 0u) {
        memset(context->output_present, 0, context->output_count);
    }
    context->stack_depth = context->original_depth;
    context->state = MIN0_TRANSACTION_ABORTED;
    return context->status;
}
