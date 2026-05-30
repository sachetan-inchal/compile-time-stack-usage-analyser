#!/bin/bash
set -e

echo "=========================================================="
echo "      STATIC STACK USAGE ANALYZER EVALUATION SUITE"
echo "=========================================================="
echo ""

# 1. Clean previous build artifact directories
mkdir -p build test_results
rm -f test/*.ll test/*.json test/*.o test/*.su

# 2. Compile simulated codebase under three optimization tiers
echo "[1/3] Lowering test_code.c to LLVM IR (3 Tiers: -O0, -O2 -fno-inline, -O2)..."
clang -O0 -S -emit-llvm test/test_code.c -o test/test_code_O0.ll
clang -O2 -fno-inline -S -emit-llvm test/test_code.c -o test/test_code_O2_noinline.ll
clang -O2 -S -emit-llvm test/test_code.c -o test/test_code_O2.ll

# 3. Compile C++ Tools
echo "[2/3] Building C++ Stack Analyzer Tools..."
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build

# 4. Run call graph extractor and stack size collector
echo "[3/3] Running Backend Codegen Stack Frame Collection..."

# -O0
./build/stack-extractor test/test_code_O0.ll test_results/cg_O0.json > /dev/null
./build/stack-size-collector test/test_code_O0.ll test_results/sizes_O0.json > /dev/null

# -O2 -fno-inline
./build/stack-extractor test/test_code_O2_noinline.ll test_results/cg_O2_noinline.json > /dev/null
./build/stack-size-collector test/test_code_O2_noinline.ll test_results/sizes_O2_noinline.json > /dev/null

# -O2
./build/stack-extractor test/test_code_O2.ll test_results/cg_O2.json > /dev/null
./build/stack-size-collector test/test_code_O2.ll test_results/sizes_O2.json > /dev/null

echo "Extraction done successfully."
echo "Results exported to test_results/."
echo ""

# Detect python
PYTHON="python3"
if ! command -v python3 &>/dev/null; then
    PYTHON="python"
fi

echo "=========================================================="
echo "   EVALUATION RESULTS 1: DEEP CALL CHAIN (-O0 CONFIG)"
echo "=========================================================="
"$PYTHON" analyzer.py --sizes test_results/sizes_O0.json --cg test_results/cg_O0.json --threshold 600

echo ""
echo "=========================================================="
echo "   EVALUATION RESULTS 2: OPTIMIZED NO-INLINE (-O2 -fno-inline)"
echo "=========================================================="
"$PYTHON" analyzer.py --sizes test_results/sizes_O2_noinline.json --cg test_results/cg_O2_noinline.json --threshold 600

echo ""
echo "=========================================================="
echo "   EVALUATION RESULTS 3: FULLY OPTIMIZED & INLINED (-O2)"
echo "=========================================================="
"$PYTHON" analyzer.py --sizes test_results/sizes_O2.json --cg test_results/cg_O2.json --threshold 600
