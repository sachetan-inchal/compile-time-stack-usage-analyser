# API Documentation: Compile-Time Stack Usage Analyzer

This document details the software interfaces, internal LLVM API mechanisms, and JSON schemas utilized by the Stack Usage Analyzer.

---

## 1. Backend Engine (C++)

The backend consists of two compiled tools parsing LLVM IR:
1. `stack-extractor`: Extracts the call graph structure and indirect call types.
2. `stack-size-collector`: Computes physical machine-level stack frames.

### StackSizeCollectorPass (MachineFunctionPass)

Inherits from `llvm::MachineFunctionPass`. This pass is designed to extract finalized stack frame measurements post-instruction selection, post-register-allocation, and post-PrologEpilogInserter (PEI).

```cpp
struct StackSizeCollectorPass : public llvm::MachineFunctionPass {
    static char ID;
    StackSizeCollectorPass();
    
    // Core callback run on every MachineFunction
    bool runOnMachineFunction(llvm::MachineFunction &MF) override;
    
    llvm::StringRef getPassName() const override;
};
```

#### How it works:
1. **Prolog/Epilog Insertion (PEI)**: Standard compiler lowering processes the IR through instruction selection and register allocation. The PEI pass then inserts assembly prologues and epilogues.
2. **Final Frame Layout**: Once PEI completes, `MachineFrameInfo::getStackSize()` reflects the actual, finalized number of bytes required by the target processor. This includes:
   - **`AllocaInst` allocation size**: The space required by local variables and structures.
   - **Spill Slots**: Register space allocated by the register allocator to save and restore variables when active registers are exhausted.
   - **Alignment Padding**: Extra space required to align objects on proper stack word boundaries.
3. **Extraction**: The pass queries `MF.getFrameInfo().getStackSize()` and inserts the data into a global map indexed by the function's assembly name.

---

## 2. Interchange Data Formats (JSON)

The C++ backends communicate with the Python analyzer using two structured JSON files:

### Schema 1: `stack_sizes.json`
A map of function names to their computed stack frame sizes in bytes.

```json
{
  "vSensorTask": 16,
  "acquire_sensor": 64,
  "format_sensor_json": 592,
  "compute_checksum": 48
}
```

### Schema 2: `call_graph.json`
An adjacency list representing direct callees and a list of indirect call type signatures.

```json
{
  "vSensorTask": {
    "callees": ["acquire_sensor", "format_sensor_json"],
    "indirect_calls": []
  },
  "dispatch_protocol": {
    "callees": [],
    "indirect_calls": ["void (i8*, i32)"]
  }
}
```

---

## 3. Frontend Solver (Python) — `analyzer.py`

The Python frontend uses dynamic programming to propagate worst-case depths across the graph.

### Tarjan's SCC Algorithm: `find_sccs(graph)`
Detects cycles in the directed call graph to identify recursion loops.

- **Arguments**: `graph` (the call graph dictionary loaded from `call_graph.json`).
- **Returns**: A list of strongly connected components. Components with size $> 1$ or single-node components with self-loops are flagged as recursion cycles.

### DFS Propagation: `compute_cumulative_stack(...)`
Applies memoization (DP) to find the longest path on the directed acyclic graph (DAG) representing calls, using cycle-breaking for recursive nodes.

```python
def compute_cumulative_stack(node, graph, sizes, visited, memo, recursion_flags, indirect_cost):
    """
    node: Current function being evaluated
    graph: Adjacency list from call_graph.json
    sizes: Map from stack_sizes.json
    visited: Set of active nodes in the current DFS path (for cycle breaking)
    memo: DP table storing (cumulative_size, worst_case_child)
    recursion_flags: Dictionary flagging nodes involved in cycles
    indirect_cost: Configurable default boundary value for indirect calls
    """
```

- **Mathematical Formula**:
  $$CumulativeStack(F) = FrameSize(F) + \max \left( \max_{C \in Callees(F)} CumulativeStack(C), \text{IndirectCost} \right)$$
