"""State management for tracking active sessions and generations."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict

from app.config import Settings

# Active streaming generations counter
_active_generations = 0
_generations_lock = asyncio.Lock()

# RLM-specific generation tracking
_active_rlm_generations = 0
_rlm_lock = asyncio.Lock()

# Page load tracking for session counting (session_id: timestamp)
_page_loads: Dict[str, datetime] = {}
_page_loads_lock = asyncio.Lock()


class StateManager:
    """Manages application state including sessions and active generations."""
    
    @staticmethod
    async def increment_generations():
        """Increment active generations counter."""
        global _active_generations
        async with _generations_lock:
            _active_generations += 1
    
    @staticmethod
    async def decrement_generations():
        """Decrement active generations counter."""
        global _active_generations
        async with _generations_lock:
            _active_generations -= 1
    
    @staticmethod
    async def get_active_generations() -> int:
        """Get current active generations count."""
        return _active_generations
    
    @staticmethod
    async def increment_rlm_generations():
        """Increment active RLM generations counter."""
        global _active_rlm_generations
        async with _rlm_lock:
            _active_rlm_generations += 1
    
    @staticmethod
    async def decrement_rlm_generations():
        """Decrement active RLM generations counter."""
        global _active_rlm_generations
        async with _rlm_lock:
            _active_rlm_generations -= 1
    
    @staticmethod
    async def get_active_rlm_generations() -> int:
        """Get current active RLM generations count."""
        return _active_rlm_generations
    
    @staticmethod
    async def check_rlm_capacity() -> bool:
        """Check if we can accept another RLM request."""
        async with _rlm_lock:
            return _active_rlm_generations < Settings.MAX_CONCURRENT_RLM
    
    @staticmethod
    async def track_session(session_id: str):
        """Track a session by its ID."""
        async with _page_loads_lock:
            _page_loads[session_id] = datetime.now()
    
    @staticmethod
    async def get_active_sessions() -> int:
        """Get count of active sessions (within timeout period)."""
        now = datetime.now()
        cutoff = now - timedelta(minutes=Settings.SESSION_TIMEOUT_MINUTES)
        
        async with _page_loads_lock:
            # Remove expired sessions
            expired_sessions = [
                sid for sid, ts in _page_loads.items() 
                if ts < cutoff
            ]
            for sid in expired_sessions:
                del _page_loads[sid]
            
            return len(_page_loads)
