cmake_minimum_required(VERSION 3.20)
project(StackAnalyzer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---------------------------------------------------------------------------
# Find LLVM package
# ---------------------------------------------------------------------------
find_package(LLVM REQUIRED CONFIG)

message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION}")
message(STATUS "LLVM headers: ${LLVM_INCLUDE_DIRS}")
message(STATUS "LLVM libraries: ${LLVM_LIBRARY_DIRS}")

include_directories(${LLVM_INCLUDE_DIRS})
add_definitions(${LLVM_DEFINITIONS})

# ---------------------------------------------------------------------------
# Tool 1: stack-extractor
#   Operates at the LLVM IR level (Module/Function/Instruction).
#   Extracts the static call graph (direct + indirect calls) and exports
#   call_graph.json for the Python analyzer.
#   Only needs the lightweight IR + support libraries.
# ---------------------------------------------------------------------------
llvm_map_components_to_libnames(EXTRACTOR_LIBS
    core
    support
    irreader
)

add_executable(stack-extractor StackExtractor.cpp)
target_link_libraries(stack-extractor PRIVATE ${EXTRACTOR_LIBS})

# ---------------------------------------------------------------------------
# Tool 2: stack-size-collector
#   Operates at the MachineFunction level (backend codegen).
#   Runs the full LLVM codegen pipeline (instruction selection, register
#   allocation, frame layout, prologue/epilogue insertion) and hooks a
#   MachineFunctionPass to read MachineFrameInfo::getStackSize() — the
#   authoritative per-function stack frame size.
#   Exports stack_sizes.json.
#
#   Requires codegen + all architecture backends so the tool can analyze
#   cross-compiled code (e.g., ARM Cortex-M firmware on an x86 host).
# ---------------------------------------------------------------------------
llvm_map_components_to_libnames(COLLECTOR_LIBS
    core
    support
    irreader
    target
    analysis
    codegen
    selectiondag
    asmprinter
    # Architecture backends — add/remove as needed for your LLVM build.
    # 'all' works if LLVM was built with all targets enabled.
    X86
    X86CodeGen
    X86AsmParser
    ARM
    ARMCodeGen
    ARMAsmParser
    AArch64
    AArch64CodeGen
    AArch64AsmParser
)

add_executable(stack-size-collector StackSizeCollector.cpp)
target_link_libraries(stack-size-collector PRIVATE ${COLLECTOR_LIBS})

# ---------------------------------------------------------------------------
# Install targets (optional — useful for system-wide deployment)
# ---------------------------------------------------------------------------
install(TARGETS stack-extractor stack-size-collector
        RUNTIME DESTINATION bin)
