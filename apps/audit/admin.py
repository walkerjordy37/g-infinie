from django.contrib import admin
from .models import AuditLog, ActivityLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user_email', 'action', 'module', 'object_repr', 'company']
    list_filter = ['action', 'module', 'company', 'timestamp']
    search_fields = ['user_email', 'object_repr', 'description']
    date_hierarchy = 'timestamp'
    readonly_fields = [
        'id', 'timestamp', 'user', 'user_email', 'ip_address', 'user_agent',
        'company', 'action', 'module', 'description', 'content_type',
        'object_id', 'object_repr', 'old_values', 'new_values', 'changes'
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'company']
    list_filter = ['action', 'company', 'timestamp']
    search_fields = ['user__email', 'action']
    date_hierarchy = 'timestamp'
    readonly_fields = ['id', 'timestamp', 'user', 'company', 'action', 'details']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
