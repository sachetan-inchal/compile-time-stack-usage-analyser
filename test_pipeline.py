"""Test script to debug the full analysis pipeline."""
import subprocess, os, json, sys

# Force stdout/stderr to UTF-8 on Windows to prevent UnicodeEncodeError with box-drawing / unicode characters
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"WORKSPACE_DIR: {WORKSPACE_DIR}")

temp_dir = os.path.join(WORKSPACE_DIR, 'test_results', 'temp')
os.makedirs(temp_dir, exist_ok=True)

c_path = os.path.join(temp_dir, 'upload.c')
ll_path = os.path.join(temp_dir, 'upload.ll')
cg_path = os.path.join(temp_dir, 'cg.json')
sizes_path = os.path.join(temp_dir, 'sizes.json')

code = '#include <stdio.h>\nint factorial(int n) { if (n<=1) return 1; return n*factorial(n-1); }\nint main() { printf("%d\\n", factorial(5)); return 0; }\n'
with open(c_path, 'w') as f:
    f.write(code)

def to_wsl(p):
    p = p.replace('\\', '/')
    if len(p) > 1 and p[1] == ':':
        return '/mnt/' + p[0].lower() + p[2:]
    return p

wsl_c = to_wsl(c_path)
wsl_ll = to_wsl(ll_path)
wsl_cg = to_wsl(cg_path)
wsl_sizes = to_wsl(sizes_path)
wsl_dir = to_wsl(WORKSPACE_DIR)

output_log = []

# Step 1: Compile
cmd1 = f'wsl clang -O0 -S -emit-llvm "{wsl_c}" -o "{wsl_ll}"'
print(f"\n=== STEP 1: Compile ===\n  {cmd1}")
r = subprocess.run(cmd1, shell=True, capture_output=True, encoding='utf-8')
output_log.append(f"$ {cmd1}")
print(f"  returncode={r.returncode}")
print(f"  stdout={repr(r.stdout)}")
print(f"  stderr={repr(r.stderr)}")
if r.returncode != 0:
    print("FAILED at step 1"); sys.exit(1)

# Step 2: Extract call graph
cmd2 = f'wsl "{wsl_dir}/build/stack-extractor" "{wsl_ll}" "{wsl_cg}"'
print(f"\n=== STEP 2: Extract CG ===\n  {cmd2}")
r = subprocess.run(cmd2, shell=True, capture_output=True, encoding='utf-8')
output_log.append(f"$ {cmd2}")
print(f"  returncode={r.returncode}")
print(f"  stdout={repr(r.stdout)}")
print(f"  stderr={repr(r.stderr)}")
if r.returncode != 0:
    print("FAILED at step 2"); sys.exit(1)

# Step 3: Collect stack sizes
cmd3 = f'wsl "{wsl_dir}/build/stack-size-collector" "{wsl_ll}" "{wsl_sizes}"'
print(f"\n=== STEP 3: Collect Sizes ===\n  {cmd3}")
r = subprocess.run(cmd3, shell=True, capture_output=True, encoding='utf-8')
output_log.append(f"$ {cmd3}")
print(f"  returncode={r.returncode}")
print(f"  stdout={repr(r.stdout)}")
print(f"  stderr={repr(r.stderr)}")
if r.returncode != 0:
    print("FAILED at step 3"); sys.exit(1)

# Step 4: Run analyzer
cmd4 = f'python "{WORKSPACE_DIR}\\analyzer.py" --sizes "{sizes_path}" --cg "{cg_path}" --threshold 600'
print(f"\n=== STEP 4: Analyzer ===\n  {cmd4}")
env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'
r = subprocess.run(cmd4, shell=True, capture_output=True, encoding='utf-8', env=env)
output_log.append(f"$ {cmd4}\n")
print(f"  returncode={r.returncode}")
print(f"  stdout type={type(r.stdout)}, len={len(r.stdout) if r.stdout else 'None'}")
print(f"  stderr type={type(r.stderr)}, len={len(r.stderr) if r.stderr else 'None'}")
if r.stdout:
    print(f"  stdout preview: {r.stdout[:200]}")
if r.stderr:
    print(f"  stderr preview: {r.stderr[:200]}")

output_log.append(r.stdout or '')
if r.stderr:
    output_log.append(r.stderr or '')

print(f"\n=== JOIN TEST ===")
print(f"  output_log has {len(output_log)} items")
for i, item in enumerate(output_log):
    print(f"  [{i}] type={type(item)} len={len(item) if item is not None else 'None'}")

try:
    result = "\n".join(output_log)
    print(f"\n  JOIN SUCCESS, total length = {len(result)}")
except Exception as e:
    print(f"\n  JOIN FAILED: {e}")
