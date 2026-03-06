"""
Middleware to check subscription status.
"""
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse


class SubscriptionMiddleware(MiddlewareMixin):
    """
    Checks that the current company has an active subscription.
    Returns 403 with specific message if subscription expired.
    """
    
    # Paths that don't require subscription check
    EXEMPT_PATHS = [
        '/api/v1/iam/auth/',
        '/api/v1/subscriptions/',
        '/api/v1/iam/users/me/',
        '/admin/',
        '/api/schema/',
        '/api/v1/sync/',
    ]

    def process_request(self, request):
        # Skip non-API requests
        if not request.path.startswith('/api/'):
            return None
        
        # Skip exempt paths
        for path in self.EXEMPT_PATHS:
            if request.path.startswith(path):
                return None
        
        # Skip if no company context (middleware runs after CompanyMiddleware)
        company = getattr(request, 'company', None)
        if not company:
            return None
        
        # Check subscription
        try:
            subscription = company.subscription
            if not subscription.is_active:
                return JsonResponse({
                    'error': 'subscription_expired',
                    'message': 'Votre abonnement a expiré. Veuillez renouveler votre abonnement pour continuer.',
                    'subscription_status': subscription.status,
                    'plan': subscription.plan.name,
                }, status=403)
        except Exception:
            # No subscription at all - could be new company during trial setup
            pass
        
        return None
