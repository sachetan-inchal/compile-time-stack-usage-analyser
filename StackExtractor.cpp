#include "llvm/IR/LLVMContext.h"
#include "llvm/IR/Module.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/IR/Instructions.h"

#include <map>
#include <vector>
#include <string>
#include <fstream>
#include <iostream>

using namespace llvm;

// Custom data structures to collect results
std::map<std::string, std::vector<std::string>> DirectCallees;
std::map<std::string, std::vector<std::string>> IndirectCallSignatures;

// Escape string for JSON
std::string escapeJSON(const std::string &s) {
    std::string out;
    for (char c : s) {
        if (c == '"') out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else out += c;
    }
    return out;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        std::cerr << "Usage: stack-extractor <input_ir.ll> [output_cg.json]\n";
        return 1;
    }

    std::string inputFilename = argv[1];
    std::string cgJsonFilename = (argc >= 3) ? argv[2] : "call_graph.json";

    LLVMContext Context;
    SMDiagnostic Err;
    std::unique_ptr<Module> Mod = parseIRFile(inputFilename, Err, Context);
    if (!Mod) {
        Err.print(argv[0], errs());
        return 1;
    }

    // Scan IR for call graph
    for (auto &F : *Mod) {
        if (F.isDeclaration()) continue;
        std::string caller = F.getName().str();
        
        // Ensure entry exists
        DirectCallees[caller] = std::vector<std::string>();
        IndirectCallSignatures[caller] = std::vector<std::string>();

        for (auto &BB : F) {
            for (auto &I : BB) {
                if (auto *CB = dyn_cast<CallBase>(&I)) {
                    if (Function *callee = CB->getCalledFunction()) {
                        DirectCallees[caller].push_back(callee->getName().str());
                    } else {
                        // Indirect call - extract signature
                        std::string sig;
                        raw_string_ostream rso(sig);
                        CB->getFunctionType()->print(rso);
                        IndirectCallSignatures[caller].push_back(rso.str());
                    }
                }
            }
        }
    }

    // Write out call graph JSON
    std::ofstream cgFile(cgJsonFilename);
    if (!cgFile.is_open()) {
        std::cerr << "Error: Failed to open call graph JSON for writing\n";
        return 1;
    }
    cgFile << "{\n";
    bool first = true;
    for (auto const& [caller, callees] : DirectCallees) {
        if (!first) cgFile << ",\n";
        cgFile << "  \"" << escapeJSON(caller) << "\": {\n";
        
        // Write direct callees
        cgFile << "    \"callees\": [";
        bool cFirst = true;
        for (auto const& callee : callees) {
            if (!cFirst) cgFile << ", ";
            cgFile << "\"" << escapeJSON(callee) << "\"";
            cFirst = false;
        }
        cgFile << "],\n";

        // Write indirect calls
        cgFile << "    \"indirect_calls\": [";
        bool iFirst = true;
        auto const& indirects = IndirectCallSignatures[caller];
        for (auto const& sig : indirects) {
            if (!iFirst) cgFile << ", ";
            cgFile << "\"" << escapeJSON(sig) << "\"";
            iFirst = false;
        }
        cgFile << "]\n";

        cgFile << "  }";
        first = false;
    }
    cgFile << "\n}\n";
    cgFile.close();

    std::cout << "Call graph successfully exported to " << cgJsonFilename << "\n";
    return 0;
}
