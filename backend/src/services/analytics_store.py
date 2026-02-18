"""Usage analytics tracking and storage."""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import Counter
import json
import os


class AnalyticsStore:
    """Track and store usage analytics."""
    
    def __init__(self, storage_path: str = "data/analytics.json"):
        self.storage_path = storage_path
        self.queries: List[Dict] = []
        self._load()
    
    def _load(self):
        """Load analytics data from file."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    self.queries = json.load(f)
            except:
                self.queries = []
    
    def _save(self):
        """Save analytics data to file."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump(self.queries, f, indent=2)
    
    def log_query(
        self,
        query: str,
        response_time_ms: float,
        sources_count: int,
        conversation_id: Optional[str] = None
    ):
        """Log a query for analytics."""
        entry = {
            "query": query,
            "response_time_ms": response_time_ms,
            "sources_count": sources_count,
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat()
        }
        self.queries.append(entry)
        self._save()
    
    def get_stats(self) -> Dict:
        """Get overall statistics."""
        if not self.queries:
            return {
                "total_queries": 0,
                "avg_response_time_ms": 0,
                "queries_today": 0,
                "queries_this_week": 0,
                "avg_sources_per_query": 0
            }
        
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        
        queries_today = sum(1 for q in self.queries 
                          if datetime.fromisoformat(q["timestamp"]) >= today)
        queries_this_week = sum(1 for q in self.queries 
                               if datetime.fromisoformat(q["timestamp"]) >= week_ago)
        
        avg_response = sum(q["response_time_ms"] for q in self.queries) / len(self.queries)
        avg_sources = sum(q["sources_count"] for q in self.queries) / len(self.queries)
        
        return {
            "total_queries": len(self.queries),
            "avg_response_time_ms": round(avg_response, 2),
            "queries_today": queries_today,
            "queries_this_week": queries_this_week,
            "avg_sources_per_query": round(avg_sources, 1)
        }
    
    def get_popular_queries(self, limit: int = 10) -> List[Dict]:
        """Get most common query patterns."""
        # Simple word frequency
        all_words = []
        for q in self.queries:
            words = q["query"].lower().split()
            all_words.extend([w for w in words if len(w) > 3])
        
        word_counts = Counter(all_words).most_common(limit)
        return [{"word": w, "count": c} for w, c in word_counts]
    
    def get_recent_queries(self, limit: int = 20) -> List[Dict]:
        """Get recent queries."""
        return self.queries[-limit:][::-1]
    
    def get_hourly_distribution(self) -> List[Dict]:
        """Get query distribution by hour."""
        hours = Counter()
        for q in self.queries:
            hour = datetime.fromisoformat(q["timestamp"]).hour
            hours[hour] += 1
        
        return [{"hour": h, "count": hours.get(h, 0)} for h in range(24)]


# Global instance
analytics_store = AnalyticsStore()
