"""
Workflow serializers.
"""
from rest_framework import serializers
from .models import (
    WorkflowDefinition, WorkflowStep, WorkflowInstance,
    WorkflowAction, WorkflowNotification
)


class WorkflowStepSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_type_display', read_only=True)
    approver_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowStep
        fields = [
            'id', 'sequence', 'name', 'description',
            'action_type', 'action_display',
            'approver', 'approver_name', 'approver_role',
            'amount_threshold', 'auto_approve_below',
            'timeout_hours', 'escalate_to', 'is_required'
        ]

    def get_approver_name(self, obj):
        if obj.approver:
            return obj.approver.get_full_name() or obj.approver.email
        return None


class WorkflowDefinitionSerializer(serializers.ModelSerializer):
    entity_display = serializers.CharField(source='get_entity_type_display', read_only=True)
    steps = WorkflowStepSerializer(many=True, read_only=True)

    class Meta:
        model = WorkflowDefinition
        fields = [
            'id', 'code', 'name', 'description',
            'entity_type', 'entity_display',
            'is_active', 'is_sequential', 'conditions', 'steps'
        ]


class WorkflowDefinitionListSerializer(serializers.ModelSerializer):
    entity_display = serializers.CharField(source='get_entity_type_display', read_only=True)
    steps_count = serializers.IntegerField(source='steps.count', read_only=True)

    class Meta:
        model = WorkflowDefinition
        fields = [
            'id', 'code', 'name', 'entity_type', 'entity_display',
            'is_active', 'steps_count'
        ]


class WorkflowActionSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    performed_by_name = serializers.SerializerMethodField()
    step_name = serializers.CharField(source='step.name', read_only=True)

    class Meta:
        model = WorkflowAction
        fields = [
            'id', 'step', 'step_name', 'action', 'action_display',
            'performed_by', 'performed_by_name', 'performed_at',
            'comments', 'delegated_to'
        ]

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.email
        return None


class WorkflowInstanceSerializer(serializers.ModelSerializer):
    workflow_name = serializers.CharField(source='workflow.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    current_step_name = serializers.CharField(source='current_step.name', read_only=True)
    initiated_by_name = serializers.SerializerMethodField()
    actions = WorkflowActionSerializer(many=True, read_only=True)

    class Meta:
        model = WorkflowInstance
        fields = [
            'id', 'workflow', 'workflow_name',
            'content_type', 'object_id',
            'status', 'status_display',
            'current_step', 'current_step_name',
            'started_at', 'completed_at',
            'initiated_by', 'initiated_by_name',
            'metadata', 'actions', 'created_at'
        ]
        read_only_fields = [
            'id', 'status', 'current_step', 'started_at', 'completed_at', 'created_at'
        ]

    def get_initiated_by_name(self, obj):
        if obj.initiated_by:
            return obj.initiated_by.get_full_name() or obj.initiated_by.email
        return None


class WorkflowInstanceListSerializer(serializers.ModelSerializer):
    workflow_name = serializers.CharField(source='workflow.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    current_step_name = serializers.CharField(source='current_step.name', read_only=True)

    class Meta:
        model = WorkflowInstance
        fields = [
            'id', 'workflow_name', 'content_type', 'object_id',
            'status', 'status_display', 'current_step_name', 'created_at'
        ]


class WorkflowNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowNotification
        fields = [
            'id', 'instance', 'message', 'is_read', 'read_at', 'created_at'
        ]
        read_only_fields = ['id', 'instance', 'message', 'created_at']
