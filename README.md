# Compile-Time Stack Usage Analyzer

> **Assignment 39** — An LLVM-native static analysis tool that computes worst-case cumulative stack usage for every entry point in a C program, identifying call chains that risk stack overflow. Built for embedded, kernel, and RTOS development where stack sizes are fixed and small.

---

## Why This Exists

| Tool | Coverage | Call-chain aware? |
|------|----------|-------------------|
| GCC `-fstack-usage` | Per-function | ❌ |
| Clang `-Wframe-larger-than` | Per-frame | ❌ |
| **This tool** | Whole-program cumulative | ✅ |

Neither GCC nor Clang can tell you that `main → sensor_read → format_json` uses **748 bytes total**. In an RTOS task with a 1 KB stack, that leaves only 276 bytes of headroom — and the next call will overflow silently, corrupting adjacent memory. This tool solves that.

---

## Architecture Overview

```
  .c file
     │
     ▼
  clang -S -emit-llvm          → upload.ll
     │
     ├──► stack-extractor       → cg.json       (C++ LLVM IR pass, call graph)
     │
     └──► stack-size-collector  → sizes.json    (C++ MachineFunctionPass, frame sizes)
                │
                ▼
          analyzer.py           → terminal report with worst-case depths, recursion warnings,
                                   overflow thresholds, and RTOS task safety tables
```

The stack-size-collector runs the **full LLVM codegen pipeline** (instruction selection → register allocation → Prologue/Epilog Insertion) and reads `MachineFrameInfo::getStackSize()` — the authoritative, post-RA, post-PEI machine frame size, inclusive of spills, alignment padding, and all local allocations.

---

## Quick Start

### Prerequisites

| Requirement | Minimum Version |
|-------------|----------------|
| WSL (Ubuntu) | Any |
| `clang` (inside WSL) | 14+ |
| `cmake` (inside WSL) | 3.20+ |
| Python | 3.9+ |
| `rich` Python library | Any |

Install Python dependencies:
```bash
pip install rich
```

---

### 1. Build the C++ Backend (one-time)

```bash
# From your project root on Windows
wsl bash build_wsl.sh
```

This compiles `stack-extractor` and `stack-size-collector` inside WSL and copies the binaries to `./build/`.

---

### 2. Run the Web Dashboard (Recommended)

```bat
run_dashboard.bat
```

Open your browser at `http://localhost:3000`, paste your C code, select an optimization level, and click **Analyze**. The dashboard shows the full analysis output including recursion warnings, call chain trees, and overflow alerts.

---

### 3. Run the CLI Directly

```bash
# Step 1: Compile your C file to LLVM IR
wsl clang -O0 -S -emit-llvm "/mnt/c/.../your_code.c" -o "/mnt/c/.../your_code.ll"

# Step 2: Extract call graph
wsl "./build/stack-extractor" your_code.ll cg.json

# Step 3: Collect machine-level stack frame sizes
wsl "./build/stack-size-collector" your_code.ll sizes.json

# Step 4: Run the Python analyzer
python analyzer.py --sizes sizes.json --cg cg.json --ll your_code.ll --threshold 1024
```

#### Key CLI Options for `analyzer.py`

| Flag | Default | Description |
|------|---------|-------------|
| `--sizes` | `stack_sizes.json` | Path to `sizes.json` from stack-size-collector |
| `--cg` | `call_graph.json` | Path to `cg.json` from stack-extractor |
| `--ll` | _(none)_ | Path to `.ll` LLVM IR file for alloca augmentation |
| `--threshold` | `1024` | Overflow alert threshold in bytes |
| `--top-n` | `5` | Number of deepest call chains to display |
| `--indirect-cost` | `256` | Penalty bytes applied per indirect/function-pointer call |
| `--rtos-report` | _off_ | Enable RTOS task safety table |
| `--task-allocs` | _(none)_ | Per-task stack budgets: `"vSensorTask=1024,vCommsTask=512"` |

---

### 4. Run the Automated Evaluation Suite

```bash
wsl bash test/run_rtos_eval.sh
```

Runs the full FreeRTOS evaluation harness at `-O0`, `-O1`, and `-O2 -fno-inline`, comparing static estimates against expected ground-truth depths.

---

## Example Output

```
┌───────────────────────────────────────────────────┐
│ ▲ COMPILE-TIME STACK USAGE ANALYZER ▲             │
│ LLVM-Native High-Fidelity Static Frame Estimation │
└───────────────────────────────────────────────────┘

┌──────────────────── ⚠️ RECURSION WARNINGS ─────────────────────┐
│ ▲ Recursion Loop: factorial -> factorial                        │
│ ▲ Recursion Loop: functionB -> functionA -> functionB           │
└─────────────────────────────────────────────────────────────────┘

Entry Point Cumulative Stack Depths:
┌──────────────────────────────┬──────────────┬──────────────────┬────────┐
│ Entry Point / Function Name  │ Frame (Own)  │ Worst-Case Depth │ Status │
├──────────────────────────────┼──────────────┼──────────────────┼────────┤
│ main                         │    24 B      │       600 B      │   OK   │
└──────────────────────────────┴──────────────┴──────────────────┴────────┘

Top-5 Deepest Call Chains:
Call chain: main  [600 bytes cumulative]
└── ↪ main (24 B frame) → printf, process, functionA
    └── ↪ process (552 B frame) → factorial
        └── ↪ factorial (24 B frame) → factorial
```

---

## Project Structure

```
compile-time-stack-usage-analyser/
├── StackExtractor.cpp          # C++ LLVM IR call graph extractor
├── StackSizeCollector.cpp      # C++ MachineFunctionPass stack frame extractor
├── analyzer.py                 # Python solver: graph propagation + rich reporting
├── CMakeLists.txt              # Build system for C++ backends
├── build_wsl.sh                # One-command WSL build script
├── run_dashboard.bat           # Windows launcher for web dashboard
├── server.py                   # Python HTTP server for the web dashboard
├── index.html                  # Web dashboard frontend
├── script.js                   # Dashboard JavaScript logic
├── style.css                   # Dashboard styling
├── test/
│   ├── freertos_eval.c         # FreeRTOS evaluation harness (5 RTOS tasks)
│   ├── test_code.c             # Baseline test cases
│   └── run_rtos_eval.sh        # Automated evaluation runner
├── docs/
│   ├── development_log.md      # Architecture decisions & milestone log
│   └── api.md                  # API documentation
├── README.md                   # This file
├── DESIGN.md                   # Approach and design alternatives
├── IMPLEMENTATION.md           # LLVM-specific implementation details
├── EVALUATION.md               # Metrics, test cases, and results
└── RECORDING.md                # Demo recording guide
```

---

## Deliverables Status

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | Per-function frame estimator (alloca, spills, padding) on MachineFunction | ✅ |
| 2 | Call graph traversal, worst-case cumulative depth per entry point | ✅ |
| 3 | Recursion detection (SCC), indirect call upper bound, inlining effects | ✅ |
| 4 | CLI tool: top-N deepest call chains with per-function breakdown | ✅ |
| 5 | RTOS evaluation comparing estimates to expected stack usage | ✅ |
