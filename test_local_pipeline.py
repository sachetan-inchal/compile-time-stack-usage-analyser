import os, json, subprocess, sys

# Force stdout/stderr to UTF-8 on Windows to prevent UnicodeEncodeError with box-drawing / unicode characters
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

def to_wsl_path(win_path):
    path = win_path.replace('\\', '/')
    if path[1] == ':':
        drive = path[0].lower()
        path = f"/mnt/{drive}{path[2:]}"
    return path

def run_pipeline(c_code, opt):
    temp_dir = os.path.join(WORKSPACE_DIR, 'test_results', 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    c_path = os.path.join(temp_dir, 'upload.c')
    ll_path = os.path.join(temp_dir, 'upload.ll')
    cg_path = os.path.join(temp_dir, 'cg.json')
    sizes_path = os.path.join(temp_dir, 'sizes.json')
    
    with open(c_path, 'w', encoding='utf-8') as f:
        f.write(c_code)
        
    wsl_c = to_wsl_path(c_path)
    wsl_ll = to_wsl_path(ll_path)
    wsl_cg = to_wsl_path(cg_path)
    wsl_sizes = to_wsl_path(sizes_path)
    wsl_dir = to_wsl_path(WORKSPACE_DIR)

    output_log = []
    
    cmd_compile = f'wsl clang {opt} -S -emit-llvm "{wsl_c}" -o "{wsl_ll}"'
    output_log.append(f"$ {cmd_compile}")
    res = subprocess.run(cmd_compile, shell=True, capture_output=True, encoding='utf-8')
    if res.returncode != 0:
        return "\n".join(output_log) + f"\n\n[Compilation Error]\n{res.stderr or ''}"

    cmd_extract = f'wsl "{wsl_dir}/build/stack-extractor" "{wsl_ll}" "{wsl_cg}"'
    output_log.append(f"$ {cmd_extract}")
    res = subprocess.run(cmd_extract, shell=True, capture_output=True, encoding='utf-8')
    if res.returncode != 0:
        return "\n".join(output_log) + f"\n\n[Call Graph Extraction Error]\n{res.stderr or ''}"

    cmd_collect = f'wsl "{wsl_dir}/build/stack-size-collector" "{wsl_ll}" "{wsl_sizes}"'
    output_log.append(f"$ {cmd_collect}")
    res = subprocess.run(cmd_collect, shell=True, capture_output=True, encoding='utf-8')
    if res.returncode != 0:
        return "\n".join(output_log) + f"\n\n[Stack Size Collector Error]\n{res.stderr or ''}"

    cmd_analyze = f'python "{WORKSPACE_DIR}/analyzer.py" --sizes "{sizes_path}" --cg "{cg_path}" --threshold 600'
    output_log.append(f"$ {cmd_analyze}\n")
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    res = subprocess.run(cmd_analyze, shell=True, capture_output=True, encoding='utf-8', env=env)
    
    output_log.append(str(res.stdout or ''))
    if res.stderr:
        output_log.append(str(res.stderr or ''))
        
    return "\n".join([str(item) for item in output_log if item is not None])

code = """#include <stdio.h>
int factorial(int n) { if (n <= 1) return 1; return n * factorial(n - 1); }
void functionB(int x);
void functionA(int x) { if (x <= 0) return; functionB(x - 1); }
void functionB(int x) { if (x <= 0) return; functionA(x - 1); }
int process(int a, int b) { int buffer[128]; for(int i = 0; i < 128; i++) buffer[i] = a + b + i; return buffer[0] + factorial(5); }
int main() { printf("Starting Stack Analyzer Demo\\n"); int result = process(10, 20); functionA(5); return result; }"""

try:
    print(run_pipeline(code, '-O0'))
except Exception as e:
    import traceback
    traceback.print_exc()
