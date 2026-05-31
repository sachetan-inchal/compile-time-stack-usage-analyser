# Implementation Details: Compile-Time Stack Usage Analyzer

This document covers the LLVM-specific implementation for all three C++ components of the tool.

---

## 1. `stack-extractor` — IR-Level Call Graph Extractor

**Source:** [`StackExtractor.cpp`](StackExtractor.cpp)

### What it does

Opens an LLVM IR module (`.ll` or `.bc`) and iterates over all `Function` and `CallBase` objects to extract:
1. **Direct calls**: `CallInst` and `InvokeInst` with a known `Function *` callee.
2. **Indirect calls**: `CallInst` with a non-null indirect operand (function pointer, type-erased call). The callee type signature is recorded.

### Key LLVM APIs used

| API | Purpose |
|-----|---------|
| `llvm::parseIRFile()` | Parses `.ll` text IR or `.bc` bitcode into a `Module` |
| `llvm::Module::functions()` | Iterates all functions in the module |
| `llvm::Function::getBasicBlockList()` | Iterates basic blocks |
| `llvm::BasicBlock::instructions()` | Iterates all instructions |
| `llvm::dyn_cast<CallBase>(I)` | Dynamically casts to call-like instruction |
| `CB->getCalledFunction()` | Returns `Function*` for direct calls, `nullptr` for indirect |
| `CB->getCalledOperand()->getType()` | Returns the type of an indirect call target |

### Output Format (`cg.json`)

```json
{
  "vSensorTask": {
    "callees": ["acquire_sensor", "format_sensor_json"],
    "indirect_calls": []
  },
  "dispatch_protocol": {
    "callees": [],
    "indirect_calls": ["void (i8*, i32)*"]
  }
}
```

---

## 2. `stack-size-collector` — MachineFunction Stack Frame Extractor

**Source:** [`StackSizeCollector.cpp`](StackSizeCollector.cpp)

### The Core Challenge: Pass Scheduling

`MachineFrameInfo::getStackSize()` only returns a valid (non-zero) result **after** the `PrologEpilogInserter` (PEI) pass has finalized the stack frame. PEI:
- Assigns physical slots to all spill registers.
- Inserts the function prologue (stack pointer adjustment).
- Inserts the function epilogue (stack pointer restoration).
- Computes the final alignment-padded frame size and stores it in `MachineFrameInfo`.

The naive approach of appending our pass after `addPassesToEmitFile()` caused it to execute after `FreeMachineFunction` — which runs at the very end of the pipeline and deallocates all machine data, resetting every frame size to 0.

We diagnosed this using LLVM's built-in pass structure logger:
```cpp
const char *debugArgs[] = { argv[0], "-debug-pass=Structure" };
cl::ParseCommandLineOptions(2, debugArgs);
```

The audit revealed the exact pipeline tail:
```
...
Prologue/Epilogue Insertion & Frame Finalization    ← PEI (frame sizes set here)
...
X86 Assembly Printer                               ← emission
Free MachineFunction                               ← all MachineFunction data freed
Stack Size Collector                               ← our pass (queried ZERO frames)
```

### The Fix: `InterceptPassManager`

```cpp
class InterceptPassManager : public legacy::PassManager {
private:
    bool addedCollector = false;
public:
    void add(Pass *P) override {
        // Intercept FreeMachineFunction registration and prepend our pass
        if (P && P->getPassName() == "Free MachineFunction" && !addedCollector) {
            legacy::PassManager::add(new StackSizeCollectorPass());
            addedCollector = true;
        }
        legacy::PassManager::add(P);
    }
};
```

After the fix, the pipeline tail becomes:
```
X86 Assembly Printer
Stack Size Collector    ← post-emission, pre-cleanup: all frame data intact
Free MachineFunction
```

### `StackSizeCollectorPass` Implementation

```cpp
struct StackSizeCollectorPass : public MachineFunctionPass {
    static char ID;
    StackSizeCollectorPass() : MachineFunctionPass(ID) {}

    bool runOnMachineFunction(MachineFunction &MF) override {
        const MachineFrameInfo &MFI = MF.getFrameInfo();
        uint64_t frameSize = MFI.getStackSize();
        StackFrameSizes[MF.getName().str()] = frameSize;
        return false;  // analysis-only, no modification
    }
};
```

`MachineFrameInfo::getStackSize()` returns the total bytes reserved on the stack for this function including:
- **Alloca regions**: All stack-allocated local variables and arrays.
- **Spill slots**: Register allocator slots for variables that couldn't stay in registers.
- **Callee-saved registers**: Save area for registers the function must preserve per ABI.
- **Alignment padding**: Extra bytes to ensure the stack pointer satisfies `MFI.getMaxAlign()`.

### Pass Manager Setup

```cpp
// Initialize the pass registry with all codegen passes (critical step!)
PassRegistry *PR = PassRegistry::getPassRegistry();
initializeCodeGen(*PR);

// Initialize target backends
LLVMInitializeX86TargetInfo(); LLVMInitializeX86Target(); ...
LLVMInitializeARMTargetInfo();  LLVMInitializeARMTarget();  ...
LLVMInitializeAArch64TargetInfo(); ...

// Create the target machine
std::unique_ptr<TargetMachine> TM(
    TheTarget->createTargetMachine(targetTriple, /*CPU=*/"", /*Features=*/"", Options, RM)
);

// Build pass pipeline using our intercepting PM
InterceptPassManager PM;
PM.add(new TargetLibraryInfoWrapperPass(TLII));

raw_null_ostream NullStream;  // discard object code — we only want MFI data
TM->addPassesToEmitFile(PM, NullStream, nullptr, CodeGenFileType::ObjectFile);

// PM.run() will internally invoke our interceptor, inserting StackSizeCollectorPass
// right before FreeMachineFunction
PM.run(*Mod);
```

### Output Format (`sizes.json`)

```json
{
  "process": 552,
  "factorial": 24,
  "functionA": 24,
  "functionB": 24,
  "main": 24
}
```

**Verified Results** for the recursive demo code (`upload.c` at `-O0` on x86_64):
| Function | Expected frame source | `MachineFrameInfo::getStackSize()` |
|----------|----------------------|-----------------------------------|
| `process` | 128×int buffer + locals | **552 bytes** |
| `factorial` | 2 ints + ret addr | **24 bytes** |
| `functionA/B` | 1 int arg + ret addr | **24 bytes** |
| `main` | 1 int result + ptrs | **24 bytes** |

---

## 3. `analyzer.py` — Graph Solver and Report Generator

**Source:** [`analyzer.py`](analyzer.py)

### 3.1 Alloca Fallback Parser

The Python analyzer also includes an IR-level fallback that parses `.ll` files for `alloca` instructions when `--ll` is provided:

```python
alloca_arr = re.compile(r'alloca\s+\[(\d+)\s+x\s+i(\d+)\]')    # e.g. alloca [128 x i32]
alloca_n   = re.compile(r'alloca\s+i(\d+),\s+i(?:32|64)\s+(\d+)') # e.g. alloca i8, i64 N
alloca_one = re.compile(r'alloca\s+i(\d+)')                        # e.g. alloca i32
alloca_ptr = re.compile(r'alloca\s+ptr')                           # pointer = 8 bytes
```

Sizes are merged: `sizes[func] = max(machine_size, alloca_estimate)`, ensuring the MachineFunction backend always wins if it provides a valid non-zero result.

### 3.2 Tarjan's SCC Algorithm

```python
def find_sccs(graph):
    """Find Strongly Connected Components (Tarjan's algorithm)."""
    # DFS-based O(V+E) algorithm
    # Returns list of SCCs; components with size > 1 or self-loops = recursion
```

An SCC is flagged as recursive if:
- `len(scc) > 1` → mutual recursion between multiple functions.
- `len(scc) == 1` and the single node calls itself → direct recursion.

### 3.3 Memoized DFS Stack Propagation

```python
def compute_cumulative_stack(node, graph, sizes, visited, memo, recursion_flags, indirect_cost):
    if node in memo:
        return memo[node][0]    # memoized result
    if node in visited:
        recursion_flags[node] = True
        return 0                # cycle-breaking: return 0 to avoid infinite loop

    visited.add(node)
    node_size = sizes.get(node, 0)
    max_callee_stack = 0

    for callee in graph.get(node, {}).get("callees", []):
        callee_stack = compute_cumulative_stack(callee, graph, sizes, visited, memo, ...)
        if callee_stack > max_callee_stack:
            max_callee_stack = callee_stack

    # Apply indirect call penalty if function has any indirect calls
    if graph.get(node, {}).get("indirect_calls", []):
        max_callee_stack = max(max_callee_stack, indirect_cost)

    visited.remove(node)
    total = node_size + max_callee_stack
    memo[node] = (total, best_callee)
    return total
```

**Mathematical formulation:**

$$CumulativeStack(F) = FrameSize(F) + \max \left( \max_{C \in Callees(F)} CumulativeStack(C),\ IndirectCost \right)$$

### 3.4 Entry Point Detection

Entry points are defined as functions that are **never called by any other function** in the module — i.e., functions with in-degree 0 in the call graph. These map to RTOS task functions, `main`, and top-level callbacks.

```python
all_callees = set()
for node, info in graph.items():
    all_callees.update(info.get("callees", []))

entry_points = [node for node in graph if node not in all_callees]
```

### 3.5 Overflow Threshold Classification

```python
if cum_stack >= args.threshold:
    status = "⚠️ RISK"      # configurable via --threshold
elif recursion_flags[entry]:
    status = "♾ Recursive"  # unbounded — cannot statically bound
else:
    status = "OK"
```

---

## 4. Build System

### `CMakeLists.txt`

The build system links against the installed LLVM development libraries (no LLVM source fork needed):

```cmake
llvm_map_components_to_libnames(COLLECTOR_LIBS
    core support irreader target analysis codegen selectiondag asmprinter
    X86 X86CodeGen X86AsmParser
    ARM ARMCodeGen ARMAsmParser
    AArch64 AArch64CodeGen AArch64AsmParser
)
```

This gives us cross-target analysis capability: ARM and AArch64 code can be analyzed on an x86 host.

### `build_wsl.sh`

Copies sources to `/tmp/build_src` (native WSL storage, not the slow Windows filesystem), runs CMake + make inside WSL, and copies binaries back to `./build/`. This avoids Windows filesystem performance issues for C++ compilation.

---

## 5. Known Limitations

| Limitation | Impact | Workaround |
|-----------|--------|------------|
| Indirect / virtual calls unresolvable statically | Conservative overestimate | `--indirect-cost` is configurable |
| Recursive functions have unbounded depth | Cannot produce a number | Flagged explicitly with `♾` warning |
| Dynamic stack allocations (`alloca(n)` at runtime) | Not captured | `hasVarSizedObjects()` flag could be added |
| Pass scheduling via `InterceptPassManager` is LLVM-version sensitive | May break on future LLVM releases | Pass name string `"Free MachineFunction"` should be verified per LLVM version |
| Analysis runs at compile time | Only models worst-case static paths; real runtime may differ | Compare against `uxTaskGetStackHighWaterMark()` |
