import os
import sys
import json
import pathlib
from flask import Flask, request, jsonify

# Setup Python Path for Vercel
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from lib import board_scan, mission_control, db
from lib.env import load_env; load_env()

app = Flask(__name__)

def require_auth(f):
    """JWT token validation middleware using Supabase Auth."""
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized: Missing Token"}), 401
            
        token = auth_header.split(" ")[1]
        
        # Verify with Supabase
        db_client = db.get_supabase()
        if db_client:
            user_response = db_client.auth.get_user(token)
            if not user_response or not user_response.user:
                return jsonify({"error": "Unauthorized: Invalid Token"}), 401
        
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@app.route("/api/board", methods=["GET"])
@require_auth
def get_board():
    client_id = request.args.get("client")
    
    # In full SaaS mode, we query db.py instead of local files
    if db.get_supabase():
        # records = db.fetch_client_records(client_id, "kanban_board")
        pass
        
    # Fallback to local files for MVP Phase 1 testing
    out = board_scan.scan_board(str(ROOT), client_filter=client_id)
    return jsonify(out)

@app.route("/api/ti", methods=["GET"])
@require_auth
def get_ti():
    client_id = request.args.get("client")
    
    # In full SaaS mode, query db.py
    if db.get_supabase():
        pass
        
    out = mission_control.build_ti_view(str(ROOT), client_id)
    return jsonify(out)

@app.route("/api/mc", methods=["GET"])
@require_auth
def get_mc():
    client_id = request.args.get("client")
    out = mission_control.build_mc_view(str(ROOT), client_id)
    return jsonify(out)

@app.route("/api/create_content", methods=["POST"])
@require_auth
def create_content_endpoint():
    data = request.json
    client_id = data.get("client")
    task_id = data.get("task")
    topic = data.get("topic", "")
    slug = data.get("slug", "")
    target = data.get("target", "")

    # Import CREATORS from the local server config (for MVP reuse)
    from apps.kanban_board.server import CREATORS
    spec = CREATORS.get(task_id)
    if not spec:
        return jsonify({"error": f"unknown content task {task_id}"}), 400

    # Build the args list
    args = list(spec.get("args", []))
    if spec.get("input") and topic: args.extend([spec["input"], topic])
    if spec.get("slug") and slug: args.extend(["--slug", slug])
    if spec.get("target") and target: args.extend(["--target", target.strip()])

    # Import Celery task
    from lib.tasks import execute_playbook

    # Dispatch to Celery background worker
    task = execute_playbook.delay(client_id, spec["script"], args)
    
    return jsonify({
        "ok": True, 
        "task": spec["label"], 
        "output": f"Dispatched to Cloud Worker (Task ID: {task.id})"
    })

if __name__ == "__main__":
    app.run(port=8080)
