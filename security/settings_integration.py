"""
Django Settings Integration for Security Improvements

This module provides functions to integrate security improvements into Django settings.
"""

import os
import logging

logger = logging.getLogger(__name__)

def integrate_security_settings(settings_module):
    """
    Integrate security settings into Django settings module
    
    Args:
        settings_module: The Django settings module to update
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Security middleware settings
        if 'django.middleware.security.SecurityMiddleware' not in settings_module.MIDDLEWARE:
            settings_module.MIDDLEWARE.insert(0, 'django.middleware.security.SecurityMiddleware')
        
        # Add security headers middleware
        if 'security.middleware.SecurityHeadersMiddleware' not in settings_module.MIDDLEWARE:
            settings_module.MIDDLEWARE.insert(1, 'security.middleware.SecurityHeadersMiddleware')
        
        # Add content security policy middleware
        if 'security.middleware.ContentSecurityPolicyMiddleware' not in settings_module.MIDDLEWARE:
            settings_module.MIDDLEWARE.insert(2, 'security.middleware.ContentSecurityPolicyMiddleware')
        
        # Security settings
        settings_module.SECURE_BROWSER_XSS_FILTER = True
        settings_module.SECURE_CONTENT_TYPE_NOSNIFF = True
        settings_module.X_FRAME_OPTIONS = 'DENY'
        settings_module.SECURE_HSTS_SECONDS = 31536000  # 1 year
        settings_module.SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        settings_module.SECURE_HSTS_PRELOAD = True
        
        # SSL/HTTPS settings
        settings_module.SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True') == 'True'
        settings_module.SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
        settings_module.SESSION_COOKIE_SECURE = True
        settings_module.CSRF_COOKIE_SECURE = True
        
        # Password validation
        settings_module.AUTH_PASSWORD_VALIDATORS = [
            {
                'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
            },
            {
                'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
                'OPTIONS': {
                    'min_length': 10,
                }
            },
            {
                'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
            },
            {
                'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
            },
            {
                'NAME': 'security.password_validation.PasswordStrengthValidator',
            },
        ]
        
        # Session settings
        settings_module.SESSION_COOKIE_HTTPONLY = True
        settings_module.SESSION_EXPIRE_AT_BROWSER_CLOSE = True
        settings_module.SESSION_COOKIE_AGE = 3600  # 1 hour
        
        # CSRF settings
        settings_module.CSRF_COOKIE_HTTPONLY = True
        settings_module.CSRF_USE_SESSIONS = True
        
        # API key settings
        settings_module.API_KEY_CUSTOM_HEADER = 'X-API-KEY'
        settings_module.API_KEY_STORAGE_PATH = os.path.join(settings_module.BASE_DIR, 'security', 'keys')
        
        # Encryption settings
        settings_module.ENCRYPTION_KEY_PATH = os.path.join(settings_module.BASE_DIR, 'security', 'crypto')
        
        logger.info("Security settings integrated successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error integrating security settings: {str(e)}")
        return False
