"""
Middleware for company context.
"""
from django.utils.deprecation import MiddlewareMixin
from .models import Company


class CompanyMiddleware(MiddlewareMixin):
    """
    Middleware to set the current company on the request.
    Company can be set via:
    1. X-Company-ID header
    2. company_id query parameter
    3. User's default company
    """

    def process_request(self, request):
        request.company = None

        if not request.user.is_authenticated:
            return

        company_id = None

        # Check header first
        company_id = request.headers.get('X-Company-ID')

        # Check query parameter
        if not company_id:
            company_id = request.GET.get('company_id')

        if company_id:
            # Verify user has access to this company
            try:
                membership = request.user.memberships.select_related('company').get(
                    company_id=company_id,
                    is_active=True
                )
                request.company = membership.company
                request.membership = membership
            except Exception:
                pass
        else:
            # Use user's default company
            membership = request.user.memberships.select_related('company').filter(
                is_active=True,
                is_default=True
            ).first()

            if not membership:
                membership = request.user.memberships.select_related('company').filter(
                    is_active=True
                ).first()

            if membership:
                request.company = membership.company
                request.membership = membership
