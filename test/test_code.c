#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// ---------------------------------------------------------
// 1. INLINING TEST CASE
// ---------------------------------------------------------
static inline __attribute__((always_inline)) int inline_add(int a, int b) {
    // This function will be inlined at -O2.
    // At -O0, it will have its own stack frame.
    volatile int temp = a + b;
    return temp;
}

int caller_of_inline(int x) {
    volatile int local_var = 42;
    return inline_add(x, local_var);
}

// ---------------------------------------------------------
// 2. DEEP NESTED CALLS & HEAVY ALLOCAS
// ---------------------------------------------------------
void hash_data(const char *input, int len) {
    // Spill-heavy simulated function
    volatile int a = 1, b = 2, c = 3, d = 4, e = 5, f = 6, g = 7, h = 8;
    volatile int sum = a + b + c + d + e + f + g + h;
    (void)sum;
}

void format_json(const char *sensor_name, double value) {
    // Heavy local array allocation (Alloca)
    char buffer[512]; 
    sprintf(buffer, "{\"sensor\": \"%s\", \"value\": %.2f}", sensor_name, value);
    hash_data(buffer, strlen(buffer));
}

void process_sensor_data() {
    volatile int status = 100;
    format_json("TemperatureSensor", 24.5);
    (void)status;
}

// Entry Point 1 (Task 1)
void vTask1(void *pvParameters) {
    while (1) {
        process_sensor_data();
    }
}

// ---------------------------------------------------------
// 3. INDIRECT CALLS (FUNCTION POINTER DISPATCH)
// ---------------------------------------------------------
typedef void (*algo_ptr)(int);

void algorithm_fast(int val) {
    volatile int x = val + 1;
    (void)x;
}

void algorithm_slow(int val) {
    // Allocate 128 bytes to show a larger stack target
    char local_buf[128];
    memset(local_buf, val, 128);
    (void)local_buf;
}

// Entry Point 2 (Task 2)
void vTask2(void *pvParameters) {
    volatile int selector = rand() % 2;
    algo_ptr current_algo = (selector == 0) ? algorithm_fast : algorithm_slow;
    
    // Indirect call via function pointer
    current_algo(42);
}

// ---------------------------------------------------------
// 4. RECURSION TESTS (DIRECT & INDIRECT)
// ---------------------------------------------------------

// Direct recursion
int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

// Indirect recursion (ping-pong mutual recursion)
void pong(int depth);

void ping(int depth) {
    if (depth <= 0) return;
    pong(depth - 1);
}

void pong(int depth) {
    if (depth <= 0) return;
    ping(depth - 1);
}

// Entry Point 3 (Task 3)
void vTask3(void *pvParameters) {
    int val = factorial(5);
    ping(val);
}

// Main method to make it a compilable program
int main() {
    vTask1(NULL);
    vTask2(NULL);
    vTask3(NULL);
    return 0;
}
