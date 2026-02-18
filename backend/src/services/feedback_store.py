"""User feedback storage for AI responses."""

from typing import Dict, List, Optional
from datetime import datetime
import json
import os


class FeedbackStore:
    """Store user feedback on AI responses."""
    
    def __init__(self, storage_path: str = "data/feedback.json"):
        self.storage_path = storage_path
        self.feedback: List[Dict] = []
        self._load()
    
    def _load(self):
        """Load feedback from file."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    self.feedback = json.load(f)
            except:
                self.feedback = []
    
    def _save(self):
        """Save feedback to file."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump(self.feedback, f, indent=2)
    
    def add_feedback(
        self, 
        query: str, 
        answer: str, 
        rating: str,  # "up" or "down"
        conversation_id: Optional[str] = None
    ) -> Dict:
        """Add feedback for a response."""
        entry = {
            "id": len(self.feedback) + 1,
            "query": query,
            "answer": answer[:500],  # Truncate for storage
            "rating": rating,
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat()
        }
        self.feedback.append(entry)
        self._save()
        return entry
    
    def get_stats(self) -> Dict:
        """Get feedback statistics."""
        total = len(self.feedback)
        positive = sum(1 for f in self.feedback if f["rating"] == "up")
        negative = sum(1 for f in self.feedback if f["rating"] == "down")
        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "satisfaction_rate": round(positive / total * 100, 1) if total > 0 else 0
        }
    
    def get_recent(self, limit: int = 20) -> List[Dict]:
        """Get recent feedback entries."""
        return self.feedback[-limit:][::-1]


# Global instance
feedback_store = FeedbackStore()
