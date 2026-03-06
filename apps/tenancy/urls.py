"""
URL configuration for tenancy module.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'currencies', views.CurrencyViewSet, basename='currency')
router.register(r'exchange-rates', views.ExchangeRateViewSet, basename='exchange-rate')
router.register(r'companies', views.CompanyViewSet, basename='company')
router.register(r'branches', views.BranchViewSet, basename='branch')
router.register(r'fiscal-years', views.FiscalYearViewSet, basename='fiscal-year')
router.register(r'fiscal-periods', views.FiscalPeriodViewSet, basename='fiscal-period')
router.register(r'document-sequences', views.DocumentSequenceViewSet, basename='document-sequence')

urlpatterns = [
    path('', include(router.urls)),
]
