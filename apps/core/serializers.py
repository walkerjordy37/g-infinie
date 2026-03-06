"""
Base serializers for the API.
"""
from rest_framework import serializers


class BaseModelSerializer(serializers.ModelSerializer):
    """Base serializer with common fields."""
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        abstract = True
        read_only_fields = ['id', 'created_at', 'updated_at']


class CompanyScopedSerializer(BaseModelSerializer):
    """Serializer for company-scoped models."""
    company = serializers.PrimaryKeyRelatedField(read_only=True)

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'company'):
            validated_data['company'] = request.company
        return super().create(validated_data)


class MoneySerializer(serializers.Serializer):
    """Serializer for money amounts with currency."""
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    currency = serializers.CharField(max_length=3)


class AddressSerializer(serializers.Serializer):
    """Serializer for address data."""
    street = serializers.CharField(max_length=255, required=False, allow_blank=True)
    street2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100)


class BulkActionSerializer(serializers.Serializer):
    """Serializer for bulk actions."""
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="Liste des IDs des éléments"
    )


class StatusTransitionSerializer(serializers.Serializer):
    """Serializer for status transition actions."""
    status = serializers.ChoiceField(choices=[])
    reason = serializers.CharField(required=False, allow_blank=True)

    def __init__(self, *args, allowed_statuses=None, **kwargs):
        super().__init__(*args, **kwargs)
        if allowed_statuses:
            self.fields['status'].choices = allowed_statuses
