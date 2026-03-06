"""
Reporting serializers.
"""
from rest_framework import serializers
from .models import (
    ReportDefinition, ReportSchedule, ReportExecution,
    Dashboard, DashboardWidget, SavedFilter
)


class ReportDefinitionSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_report_type_display', read_only=True)

    class Meta:
        model = ReportDefinition
        fields = [
            'id', 'code', 'name', 'description',
            'report_type', 'type_display',
            'query', 'template', 'parameters',
            'default_format', 'is_active', 'is_system'
        ]


class ReportScheduleSerializer(serializers.ModelSerializer):
    report_name = serializers.CharField(source='report.name', read_only=True)
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)

    class Meta:
        model = ReportSchedule
        fields = [
            'id', 'report', 'report_name', 'name',
            'frequency', 'frequency_display',
            'day_of_week', 'day_of_month', 'time',
            'parameters', 'format', 'recipients',
            'is_active', 'last_run', 'next_run'
        ]


class ReportExecutionSerializer(serializers.ModelSerializer):
    report_name = serializers.CharField(source='report.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    executed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ReportExecution
        fields = [
            'id', 'report', 'report_name', 'schedule',
            'status', 'status_display', 'parameters', 'format',
            'started_at', 'completed_at', 'duration_seconds',
            'output_file', 'error_message',
            'executed_by', 'executed_by_name', 'created_at'
        ]
        read_only_fields = [
            'id', 'status', 'started_at', 'completed_at',
            'duration_seconds', 'output_file', 'error_message', 'created_at'
        ]

    def get_executed_by_name(self, obj):
        if obj.executed_by:
            return obj.executed_by.get_full_name() or obj.executed_by.email
        return None


class DashboardWidgetSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_widget_type_display', read_only=True)

    class Meta:
        model = DashboardWidget
        fields = [
            'id', 'name', 'widget_type', 'type_display',
            'report', 'query', 'parameters',
            'position_x', 'position_y', 'width', 'height',
            'refresh_interval'
        ]


class DashboardSerializer(serializers.ModelSerializer):
    widgets = DashboardWidgetSerializer(many=True, read_only=True)
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = Dashboard
        fields = [
            'id', 'code', 'name', 'description',
            'is_default', 'is_public', 'layout',
            'owner', 'owner_name', 'widgets'
        ]

    def get_owner_name(self, obj):
        if obj.owner:
            return obj.owner.get_full_name() or obj.owner.email
        return None


class DashboardListSerializer(serializers.ModelSerializer):
    widgets_count = serializers.IntegerField(source='widgets.count', read_only=True)

    class Meta:
        model = Dashboard
        fields = ['id', 'code', 'name', 'is_default', 'is_public', 'widgets_count']


class SavedFilterSerializer(serializers.ModelSerializer):
    report_name = serializers.CharField(source='report.name', read_only=True)

    class Meta:
        model = SavedFilter
        fields = [
            'id', 'name', 'report', 'report_name',
            'filters', 'is_default', 'owner'
        ]
        read_only_fields = ['owner']
