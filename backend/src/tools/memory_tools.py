from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import List, Optional
from src.utils.memory_manager import get_memory_manager

class SearchMemoryInput(BaseModel):
    query: str = Field(..., description="Search query to find relevant memories")
    limit: int = Field(default=5, description="Maximum number of memories to retrieve")

class AddMemoryInput(BaseModel):
    content: str = Field(..., description="The memory content to store, it should be detailed and specific and useful for future interactions and personalization.")
    category: Optional[str] = Field(None, description="Chose Category like: 'preferences', 'contacts', 'scheduling', 'tasks', 'facts'")
    importance: Optional[str] = Field(None, description="Importance level: 'high', 'medium', 'low'")

class UpdateMemoryInput(BaseModel):
    memory_id: str = Field(..., description="ID of the memory to update")
    new_content: str = Field(..., description="Updated content")

class DeleteMemoryInput(BaseModel):
    memory_id: str = Field(..., description="ID of the memory to delete")


@tool("search_memory", args_schema=SearchMemoryInput)
def search_memory(query: str, limit: int = 5, more :bool = True ) -> str:
    """
    Search for relevant memories based on a query.
    Use this when you need to recall information from past conversations,
    user preferences, or any stored context that might be relevant to the current task.
    
    Returns a formatted string with the most relevant memories found.
    """
    try:
        memory_manager = get_memory_manager()
        results = memory_manager.search_memory(query, limit=limit)
        
        # Extract results list from the wrapper dict
        if isinstance(results, dict) and 'results' in results:
            memories = results['results']
        elif isinstance(results, list):
            memories = results
        else:
            return f"Unexpected result format: {type(results)}"
        
        if not memories:
            return "No relevant memories found."
        
        output = ["Found relevant memories:\n"]
        
        for i, mem in enumerate(memories, 1):
            memory_text = mem.get('memory', 'N/A')
            memory_id = mem.get('id', 'N/A')
            metadata = mem.get('metadata', {})
            score = mem.get('score', 'N/A')
            created_at = mem.get('created_at', 'N/A')
            if more:
                output.append(f"{i}. {memory_text}")
                output.append(f"   ID: {memory_id}")
                output.append(f"   Score: {score:.4f}" if isinstance(score, (int, float)) else f"   Score: {score}")
                
                if metadata:
                    category = metadata.get('category', 'N/A')
                    importance = metadata.get('importance', 'N/A')
                    output.append(f"   Category: {category}, Importance: {importance}")
                
                output.append(f"   Created: {created_at}")
                output.append("")
            else:
                output.append(f"{i}. {memory_text}")
                if metadata:
                    category = metadata.get('category', 'N/A')
                    importance = metadata.get('importance', 'N/A')
                    output.append(f"   Category: {category}, Importance: {importance}")
            
        return "\n".join(output)
    
    except Exception as e:
        import traceback
        return f"Error searching memories: {str(e)}\n{traceback.format_exc()}"


@tool("add_memory", args_schema=AddMemoryInput)
def add_memory(content: str, category: Optional[str] = None, importance: Optional[str] = None) -> str:
    """
    Store important information in long-term memory.
    Use this to save:
    - User preferences (email tone, meeting times, communication style)
    - Important facts about contacts (how to address them, their preferences)
    - Recurring patterns (typical workflows, common requests)
    - Key decisions or outcomes
    
    Only store information that would be useful to recall in future conversations.
    Don't store temporary or one-time information.
    """
    try:
        memory_manager = get_memory_manager()
        
        metadata = {}
        if category:
            metadata['category'] = category
        if importance:
            metadata['importance'] = importance
        
        result = memory_manager.add_memory(content, metadata=metadata if metadata else None)
        
        # Try multiple ways to extract the memory ID
        memory_id = 'unknown'
        
        if isinstance(result, dict):
            # Check for 'results' wrapper with list
            if 'results' in result and isinstance(result['results'], list) and result['results']:
                memory_id = result['results'][0].get('id', 'unknown')
            # Check for direct 'id' field
            elif 'id' in result:
                memory_id = result.get('id')
            # Check for 'memory_id' field
            elif 'memory_id' in result:
                memory_id = result.get('memory_id')
        elif isinstance(result, str):
            # If it's a string ID
            memory_id = result
        
        return f"✓ Memory stored successfully!\n   ID: {memory_id}\n   Content: {content[:80]}..."
    
    except Exception as e:
        import traceback
        return f"✗ Error storing memory: {str(e)}\n{traceback.format_exc()}"


@tool("get_all_memories", args_schema=None)
def get_all_memories() -> str:
    """
    Retrieve all stored memories for the current user.
    Use this sparingly, only when you need to see everything that's been stored.
    For most cases, use search_memory instead.
    """
    try:
        memory_manager = get_memory_manager()
        result = memory_manager.get_all_memories()
        
        # Extract memories list from the wrapper dict
        if isinstance(result, dict) and 'results' in result:
            memories = result['results']
        elif isinstance(result, list):
            memories = result
        else:
            return f"Unexpected result format: {type(result)}"
        
        if not memories:
            return "No memories stored yet."
        
        output = [f"📊 Total memories: {len(memories)}\n"]
        
        # Display first 10 memories
        display_count = min(10, len(memories))
        for i in range(display_count):
            mem = memories[i]
            memory_text = mem.get('memory', str(mem))
            memory_id = mem.get('id', 'N/A')
            metadata = mem.get('metadata', {})
            
            # Truncate long memories
            if len(memory_text) > 80:
                display_text = memory_text[:80] + "..."
            else:
                display_text = memory_text
            
            output.append(f"{i+1}. {display_text}")
            output.append(f"   ID: {memory_id}")
            
            if metadata:
                category = metadata.get('category', 'N/A')
                importance = metadata.get('importance', 'N/A')
                output.append(f"   📁 {category} | ⭐ {importance}")
            
            output.append("")
        
        if len(memories) > 10:
            output.append(f"... and {len(memories) - 10} more memories")
        
        return "\n".join(output)
    
    except Exception as e:
        import traceback
        return f"Error retrieving memories: {str(e)}\n{traceback.format_exc()}"


@tool("update_memory", args_schema=UpdateMemoryInput)
def update_memory(memory_id: str, new_content: str) -> str:
    """
    Update an existing memory with new information.
    Use this when information changes or needs to be refined.
    """
    try:
        memory_manager = get_memory_manager()
        result = memory_manager.update_memory(memory_id, new_content)
        return f"✓ Memory updated successfully!\n   ID: {memory_id}\n   New content: {new_content[:80]}..."
    
    except Exception as e:
        import traceback
        return f"✗ Error updating memory: {str(e)}\n{traceback.format_exc()}"


@tool("delete_memory", args_schema=DeleteMemoryInput)
def delete_memory(memory_id: str) -> str:
    """
    Delete a specific memory.
    Use this when information is no longer relevant or was stored incorrectly.
    """
    try:
        memory_manager = get_memory_manager()
        result = memory_manager.delete_memory(memory_id)
        return f"✓ Memory deleted successfully! (ID: {memory_id})"
    
    except Exception as e:
        import traceback
        return f"✗ Error deleting memory: {str(e)}\n{traceback.format_exc()}"


# Export all memory tools
MEMORY_TOOLS = [
    search_memory,
    add_memory,
    get_all_memories,
    update_memory,
    delete_memory
]


# Enhanced test function
if __name__ == "__main__":
    import time
    
    print("=" * 70)
    print(" " * 20 + "MEMORY TOOLS TEST")
    print("=" * 70)
    
    # Test 1: Add memories
    print("\n📝 TEST 1: Adding memories...")
    print("-" * 70)
    
    test_memories = [
        {
            "content": "User prefers emails in a casual and friendly tone",
            "category": "preferences",
            "importance": "high"
        },
        {
            "content": "Sarah Chen is the Product Manager, prefers detailed updates",
            "category": "contacts",
            "importance": "high"
        },
        {
            "content": "Sprint planning meetings every other Friday at 2 PM",
            "category": "scheduling",
            "importance": "medium"
        }
    ]
    
    added_ids = []
    for mem_data in test_memories:
        result = add_memory.invoke(mem_data)
        print(result)
        time.sleep(0.3)
    
    # Test 2: Get all memories
    print("\n📚 TEST 2: Retrieving all memories...")
    print("-" * 70)
    all_memories_result = get_all_memories.invoke({})
    print(all_memories_result)
    
    # Test 3: Search memories
    print("\n🔍 TEST 3: Searching memories...")
    print("-" * 70)
    
    search_queries = [
        ("email preferences", 2),
        ("Product Manager", 2),
        ("meetings Friday", 2)
    ]
    
    for query, limit in search_queries:
        print(f"\n→ Searching for '{query}':")
        result = search_memory.invoke({"query": query, "limit": limit})
        print(result)
        time.sleep(0.3)
    
    # Test 4: Update memory (interactive)
    print("\n✏️  TEST 4: Update memory...")
    print("-" * 70)
    print("To test update, uncomment the code below and use a real memory ID:")
    print("Example:")
    print("  update_result = update_memory.invoke({")
    print("      'memory_id': '24afdf12-d0ed-416e-8bb8-b48b74e7db63',")
    print("      'new_content': 'User STRONGLY prefers casual, friendly emails'")
    print("  })")
    
    # Uncomment to test with a real ID:
    # update_result = update_memory.invoke({
    #     "memory_id": "YOUR_MEMORY_ID_HERE",
    #     "new_content": "Updated content here"
    # })
    # print(update_result)
    
    # Test 5: Delete memory (interactive)
    print("\n🗑️  TEST 5: Delete memory...")
    print("-" * 70)
    print("To test delete, uncomment the code below and use a real memory ID:")
    print("Example:")
    print("  delete_result = delete_memory.invoke({")
    print("      'memory_id': 'f74f0453-082c-41e8-8298-fc7e04f6b11d'")
    print("  })")
    
    # Uncomment to test with a real ID:
    # delete_result = delete_memory.invoke({
    #     "memory_id": "YOUR_MEMORY_ID_HERE"
    # })
    # print(delete_result)
    
    print("\n" + "=" * 70)
    print(" " * 25 + "✓ TEST COMPLETED")
    print("=" * 70)
    print("\n💡 Tips:")
    print("  • Use search_memory for most queries (faster than get_all)")
    print("  • Lower scores = better match in search results")
    print("  • Copy a memory ID from the output to test update/delete")