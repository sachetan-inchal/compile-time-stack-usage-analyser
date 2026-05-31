# Design Document: Compile-Time Stack Usage Analyzer

## 1. Problem Statement

Stack overflow is the **#1 cause of mysterious crashes** in embedded and RTOS systems. When an RTOS task overflows its statically-allocated stack, it silently corrupts adjacent memory — not its own — causing failures in completely unrelated code at unpredictable times. This makes bugs extremely difficult to reproduce and trace.

The fundamental gap: neither GCC nor Clang provides **call-chain-aware, whole-program** static stack analysis. Existing tools stop at per-function frame sizes and leave the cumulative summation to the developer.

**The goal**: Given any C program (or RTOS task set), automatically compute the worst-case total stack depth for every possible call chain, starting from every entry point, and flag any path that exceeds a configurable safety threshold.

---

## 2. Design Alternatives Considered

### Option A: Pure IR-Level Alloca Scanning (`AllocaInst` traversal)

**Approach:** Write an LLVM `FunctionPass` operating on LLVM IR. For each function, iterate over all `AllocaInst` instructions in its basic blocks and sum their sizes. This is purely IR-level with no backend involvement.

**Pros:**
- Simple to implement; no target machine setup needed.
- Cross-platform: runs before any target-specific lowering.
- Low compilation overhead.

**Cons (why we rejected it):**
- **Deeply inaccurate.** LLVM IR `alloca`s only represent the programmer's local variables. The backend adds significant extra stack: register spill slots, callee-saved register saves, alignment padding, call argument areas, and platform-specific ABI overhead.
- Completely invisible to the callee-saved register save area which can be 40–160 bytes on x86_64 alone.
- Accuracy gap can exceed 30–50% on typical real-world functions.

---

### Option B: Pure C++ MachineFunctionPass in LLVM Source Tree

**Approach:** Fork the LLVM source tree, add a custom `MachineFunctionPass` to the X86/ARM/AArch64 target machine pass configurations (`TargetPassConfig::addPreEmitPass`), build the full LLVM monorepo, and install a modified `llc`.

**Pros:**
- Maximal accuracy. Full integration into the target's native pass pipeline.
- Precise post-PEI scheduling via standard LLVM mechanisms.

**Cons (why we rejected it):**
- **Extreme setup cost.** LLVM full build takes 1–3 hours and requires 30–80 GB of disk space.
- Requires modification of upstream C++ source files in `lib/Target/X86/`, `lib/Target/ARM/`, etc.
- Produces a non-portable, modified LLVM installation that is difficult to distribute.
- Call graph propagation, SCC cycle detection, and rich report generation are extremely verbose and rigid in C++.

---

### Option C: Hybrid C++ Backend + Python Solver ✅ **(Selected)**

**Approach:** Build two lightweight standalone C++ LLVM tools against the installed LLVM development libraries (no LLVM source fork required). Use Python for all graph algorithm work and report generation.

**The C++ backend tools:**
1. `stack-extractor`: Opens LLVM IR, traverses IR `CallBase` instructions, exports the call graph as JSON.
2. `stack-size-collector`: Runs the **full LLVM target codegen pipeline** (`addPassesToEmitFile`), injects a custom `MachineFunctionPass` at precisely the correct pipeline position (using an `InterceptPassManager` to insert before `FreeMachineFunction`), and reads `MachineFrameInfo::getStackSize()`.

**The Python solver:**
- Loads both JSON outputs.
- Runs Tarjan's SCC algorithm to detect recursion cycles.
- Performs memoized DFS propagation across the call graph DAG.
- Generates a rich colored terminal report using the `rich` library.
- Optionally performs RTOS task budget analysis.

**Why this wins:**
| Property | Option A | Option B | Option C |
|----------|----------|----------|----------|
| Frame accuracy | Low | Highest | High |
| Setup complexity | Trivial | Extreme | Low |
| Portability | High | None | High |
| Report extensibility | Medium | Low | Highest |
| Cross-target support | N/A | Target-specific | ✅ (ARM, AArch64, X86) |

---

## 3. Key Architectural Decisions

### 3.1 Pass Injection via `InterceptPassManager`

The central engineering challenge in this project was inserting our `StackSizeCollectorPass` at **precisely the right moment** in the LLVM legacy codegen pass pipeline.

**The Bug (discovered via `-debug-pass=Structure`):**

When `TargetMachine::addPassesToEmitFile()` builds the codegen pipeline, it adds the following passes at the end:
```
  X86 Assembly Printer
  Free MachineFunction       ← deletes all MachineFunction data
  StackSizeCollectorPass     ← ours (added AFTER the pipeline)
```

Adding our pass after `addPassesToEmitFile()` caused it to execute **after** `FreeMachineFunction` deallocated all stack frame data, resulting in `getStackSize() == 0` for every function.

**The Solution:**

We subclassed `legacy::PassManager` to create `InterceptPassManager`, which overrides the virtual `add()` method:

```cpp
class InterceptPassManager : public legacy::PassManager {
    bool addedCollector = false;
public:
    void add(Pass *P) override {
        if (P && P->getPassName() == "Free MachineFunction" && !addedCollector) {
            legacy::PassManager::add(new StackSizeCollectorPass());
            addedCollector = true;
        }
        legacy::PassManager::add(P);
    }
};
```

When `addPassesToEmitFile()` registers `Free MachineFunction`, our interceptor dynamically inserts `StackSizeCollectorPass` immediately before it. The resulting pipeline becomes:

```
  X86 Assembly Printer
  Stack Size Collector    ← post-emission, pre-cleanup: getStackSize() is valid!
  Free MachineFunction
```

### 3.2 Alloca Augmentation Fallback

The Python analyzer includes a secondary fallback parser (`parse_ll_alloca_sizes`) that extracts alloca instruction sizes directly from the LLVM IR `.ll` file. This provides:
- A safety net when the C++ backend produces unexpected zeros.
- Merged estimates: `sizes[func] = max(machine_size, alloca_estimate)`.

### 3.3 SCC-Based Recursion Detection

We use **Tarjan's Strongly Connected Components** (SCC) algorithm to detect both direct recursion (self-loops) and mutual recursion (cycles of any length). Functions inside an SCC are flagged with recursion warnings and treated conservatively during depth propagation (their sub-cycle is not accumulated to prevent infinite loops).

### 3.4 Memoized DAG Propagation

The cumulative stack depth solver uses DFS with memoization:

```
CumulativeStack(F) = FrameSize(F) + max(
    max over all callees C of CumulativeStack(C),
    IndirectCallPenalty  (if F has indirect calls)
)
```

Memoization ensures each function's maximum depth is computed exactly once, giving O(V+E) complexity over the call graph.

### 3.5 Configurable Indirect Call Penalty

When a function contains an indirect call (function pointer, virtual method), the static analyzer cannot resolve the callee. Instead of reporting an unknowable depth, the tool applies a **configurable upper bound** (`--indirect-cost`, default 256 bytes), representing a conservative worst-case estimate for embedded systems.

---

## 4. Data Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Input: C source file                                                    │
└───────────────────────────────────────┬──────────────────────────────────┘
                                        │ clang -O0 -S -emit-llvm
                                        ▼
                               ┌─────────────────┐
                               │   upload.ll      │  (LLVM IR)
                               └────────┬────────┘
                                        │
                   ┌────────────────────┼────────────────────┐
                   │                    │                    │
                   ▼                    ▼                    │
          stack-extractor      stack-size-collector          │
          (IR-level pass)      (MachineFunctionPass)         │
                   │                    │                    │
                   ▼                    ▼                    │
               cg.json            sizes.json              upload.ll
               (call graph)       (frame sizes)           (for alloca fallback)
                   │                    │                    │
                   └────────────────────┴────────────────────┘
                                        │
                                        ▼
                                  analyzer.py
                          ┌──────────────────────────┐
                          │ 1. Load cg.json + sizes   │
                          │ 2. Tarjan SCC (recursion) │
                          │ 3. Memoized DFS propagate │
                          │ 4. Rich terminal report   │
                          └──────────────────────────┘
```

---

## 5. Component Boundaries

| Component | Language | Role |
|-----------|----------|------|
| `StackExtractor.cpp` | C++ / LLVM IR APIs | Call graph extraction from LLVM IR |
| `StackSizeCollector.cpp` | C++ / LLVM CodeGen APIs | Machine-level frame size extraction |
| `analyzer.py` | Python | Graph solver, recursion detection, reporting |
| `server.py` | Python | HTTP backend for web dashboard |
| `index.html` + `script.js` + `style.css` | Web | Browser-based UI for code upload and analysis |
