import sqlite3
import json
from typing import List, Dict, Any
import datetime
from pathlib import Path

# DB file path
DB_PATH = Path("chat_history.db")

def create_db_and_tables():
    """Initialize the database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Enable WAL mode for better concurrency
    cursor.execute("PRAGMA journal_mode=WAL;")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized at {DB_PATH.absolute()}")

def add_message(thread_id: str, role: str, content: str):
    """Add a new message to the history."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO messages (thread_id, role, content)
        VALUES (?, ?, ?)
        """, (thread_id, role, content))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Error adding message to DB: {e}")

def get_messages(thread_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get the last N messages for a thread."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row # Access columns by name
        cursor = conn.cursor()
        
        # Get last N messages (ordered by creation time descending, then reverse them)
        cursor.execute("""
        SELECT role, content, created_at 
        FROM messages 
        WHERE thread_id = ? 
        ORDER BY created_at DESC 
        LIMIT ?
        """, (thread_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Reverse to get chronological order
        messages = [dict(row) for row in rows]
        return messages[::-1]
    except Exception as e:
        print(f"❌ Error getting messages from DB: {e}")
        return []
