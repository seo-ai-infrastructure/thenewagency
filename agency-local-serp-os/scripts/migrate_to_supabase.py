import os
import sys
import json
import pathlib
from dotenv import load_dotenv

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from lib import db

def migrate():
    load_dotenv()
    supabase = db.get_supabase()
    if not supabase:
        print("Error: Supabase is not connected. Make sure SUPABASE_URL and SUPABASE_KEY are in .env")
        return

    client_id = "example-hvac-client"
    
    print(f"Migrating client '{client_id}'...")
    # Insert client
    try:
        supabase.table("clients").insert({"id": client_id, "name": "Example HVAC Client"}).execute()
        print("Created client record.")
    except Exception as e:
        print("Client likely exists already.")

    print("Uploading work orders...")
    client_dir = ROOT / "clients" / client_id
    for area in ["web", "browser", "rpa"]:
        pending_dir = client_dir / area / "approvals" / "pending"
        if pending_dir.exists():
            for f in pending_dir.glob("*.json"):
                payload = json.loads(f.read_text(encoding="utf-8"))
                # Remove ID from payload to avoid duplication, or keep it
                subsystem = payload.get("subsystem", "unknown")
                status = payload.get("status", "pending_human_review")
                kind = payload.get("kind", "unknown")
                
                try:
                    supabase.table("work_orders").insert({
                        "client_id": client_id,
                        "area": area,
                        "subsystem": subsystem,
                        "status": status,
                        "kind": kind,
                        "payload": payload
                    }).execute()
                    print(f"  Uploaded {f.name}")
                except Exception as e:
                    print(f"  Error uploading {f.name}: {e}")

    print("Migration complete!")

if __name__ == "__main__":
    migrate()
