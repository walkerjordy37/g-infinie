"""
Reporting admin.
"""
from django.contrib import admin
from .models import (
    ReportDefinition, ReportSchedule, ReportExecution,
    Dashboard, DashboardWidget, SavedFilter
)


@admin.register(ReportDefinition)
class ReportDefinitionAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'report_type', 'default_format', 'is_active']
    list_filter = ['report_type', 'is_active', 'is_system']
    search_fields = ['code', 'name']


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ['name', 'report', 'frequency', 'is_active', 'next_run']
    list_filter = ['frequency', 'is_active']
    autocomplete_fields = ['report']


@admin.register(ReportExecution)
class ReportExecutionAdmin(admin.ModelAdmin):
    list_display = ['report', 'status', 'format', 'started_at', 'duration_seconds']
    list_filter = ['status', 'format']
    readonly_fields = ['started_at', 'completed_at', 'duration_seconds']


class DashboardWidgetInline(admin.TabularInline):
    model = DashboardWidget
    extra = 1


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_default', 'is_public', 'owner']
    list_filter = ['is_default', 'is_public']
    search_fields = ['code', 'name']
    inlines = [DashboardWidgetInline]


@admin.register(SavedFilter)
class SavedFilterAdmin(admin.ModelAdmin):
    list_display = ['name', 'report', 'is_default', 'owner']
    list_filter = ['is_default']
    autocomplete_fields = ['report', 'owner']
