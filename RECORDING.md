# Demo Recording Guide

> A step-by-step guide to recording a professional, evaluator-ready demo video for the **Compile-Time Stack Usage Analyzer**.

---

## Before You Start: Setup Checklist

- [ ] `wsl bash build_wsl.sh` has been run — binaries in `./build/` are fresh.
- [ ] `pip install rich` — Python rich library installed.
- [ ] Python >= 3.9 available on Windows.
- [ ] Server is NOT already running (kill any stray `server.py` processes).
- [ ] Display resolution set to **1920×1080** (or **1280×720** minimum).
- [ ] Browser zoom set to **100%** in Chrome/Edge.
- [ ] Terminal font size: **14–16px** (readable on video).
- [ ] Close all unrelated browser tabs, IDE windows, notifications.
- [ ] Enable **"Do Not Disturb"** mode on Windows (Settings → Focus Assist).
- [ ] Pick a **screen recorder**: OBS Studio (free, recommended), Windows Game Bar (`Win+G`), or Loom.

---

## Recommended Recording Structure (~5–8 minutes)

```
[0:00] Title card / Introduction
[0:30] Problem motivation (30 sec)
[1:00] Architecture overview (45 sec)
[1:45] DEMO PART 1: Web dashboard — working case (2 min)
[3:45] DEMO PART 2: CLI — RTOS evaluation (1.5 min)
[5:15] DEMO PART 3: Failure / edge case — recursion (1 min)
[6:15] Key results summary (45 sec)
[7:00] END
```

---

## Scene-by-Scene Script

### Scene 1 — Introduction (0:00–0:30)
**What to show:** A clean desktop with the project folder open.

**Say out loud:**
> "This is the Compile-Time Stack Usage Analyzer for Assignment 39. It's an LLVM-native static analysis tool that computes worst-case cumulative stack depths for any C program — specifically designed for embedded and RTOS development where stack overflow is the number-one cause of silent memory corruption."

---

### Scene 2 — Architecture Overview (0:30–1:45)
**What to show:** Open `README.md` in VS Code or a browser. Scroll to the architecture diagram block.

**Talk through the pipeline:**
> "The tool has three parts: first, clang compiles the C code to LLVM IR. Then our C++ backend — `stack-extractor` — walks the IR and exports the call graph as JSON. Simultaneously, `stack-size-collector` runs the full LLVM backend pipeline including register allocation and prologue/epilogue insertion, and reads the authoritative `MachineFrameInfo::getStackSize()` for each function. Finally, `analyzer.py` propagates worst-case stack depths across the call graph using Tarjan's SCC algorithm and memoized DFS."

---

### Scene 3 — DEMO: Web Dashboard, Working Case (1:45–3:45)

**Steps:**
1. Open a terminal in the project folder.
2. Run:
   ```
   run_dashboard.bat
   ```
3. Browser opens `http://localhost:3000`.
4. **Paste this code** into the editor panel (it's the canonical demo code):
   ```c
   #include <stdio.h>
   int factorial(int n) {
       if (n <= 1) return 1;
       return n * factorial(n - 1);
   }
   void functionB(int x);
   void functionA(int x) { if (x <= 0) return; functionB(x - 1); }
   void functionB(int x) { if (x <= 0) return; functionA(x - 1); }
   int process(int a, int b) {
       int buffer[128];
       for(int i = 0; i < 128; i++) buffer[i] = a + b + i;
       return buffer[0] + factorial(5);
   }
   int main() {
       printf("Starting Stack Analyzer Demo\n");
       int result = process(10, 20);
       functionA(5);
       return result;
   }
   ```
5. Select **Optimization: -O0**.
6. Click **Analyze**.
7. **Wait ~3 seconds**, then scroll through the output slowly.

**Narrate while scrolling:**
> "The tool compiled the code to LLVM IR, extracted the call graph, and ran the full x86_64 backend pipeline. The recursion warnings panel correctly identifies direct recursion in `factorial` and mutual recursion between `functionA` and `functionB`. The entry point table shows `main` has a worst-case cumulative depth of 576 bytes — that's the `process` function's 552-byte frame plus `main`'s own 24-byte frame. The call chain tree breaks down exactly which function contributes what."

**Key things to highlight on screen:**
- ⚠️ Recursion Warnings panel
- The entry-point table showing `576 B` cumulative
- The call chain tree: `main (24B) → process (552B) → factorial (24B)`

---

### Scene 4 — DEMO: CLI, RTOS Evaluation (3:45–5:15)

**Steps:**
1. Open a **Windows PowerShell** or terminal (NOT the server terminal).
2. Run:
   ```powershell
   wsl bash test/run_rtos_eval.sh
   ```
3. Let it run (~20 seconds). Do not cut this; let the build and analysis run live.
4. Scroll through the output.

**Narrate:**
> "Now let's run the full FreeRTOS evaluation suite. This harness models three realistic RTOS tasks: a sensor task with a 512-byte JSON formatting buffer, a comms task with function-pointer protocol dispatch, and a control task with a mutually recursive PID controller. The analyzer runs at three optimization levels: O0, O1, and O2 with inlining disabled."

**Key things to highlight:**
- `vSensorTask` cumulative depth vs 1024 B budget → `SAFE`
- `vControlTask` flagged `♾ RECURSIVE` (mutual recursion PID loop)
- Frame size reduction from `-O0` to `-O2` for `compute_checksum` (optimization impact)

---

### Scene 5 — DEMO: Failure / Edge Case — Recursion & Overflow (5:15–6:15)

**Steps:**
1. Switch back to the browser dashboard.
2. **Change the threshold to a very low value by running this directly in PowerShell:**
   ```powershell
   python analyzer.py --sizes test_results/temp/sizes.json --cg test_results/temp/cg.json --ll test_results/temp/upload.ll --threshold 100
   ```
3. Show the output in the terminal — the `main` chain (576 B) now exceeds the 100 B threshold and is flagged with `⚠️ RISK`.

**Narrate:**
> "Here's the edge/failure case. We've lowered the overflow threshold to 100 bytes. The tool now correctly flags `main`'s worst-case call chain of 576 bytes as an overflow risk. This is exactly the workflow an embedded developer would use — set the threshold to match the RTOS task's configured stack allocation, and the tool will immediately tell you which entry points are over budget."

**Key things to highlight:**
- `⚠️ RISK` label on the entry point
- The call chain tree turning red
- The exact byte count vs threshold comparison in the debug line

---

### Scene 6 — Summary (6:15–7:00)

**What to show:** Either a terminal with the analyzer output or the `EVALUATION.md` file.

**Say:**
> "To summarize: this tool delivers what no existing compiler provides — call-chain-aware, whole-program worst-case stack depth analysis using real LLVM machine-level frame sizes. We validated it against 7 test cases covering direct recursion, mutual recursion, deep call chains, large local arrays, indirect calls, and the impact of three optimization levels. The core technical breakthrough was solving the LLVM pass scheduling bug — our `InterceptPassManager` ensures `MachineFrameInfo::getStackSize()` is read after Prologue/Epilog Insertion completes but before the machine function data is freed."

---

## Recording Tips

### ✅ DO
- **Speak slowly and clearly.** You have time. Viewers can pause; they cannot slow you down.
- **Click deliberately.** Hover over important UI elements before clicking so viewers can track what you're doing.
- **Zoom in** on key numbers in the output (use `Ctrl++` in browser or increase terminal font temporarily).
- **Pause on the recursion warning panel** for at least 3 seconds.
- **Narrate the numbers out loud**: say "five hundred and seventy-six bytes" not just pointing at the screen.
- **Record a "second take"** — always do at least two recordings and pick the better one.
- **Keep it under 8 minutes**. Evaluators watch many videos.

### ❌ DON'T
- Don't apologize mid-recording. If you make a minor mistake, keep going.
- Don't show your email, GitHub credentials, or personal files.
- Don't record with background noise (fans, music, notifications).
- Don't rush through the call chain tree — that's the most important output.
- Don't show "0 bytes" from the old broken build. Make sure you've rebuilt with `build_wsl.sh` first.
- Don't skip the RTOS test — Deliverable #5 requires RTOS evaluation evidence.

---

## Recommended Tools

| Tool | Platform | Notes |
|------|----------|-------|
| **OBS Studio** | Windows/Mac/Linux | Free, professional, records desktop + audio |
| Windows Game Bar | Windows | `Win + G` → Record, easiest option |
| Loom | Browser extension | Automatically uploads, easy sharing link |
| ShareX | Windows | Free, supports annotations and zoom |

---

## Post-Production (Optional but Impressive)

If you have 20 extra minutes:
1. **Add captions / labels** at key moments: "← 552 bytes from int buffer[128]", "← Mutual recursion detected".
2. **Speed up** the compilation step (`wsl bash build_wsl.sh`) by 2× — nobody needs to watch compilation in real time.
3. **Add a title card** at the start: "Assignment 39 — Compile-Time Stack Usage Analyzer" with your name.
4. **Trim the ends** — cut any setup dead time at the start and end of the recording.
5. Export at **1080p, 30fps** minimum. Submit as `.mp4`.

---

## Upload Checklist

- [ ] Video is under 10 minutes.
- [ ] All 5 deliverables are visible somewhere in the video.
- [ ] Recursion detection shown (direct + mutual).
- [ ] RTOS task safety report shown.
- [ ] At least one "failure case" / overflow alert shown.
- [ ] Machine-level frame sizes (non-zero!) visible in output.
- [ ] GitHub repo URL shown or mentioned.
