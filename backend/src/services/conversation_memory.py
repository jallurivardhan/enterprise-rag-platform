"""Conversation memory management for context-aware RAG responses."""

from typing import List, Dict, Optional
from datetime import datetime
import uuid


class ConversationMemory:
    """Manages conversation history for context-aware responses."""
    
    def __init__(self, max_history: int = 10):
        self.conversations: Dict[str, List[Dict]] = {}
        self.max_history = max_history
    
    def create_conversation(self) -> str:
        """Create a new conversation and return its ID."""
        conv_id = str(uuid.uuid4())
        self.conversations[conv_id] = []
        return conv_id
    
    def add_message(self, conversation_id: str, role: str, content: str, sources: List = None):
        """Add a message to conversation history."""
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        
        self.conversations[conversation_id].append({
            "role": role,  # "user" or "assistant"
            "content": content,
            "sources": sources or [],
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last N messages
        if len(self.conversations[conversation_id]) > self.max_history:
            self.conversations[conversation_id] = self.conversations[conversation_id][-self.max_history:]
    
    def get_history(self, conversation_id: str) -> List[Dict]:
        """Get conversation history."""
        return self.conversations.get(conversation_id, [])
    
    def get_context_string(self, conversation_id: str) -> str:
        """Format history as context string for the LLM."""
        history = self.get_history(conversation_id)
        if not history:
            return ""
        
        context_parts = []
        for msg in history[-6:]:  # Last 6 messages (3 exchanges)
            role = "User" if msg["role"] == "user" else "Assistant"
            context_parts.append(f"{role}: {msg['content']}")
        
        return "\n".join(context_parts)
    
    def clear_conversation(self, conversation_id: str):
        """Clear a conversation."""
        if conversation_id in self.conversations:
            self.conversations[conversation_id] = []


# Global instance
conversation_memory = ConversationMemory()
