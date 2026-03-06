"""
Workflow admin.
"""
from django.contrib import admin
from .models import (
    WorkflowDefinition, WorkflowStep, WorkflowInstance,
    WorkflowAction, WorkflowNotification
)


class WorkflowStepInline(admin.TabularInline):
    model = WorkflowStep
    extra = 1
    ordering = ['sequence']


@admin.register(WorkflowDefinition)
class WorkflowDefinitionAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'entity_type', 'is_active', 'is_sequential']
    list_filter = ['entity_type', 'is_active']
    search_fields = ['code', 'name']
    inlines = [WorkflowStepInline]


class WorkflowActionInline(admin.TabularInline):
    model = WorkflowAction
    extra = 0
    readonly_fields = ['performed_at']


@admin.register(WorkflowInstance)
class WorkflowInstanceAdmin(admin.ModelAdmin):
    list_display = [
        'workflow', 'content_type', 'object_id',
        'status', 'current_step', 'initiated_by', 'created_at'
    ]
    list_filter = ['status', 'workflow']
    readonly_fields = ['started_at', 'completed_at']
    inlines = [WorkflowActionInline]


@admin.register(WorkflowNotification)
class WorkflowNotificationAdmin(admin.ModelAdmin):
    list_display = ['instance', 'recipient', 'is_read', 'created_at']
    list_filter = ['is_read']
