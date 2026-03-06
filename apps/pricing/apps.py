"""
Pricing app configuration.
"""
from django.apps import AppConfig


class PricingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pricing'
    verbose_name = 'Tarification'

    def ready(self):
        pass
