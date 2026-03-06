"""
Treasury app configuration.
"""
from django.apps import AppConfig


class TreasuryConfig(AppConfig):
    """Configuration for Treasury app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.treasury'
    verbose_name = 'Trésorerie'

    def ready(self):
        pass
