# src/config/memory_config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from functools import lru_cache
from mem0 import Memory

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # adjust if needed
CHROMA_DB_PATH = PROJECT_ROOT / "chroma_db"

config = {
    "llm": {
        "provider": "openai",
        "config": {
            "model": "gpt-4o-mini",
            "temperature": 0,
            "api_key": os.getenv("OPENAI_API_KEY"),
        }
    },
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": "personal_agent_memory",
            "path": str(CHROMA_DB_PATH),
        }
    }
}

@lru_cache(maxsize=1)
def get_memory_instance() -> Memory:
    # Only runs once per PROCESS
    CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
    print(f"📁 ChromaDB will be stored at: {CHROMA_DB_PATH.absolute()}")
    print("🔄 Initializing Memory (mem0 + ChromaDB)...")
    mem = Memory.from_config(config)
    print("✅ Memory initialized!")
    return mem
