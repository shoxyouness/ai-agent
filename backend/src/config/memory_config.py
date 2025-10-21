import os
from pathlib import Path
from dotenv import load_dotenv
from mem0 import Memory

load_dotenv()

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
CHROMA_DB_PATH = PROJECT_ROOT / "chroma_db"

# Ensure the directory exists
CHROMA_DB_PATH.mkdir(exist_ok=True)

print(f"📁 ChromaDB will be stored at: {CHROMA_DB_PATH.absolute()}")

# Configure mem0 with ChromaDB
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
            "path": str(CHROMA_DB_PATH),  # Absolute path
        }
    }
}

# Initialize memory instance
_memory_instance = None

def get_memory_instance():
    """Returns the configured memory instance (singleton)."""
    global _memory_instance
    
    if _memory_instance is None:
        print("🔄 Initializing Memory Manager with ChromaDB...")
        _memory_instance = Memory.from_config(config)
        print(f"✅ Memory Manager initialized! DB path: {CHROMA_DB_PATH}")
    
    return _memory_instance