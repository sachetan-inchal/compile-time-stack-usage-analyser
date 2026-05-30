# save as repo_to_text.py
import os, sys

IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'dist', 'build'}
ALLOW_EXTS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.css', '.html', '.json', '.md', '.yaml', '.yml', '.toml', '.rs', '.go', '.java', '.cpp', '.h', '.c'}

def export_codebase(root, out_file):
    with open(out_file, 'w', encoding='utf-8') as f:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
            for fname in filenames:
                if os.path.splitext(fname)[1].lower() in ALLOW_EXTS:
                    fpath = os.path.join(dirpath, fname)
                    try:
                        content = open(fpath, 'r', encoding='utf-8').read()
                        f.write(f"# File: {fpath}\n```\n{content}\n```\n\n")
                    except Exception:
                        pass
    print(f"✅ Exported to {out_file}")

if __name__ == "__main__":
    export_codebase(sys.argv[1] if len(sys.argv) > 1 else ".", "codebase.txt")