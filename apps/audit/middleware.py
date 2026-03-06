"""
Audit middleware for request tracking.
"""
import threading
from django.utils.deprecation import MiddlewareMixin

_thread_locals = threading.local()


def get_current_request():
    """Get the current request from thread local storage."""
    return getattr(_thread_locals, 'request', None)


def get_current_user():
    """Get the current user from thread local storage."""
    request = get_current_request()
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        return request.user
    return None


class AuditMiddleware(MiddlewareMixin):
    """Middleware to store request in thread local for audit logging."""

    def process_request(self, request):
        _thread_locals.request = request

    def process_response(self, request, response):
        if hasattr(_thread_locals, 'request'):
            del _thread_locals.request
        return response

    def process_exception(self, request, exception):
        if hasattr(_thread_locals, 'request'):
            del _thread_locals.request
        return None
