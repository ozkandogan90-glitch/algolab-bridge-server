"""
Session Management for Bridge Server
Stores Algolab authentication sessions in Redis
"""

import json
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import redis.asyncio as redis
from pydantic import BaseModel


class AlgolabSession(BaseModel):
    """Algolab session data"""
    session_id: str
    api_key: str
    hash: str  # JWT token from Algolab
    token: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    last_refreshed_at: Optional[datetime] = None


class SessionManager:
    """
    Manages Algolab sessions in Redis

    Session lifecycle:
    1. User logs in → create session
    2. Session stored with TTL
    3. Auto-refresh before expiration
    4. Session deleted on logout or expiration
    """

    def __init__(self, redis_url: str, ttl_seconds: int = 3600):
        """
        Initialize session manager

        Args:
            redis_url: Redis connection URL
            ttl_seconds: Session TTL in seconds (default 1 hour)
        """
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self.redis_client: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis"""
        self.redis_client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()

    def _make_key(self, session_id: str) -> str:
        """Generate Redis key for session"""
        return f"algolab_session:{session_id}"

    async def create_session(
        self,
        api_key: str,
        hash: str,
        token: Optional[str] = None
    ) -> AlgolabSession:
        """
        Create new session

        Args:
            api_key: User's Algolab API key
            hash: JWT authentication hash from Algolab
            token: Optional token from Algolab

        Returns:
            Created session object
        """
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        session = AlgolabSession(
            session_id=session_id,
            api_key=api_key,
            hash=hash,
            token=token,
            created_at=now,
            expires_at=now + timedelta(seconds=self.ttl_seconds)
        )

        # Store in Redis
        key = self._make_key(session_id)
        await self.redis_client.setex(
            key,
            self.ttl_seconds,
            session.model_dump_json()
        )

        return session

    async def get_session(self, session_id: str) -> Optional[AlgolabSession]:
        """
        Retrieve session by ID

        Args:
            session_id: Session ID

        Returns:
            Session object or None if not found/expired
        """
        key = self._make_key(session_id)
        data = await self.redis_client.get(key)

        if not data:
            return None

        try:
            session = AlgolabSession.model_validate_json(data)
            return session
        except Exception:
            # Invalid session data, delete it
            await self.delete_session(session_id)
            return None

    async def update_session(
        self,
        session_id: str,
        hash: Optional[str] = None,
        token: Optional[str] = None,
        extend_ttl: bool = True
    ) -> Optional[AlgolabSession]:
        """
        Update existing session

        Args:
            session_id: Session ID
            hash: New hash (if refreshed)
            token: New token (if refreshed)
            extend_ttl: Whether to extend TTL

        Returns:
            Updated session or None if not found
        """
        session = await self.get_session(session_id)
        if not session:
            return None

        # Update fields
        if hash:
            session.hash = hash
        if token:
            session.token = token

        session.last_refreshed_at = datetime.utcnow()

        if extend_ttl:
            session.expires_at = datetime.utcnow() + timedelta(seconds=self.ttl_seconds)

        # Save to Redis
        key = self._make_key(session_id)
        ttl = self.ttl_seconds if extend_ttl else await self.redis_client.ttl(key)

        await self.redis_client.setex(
            key,
            max(ttl, 60),  # At least 60 seconds
            session.model_dump_json()
        )

        return session

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete session

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        key = self._make_key(session_id)
        result = await self.redis_client.delete(key)
        return result > 0

    async def list_sessions(self, pattern: str = "*") -> list[str]:
        """
        List all session IDs matching pattern

        Args:
            pattern: Redis key pattern

        Returns:
            List of session IDs
        """
        keys = await self.redis_client.keys(f"algolab_session:{pattern}")
        return [key.split(":", 1)[1] for key in keys]

    async def get_session_ttl(self, session_id: str) -> Optional[int]:
        """
        Get remaining TTL for session

        Args:
            session_id: Session ID

        Returns:
            Remaining seconds or None if not found
        """
        key = self._make_key(session_id)
        ttl = await self.redis_client.ttl(key)

        if ttl < 0:  # Key doesn't exist or has no TTL
            return None

        return ttl

    async def health_check(self) -> bool:
        """
        Check Redis connection health

        Returns:
            True if healthy, False otherwise
        """
        try:
            await self.redis_client.ping()
            return True
        except Exception:
            return False


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test_session_manager():
        """Test session manager"""
        manager = SessionManager("redis://localhost:6379/0", ttl_seconds=60)

        try:
            await manager.connect()
            print("Connected to Redis")

            # Create session
            session = await manager.create_session(
                api_key="APIKEY-xyz==",
                hash="test_hash_jwt_token"
            )
            print(f"Created session: {session.session_id}")

            # Retrieve session
            retrieved = await manager.get_session(session.session_id)
            print(f"Retrieved: {retrieved}")

            # Check TTL
            ttl = await manager.get_session_ttl(session.session_id)
            print(f"TTL: {ttl} seconds")

            # Update session
            updated = await manager.update_session(
                session.session_id,
                hash="new_hash_after_refresh"
            )
            print(f"Updated: {updated.hash}")

            # Delete session
            deleted = await manager.delete_session(session.session_id)
            print(f"Deleted: {deleted}")

        finally:
            await manager.close()

    asyncio.run(test_session_manager())
