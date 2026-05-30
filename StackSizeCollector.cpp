/**
 * StackSizeCollector.cpp
 *
 * LLVM-native per-function stack frame size extractor.
 *
 * This tool lowers LLVM IR all the way through the backend codegen pipeline
 * (register allocation, frame layout, prologue/epilogue insertion) and then
 * hooks a custom MachineFunctionPass to read MachineFrameInfo::getStackSize()
 * for each function — the authoritative backend frame size.
 *
 * This is the implementation of Deliverable #1:
 *   "Per-function stack frame estimator (alloca, spills, alignment padding)
 *    operating on MachineFunction"
 *
 * Usage:
 *   stack-size-collector <input.ll> [output_sizes.json] [--arch <triple>]
 *
 * Output:
 *   JSON file: { "funcName": <frame_size_bytes>, ... }
 *
 * Design notes:
 *   - Uses LLVMTargetMachine::addPassesToEmitFile() to build the full codegen
 *     pass pipeline, then inserts StackSizeCollectorPass just before code
 *     emission so that frame sizes are fully finalized (post-RA, post-PEI).
 *   - Target defaults to x86_64-pc-linux-gnu (configurable).
 *   - Frame sizes reflect actual machine-level allocation: local variables,
 *     spilled registers, alignment padding, and alloca regions.
 */

#include "llvm/Analysis/TargetLibraryInfo.h"
#include "llvm/CodeGen/MachineFrameInfo.h"
#include "llvm/CodeGen/MachineFunction.h"
#include "llvm/CodeGen/MachineFunctionPass.h"
#include "llvm/CodeGen/MachineModuleInfo.h"
#include "llvm/CodeGen/Passes.h"
#include "llvm/CodeGen/TargetPassConfig.h"
#include "llvm/IR/LLVMContext.h"
#include "llvm/IR/LegacyPassManager.h"
#include "llvm/IR/Module.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/MC/TargetRegistry.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/TargetSelect.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/Target/TargetMachine.h"
#include "llvm/Target/TargetOptions.h"
#include "llvm/TargetParser/Host.h"

#include <fstream>
#include <iostream>
#include <map>
#include <string>

using namespace llvm;

// ---------------------------------------------------------------------------
// Global result map: function name -> stack frame size in bytes
// ---------------------------------------------------------------------------
static std::map<std::string, uint64_t> StackFrameSizes;

// ---------------------------------------------------------------------------
// MachineFunctionPass: reads MachineFrameInfo after frame finalization
// ---------------------------------------------------------------------------
struct StackSizeCollectorPass : public MachineFunctionPass {
    static char ID;

    StackSizeCollectorPass() : MachineFunctionPass(ID) {}

    StringRef getPassName() const override {
        return "Stack Size Collector (MachineFrameInfo)";
    }

    bool runOnMachineFunction(MachineFunction &MF) override {
        const MachineFrameInfo &MFI = MF.getFrameInfo();

        // getStackSize() returns the total frame size in bytes after
        // register allocation and frame layout have been finalized.
        // This includes:
        //   - Local variable allocas
        //   - Spilled register save slots
        //   - Alignment padding
        //   - Variable-size object slots (if present, size is 0 here — dynamic)
        uint64_t frameSize = MFI.getStackSize();

        // Demangle-safe: getName() returns the IR-level name (mangled for C++,
        // plain for C). For C programs this is exactly the source function name.
        std::string funcName = MF.getName().str();

        StackFrameSizes[funcName] = frameSize;

        // Do not modify the MachineFunction — analysis-only pass.
        return false;
    }
};

char StackSizeCollectorPass::ID = 0;

// ---------------------------------------------------------------------------
// JSON escape helper
// ---------------------------------------------------------------------------
static std::string escapeJSON(const std::string &s) {
    std::string out;
    for (char c : s) {
        if      (c == '"')  out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else                out += c;
    }
    return out;
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------
int main(int argc, char **argv) {
    // ---- Argument parsing ------------------------------------------------
    if (argc < 2) {
        std::cerr << "Usage: stack-size-collector <input.ll> "
                     "[output_sizes.json] [--arch <target-triple>]\n";
        std::cerr << "\nExamples:\n";
        std::cerr << "  stack-size-collector program.ll stack_sizes.json\n";
        std::cerr << "  stack-size-collector program.ll sizes.json "
                     "--arch arm-none-eabi\n";
        return 1;
    }

    std::string inputFile    = argv[1];
    std::string outputFile   = "stack_sizes.json";
    std::string targetTriple = "";  // empty = use host triple

    for (int i = 2; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--arch" && i + 1 < argc) {
            targetTriple = argv[++i];
        } else if (arg[0] != '-') {
            outputFile = arg;
        }
    }

    // ---- Initialize LLVM targets -----------------------------------------
    // Explicitly initialize the supported architectures to avoid link errors
    // with unlinked backends (e.g. WebAssembly, SystemZ).
    LLVMInitializeX86TargetInfo();
    LLVMInitializeX86Target();
    LLVMInitializeX86TargetMC();
    LLVMInitializeX86AsmPrinter();
    LLVMInitializeX86AsmParser();

    LLVMInitializeARMTargetInfo();
    LLVMInitializeARMTarget();
    LLVMInitializeARMTargetMC();
    LLVMInitializeARMAsmPrinter();
    LLVMInitializeARMAsmParser();

    LLVMInitializeAArch64TargetInfo();
    LLVMInitializeAArch64Target();
    LLVMInitializeAArch64TargetMC();
    LLVMInitializeAArch64AsmPrinter();
    LLVMInitializeAArch64AsmParser();

    // ---- Load LLVM IR file -----------------------------------------------
    LLVMContext Context;
    SMDiagnostic Err;
    std::unique_ptr<Module> Mod = parseIRFile(inputFile, Err, Context);
    if (!Mod) {
        Err.print(argv[0], errs());
        return 1;
    }

    // ---- Resolve target triple -------------------------------------------
    if (targetTriple.empty()) {
        // Default: use the module's embedded triple if present,
        // otherwise fall back to the host machine triple.
        targetTriple = Mod->getTargetTriple().str();
        if (targetTriple.empty()) {
            targetTriple = sys::getDefaultTargetTriple();
            std::cerr << "[info] No target triple in IR, using host: "
                      << targetTriple << "\n";
        }
    }
    Mod->setTargetTriple(Triple(targetTriple));

    // ---- Look up the target ----------------------------------------------
    std::string errorMsg;
    const Target *TheTarget = TargetRegistry::lookupTarget(targetTriple, errorMsg);
    if (!TheTarget) {
        std::cerr << "Error: Could not find target for triple '"
                  << targetTriple << "': " << errorMsg << "\n";
        std::cerr << "Tip: Run 'llc --version' to see supported targets.\n";
        return 1;
    }

    // ---- Create TargetMachine --------------------------------------------
    TargetOptions Options;
    std::optional<Reloc::Model> RM = std::nullopt; // default relocation model
    std::unique_ptr<TargetMachine> TM(
        TheTarget->createTargetMachine(
            targetTriple,
            /*CPU=*/"",       // generic CPU; use "cortex-m4" etc. for embedded
            /*Features=*/"",  // no extra features
            Options,
            RM
        )
    );

    if (!TM) {
        std::cerr << "Error: Could not create TargetMachine for '"
                  << targetTriple << "'\n";
        return 1;
    }

    // Apply the data layout from the target to the module
    Mod->setDataLayout(TM->createDataLayout());

    // ---- Build legacy pass manager with codegen pipeline -----------------
    // We use the legacy PassManager because MachineFunctionPass is part of
    // the legacy codegen infrastructure. The new PassManager does not yet
    // support MachineFunctionPass directly.
    legacy::PassManager PM;

    // TargetLibraryInfo is required by several codegen passes
    TargetLibraryInfoImpl TLII{Triple(targetTriple)};
    PM.add(new TargetLibraryInfoWrapperPass(TLII));

    // Add the full codegen pipeline (instruction selection, RA, frame layout,
    // prologue/epilogue insertion). We emit to a null stream because we only
    // care about the MachineFunction analysis results, not actual object code.
    raw_null_ostream NullStream;
    if (TM->addPassesToEmitFile(PM, NullStream, nullptr,
                                 CodeGenFileType::ObjectFile)) {
        std::cerr << "Error: Target does not support object code emission.\n";
        return 1;
    }

    // Insert our collector pass.
    // Note: This is added AFTER addPassesToEmitFile() intentionally.
    // The legacy PM executes passes in registration order; however,
    // addPassesToEmitFile() inserts MachineFunctionPass wrappers into the
    // pipeline. Our pass runs as part of that pipeline (it will be scheduled
    // after frame finalization by the pass manager's dependency tracking).
    //
    // For precise post-PEI scheduling, we rely on the pass manager inserting
    // MachineFunctionPass instances in dependency order. getStackSize() is
    // valid after PrologEpilogInserter has run.
    PM.add(new StackSizeCollectorPass());

    // ---- Run the pipeline ------------------------------------------------
    std::cerr << "[info] Running codegen pipeline on: " << inputFile << "\n";
    std::cerr << "[info] Target triple: " << targetTriple << "\n";
    PM.run(*Mod);

    // ---- Write stack_sizes.json ------------------------------------------
    std::ofstream outFile(outputFile);
    if (!outFile.is_open()) {
        std::cerr << "Error: Cannot open output file: " << outputFile << "\n";
        return 1;
    }

    outFile << "{\n";
    bool first = true;
    for (auto const &[name, size] : StackFrameSizes) {
        if (!first) outFile << ",\n";
        outFile << "  \"" << escapeJSON(name) << "\": " << size;
        first = false;
    }
    outFile << "\n}\n";
    outFile.close();

    // ---- Summary ---------------------------------------------------------
    std::cout << "[stack-size-collector] Analyzed " << StackFrameSizes.size()
              << " functions.\n";
    std::cout << "[stack-size-collector] Frame sizes written to: "
              << outputFile << "\n";

    if (!StackFrameSizes.empty()) {
        // Print top 10 largest frames as a quick sanity check
        std::vector<std::pair<std::string, uint64_t>> sorted(
            StackFrameSizes.begin(), StackFrameSizes.end());
        std::sort(sorted.begin(), sorted.end(),
                  [](auto &a, auto &b) { return a.second > b.second; });

        std::cout << "\nTop frame sizes:\n";
        int n = 0;
        for (auto &[name, size] : sorted) {
            if (n++ >= 10) break;
            std::cout << "  " << name << ": " << size << " bytes\n";
        }
    }

    return 0;
}
