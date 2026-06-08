import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

_client = None

def get_supabase() -> Client:
    global _client
    if not _client and SUPABASE_URL and SUPABASE_KEY:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client

def fetch_client_records(client_id: str, table: str):
    """Fetch records from a Supabase table for a specific client."""
    db = get_supabase()
    if db:
        response = db.table(table).select("*").eq("client_id", client_id).execute()
        return response.data
    else:
        # Fallback to local file system for now until keys are provided
        print("WARNING: Supabase not configured. Using local fallback.")
        return []

def insert_record(table: str, data: dict):
    """Insert a record into Supabase."""
    db = get_supabase()
    if db:
        return db.table(table).insert(data).execute()
    return None
