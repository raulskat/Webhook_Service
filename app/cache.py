import redis
import json
from typing import Optional, Dict, Any, Union
import os
from dotenv import load_dotenv
from app.models import Subscription

load_dotenv()

# Redis configuration - Use service name in Docker, fallback to localhost for local development
REDIS_HOST = os.getenv("REDIS_HOST", "redis")  # Changed from localhost to redis
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")

# Create Redis client
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=int(REDIS_PORT),
    db=int(REDIS_DB),
    decode_responses=True
)

# Cache keys
SUBSCRIPTION_KEY = "subscription:{id}"
SUBSCRIPTION_TTL = 3600  # 1 hour in seconds

def cache_subscription(subscription: Union[Subscription, Dict[str, Any]]) -> None:
    """Cache subscription details in Redis"""
    if isinstance(subscription, Subscription):
        data = {
            "target_url": subscription.target_url,
            "secret": subscription.secret,
            "event_types": subscription.event_types,
            "is_active": subscription.is_active
        }
    else:
        data = subscription
    
    key = SUBSCRIPTION_KEY.format(id=subscription.id if isinstance(subscription, Subscription) else subscription["id"])
    redis_client.setex(
        key,
        SUBSCRIPTION_TTL,
        json.dumps(data)
    )

def get_cached_subscription(subscription_id: int) -> Optional[Dict[str, Any]]:
    """Get subscription details from cache"""
    key = SUBSCRIPTION_KEY.format(id=subscription_id)
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None

def invalidate_subscription_cache(subscription_id: int) -> None:
    """Remove subscription from cache"""
    key = SUBSCRIPTION_KEY.format(id=subscription_id)
    redis_client.delete(key)

def clear_all_cache() -> None:
    """Clear all cached data (useful for testing)"""
    redis_client.flushdb() 