# Development Log: Compile-Time Stack Usage Analyzer

This log tracks architectural decisions, milestone completions, and research details during the development of the Stack Usage Analyzer.

---

## 1. Architectural Decisions & Rationale

During initial planning, three different architectural directions were analyzed:

1. **Option A: Pure C++ Pass running on IR (`AllocaInst` scanning)**
   * *Cons*: Inaccurate. Misses register spills, compiler-inserted temporaries, target frame alignment padding, and target call conventions.
2. **Option B: Pure C++ Pass running on Machine IR (`MachineFunctionPass`)**
   * *Cons*: Integrating recursive path propagation, cycle breaking, and highly customized CLI table/tree outputs entirely in C++ LLVM source files is verbose, structurally rigid, and harder to quickly extend for dynamic reports during project presentations.
3. **Option C: Hybrid C++ Backend & Python Solver (Selected)**
   * *Pros*: Peak accuracy and maximum design flexibility. The C++ backend performs low-level backend operations (parsing LLVM IR, running code-generation pipeline, extracting finalized target-specific `MachineFrameInfo` sizes). The Python frontend performs high-level graph solving (Tarjan's SCC cycle isolation, memoized DAG propagation, rich colored visualizations).

We completed the architecture by creating:
- `stack-extractor`: Focuses purely on extracting direct and indirect call graphs from LLVM IR.
- `stack-size-collector`: A dedicated native tool that runs the full LLVM target machine code generation pipeline on LLVM IR, hooks a `MachineFunctionPass` post-PEI (Prolog/Epilog Insertion), and pulls the authoritative target-specific `MachineFrameInfo::getStackSize()`.

---

## 2. Milestone Logs

### Milestone 1: Target Environment Calibration
- **Research**: Investigated the user's local Windows workstation environment. Identified that `WSL Ubuntu` is available.
- **Action**: Set up LLVM dev libraries, CMake, and Python dependencies to ensure clean cross-compilation support.

### Milestone 2: C++ Backend Call Graph Extractor (`stack-extractor`)
- **Design**: Implemented a standalone driver program using LLVM's C++ IR APIs. It reads LLVM IR (`.ll` or `.bc`) and exports a raw, lightweight JSON adjacency list of direct and indirect calls.

### Milestone 3: Python Solver (`analyzer.py`)
- **Algorithms**: Implemented Tarjan's SCC cycle isolation to gracefully flag direct and mutual recursion loops, preventing infinite cycles.
- **Propagation**: Designed a memoized dynamic programming recursive DAG walker to find the worst-case cumulative stack depth starting from entry points.
- **Rich Aesthetics**: Integrated the Python `rich` CLI console library. Developed a judge-ready terminal experience showing summary stat cards, cycle warnings, and gradient color-coded trees for worst-case call paths.
- **RTOS Extension**: Added support for `--rtos-report`, `--stack-alloc`, and `--task-allocs` to directly match worst-case static analysis depths against expected RTOS task budgets and output safety warnings.

### Milestone 4: Native LLVM MachineFunction Pass (`stack-size-collector`) [NEW]
- **Design**: Built `StackSizeCollector.cpp` which sets up standard target machines (e.g., `x86_64`, `ARM`, `AArch64`) and uses LLVM's `TargetMachine::addPassesToEmitFile` legacy pipeline wrapper to schedule a custom `MachineFunctionPass` after Prolog/Epilog Insertion (PEI).
- **Result**: Fulfills **Deliverable #1** completely. The tool prints a summary of analyzed functions and exports a precise `stack_sizes.json` map of actual backend stack frames (inclusive of spills, alignment, padding, and local arrays).

### Milestone 5: RTOS Test Suite & Ground-Truth Evaluation (`freertos_eval.c`) [NEW]
- **Design**: Created a representative RTOS evaluation codebase under `test/freertos_eval.c` containing:
  - `vSensorTask`: Models deep calls with a heavy local `char[512]` JSON formatting buffer.
  - `vCommsTask`: Models dynamic protocol dispatch via function pointers (indirect call).
  - `vControlTask`: Models a PID-like controller loop with mutual recursion (`pid_correct` ↔ `pid_anti_windup`).
- **Evaluation Runner**: Created `test/run_rtos_eval.sh` to compile test cases under three optimization tiers (`-O0`, `-O1`, `-O2 -fno-inline`), invoke the dual C++ backends, and run `analyzer.py --rtos-report` to generate clear comparison reports.

---

## 3. Key Observations & Inlining Impacts

During testing, the following structural impacts of optimization were documented:
1. **At `-O0`**: Inlining is inactive. A call to a small helper function `inline_add` generates a distinct call instruction and incurs its own frame size.
2. **At `-O2`**: Clang automatically inline-optimizes small functions.
   - **Stack Shrinkage**: `inline_add`'s body is directly merged into the caller, removing the call edge entirely from the static call graph.
   - **Compiler Frame Layouts**: The caller's stack frame naturally increases to cover the merged variables, while the callee's individual stack size reports as nonexistent.
   - **Dual-Counting Avoided**: Our post-codegen analysis correctly measures this combined stack frame without double-counting a call edge, ensuring high fidelity.
