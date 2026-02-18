"""User storage with password hashing."""

from typing import Dict, Optional, List
from datetime import datetime
import json
import os
from pathlib import Path

import bcrypt


class UserStore:
    """Simple user storage with password hashing."""

    def __init__(self, storage_path: str = "data/users.json"):
        self.storage_path = Path(storage_path)
        self.users: List[Dict] = []
        self._load()

    def _load(self):
        """Load users from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    self.users = json.load(f)
            except Exception:
                self.users = []

    def _save(self):
        """Save users to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(self.users, f, indent=2)

    def create_user(self, username: str, email: str, password: str, role: str = "user") -> Optional[Dict]:
        """Create a new user with role."""
        # Check if user exists
        if self.get_user_by_email(email):
            return None
        if self.get_user_by_username(username):
            return None

        # Hash password using bcrypt directly
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

        user = {
            "id": f"user_{len(self.users) + 1}",
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "role": role,  # "admin" or "user"
            "created_at": datetime.now().isoformat(),
        }
        self.users.append(user)
        self._save()
        return {k: v for k, v in user.items() if k != "password_hash"}

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email."""
        for user in self.users:
            if user["email"] == email:
                return user
        return None

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username."""
        for user in self.users:
            if user["username"] == username:
                return user
        return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID."""
        for user in self.users:
            if user["id"] == user_id:
                return user
        return None

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )

    def authenticate(self, email: str, password: str) -> Optional[Dict]:
        """Authenticate user and return user dict (without password)."""
        user = self.get_user_by_email(email)
        if not user:
            return None
        if not self.verify_password(password, user["password_hash"]):
            return None
        return {k: v for k, v in user.items() if k != "password_hash"}


user_store = UserStore()
