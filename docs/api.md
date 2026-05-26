# API Documentation: Compile-Time Stack Usage Analyzer

This document details the software interfaces, internal LLVM API mechanisms, and JSON schemas utilized by the Stack Usage Analyzer.

---

## 1. Backend Engine (C++) — `stack-extractor`

The C++ executable parses LLVM IR and leverages target-specific code generation pipelines to calculate static stack frames.

### StackSizeCollector Class (MachineFunctionPass)

Inherits from `llvm::MachineFunctionPass`. This pass is designed to extract finalized stack frame measurements.

```cpp
class StackSizeCollector : public llvm::MachineFunctionPass {
public:
    static char ID;
    StackSizeCollector();
    
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

### Static Call Graph Scanner

Scanning is performed at the IR level by traversing all instructions inside every basic block of defined functions.

- **Direct Call Extraction**: Scans for `llvm::CallBase` instruction instances. If `CB->getCalledFunction()` is non-null, the direct callee name is extracted.
- **Indirect Call Signature Extraction**: If the callee is null, the target is resolved through a function pointer. The analyzer prints the function pointer's signature representation using `CB->getFunctionType()->print()` and registers it for user-configured boundary analysis.

---

## 2. Interchange Data Formats (JSON)

The C++ backend communicates with the Python analyzer using two structured JSON files:

### Schema 1: `stack_sizes.json`
A map of function names to their computed stack frame sizes in bytes.

```json
{
  "vTask1": 0,
  "process_sensor_data": 16,
  "format_json": 528,
  "hash_data": 32
}
```

### Schema 2: `call_graph.json`
An adjacency list representing direct callees and a list of indirect call type signatures.

```json
{
  "vTask1": {
    "callees": ["process_sensor_data"],
    "indirect_calls": []
  },
  "vTask2": {
    "callees": [],
    "indirect_calls": ["void (int)"]
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
