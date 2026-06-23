import os
from unittest.mock import MagicMock

# Set dummy environment variables to pass the import-time validation check
os.environ["SUPABASE_URL"] = "https://dummy-supabase-url.supabase.co"
os.environ["SUPABASE_KEY"] = "dummy-key"

# Mock the supabase library's create_client function to prevent it from validating keys or connecting
import supabase
supabase.create_client = MagicMock()
