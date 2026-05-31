// ========================================================================
// Compile-Time Stack Usage Analyzer — Frontend Script
// ========================================================================

// Terminal demo content for each tab
const terminalData = {
    eval1: `<span class="t-bold">══════════════════════════════════════════════════════</span>
<span class="t-bold">   STATIC STACK USAGE ANALYZER — EVALUATION (-O0)</span>
<span class="t-bold">══════════════════════════════════════════════════════</span>

<span class="t-cyan">╭───────────────────────────────────────────────────╮</span>
<span class="t-cyan">│</span> <span class="t-bold">▲ COMPILE-TIME STACK USAGE ANALYZER ▲</span>             <span class="t-cyan">│</span>
<span class="t-cyan">│</span> <span class="t-dim">LLVM-Native High-Fidelity Static Frame Estimation</span> <span class="t-cyan">│</span>
<span class="t-cyan">╰───────────────────────────────────────────────────╯</span>

<span class="t-green">[ok]</span> Loaded MachineFunction frame sizes from: sizes_O0.json

<span class="t-yellow">╭────────────────────── Analysis Summary ──────────────────────╮</span>
<span class="t-yellow">│</span> • Total Functions Analyzed:     <span class="t-bold">13</span>                           <span class="t-yellow">│</span>
<span class="t-yellow">│</span> • Deepest Estimated Path:       <span class="t-bold">856 bytes</span>                    <span class="t-yellow">│</span>
<span class="t-yellow">│</span> • Indirect Call Penalty:        <span class="t-bold">256 bytes</span>                    <span class="t-yellow">│</span>
<span class="t-yellow">│</span> • Overflow Alert Threshold:     <span class="t-bold">600 bytes</span>                    <span class="t-yellow">│</span>
<span class="t-yellow">│</span> • Frame Size Source:            <span class="t-cyan">MachineFunction</span>              <span class="t-yellow">│</span>
<span class="t-yellow">╰──────────────────────────────────────────────────────────────╯</span>

<span class="t-red">╭────────────────────── ⚠️ RECURSION WARNINGS ─────────────────╮</span>
<span class="t-red">│</span> ▲ Recursion Loop: <span class="t-red">pong -> ping -> pong</span>                      <span class="t-red">│</span>
<span class="t-red">│</span> ▲ Recursion Loop: <span class="t-red">factorial -> factorial</span>                     <span class="t-red">│</span>
<span class="t-red">╰──────────────────────────────────────────────────────────────╯</span>

<span class="t-green">         Entry Point Cumulative Stack Depths</span>
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ <span class="t-bold">Entry Point</span>            ┃ <span class="t-bold">Own Frame</span>  ┃ <span class="t-bold">Worst-Case Depth</span> ┃ <span class="t-bold">Status</span> ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ <span class="t-cyan">vTask1</span>                 │     <span class="t-magenta">56 B</span>   │   <span class="t-red">856 B</span>          │ <span class="t-red">⚠ RISK</span> │
│ <span class="t-cyan">vTask2</span>                 │     <span class="t-magenta">48 B</span>   │   <span class="t-yellow">304 B</span>          │ <span class="t-green">  OK</span>   │
│ <span class="t-cyan">vTask3</span>                 │     <span class="t-magenta">32 B</span>   │   <span class="t-green">128 B</span>          │ <span class="t-green">  OK</span>   │
│ <span class="t-cyan">main</span>                   │     <span class="t-magenta">16 B</span>   │   <span class="t-red">856 B</span>          │ <span class="t-red">⚠ RISK</span> │
└────────────────────────┴────────────┴──────────────────┴────────┘

<span class="t-cyan">Top-5 Deepest Statically Estimated Call Chains:</span>

Worst-Case Chain from <span class="t-cyan">vTask1</span> (Total: <span class="t-red">856 bytes</span>)
└── ↪ <span class="t-cyan">vTask1</span> <span class="t-magenta">(56 B frame)</span> <span class="t-dim">(cum: 856 B)</span>
    └── ↪ <span class="t-cyan">process_sensor_data</span> <span class="t-magenta">(24 B frame)</span> <span class="t-dim">(cum: 800 B)</span>
        └── ↪ <span class="t-cyan">format_json</span> <span class="t-magenta">(552 B frame)</span> <span class="t-dim">(cum: 776 B)</span>
            └── ↪ <span class="t-cyan">hash_data</span> <span class="t-magenta">(48 B frame)</span> <span class="t-dim">(cum: 48 B)</span>

Worst-Case Chain from <span class="t-cyan">vTask2</span> (Total: <span class="t-yellow">304 bytes</span>)
└── ↪ <span class="t-cyan">vTask2</span> <span class="t-magenta">(48 B frame)</span> <span class="t-dim">(cum: 304 B)</span>
    └── ↪ <span class="t-yellow">‹Indirect: void (i32)›</span> (+256 bytes boundary)`,

    eval2: `<span class="t-bold">══════════════════════════════════════════════════════</span>
<span class="t-bold">   RTOS STACK USAGE EVALUATION — FreeRTOS Harness</span>
<span class="t-bold">══════════════════════════════════════════════════════</span>

<span class="t-cyan">╭───────────────────────────────────────────────────╮</span>
<span class="t-cyan">│</span> <span class="t-bold">▲ COMPILE-TIME STACK USAGE ANALYZER ▲</span>             <span class="t-cyan">│</span>
<span class="t-cyan">│</span> <span class="t-dim">LLVM-Native High-Fidelity Static Frame Estimation</span> <span class="t-cyan">│</span>
<span class="t-cyan">╰───────────────────────────────────────────────────╯</span>

<span class="t-green">[ok]</span> Loaded MachineFunction frame sizes from: sizes_O0.json

<span class="t-red">╭────────────────────── ⚠️ RECURSION WARNINGS ─────────────────╮</span>
<span class="t-red">│</span> ▲ Recursion Loop: <span class="t-red">pid_correct -> pid_anti_windup -> pid_correct</span><span class="t-red">│</span>
<span class="t-red">╰──────────────────────────────────────────────────────────────╯</span>

<span class="t-magenta">╭─────────────────────── ▲ RTOS SAFETY REPORT ─────────────────╮</span>
<span class="t-magenta">│</span> Compares static worst-case depth against task stack allocs   <span class="t-magenta">│</span>
<span class="t-magenta">╰──────────────────────────────────────────────────────────────╯</span>

┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ <span class="t-bold">Task</span>            ┃ <span class="t-bold">Own Frame</span>┃ <span class="t-bold">Worst Depth</span>  ┃ <span class="t-bold">Stack Alloc</span>  ┃ <span class="t-bold">Margin</span>     ┃ <span class="t-bold">Status</span>           ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ <span class="t-cyan">vSensorTask</span>     │   <span class="t-magenta">72 B</span>   │   <span class="t-yellow">748 B</span>      │   <span class="t-yellow">1024 B</span>    │   <span class="t-yellow">276 B</span>    │ <span class="t-yellow">⚡ LOW MARGIN</span>    │
│ <span class="t-cyan">vCommsTask</span>      │   <span class="t-magenta">48 B</span>   │   <span class="t-green">356 B</span>      │   <span class="t-yellow">512 B</span>     │   <span class="t-green">156 B</span>    │ <span class="t-green">✅ SAFE</span>          │
│ <span class="t-cyan">vControlTask</span>    │   <span class="t-magenta">40 B</span>   │   <span class="t-yellow">224 B</span>      │   <span class="t-yellow">2048 B</span>    │   <span class="t-yellow">N/A</span>      │ <span class="t-yellow">♾  RECURSIVE</span>    │
└─────────────────┴──────────┴──────────────┴──────────────┴────────────┴──────────────────┘

<span class="t-bold">Ground-Truth Comparison:</span>
┌─────────────────┬──────────────────────────────────────────────────────────┐
│ <span class="t-bold">Task</span>            │ <span class="t-bold">Expected Chain Depth (x86_64 -O0)</span>                        │
├─────────────────┼──────────────────────────────────────────────────────────┤
│ vSensorTask     │ <span class="t-green">~750 B</span>  (dominator: format_sensor_json 512B buffer)       │
│ vCommsTask      │ <span class="t-green">~360 B</span>  (dominator: handle_spi 256B buffer via indirect)  │
│ vControlTask    │ <span class="t-yellow">RECURSIVE</span> — unbounded (pid_correct ↔ pid_anti_windup)    │
└─────────────────┴──────────────────────────────────────────────────────────┘

<span class="t-bold">Evaluation Criteria:</span>
  <span class="t-green">[PASS]</span> vSensorTask estimate within 20% of 750 B
  <span class="t-green">[PASS]</span> vCommsTask captures indirect call penalty correctly
  <span class="t-green">[PASS]</span> vControlTask flagged as RECURSIVE with unbounded depth
  <span class="t-green">[PASS]</span> Frame sizes match -fstack-usage within ~16 B`,

    eval3: `<span class="t-bold">══════════════════════════════════════════════════════</span>
<span class="t-bold">   USAGE GUIDE — Compile-Time Stack Usage Analyzer</span>
<span class="t-bold">══════════════════════════════════════════════════════</span>

<span class="t-dim"># Step 1: Compile your C code to LLVM IR</span>
<span class="t-green">$</span> clang -O0 -S -emit-llvm your_code.c -o your_code.ll

<span class="t-dim"># Step 2: Extract the static call graph</span>
<span class="t-green">$</span> ./build/stack-extractor your_code.ll call_graph.json
<span class="t-cyan">Call graph successfully exported to call_graph.json</span>

<span class="t-dim"># Step 3: Collect MachineFunction frame sizes</span>
<span class="t-green">$</span> ./build/stack-size-collector your_code.ll stack_sizes.json
<span class="t-cyan">[stack-size-collector] Analyzed 15 functions.</span>
<span class="t-cyan">[stack-size-collector] Frame sizes written to: stack_sizes.json</span>

<span class="t-dim"># Step 4: Run the analyzer</span>
<span class="t-green">$</span> python3 analyzer.py \\
    --sizes stack_sizes.json \\
    --cg call_graph.json \\
    --threshold 1024 \\
    --top-n 10

<span class="t-dim"># Available CLI flags:</span>
  <span class="t-yellow">--sizes</span>          Path to stack sizes JSON or .su file
  <span class="t-yellow">--cg</span>             Path to call_graph.json
  <span class="t-yellow">--indirect-cost</span>  Upper bound for indirect calls (default: 256)
  <span class="t-yellow">--threshold</span>      Alert threshold in bytes (default: 1024)
  <span class="t-yellow">--top-n</span>          Number of deepest chains to show (default: 5)
  <span class="t-yellow">--rtos-report</span>    Enable RTOS task safety comparison
  <span class="t-yellow">--stack-alloc</span>    Default task stack size (default: 2048)
  <span class="t-yellow">--task-allocs</span>    Per-task stack sizes: "task1=1024,task2=512"

<span class="t-dim"># Run the full automated evaluation suite:</span>
<span class="t-green">$</span> bash test/run_eval.sh        <span class="t-dim"># Basic evaluation</span>
<span class="t-green">$</span> bash test/run_rtos_eval.sh   <span class="t-dim"># FreeRTOS RTOS evaluation</span>`
};

// Sample recursive and nested function program in C
const SAMPLE_C_CODE = `#include <stdio.h>

// Direct recursion
int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

// Mutual recursion loop: A -> B -> A
void functionB(int x);

void functionA(int x) {
    if (x <= 0) return;
    functionB(x - 1);
}

void functionB(int x) {
    if (x <= 0) return;
    functionA(x - 1);
}

// Normal stack-using functions
int process(int a, int b) {
    int buffer[128]; // Local array allocates stack space
    for(int i = 0; i < 128; i++) {
        buffer[i] = a + b + i;
    }
    return buffer[0] + factorial(5);
}

int main() {
    printf("Starting Stack Analyzer Demo\\n");
    int result = process(10, 20);
    functionA(5);
    return result;
}
`;

// ===================== DOM Ready =====================
let currentMode = 'upload';   // 'upload' | 'paste'
let uploadedFileContent = null;
let uploadedFileName = '';

document.addEventListener('DOMContentLoaded', () => {
    initNavbar();
    initCounters();
    initTabs();
    initScrollAnimations();
    initInteractiveAnalysis();
    initDropzone();
});

// ===================== Mode Switcher =====================
function switchMode(mode) {
    currentMode = mode;
    document.getElementById('upload-panel').style.display = mode === 'upload' ? 'block' : 'none';
    document.getElementById('paste-panel').style.display  = mode === 'paste'  ? 'block' : 'none';
    document.getElementById('mode-upload').classList.toggle('active', mode === 'upload');
    document.getElementById('mode-paste').classList.toggle('active',  mode === 'paste');
}

// ===================== Dropzone =====================
function initDropzone() {
    const dz  = document.getElementById('dropzone');
    const inp = document.getElementById('file-input');

    dz.addEventListener('click', () => inp.click());
    inp.addEventListener('change', () => { if (inp.files[0]) handleFile(inp.files[0]); });

    dz.addEventListener('dragover',  e => { e.preventDefault(); dz.classList.add('drag-over'); });
    dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
    dz.addEventListener('drop', e => {
        e.preventDefault();
        dz.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    });
}

function handleFile(file) {
    if (!file.name.match(/\.(c|h)$/i)) {
        showToast('⚠️ Only .c and .h files are supported.', 'warn');
        return;
    }
    if (file.size > 256 * 1024) {
        showToast('⚠️ File too large. Max size is 256 KB.', 'warn');
        return;
    }
    const reader = new FileReader();
    reader.onload = e => {
        uploadedFileContent = e.target.result;
        uploadedFileName    = file.name;
        // Show badge
        document.getElementById('file-status').style.display = 'block';
        document.getElementById('file-badge-name').textContent = file.name;
        document.getElementById('file-badge-size').textContent = formatBytes(file.size);
        // Animate dropzone
        const dz = document.getElementById('dropzone');
        dz.classList.add('file-loaded');
        showToast(`✅ "${file.name}" loaded — click Run Stack Analysis!`, 'ok');
    };
    reader.readAsText(file);
}

function clearFile() {
    uploadedFileContent = null;
    uploadedFileName    = '';
    document.getElementById('file-status').style.display = 'none';
    document.getElementById('file-input').value = '';
    document.getElementById('dropzone').classList.remove('file-loaded');
}

function clearEditor() {
    document.getElementById('code-editor').value = '';
    document.getElementById('code-editor').focus();
}

function loadSample() {
    // Switch to paste mode and fill sample
    switchMode('paste');
    document.getElementById('code-editor').value = SAMPLE_C_CODE;
    document.getElementById('code-editor').focus();
    showToast('📋 Recursive sample loaded!', 'ok');
}

function formatBytes(b) {
    return b < 1024 ? b + ' B' : (b / 1024).toFixed(1) + ' KB';
}

function showToast(msg, type) {
    let t = document.getElementById('toast-msg');
    if (!t) {
        t = document.createElement('div');
        t.id = 'toast-msg';
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.className = 'toast toast-' + type + ' toast-show';
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove('toast-show'), 3500);
}

function copyOutput() {
    const text = document.getElementById('terminal-content').innerText;
    navigator.clipboard.writeText(text).then(() => showToast('📋 Output copied!', 'ok'));
}

// ===================== Interactive C Compiler & Analyzer =====================
function initInteractiveAnalysis() {
    const btnAnalyze = document.getElementById('btn-analyze');
    const optLevel   = document.getElementById('opt-level');
    const terminalContent = document.getElementById('terminal-content');
    const terminalTitle   = document.getElementById('terminal-title');
    const liveTab = document.querySelector('.demo-tab[data-tab="live"]');

    btnAnalyze.addEventListener('click', async () => {
        // Get code from the active input mode
        let code = '';
        let sourceName = 'stdin';
        if (currentMode === 'upload') {
            if (!uploadedFileContent) {
                showToast('⚠️ Please upload a .c file first, or switch to Paste mode.', 'warn');
                return;
            }
            code = uploadedFileContent;
            sourceName = uploadedFileName;
        } else {
            code = (document.getElementById('code-editor').value || '').trim();
            if (!code) {
                showToast('⚠️ Please paste or write some C code first.', 'warn');
                return;
            }
            sourceName = 'pasted_code.c';
        }

        btnAnalyze.disabled = true;
        btnAnalyze.textContent = '⏳ Analyzing...';
        terminalTitle.textContent = `stack-analyzer — compiling ${sourceName}…`;
        terminalContent.innerHTML =
            `<span class="t-cyan">[info]</span> Source: <span class="t-bold">${sourceName}</span>\n` +
            `<span class="t-cyan">[info]</span> Optimization: <span class="t-bold">${optLevel.value}</span>\n` +
            `<span class="t-yellow">[  1/4]</span> Sending to compilation pipeline…\n`;

        // Switch to live output tab
        document.querySelectorAll('.demo-tab').forEach(t => t.classList.remove('active'));
        liveTab.classList.add('active');

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code, opt: optLevel.value })
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Server error during compilation.');

            const formatted = formatTerminalColors(data.output);
            terminalContent.innerHTML = formatted;
            terminalData.live = formatted;
            terminalTitle.textContent = `stack-analyzer — ${sourceName} ✓`;
            showToast('✅ Analysis complete!', 'ok');
        } catch (err) {
            terminalContent.innerHTML =
                `<span class="t-red">[ERROR]</span> ${escapeHtml(err.message)}\n\n` +
                `<span class="t-dim">Make sure the WSL backend is running and clang/llvm are installed.</span>`;
            terminalTitle.textContent = 'stack-analyzer — error';
            showToast('❌ Analysis failed. See terminal.', 'warn');
        } finally {
            btnAnalyze.disabled = false;
            btnAnalyze.textContent = '⚡ Run Stack Analysis';
        }
    });
}

function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// Convert rich/bash CLI color codes to colorful HTML spans
function formatTerminalColors(text) {
    if (!text) return "";
    
    // Replace standard ANSI color sequences if any
    let formatted = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Replace rich boundaries and headers
    formatted = formatted
        .replace(/╭─/g, '<span class="t-cyan">╭─</span>')
        .replace(/╰─/g, '<span class="t-cyan">╰─</span>')
        .replace(/│/g, '<span class="t-cyan">│</span>')
        .replace(/┡━/g, '<span class="t-bold">┡━</span>')
        .replace(/┹━/g, '<span class="t-bold">┹━</span>')
        .replace(/┏━/g, '<span class="t-bold">┏━</span>')
        .replace(/┗━/g, '<span class="t-bold">┗━</span>')
        .replace(/┠─/g, '<span class="t-dim">┠─</span>')
        .replace(/┸─/g, '<span class="t-dim">┸─</span>');

    // Replace color codes from rich or custom logger
    formatted = formatted
        .replace(/\[ok\]/g, '<span class="t-green">[ok]</span>')
        .replace(/\[info\]/g, '<span class="t-cyan">[info]</span>')
        .replace(/\[ERROR\]/g, '<span class="t-red">[ERROR]</span>')
        .replace(/FAIL/g, '<span class="t-red">FAIL</span>')
        .replace(/PASS/g, '<span class="t-green">PASS</span>')
        .replace(/RISK/g, '<span class="t-red">RISK</span>')
        .replace(/Recursive/g, '<span class="t-red">Recursive</span>')
        .replace(/RECURSIVE/g, '<span class="t-red">RECURSIVE</span>')
        .replace(/Recursion/g, '<span class="t-red">Recursion</span>')
        .replace(/WARNING/g, '<span class="t-yellow">WARNING</span>')
        .replace(/✓/g, '<span class="t-green">✓</span>')
        .replace(/(\b\d+\s+bytes\b)/gi, '<span class="t-bold">$1</span>')
        .replace(/(\b\d+\s+B\b)/gi, '<span class="t-magenta">$1</span>')
        .replace(/(\d+\/\d+\s+PASS)/gi, '<span class="t-green">$1</span>')
        .replace(/(--[a-zA-Z0-9-]+)/g, '<span class="t-yellow">$1</span>');

    return formatted;
}

// ===================== Navbar scroll effect =====================
function initNavbar() {
    const navbar = document.getElementById('navbar');
    window.addEventListener('scroll', () => {
        navbar.classList.toggle('scrolled', window.scrollY > 50);
    });
}

// ===================== Animated counters =====================
function initCounters() {
    const counters = document.querySelectorAll('.stat-value[data-count]');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    counters.forEach(counter => observer.observe(counter));
}

function animateCounter(el) {
    const target = parseInt(el.dataset.count);
    const duration = 1500;
    const start = performance.now();

    function update(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(eased * target);

        el.textContent = current >= 1000
            ? current.toLocaleString()
            : current;

        if (progress < 1) requestAnimationFrame(update);
    }

    requestAnimationFrame(update);
}

// ===================== Demo tabs =====================
function initTabs() {
    const tabs = document.querySelectorAll('.demo-tab');
    const content = document.getElementById('terminal-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            const tabId = tab.dataset.tab;
            content.style.opacity = '0';
            content.style.transform = 'translateY(10px)';

            setTimeout(() => {
                content.innerHTML = terminalData[tabId] || 'Waiting for you to run analysis...';
                content.style.opacity = '1';
                content.style.transform = 'translateY(0)';
            }, 200);
        });
    });

    content.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
}

// ===================== Scroll animations =====================
function initScrollAnimations() {
    const animElements = document.querySelectorAll(
        '.problem-card, .pipeline-step, .deliverable-card, .metric-card, .tech-item, .qs-step'
    );

    animElements.forEach(el => el.classList.add('fade-in'));

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.classList.add('visible');
                }, index * 80);
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

    animElements.forEach(el => observer.observe(el));
}
