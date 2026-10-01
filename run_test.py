import subprocess, time, sys, os

app_path = r"D:\My-GitHub\GitHub\FireEngineerAI\app.py"
log_path = r"D:\My-GitHub\GitHub\FireEngineerAI\run_test.log"

# Ensure we use the correct Python
python_exe = r"C:\Users\mohda\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
if not os.path.exists(python_exe):
    python_exe = sys.executable

print(f"Using Python: {python_exe}")
print(f"App: {app_path}")

proc = subprocess.Popen(
    [python_exe, app_path],
    cwd=r"D:\My-GitHub\GitHub\FireEngineerAI",
    stdout=open(log_path, "w", encoding="utf-8"),
    stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NO_WINDOW,
)

print(f"Started PID={proc.pid}, waiting 4 seconds...")
time.sleep(4)

# Read what was logged
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"\n=== Log output ({len(content)} bytes) ===")
    print(content[:2000])
else:
    print("No log file generated")

# Cleanup
if proc.poll() is None:
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    print(f"\nProcess terminated (exit code: {proc.returncode})")
else:
    print(f"\nProcess exited with code: {proc.returncode}")
