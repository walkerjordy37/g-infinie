"""
Subscriptions URLs.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PlatformPlanViewSet,
    CompanySubscriptionViewSet,
    PaymentViewSet,
    WebhookViewSet,
)

router = DefaultRouter()
router.register(r'plans', PlatformPlanViewSet, basename='platform-plan')
router.register(r'subscription', CompanySubscriptionViewSet, basename='subscription')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'webhooks', WebhookViewSet, basename='webhook')

urlpatterns = [
    path('', include(router.urls)),
]
