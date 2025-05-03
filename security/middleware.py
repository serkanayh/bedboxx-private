"""
Security Middleware for StopSale Automation System

This module provides security middleware for Django applications.
"""

import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers to HTTP responses
    """
    
    def process_response(self, request, response):
        """
        Add security headers to the response
        
        Args:
            request: The HTTP request
            response: The HTTP response
            
        Returns:
            HttpResponse: The modified response
        """
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-XSS-Protection'] = '1; mode=block'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Add feature policy
        response['Feature-Policy'] = (
            "geolocation 'none'; "
            "microphone 'none'; "
            "camera 'none'; "
            "payment 'none'; "
            "usb 'none'; "
            "accelerometer 'none'; "
            "gyroscope 'none'; "
            "magnetometer 'none'; "
            "midi 'none'"
        )
        
        return response


class ContentSecurityPolicyMiddleware(MiddlewareMixin):
    """
    Middleware to add Content Security Policy headers to HTTP responses
    """
    
    def process_response(self, request, response):
        """
        Add Content Security Policy headers to the response
        
        Args:
            request: The HTTP request
            response: The HTTP response
            
        Returns:
            HttpResponse: The modified response
        """
        # Define CSP directives
        csp_directives = {
            'default-src': "'self'",
            'script-src': "'self' 'unsafe-inline' 'unsafe-eval'",
            'style-src': "'self' 'unsafe-inline'",
            'img-src': "'self' data:",
            'font-src': "'self'",
            'connect-src': "'self'",
            'frame-src': "'none'",
            'object-src': "'none'",
            'base-uri': "'self'",
            'form-action': "'self'",
            'frame-ancestors': "'none'",
            'upgrade-insecure-requests': ''
        }
        
        # Build CSP header value
        csp_value = '; '.join([f"{key} {value}" for key, value in csp_directives.items() if value])
        
        # Add CSP header
        response['Content-Security-Policy'] = csp_value
        
        return response


class APIKeyMiddleware(MiddlewareMixin):
    """
    Middleware to validate API keys for API requests
    """
    
    def __init__(self, get_response=None):
        """
        Initialize the middleware
        
        Args:
            get_response: The get_response callable
        """
        super().__init__(get_response)
        
        # Import API key manager
        from security.secure_api_key_manager import ApiKeyManager
        self.api_key_manager = ApiKeyManager()
    
    def process_request(self, request):
        """
        Process the request and validate API key if needed
        
        Args:
            request: The HTTP request
            
        Returns:
            HttpResponse or None: Response if validation fails, None otherwise
        """
        # Check if this is an API request
        if request.path.startswith('/api/'):
            # Get API key from custom header or query parameter
            from django.conf import settings
            api_key_header = getattr(settings, 'API_KEY_CUSTOM_HEADER', 'X-API-KEY')
            
            api_key = request.headers.get(api_key_header) or request.GET.get('api_key')
            
            if not api_key:
                from django.http import JsonResponse
                return JsonResponse({'error': 'API key is required'}, status=401)
            
            # Validate API key
            if not self.api_key_manager.validate_key(api_key):
                from django.http import JsonResponse
                return JsonResponse({'error': 'Invalid API key'}, status=401)
            
            # Add API key info to request
            request.api_key_info = self.api_key_manager.get_key_info(api_key)
        
        return None
