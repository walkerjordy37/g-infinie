"""
URL configuration for audit module.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'audit-logs', views.AuditLogViewSet, basename='audit-log')
router.register(r'activity-logs', views.ActivityLogViewSet, basename='activity-log')

urlpatterns = [
    path('', include(router.urls)),
]
