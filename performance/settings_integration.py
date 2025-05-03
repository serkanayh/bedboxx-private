"""
Django Settings Integration for Performance Optimizations

This module provides functions to integrate performance optimizations into Django settings.
"""

import os
import logging

logger = logging.getLogger(__name__)

def integrate_cache_settings(settings_module):
    """
    Integrate cache settings into Django settings module
    
    Args:
        settings_module: The Django settings module to update
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Define Redis cache settings
        cache_settings = {
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
                'OPTIONS': {
                    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                    'PARSER_CLASS': 'redis.connection.HiredisParser',
                    'CONNECTION_POOL_CLASS': 'redis.BlockingConnectionPool',
                    'CONNECTION_POOL_CLASS_KWARGS': {
                        'max_connections': 50,
                        'timeout': 20,
                    },
                    'SOCKET_CONNECT_TIMEOUT': 5,
                    'SOCKET_TIMEOUT': 5,
                    'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
                    'IGNORE_EXCEPTIONS': True,
                }
            }
        }
        
        # Add cache settings to Django settings
        settings_module.CACHES = cache_settings
        
        # Add cache middleware
        if 'django.middleware.cache.UpdateCacheMiddleware' not in settings_module.MIDDLEWARE:
            settings_module.MIDDLEWARE.insert(0, 'django.middleware.cache.UpdateCacheMiddleware')
            settings_module.MIDDLEWARE.append('django.middleware.cache.FetchFromCacheMiddleware')
        
        # Configure cache timeouts
        settings_module.CACHE_MIDDLEWARE_ALIAS = 'default'
        settings_module.CACHE_MIDDLEWARE_SECONDS = 600  # 10 minutes
        settings_module.CACHE_MIDDLEWARE_KEY_PREFIX = 'stopsale'
        
        logger.info("Cache settings integrated successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error integrating cache settings: {str(e)}")
        return False

def integrate_database_settings(settings_module):
    """
    Integrate database optimization settings into Django settings module
    
    Args:
        settings_module: The Django settings module to update
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get current database settings
        databases = getattr(settings_module, 'DATABASES', {})
        
        # Update default database settings
        if 'default' in databases:
            # Add connection pooling
            databases['default'].setdefault('OPTIONS', {})
            databases['default']['OPTIONS']['CONN_MAX_AGE'] = 600  # 10 minutes
            
            # Add timeout settings
            databases['default']['OPTIONS']['connect_timeout'] = 5
            databases['default']['OPTIONS']['statement_timeout'] = 30000  # 30 seconds
            
            # Set atomic requests for better transaction handling
            databases['default']['ATOMIC_REQUESTS'] = True
        
        # Update settings module
        settings_module.DATABASES = databases
        
        logger.info("Database settings integrated successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error integrating database settings: {str(e)}")
        return False

def integrate_async_settings(settings_module):
    """
    Integrate asynchronous processing settings into Django settings module
    
    Args:
        settings_module: The Django settings module to update
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Celery settings
        settings_module.CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
        settings_module.CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/0')
        settings_module.CELERY_ACCEPT_CONTENT = ['json']
        settings_module.CELERY_TASK_SERIALIZER = 'json'
        settings_module.CELERY_RESULT_SERIALIZER = 'json'
        settings_module.CELERY_TIMEZONE = settings_module.TIME_ZONE
        settings_module.CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'False') == 'True'
        settings_module.CELERY_TASK_EAGER_PROPAGATES = True
        
        # Task queues
        settings_module.CELERY_TASK_DEFAULT_QUEUE = 'default'
        settings_module.CELERY_TASK_QUEUES = {
            'default': {'exchange': 'default', 'binding_key': 'default'},
            'email_processing': {'exchange': 'email_processing', 'binding_key': 'email_processing'},
            'ai_analysis': {'exchange': 'ai_analysis', 'binding_key': 'ai_analysis'},
        }
        
        # Task routing
        settings_module.CELERY_TASK_ROUTES = {
            'emails.*': {'queue': 'email_processing'},
            'ai.*': {'queue': 'ai_analysis'},
        }
        
        logger.info("Async settings integrated successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error integrating async settings: {str(e)}")
        return False

def integrate_all_performance_settings(settings_module):
    """
    Integrate all performance optimization settings into Django settings module
    
    Args:
        settings_module: The Django settings module to update
    
    Returns:
        bool: True if successful, False otherwise
    """
    cache_result = integrate_cache_settings(settings_module)
    database_result = integrate_database_settings(settings_module)
    async_result = integrate_async_settings(settings_module)
    
    return cache_result and database_result and async_result
