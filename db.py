import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_url = os.getenv("SUPABASE_URL", "")
_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not _url:
    raise RuntimeError("SUPABASE_URL is not set. Add it to your .env file.")
if not _key:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not set. Add it to your .env file.")

supabase: Client = create_client(_url, _key)
