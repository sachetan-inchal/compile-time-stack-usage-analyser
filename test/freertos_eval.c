/**
 * freertos_eval.c — RTOS Stack Usage Evaluation Harness
 *
 * A self-contained C program that mimics a realistic FreeRTOS application
 * WITHOUT requiring the actual FreeRTOS headers or RTOS runtime.
 *
 * Purpose (Deliverable #5):
 *   Evaluate the compile-time stack analyzer against known/expected stack
 *   depths, comparing static estimates to the documented "expected stack
 *   high-water mark" for each task.
 *
 * Ground truth methodology:
 *   Each function has a comment indicating the EXPECTED minimum stack frame
 *   size in bytes for the x86_64 target at -O0. These serve as the reference
 *   against which the analyzer's MachineFunction-derived estimates are compared.
 *
 *   In a real FreeRTOS deployment you would compare against:
 *     uxTaskGetStackHighWaterMark(taskHandle)
 *   which returns the minimum free stack words ever observed at runtime.
 *   Here we reason from source to provide ground-truth without needing a
 *   physical RTOS target.
 *
 * Task structure:
 *   Task A — vSensorTask:    Deep call chain, large alloca (512 B buffer)
 *                            Expected chain depth: ~620 B
 *   Task B — vCommsTask:     Indirect call via function pointer dispatch
 *                            Expected chain depth: ~300 B (+ indirect penalty)
 *   Task C — vControlTask:   Mutual recursion (ping/pong) + moderate depth
 *                            Expected chain depth: unbounded (recursion flag)
 *
 * Build:
 *   clang -O0 -S -emit-llvm test/freertos_eval.c -o test/freertos_eval_O0.ll
 *   clang -O0 -fstack-usage -c test/freertos_eval.c -o test/freertos_eval_O0.o
 */

#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* =========================================================================
 * FreeRTOS type stubs — mirrors the real API without linking the RTOS
 * ========================================================================= */
typedef void* TaskHandle_t;
typedef uint32_t UBaseType_t;
typedef uint32_t StackType_t;

/* Stub: in a real FreeRTOS app this returns min free stack words observed */
UBaseType_t uxTaskGetStackHighWaterMark(TaskHandle_t xTask) {
    (void)xTask;
    return 0; /* stubbed — not called at runtime in this harness */
}

/* =========================================================================
 * TASK A — vSensorTask
 * Models a sensor acquisition + JSON formatting pipeline.
 * Expected ground truth: deep call chain, dominated by format_sensor_json.
 * ========================================================================= */

/**
 * compute_checksum — small leaf function.
 * Expected frame: ~48 B (8 volatile ints + overhead)
 */
static uint32_t compute_checksum(const uint8_t *data, uint32_t len) {
    volatile uint32_t a = 0, b = 0, c = 0, d = 0;
    volatile uint32_t e = 0, f = 0, g = 0, h = 0;
    for (uint32_t i = 0; i < len; i++) {
        a ^= data[i];
        b += data[i];
        c ^= (a << 3);
        d += (b >> 1);
        e ^= (c + i);
        f += (d ^ a);
        g ^= (e + b);
        h += (f ^ c);
    }
    return a ^ b ^ c ^ d ^ e ^ f ^ g ^ h;
}

/**
 * format_sensor_json — large alloca.
 * Expected frame: ~580 B (512 B buffer + format overhead + args)
 */
static void format_sensor_json(const char *sensor_name,
                                float value,
                                uint32_t timestamp,
                                uint8_t *out_buf,
                                uint32_t out_len) {
    char json_buf[512];  /* This alloca dominates the frame size */
    snprintf(json_buf, sizeof(json_buf),
             "{\"sensor\":\"%s\",\"value\":%.4f,\"ts\":%u}",
             sensor_name, (double)value, timestamp);

    uint32_t chk = compute_checksum((uint8_t*)json_buf, strlen(json_buf));
    snprintf((char*)out_buf, out_len, "%s,\"chk\":%u}", json_buf, chk);
}

/**
 * acquire_sensor — mid-level function, medium frame.
 * Expected frame: ~64 B (local variables + call args)
 */
static float acquire_sensor(uint32_t channel) {
    volatile float reading = 0.0f;
    volatile uint32_t raw = channel * 37 + 1024; /* simulated ADC read */
    volatile float voltage = (float)raw * 3.3f / 4096.0f;
    reading = voltage * 100.0f; /* scale to engineering unit */
    return reading;
}

/**
 * vSensorTask — FreeRTOS task entry point.
 * Chain: vSensorTask -> acquire_sensor -> format_sensor_json -> compute_checksum
 * Expected worst-case cumulative depth: ~750 B
 * Suggested RTOS stack allocation: 1024 B (safe margin)
 */
void vSensorTask(void *pvParameters) {
    (void)pvParameters;
    static uint32_t tick = 0;
    uint8_t output[64];

    /* Infinite task loop */
    for (;;) {
        float reading = acquire_sensor(tick % 4);
        format_sensor_json("TemperatureSensor", reading, tick, output, sizeof(output));
        tick++;
        /* In real FreeRTOS: vTaskDelay(pdMS_TO_TICKS(100)); */
    }
}

/* =========================================================================
 * TASK B — vCommsTask
 * Models a protocol dispatch via function pointer (indirect call).
 * Tests the analyzer's indirect call upper-bound modeling.
 * ========================================================================= */
typedef void (*protocol_handler_t)(const uint8_t *frame, uint32_t len);

/**
 * handle_uart — protocol handler A.
 * Expected frame: ~160 B (128 B local buf + overhead)
 */
static void handle_uart(const uint8_t *frame, uint32_t len) {
    char uart_buf[128];
    uint32_t copy_len = (len < 127) ? len : 127;
    memcpy(uart_buf, frame, copy_len);
    uart_buf[copy_len] = '\0';
    /* Simulate UART transmission */
    volatile uint32_t bytes_sent = copy_len;
    (void)bytes_sent;
}

/**
 * handle_spi — protocol handler B.
 * Expected frame: ~280 B (256 B local buf + overhead)
 */
static void handle_spi(const uint8_t *frame, uint32_t len) {
    uint8_t spi_staging[256]; /* SPI DMA staging buffer */
    uint32_t aligned_len = (len + 3) & ~3u; /* 4-byte align */
    if (aligned_len > sizeof(spi_staging)) aligned_len = sizeof(spi_staging);
    memcpy(spi_staging, frame, aligned_len);
    /* Simulate SPI DMA transfer */
    volatile uint32_t crc = compute_checksum(spi_staging, aligned_len);
    (void)crc;
}

/**
 * handle_i2c — protocol handler C.
 * Expected frame: ~64 B (small overhead, no large locals)
 */
static void handle_i2c(const uint8_t *frame, uint32_t len) {
    volatile uint32_t addr = frame[0];
    volatile uint32_t reg  = frame[1];
    volatile uint32_t data = (len > 2) ? frame[2] : 0;
    /* Simulate I2C register write */
    (void)(addr + reg + data);
}

/**
 * dispatch_protocol — indirect call dispatch.
 * At runtime the handler is selected based on active_protocol.
 * The analyzer cannot statically resolve this — it applies the
 * configured indirect call upper bound (default 256 B).
 *
 * Expected frame: ~48 B own frame + indirect_cost penalty in analysis.
 */
static void dispatch_protocol(uint32_t active_protocol,
                               const uint8_t *frame,
                               uint32_t len) {
    protocol_handler_t handlers[] = {handle_uart, handle_spi, handle_i2c};
    uint32_t idx = active_protocol % 3;
    /* Indirect call — resolved only at runtime */
    handlers[idx](frame, len);
}

/**
 * vCommsTask — FreeRTOS task entry point.
 * Chain: vCommsTask -> dispatch_protocol -> [handle_uart | handle_spi | handle_i2c]
 * The worst-case static path (handle_spi) uses 280 B.
 * Expected cumulative depth (worst-case): ~360 B
 * Suggested RTOS stack allocation: 512 B
 */
void vCommsTask(void *pvParameters) {
    (void)pvParameters;
    static uint8_t frame_buf[32];
    static uint32_t protocol_idx = 0;

    for (;;) {
        /* Simulate receiving a frame */
        volatile uint32_t frame_len = 8 + (protocol_idx % 16);
        memset(frame_buf, (int)protocol_idx, frame_len);
        dispatch_protocol(protocol_idx % 3, frame_buf, frame_len);
        protocol_idx++;
    }
}

/* =========================================================================
 * TASK C — vControlTask
 * Models a PID-like control loop with mutual recursion (for recursion detection).
 * ========================================================================= */

/* Forward declarations for mutual recursion */
static int32_t pid_correct(int32_t error, uint32_t depth);

/**
 * pid_anti_windup — mutually recursive with pid_correct.
 * Implements anti-windup saturation with a bounded recursive correction.
 * Expected behavior: analyzer flags mutual recursion (unbounded depth).
 */
static int32_t pid_anti_windup(int32_t output, uint32_t depth) {
    volatile int32_t limit = 1000;
    if (depth == 0) return output;
    if (output > limit) {
        /* Recursively reduce via correction — triggers mutual recursion */
        return pid_correct(output - limit, depth - 1);
    }
    if (output < -limit) {
        return pid_correct(output + limit, depth - 1);
    }
    return output;
}

/**
 * pid_correct — mutually recursive with pid_anti_windup.
 * Expected frame: ~32 B
 */
static int32_t pid_correct(int32_t error, uint32_t depth) {
    volatile int32_t kp = 10, ki = 2, kd = 5;
    volatile int32_t correction = (kp * error + ki + kd) / 3;
    /* Anti-windup check — mutual recursion back to pid_anti_windup */
    return pid_anti_windup(correction, depth);
}

/**
 * run_pid_controller — top-level PID call.
 * Expected frame: ~64 B (several locals + call to pid_correct)
 */
static int32_t run_pid_controller(int32_t setpoint, int32_t measured) {
    volatile int32_t error = setpoint - measured;
    volatile int32_t integral_term = error / 10;
    volatile int32_t derivative_term = error * 2;
    volatile int32_t feed_forward = setpoint / 20;
    volatile int32_t raw_output = error + integral_term + derivative_term + feed_forward;
    return pid_correct(raw_output, 3); /* bounded recursion depth */
}

/**
 * vControlTask — FreeRTOS task entry point.
 * Chain: vControlTask -> run_pid_controller -> pid_correct <-> pid_anti_windup (recursive!)
 * Analyzer should: flag recursion, report unbounded depth warning.
 * Suggested RTOS stack allocation: 2048 B (conservative for recursive tasks)
 */
void vControlTask(void *pvParameters) {
    (void)pvParameters;
    volatile int32_t setpoint = 500;
    volatile int32_t measured = 0;

    for (;;) {
        int32_t control_signal = run_pid_controller(setpoint, measured);
        /* Simulate plant response */
        measured += control_signal / 100;
        if (measured > 1000) measured = 0;
    }
}

/* =========================================================================
 * main — ties tasks together for a compilable standalone binary.
 * In real FreeRTOS these would be xTaskCreate() calls followed by
 * vTaskStartScheduler(). Here we call them once for static analysis purposes.
 * ========================================================================= */
int main(void) {
    /* These calls let the compiler see all functions as reachable from main,
     * ensuring the call graph extractor picks them all up. */
    vSensorTask(NULL);
    vCommsTask(NULL);
    vControlTask(NULL);
    return 0;
}
