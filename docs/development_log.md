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

---

## 2. Milestone Logs

### Milestone 1: Target Environment Calibration
- **Research**: Investigated the user's local Windows workstation environment. Identified that `WSL Ubuntu 24.04` is available.
- **Action**: Set up `llvm-dev` (LLVM 18), `clang-18`, `cmake`, and `build-essential` inside the WSL environment to ensure clean Linux ELF compilation support.

### Milestone 2: C++ Backend Extractor (`stack-extractor`)
- **Design**: Implemented a standalone driver program using LLVM's C++ APIs. It reads LLVM IR (`.ll` or `.bc`), initiates standard machine target builders, and creates the legacy `PassManager`.
- **Breakthrough**: Realized that if we manually call `TM->addPassesToEmitFile()` to populate the legacy pipeline and then append our custom `MachineFunctionPass`, LLVM will execute our pass *after* Prolog/Epilog Insertion (PEI). This is the exact moment stack frames are finalized, guaranteeing 100% accurate static measurements.
- **Data Export**: Designed raw, lightweight JSON exporters for function sizes and direct/indirect calls, avoiding external JSON library linkages to keep compilation dependencies minimal.

### Milestone 3: Python Solver (`analyzer.py`)
- **Algorithms**: Implemented Tarjan's SCC cycle isolation to gracefully flag direct and mutual recursion loops, preventing infinite cycles.
- **Propagation**: Designed a memoized dynamic programming recursive DAG walker to find the worst-case cumulative stack depth starting from entry points.
- **Rich Aesthetics**: Integrated the Python `rich` CLI console library. Developed a judge-ready terminal experience showing summary stat cards, cycle warnings, and gradient color-coded trees for worst-case call paths.

### Milestone 4: Simulated RTOS Test Suite (`test_code.c`)
- **Design**: Created a representative RTOS test suite:
  - `vTask1` triggers a sequential call chain (`vTask1` -> `process_sensor_data` -> `format_json` -> `hash_data`), using a heavy local `char[512]` buffer to demonstrate `Alloca` size analysis.
  - `vTask2` triggers dynamic function dispatch via a function pointer to demonstrate indirect call bounds.
  - `vTask3` triggers direct (`factorial`) and mutual recursion (`ping` -> `pong` -> `ping`) to showcase SCC loop warnings.
- **Evaluation Runner**: Created `run_eval.sh` to compile test cases under three optimization tiers (`-O0`, `-O2 -fno-inline`, `-O2`) and display analysis side-by-side.

---

## 3. Key Observations & Inlining Impacts

During testing, the following structural impacts of optimization were documented:
1. **At `-O0`**: Inlining is inactive. A call to a small helper function `inline_add` generates a distinct call instruction and incurs its own frame size.
2. **At `-O2`**: Clang automatically inline-optimizes small functions.
   - **Stack Shrinkage**: `inline_add`'s body is directly merged into the caller, removing the call edge entirely from the static call graph.
   - **Compiler Frame Layouts**: The caller's stack frame naturally increases to cover the merged variables, while the callee's individual stack size reports as nonexistent.
   - **Dual-Counting Avoided**: Our post-codegen analysis correctly measures this combined stack frame without double-counting a call edge, ensuring high fidelity.
