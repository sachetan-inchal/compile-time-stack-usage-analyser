#!/bin/bash
set -e

echo "=========================================================="
echo "      STATIC STACK USAGE ANALYZER EVALUATION SUITE"
echo "=========================================================="
echo ""

# 1. Clean previous build artifact directories
mkdir -p build test_results
rm -f test/*.ll test/*.json test/*.o test/*.su

# 2. Compile simulated FreeRTOS codebase under three optimization tiers
echo "[1/3] Lowering test_code.c to LLVM IR (3 Tiers: -O0, -O2 -fno-inline, -O2)..."
clang -O0 -S -emit-llvm test/test_code.c -o test/test_code_O0.ll
clang -O2 -fno-inline -S -emit-llvm test/test_code.c -o test/test_code_O2_noinline.ll
clang -O2 -S -emit-llvm test/test_code.c -o test/test_code_O2.ll

echo "[1/3b] Compiling object files and extracting backend MachineFunction stack frame sizes (.su)..."
clang -O0 -fstack-usage -c test/test_code.c -o test/test_code_O0.o
clang -O2 -fno-inline -fstack-usage -c test/test_code.c -o test/test_code_O2_noinline.o
clang -O2 -fstack-usage -c test/test_code.c -o test/test_code_O2.o

# 3. Compile C++ Stack Extractor
echo "[2/3] Building C++ Stack Extractor..."
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build

# 4. Run extractor on LLVM IR files
echo "[3/3] Running Backend Call Graph Extraction..."
./build/stack-extractor test/test_code_O0.ll test_results/cg_O0.json > /dev/null
./build/stack-extractor test/test_code_O2_noinline.ll test_results/cg_O2_noinline.json > /dev/null
./build/stack-extractor test/test_code_O2.ll test_results/cg_O2.json > /dev/null

echo "Extraction done successfully."
echo "Results exported to test_results/."
echo ""
echo "=========================================================="
echo "   EVALUATION RESULTS 1: DEEP CALL CHAIN (-O0 CONFIG)"
echo "=========================================================="
.venv/bin/python analyzer.py --sizes test/test_code_O0.su --cg test_results/cg_O0.json --threshold 600

echo ""
echo "=========================================================="
echo "   EVALUATION RESULTS 2: OPTIMIZED NO-INLINE (-O2 -fno-inline)"
echo "=========================================================="
.venv/bin/python analyzer.py --sizes test/test_code_O2_noinline.su --cg test_results/cg_O2_noinline.json --threshold 600

echo ""
echo "=========================================================="
echo "   EVALUATION RESULTS 3: FULLY OPTIMIZED & INLINED (-O2)"
echo "=========================================================="
.venv/bin/python analyzer.py --sizes test/test_code_O2.su --cg test_results/cg_O2.json --threshold 600
