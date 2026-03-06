"""
Payments URLs - Router configuration for payments API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers as nested_routers

from .views import (
    PaymentMethodViewSet,
    PaymentTermViewSet,
    PaymentViewSet,
    PaymentAllocationViewSet,
    RefundViewSet,
)

router = DefaultRouter()
router.register(r'methods', PaymentMethodViewSet, basename='payment-method')
router.register(r'terms', PaymentTermViewSet, basename='payment-term')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'refunds', RefundViewSet, basename='refund')

payments_router = nested_routers.NestedDefaultRouter(router, r'payments', lookup='payment')
payments_router.register(r'allocations', PaymentAllocationViewSet, basename='payment-allocations')

app_name = 'payments'

urlpatterns = [
    path('', include(router.urls)),
    path('', include(payments_router.urls)),
]
