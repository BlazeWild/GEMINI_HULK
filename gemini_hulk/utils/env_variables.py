from dotenv import load_dotenv
import os
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL",None)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", None)
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", None)
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", None)
DATABASE_URI = os.getenv("DATABASE_URI", None)

print("SUPABASE_URL", SUPABASE_URL)
print("GOOGLE_API_KEY", GOOGLE_API_KEY)
print("LANGSMITH_API_KEY", LANGSMITH_API_KEY)
print("TOGETHER_API_KEY", TOGETHER_API_KEY)
print("DATABASE_URI", DATABASE_URI)