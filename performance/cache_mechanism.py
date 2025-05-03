"""
Cache Mechanism Module for StopSale Automation System

This module implements a Redis-based caching system to optimize performance
by caching frequently accessed data and API results.
"""

import json
import logging
import time
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from functools import wraps

# Set up logging
logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not installed. Caching will use in-memory fallback.")


class CacheManager:
    """Class for managing cache operations"""
    
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0, 
                 redis_password=None, prefix='stopsale:', ttl=3600):
        """
        Initialize the cache manager
        
        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
            redis_db: Redis database number
            redis_password: Redis password (if required)
            prefix: Key prefix for all cache entries
            ttl: Default time-to-live for cache entries in seconds
        """
        self.prefix = prefix
        self.default_ttl = ttl
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
        
        # Initialize Redis connection if available
        if REDIS_AVAILABLE:
            try:
                self.redis = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password=redis_password,
                    decode_responses=True  # Automatically decode responses to strings
                )
                self.redis.ping()  # Test connection
                self.backend = 'redis'
                logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                self.backend = 'memory'
                self.memory_cache = {}
        else:
            self.backend = 'memory'
            self.memory_cache = {}
            logger.info("Using in-memory cache backend")
    
    def _get_full_key(self, key: str) -> str:
        """
        Get the full cache key with prefix
        
        Args:
            key: The base key
            
        Returns:
            str: The full key with prefix
        """
        return f"{self.prefix}{key}"
    
    def get(self, key: str) -> Any:
        """
        Get a value from the cache
        
        Args:
            key: The cache key
            
        Returns:
            Any: The cached value, or None if not found
        """
        full_key = self._get_full_key(key)
        
        try:
            if self.backend == 'redis':
                value = self.redis.get(full_key)
                if value is not None:
                    self.stats["hits"] += 1
                    return json.loads(value)
                else:
                    self.stats["misses"] += 1
                    return None
            else:
                # Memory backend
                if full_key in self.memory_cache:
                    entry = self.memory_cache[full_key]
                    # Check if entry is expired
                    if entry["expires"] > time.time() or entry["expires"] == -1:
                        self.stats["hits"] += 1
                        return entry["value"]
                    else:
                        # Remove expired entry
                        del self.memory_cache[full_key]
                
                self.stats["misses"] += 1
                return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {str(e)}")
            self.stats["errors"] += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in the cache
        
        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds (uses default if None)
            
        Returns:
            bool: True if successful, False otherwise
        """
        full_key = self._get_full_key(key)
        ttl = ttl if ttl is not None else self.default_ttl
        
        try:
            # Convert value to JSON string
            json_value = json.dumps(value)
            
            if self.backend == 'redis':
                self.redis.set(full_key, json_value, ex=ttl)
            else:
                # Memory backend
                expires = time.time() + ttl if ttl > 0 else -1
                self.memory_cache[full_key] = {
                    "value": value,
                    "expires": expires
                }
            
            self.stats["sets"] += 1
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {str(e)}")
            self.stats["errors"] += 1
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete a value from the cache
        
        Args:
            key: The cache key
            
        Returns:
            bool: True if successful, False otherwise
        """
        full_key = self._get_full_key(key)
        
        try:
            if self.backend == 'redis':
                self.redis.delete(full_key)
            else:
                # Memory backend
                if full_key in self.memory_cache:
                    del self.memory_cache[full_key]
            
            self.stats["deletes"] += 1
            return True
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {str(e)}")
            self.stats["errors"] += 1
            return False
    
    def flush(self, pattern: Optional[str] = None) -> int:
        """
        Flush cache entries matching a pattern
        
        Args:
            pattern: Pattern to match (e.g., "user:*"), or None to flush all
            
        Returns:
            int: Number of entries flushed
        """
        try:
            if pattern is None:
                pattern = "*"
            
            full_pattern = self._get_full_key(pattern)
            
            if self.backend == 'redis':
                keys = self.redis.keys(full_pattern)
                if keys:
                    count = self.redis.delete(*keys)
                    self.stats["deletes"] += count
                    return count
                return 0
            else:
                # Memory backend
                count = 0
                keys_to_delete = []
                
                import fnmatch
                for key in self.memory_cache.keys():
                    if fnmatch.fnmatch(key, full_pattern):
                        keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    del self.memory_cache[key]
                    count += 1
                
                self.stats["deletes"] += count
                return count
        except Exception as e:
            logger.error(f"Error flushing cache with pattern {pattern}: {str(e)}")
            self.stats["errors"] += 1
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            dict: Cache statistics
        """
        stats = self.stats.copy()
        stats["backend"] = self.backend
        
        if self.backend == 'redis':
            try:
                # Add Redis info
                info = self.redis.info()
                stats["redis_used_memory"] = info.get("used_memory_human", "N/A")
                stats["redis_total_keys"] = len(self.redis.keys(f"{self.prefix}*"))
            except Exception as e:
                logger.error(f"Error getting Redis info: {str(e)}")
        else:
            # Memory backend stats
            stats["memory_total_keys"] = len(self.memory_cache)
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the cache system
        
        Returns:
            dict: Health check results
        """
        results = {
            "status": "healthy",
            "backend": self.backend,
            "errors": []
        }
        
        try:
            if self.backend == 'redis':
                # Test Redis connection
                self.redis.ping()
                
                # Test basic operations
                test_key = self._get_full_key("health_check")
                self.redis.set(test_key, "test", ex=10)
                value = self.redis.get(test_key)
                self.redis.delete(test_key)
                
                if value != "test":
                    results["status"] = "degraded"
                    results["errors"].append("Redis read/write test failed")
            else:
                # Test memory cache
                test_key = self._get_full_key("health_check")
                self.memory_cache[test_key] = {
                    "value": "test",
                    "expires": time.time() + 10
                }
                value = self.memory_cache[test_key]["value"]
                del self.memory_cache[test_key]
                
                if value != "test":
                    results["status"] = "degraded"
                    results["errors"].append("Memory cache read/write test failed")
        except Exception as e:
            results["status"] = "unhealthy"
            results["errors"].append(str(e))
        
        return results


def cached(ttl: Optional[int] = None, key_prefix: Optional[str] = None):
    """
    Decorator for caching function results
    
    Args:
        ttl: Time-to-live in seconds (uses default if None)
        key_prefix: Prefix for the cache key
        
    Returns:
        Callable: Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get cache manager from global scope or create a new one
            global _cache_manager
            if '_cache_manager' not in globals():
                _cache_manager = CacheManager()
            
            # Generate cache key
            if key_prefix:
                prefix = key_prefix
            else:
                prefix = f"{func.__module__}.{func.__name__}"
            
            # Create a hash of the arguments
            key_parts = [prefix]
            
            # Add args to key
            for arg in args:
                key_parts.append(str(arg))
            
            # Add kwargs to key (sorted for consistency)
            for k in sorted(kwargs.keys()):
                key_parts.append(f"{k}:{kwargs[k]}")
            
            # Create a hash of the key parts
            key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Try to get from cache
            cached_value = _cache_manager.get(key)
            if cached_value is not None:
                return cached_value
            
            # Call the function
            result = func(*args, **kwargs)
            
            # Cache the result
            _cache_manager.set(key, result, ttl)
            
            return result
        return wrapper
    return decorator


class AIResultCache:
    """Class for caching AI analysis results"""
    
    def __init__(self, cache_manager=None):
        """
        Initialize the AI result cache
        
        Args:
            cache_manager: Cache manager instance (creates new one if None)
        """
        self.cache_manager = cache_manager or CacheManager(prefix='stopsale:ai:')
    
    def get_result(self, email_content: str, subject: str = "") -> Optional[Dict[str, Any]]:
        """
        Get cached AI analysis result
        
        Args:
            email_content: Email content
            subject: Email subject
            
        Returns:
            dict: Cached result or None if not found
        """
        # Create a hash of the email content and subject
        key = self._generate_key(email_content, subject)
        return self.cache_manager.get(key)
    
    def set_result(self, email_content: str, subject: str, result: Dict[str, Any], ttl: int = 86400) -> bool:
        """
        Cache AI analysis result
        
        Args:
            email_content: Email content
            subject: Email subject
            result: Analysis result
            ttl: Time-to-live in seconds (default: 24 hours)
            
        Returns:
            bool: True if successful, False otherwise
        """
        key = self._generate_key(email_content, subject)
        return self.cache_manager.set(key, result, ttl)
    
    def _generate_key(self, email_content: str, subject: str) -> str:
        """
        Generate a cache key for an email
        
        Args:
            email_content: Email content
            subject: Email subject
            
        Returns:
            str: Cache key
        """
        # Create a hash of the email content and subject
        content_hash = hashlib.md5((subject + email_content).encode()).hexdigest()
        return f"email:{content_hash}"


class ModelCache:
    """Class for caching Django model queries"""
    
    def __init__(self, cache_manager=None):
        """
        Initialize the model cache
        
        Args:
            cache_manager: Cache manager instance (creates new one if None)
        """
        self.cache_manager = cache_manager or CacheManager(prefix='stopsale:model:')
    
    def get_object(self, model_name: str, pk: int) -> Optional[Dict[str, Any]]:
        """
        Get cached model object
        
        Args:
            model_name: Model name
            pk: Primary key
            
        Returns:
            dict: Cached object or None if not found
        """
        key = f"{model_name}:{pk}"
        return self.cache_manager.get(key)
    
    def set_object(self, model_name: str, pk: int, obj: Dict[str, Any], ttl: int = 3600) -> bool:
        """
        Cache model object
        
        Args:
            model_name: Model name
            pk: Primary key
            obj: Object data
            ttl: Time-to-live in seconds (default: 1 hour)
            
        Returns:
            bool: True if successful, False otherwise
        """
        key = f"{model_name}:{pk}"
        return self.cache_manager.set(key, obj, ttl)
    
    def delete_object(self, model_name: str, pk: int) -> bool:
        """
        Delete cached model object
        
        Args:
            model_name: Model name
            pk: Primary key
            
        Returns:
            bool: True if successful, False otherwise
        """
        key = f"{model_name}:{pk}"
        return self.cache_manager.delete(key)
    
    def get_queryset(self, model_name: str, query_hash: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached queryset
        
        Args:
            model_name: Model name
            query_hash: Hash of the query
            
        Returns:
            list: Cached queryset or None if not found
        """
        key = f"{model_name}:qs:{query_hash}"
        return self.cache_manager.get(key)
    
    def set_queryset(self, model_name: str, query_hash: str, queryset: List[Dict[str, Any]], ttl: int = 300) -> bool:
        """
        Cache queryset
        
        Args:
            model_name: Model name
            query_hash: Hash of the query
            queryset: Queryset data
            ttl: Time-to-live in seconds (default: 5 minutes)
            
        Returns:
            bool: True if successful, False otherwise
        """
        key = f"{model_name}:qs:{query_hash}"
        return self.cache_manager.set(key, queryset, ttl)
    
    def invalidate_model(self, model_name: str) -> int:
        """
        Invalidate all cache entries for a model
        
        Args:
            model_name: Model name
            
        Returns:
            int: Number of entries invalidated
        """
        return self.cache_manager.flush(f"{model_name}:*")


def install_dependencies():
    """Install required dependencies if not already installed"""
    try:
        import pip
        
        # Check and install dependencies
        if not REDIS_AVAILABLE:
            print("Installing redis-py...")
            pip.main(['install', 'redis'])
        
        print("Dependencies installed successfully.")
        
    except Exception as e:
        print(f"Error installing dependencies: {str(e)}")


# Django integration
def setup_django_cache_middleware():
    """
    Set up Django cache middleware
    
    Returns:
        str: Setup instructions
    """
    instructions = """
    # Add the following to your Django settings.py:
    
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': 'redis://127.0.0.1:6379/1',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }
    
    # Add cache middleware to your MIDDLEWARE setting:
    MIDDLEWARE = [
        'django.middleware.cache.UpdateCacheMiddleware',
        # ... other middleware ...
        'django.middleware.cache.FetchFromCacheMiddleware',
    ]
    
    # Cache settings
    CACHE_MIDDLEWARE_ALIAS = 'default'
    CACHE_MIDDLEWARE_SECONDS = 600  # 10 minutes
    CACHE_MIDDLEWARE_KEY_PREFIX = 'stopsale'
    """
    return instructions


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("Cache Mechanism Module")
    print("---------------------")
    print("This module provides Redis-based caching for the StopSale Automation System.")
    
    # Check if Redis is installed
    if not REDIS_AVAILABLE:
        print("\nRedis client not installed.")
        install = input("Do you want to install it? (y/n): ")
        if install.lower() == 'y':
            install_dependencies()
    
    # Example usage
    print("\nExample usage:")
    cache = CacheManager()
    
    # Set a value
    cache.set("example_key", {"name": "Example", "value": 42})
    
    # Get the value
    value = cache.get("example_key")
    print(f"Retrieved value: {value}")
    
    # Get cache stats
    stats = cache.get_stats()
    print(f"Cache stats: {stats}")
    
    # Health check
    health = cache.health_check()
    print(f"Health check: {health}")
    
    # Django integration
    print("\nDjango integration:")
    print(setup_django_cache_middleware())
