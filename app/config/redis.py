"""Redis client configuration."""
import os
from typing import Optional

from dotenv import load_dotenv
from redis import Redis
from redis.connection import ConnectionPool

# Load environment variables
load_dotenv()

# Get REDIS_URL from environment
REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise ValueError("REDIS_URL environment variable is not set")

# Create connection pool
_connection_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None


def get_redis() -> Redis:
    """
    Get or create Redis client instance.
    
    Returns:
        Redis: Redis client instance
    """
    global _redis_client, _connection_pool
    
    if _redis_client is None:
        _connection_pool = ConnectionPool.from_url(
            REDIS_URL,
            decode_responses=True,  # Automatically decode responses to strings
        )
        _redis_client = Redis(connection_pool=_connection_pool)
    
    return _redis_client
