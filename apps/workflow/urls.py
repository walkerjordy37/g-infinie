"""
Workflow URLs.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import (
    WorkflowDefinitionViewSet, WorkflowStepViewSet,
    WorkflowInstanceViewSet, WorkflowNotificationViewSet
)

router = DefaultRouter()
router.register(r'definitions', WorkflowDefinitionViewSet, basename='workflow-definition')
router.register(r'instances', WorkflowInstanceViewSet, basename='workflow-instance')
router.register(r'notifications', WorkflowNotificationViewSet, basename='workflow-notification')

definitions_router = routers.NestedDefaultRouter(router, r'definitions', lookup='workflow')
definitions_router.register(r'steps', WorkflowStepViewSet, basename='workflow-steps')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(definitions_router.urls)),
]
