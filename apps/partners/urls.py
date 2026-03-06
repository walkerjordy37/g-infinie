"""
Partners URL configuration.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PartnerCategoryViewSet,
    PartnerViewSet,
    PartnerContactViewSet,
    PartnerAddressViewSet,
    PartnerBankAccountViewSet,
)

router = DefaultRouter()
router.register(r'categories', PartnerCategoryViewSet, basename='partner-category')
router.register(r'partners', PartnerViewSet, basename='partner')
router.register(r'contacts', PartnerContactViewSet, basename='partner-contact')
router.register(r'addresses', PartnerAddressViewSet, basename='partner-address')
router.register(r'bank-accounts', PartnerBankAccountViewSet, basename='partner-bank-account')

app_name = 'partners'

urlpatterns = [
    path('', include(router.urls)),
]
