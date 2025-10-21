from typing import List, Dict, Optional
from src.config.memory_config import get_memory_instance
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

class MemoryManager:
    """Manages long-term memory for the multi-agent system using mem0."""
    
    def __init__(self, user_id: str = "default_user"):
        self.memory = get_memory_instance()
        self.user_id = user_id
    
    def add_memory(self, content: str, metadata: Optional[Dict] = None) -> Dict:
        """
        Add a new memory.
        
        Args:
            content: The memory content to store
            metadata: Optional metadata (e.g., agent_name, category, timestamp)
        
        Returns:
            Dict with memory_id and other details
        """
        messages = [{"role": "user", "content": content}]
        result = self.memory.add(messages, user_id=self.user_id, metadata=metadata)
        return result
    
    def add_from_conversation(self, messages: List[BaseMessage], agent_name: str = None) -> Dict:
        """
        Extract and store memories from a conversation.
        
        Args:
            messages: List of conversation messages
            agent_name: Name of the agent handling the conversation
        
        Returns:
            Dict with stored memory details
        """
        # Convert LangChain messages to mem0 format
        mem0_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                mem0_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                mem0_messages.append({"role": "assistant", "content": msg.content})
        
        metadata = {"agent": agent_name} if agent_name else {}
        result = self.memory.add(mem0_messages, user_id=self.user_id, metadata=metadata)
        return result
    
    def search_memory(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search for relevant memories based on a query.
        
        Args:
            query: Search query
            limit: Maximum number of results
        
        Returns:
            List of relevant memories
        """
        results = self.memory.search(query, user_id=self.user_id, limit=limit)
        return results
    
    def get_all_memories(self) -> List[Dict]:
        """Retrieve all memories for the user."""
        return self.memory.get_all(user_id=self.user_id)
    
    def update_memory(self, memory_id: str, content: str) -> Dict:
        """
        Update an existing memory.
        
        Args:
            memory_id: ID of the memory to update
            content: New content
        
        Returns:
            Updated memory details
        """
        result = self.memory.update(memory_id, data=content)
        return result
    
    def delete_memory(self, memory_id: str) -> Dict:
        """Delete a specific memory."""
        result = self.memory.delete(memory_id)
        return result
    
    def get_relevant_context(self, query: str, limit: int = 3) -> str:
        """
        Get relevant context as a formatted string for prompt injection.
        
        Args:
            query: Current user query
            limit: Number of memories to retrieve
        
        Returns:
            Formatted string with relevant memories
        """
        memories = self.search_memory(query, limit=limit)
        
        if not memories:
            return ""
        
        context_parts = ["=== Relevant Memories ==="]
        for i, mem in enumerate(memories, 1):
            content = mem.get('memory', mem.get('text', ''))
            metadata = mem.get('metadata', {})
            context_parts.append(f"{i}. {content}")
            if metadata:
                context_parts.append(f"   Context: {metadata}")
        
        context_parts.append("=== End Memories ===\n")
        return "\n".join(context_parts)
    
    def reset_memory(self) -> Dict:
        """Delete all memories for the user. Use with caution!"""
        return self.memory.reset(user_id=self.user_id)


# Singleton instance
_memory_manager_instance = None

def get_memory_manager(user_id: str = "default_user") -> MemoryManager:
    """Get or create a MemoryManager instance."""
    global _memory_manager_instance
    if _memory_manager_instance is None:
        _memory_manager_instance = MemoryManager(user_id)
    return _memory_manager_instance