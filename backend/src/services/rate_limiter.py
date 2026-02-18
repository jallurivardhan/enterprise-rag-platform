"""Rate limiting service for API endpoints."""

from datetime import datetime, timedelta
from typing import Dict, List


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests_per_minute: int = 20):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, List[datetime]] = {}  # user_id -> list of timestamps

    def _clean_old_requests(self, user_id: str):
        """Remove requests older than 1 minute."""
        if user_id not in self.requests:
            return

        cutoff = datetime.now() - timedelta(minutes=1)
        self.requests[user_id] = [
            ts for ts in self.requests[user_id] if ts > cutoff
        ]

    def check_rate_limit(self, user_id: str) -> dict:
        """Check if user is within rate limit. Returns limit info."""
        self._clean_old_requests(user_id)

        current_requests = len(self.requests.get(user_id, []))
        remaining = max(0, self.requests_per_minute - current_requests)

        return {
            "limit": self.requests_per_minute,
            "remaining": remaining,
            "reset_in_seconds": 60
        }

    def is_allowed(self, user_id: str) -> bool:
        """Check if request is allowed."""
        self._clean_old_requests(user_id)

        if user_id not in self.requests:
            self.requests[user_id] = []

        if len(self.requests[user_id]) >= self.requests_per_minute:
            return False

        # Record this request
        self.requests[user_id].append(datetime.now())
        return True

    def get_wait_time(self, user_id: str) -> int:
        """Get seconds until rate limit resets."""
        if user_id not in self.requests or not self.requests[user_id]:
            return 0

        oldest = min(self.requests[user_id])
        reset_time = oldest + timedelta(minutes=1)
        wait = (reset_time - datetime.now()).total_seconds()
        return max(0, int(wait))


# Global instance
rate_limiter = RateLimiter(requests_per_minute=20)
