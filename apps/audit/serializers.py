"""
Serializers for audit module.
"""
from rest_framework import serializers
from .models import AuditLog, ActivityLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'timestamp', 'user', 'user_email', 'ip_address',
            'company', 'company_name', 'action', 'module', 'description',
            'object_id', 'object_repr', 'old_values', 'new_values', 'changes'
        ]
        read_only_fields = fields


class ActivityLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = ActivityLog
        fields = ['id', 'timestamp', 'user', 'user_email', 'company', 'action', 'details']
        read_only_fields = fields
