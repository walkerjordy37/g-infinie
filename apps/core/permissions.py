"""
Custom permission classes for the API.
"""
from rest_framework.permissions import BasePermission


class IsCompanyMember(BasePermission):
    """Permission to check if user belongs to the company."""
    message = "Vous n'êtes pas membre de cette entreprise."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        # Allow access even without company - viewset will return empty queryset
        return True

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'company'):
            return obj.company == request.company
        return True


class IsCompanyAdmin(BasePermission):
    """Permission to check if user is admin of the company."""
    message = "Vous devez être administrateur de l'entreprise."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not hasattr(request, 'company') or not request.company:
            return False
        membership = request.user.memberships.filter(company=request.company).first()
        return membership and membership.role in ['admin', 'owner']


class CanViewFinancials(BasePermission):
    """Permission to view financial data."""
    message = "Vous n'avez pas accès aux données financières."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if not hasattr(request, 'company') or not request.company:
            return False
        membership = request.user.memberships.filter(company=request.company).first()
        return membership and membership.can_view_financials


class CanPostAccounting(BasePermission):
    """Permission to post accounting entries."""
    message = "Vous n'avez pas le droit de valider des écritures comptables."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if not hasattr(request, 'company') or not request.company:
            return False
        membership = request.user.memberships.filter(company=request.company).first()
        return membership and membership.can_post_accounting


class CanManageInventory(BasePermission):
    """Permission to manage inventory."""
    message = "Vous n'avez pas le droit de gérer le stock."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if not hasattr(request, 'company') or not request.company:
            return False
        membership = request.user.memberships.filter(company=request.company).first()
        return membership and membership.can_manage_inventory


class CanApprovePurchases(BasePermission):
    """Permission to approve purchase orders."""
    message = "Vous n'avez pas le droit d'approuver les commandes d'achat."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if not hasattr(request, 'company') or not request.company:
            return False
        membership = request.user.memberships.filter(company=request.company).first()
        return membership and membership.can_approve_purchases
