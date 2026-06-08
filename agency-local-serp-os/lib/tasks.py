import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# If REDIS_URL is not set or we want to run locally without Redis, set eager to True
# Eager mode runs the tasks synchronously in the same process
is_eager = "REDIS_URL" not in os.environ

app = Celery("agency_os", broker=REDIS_URL, backend=REDIS_URL)

app.conf.update(
    task_always_eager=is_eager,
    task_eager_propagates=True,
    broker_connection_retry_on_startup=True
)

@app.task(name="execute_playbook")
def execute_playbook(client_id, script_path, args=None):
    """
    Background worker task to execute an AI playbook.
    """
    import subprocess
    import pathlib
    import sys

    ROOT = pathlib.Path(__file__).resolve().parents[1]
    
    cmd = [sys.executable, str(ROOT / script_path), "--client", client_id]
    if args:
        cmd.extend(args)
        
    print(f"[Worker] Executing: {' '.join(cmd)}")
    
    # Run the long-running process
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"[Worker] Success: {result.stdout}")
        return {"status": "success", "output": result.stdout}
    else:
        print(f"[Worker] Error: {result.stderr}")
        return {"status": "error", "output": result.stderr}
