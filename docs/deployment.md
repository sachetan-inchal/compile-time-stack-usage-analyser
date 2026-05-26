# Deployment and Usage Guide: Stack Usage Analyzer

This guide details the steps to compile, deploy, and execute the Compile-Time Stack Usage Analyzer inside WSL Ubuntu.

---

## 1. Environment Setup & Prerequisites

The analyzer runs within a **WSL Ubuntu 24.04** environment to leverage high-fidelity target compilation and standard package managers.

### Step 1: Install System Dependencies
Execute the following commands inside your WSL terminal:
```bash
sudo apt-get update
sudo apt-get install -y llvm-dev clang cmake build-essential python3-venv python3-pip
```

### Step 2: Set Up Python Virtual Environment
Initialize a clean Python virtual environment to manage frontend packages:
```bash
python3 -m venv .venv
.venv/bin/pip install rich
```

---

## 2. Compilation and Build

Build the C++ backend component `stack-extractor` using CMake:

```bash
# Generate build configuration
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release

# Compile the extractor
cmake --build build
```

This compiles the extractor and outputs a standalone executable to `build/stack-extractor`.

---

## 3. Running Analysis (Step-by-Step)

The workflow consists of generating LLVM IR, extracting metadata, and running the graph solver.

### Step 1: Generate LLVM IR
Compile your source code into optimized LLVM IR. For accurate estimation reflecting real-world deployments, use `-O2`:
```bash
clang -O2 -S -emit-llvm my_code.c -o my_code.ll
```

### Step 2: Run Extractor
Process the IR using the C++ backend engine to extract raw stack size metadata and the call graph:
```bash
./build/stack-extractor my_code.ll stack_sizes.json call_graph.json
```

### Step 3: Run Graph Solver & CLI Visualizer
Run the Python analyzer on the extracted metadata to propagate stack usage, detect cycles, and present the final report:
```bash
.venv/bin/python analyzer.py --sizes stack_sizes.json --cg call_graph.json --threshold 1024 --top-n 5
```

---

## 4. CLI Options Reference

The Python frontend solver supports several configuration options to customize boundaries and warning alerts:

| CLI Option | Default | Description |
| :--- | :--- | :--- |
| `--sizes` | `stack_sizes.json` | Path to the stack sizes metadata file. |
| `--cg` | `call_graph.json` | Path to the call graph adjacency list file. |
| `--indirect-cost` | `256` | Static stack cost penalty applied to indirect call sites (in bytes). |
| `--threshold` | `1024` | Cumulative stack size threshold. Paths exceeding this will display warning banners and blinking risk flags. |
| `--top-n` | `5` | Number of deepest static call chains to display in the tree breakdown. |
