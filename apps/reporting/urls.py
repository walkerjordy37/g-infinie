"""
Reporting URLs.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import (
    ReportDefinitionViewSet, ReportScheduleViewSet, ReportExecutionViewSet,
    DashboardViewSet, DashboardWidgetViewSet, SavedFilterViewSet
)

router = DefaultRouter()
router.register(r'reports', ReportDefinitionViewSet, basename='report')
router.register(r'schedules', ReportScheduleViewSet, basename='report-schedule')
router.register(r'executions', ReportExecutionViewSet, basename='report-execution')
router.register(r'dashboards', DashboardViewSet, basename='dashboard')
router.register(r'filters', SavedFilterViewSet, basename='saved-filter')

dashboards_router = routers.NestedDefaultRouter(router, r'dashboards', lookup='dashboard')
dashboards_router.register(r'widgets', DashboardWidgetViewSet, basename='dashboard-widgets')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(dashboards_router.urls)),
]
