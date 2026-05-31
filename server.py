import http.server
import socketserver
import json
import subprocess
import os
import traceback

PORT = 3000
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))


def safe_decode(raw_bytes):
    """Decode bytes to string safely — tries utf-8, then latin-1 (never fails)."""
    if raw_bytes is None:
        return ''
    if isinstance(raw_bytes, str):
        return raw_bytes
    try:
        return raw_bytes.decode('utf-8')
    except (UnicodeDecodeError, AttributeError):
        return raw_bytes.decode('latin-1', errors='replace')


def run_cmd(cmd, env=None):
    """Run a shell command and return (returncode, stdout_str, stderr_str).
    Uses BINARY mode to avoid Windows cp1252 decoding crashes, then
    manually decodes with safe_decode."""
    res = subprocess.run(
        cmd, shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    return res.returncode, safe_decode(res.stdout), safe_decode(res.stderr)


def to_wsl_path(win_path):
    """Convert C:\\path\\to\\file to /mnt/c/path/to/file"""
    path = win_path.replace('\\', '/')
    if len(path) > 1 and path[1] == ':':
        drive = path[0].lower()
        path = f"/mnt/{drive}{path[2:]}"
    return path


class AnalysisRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Prevent caching so code changes reload immediately
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_POST(self):
        if self.path == '/analyze':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            try:
                payload = json.loads(post_data.decode('utf-8'))
                c_code = payload.get('code', '')
                optimization = payload.get('opt', '-O0')

                # Run the compile and extraction pipeline
                result_text = self.run_pipeline(c_code, optimization)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'output': result_text}).encode('utf-8'))
            except Exception as e:
                tb = traceback.format_exc()
                print(f"[SERVER ERROR]\n{tb}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def run_pipeline(self, c_code, opt):
        """Full analysis pipeline: C code → LLVM IR → call graph → stack sizes → report."""
        # Create temp folder for workspace processing
        temp_dir = os.path.join(WORKSPACE_DIR, 'test_results', 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        c_path = os.path.join(temp_dir, 'upload.c')
        ll_path = os.path.join(temp_dir, 'upload.ll')
        cg_path = os.path.join(temp_dir, 'cg.json')
        sizes_path = os.path.join(temp_dir, 'sizes.json')

        # Write C code locally
        with open(c_path, 'w', encoding='utf-8') as f:
            f.write(c_code)

        # Convert absolute paths to WSL paths
        wsl_c = to_wsl_path(c_path)
        wsl_ll = to_wsl_path(ll_path)
        wsl_cg = to_wsl_path(cg_path)
        wsl_sizes = to_wsl_path(sizes_path)
        wsl_dir = to_wsl_path(WORKSPACE_DIR)

        output_lines = []

        # ── Step 1: Compile C → LLVM IR inside WSL ──
        cmd = f'wsl -d Ubuntu clang {opt} -S -emit-llvm "{wsl_c}" -o "{wsl_ll}"'
        output_lines.append(f"$ {cmd}")
        rc, stdout, stderr = run_cmd(cmd)
        if rc != 0:
            output_lines.append(f"\n[Compilation Error]\n{stderr}")
            return "\n".join(output_lines)

        # ── Step 2: Extract Call Graph ──
        cmd = f'wsl -d Ubuntu "{wsl_dir}/build/stack-extractor" "{wsl_ll}" "{wsl_cg}"'
        output_lines.append(f"$ {cmd}")
        rc, stdout, stderr = run_cmd(cmd)
        if stdout:
            output_lines.append(stdout.strip())
        if rc != 0:
            output_lines.append(f"\n[Call Graph Extraction Error]\n{stderr}")
            return "\n".join(output_lines)

        # ── Step 3: Collect Stack Sizes ──
        cmd = f'wsl -d Ubuntu "{wsl_dir}/build/stack-size-collector" "{wsl_ll}" "{wsl_sizes}"'
        output_lines.append(f"$ {cmd}")
        rc, stdout, stderr = run_cmd(cmd)
        if stdout:
            output_lines.append(stdout.strip())
        if rc != 0:
            output_lines.append(f"\n[Stack Size Collector Error]\n{stderr}")
            return "\n".join(output_lines)

        # ── Step 4: Run Python analyzer ──
        cmd = f'python "{WORKSPACE_DIR}/analyzer.py" --sizes "{sizes_path}" --cg "{cg_path}" --ll "{ll_path}" --threshold 600'
        output_lines.append(f"\n$ {cmd}\n")
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        rc, stdout, stderr = run_cmd(cmd, env=env)
        if stdout:
            output_lines.append(stdout)
        if stderr:
            output_lines.append(stderr)
        if rc != 0 and not stdout and not stderr:
            output_lines.append("[Analyzer Error] analyzer.py returned a non-zero exit code with no output.")

        return "\n".join(output_lines)


if __name__ == '__main__':
    # Ensure serving static files runs from the workspace directory
    os.chdir(WORKSPACE_DIR)
    handler = AnalysisRequestHandler

    # Allow port reuse to avoid 'Address already in use' errors
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"Stack Analyzer Backend running at http://localhost:{PORT}")
        print(f"Workspace: {WORKSPACE_DIR}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
