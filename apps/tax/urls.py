"""
Tax URLs - API routes for taxes, rates, rules, and declarations.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import (
    TaxTypeViewSet, TaxRateViewSet, TaxGroupViewSet, TaxRuleViewSet,
    WithholdingTaxViewSet, TaxDeclarationViewSet, TaxDeclarationLineViewSet,
    TaxCalculationViewSet
)

router = DefaultRouter()
router.register(r'types', TaxTypeViewSet, basename='tax-type')
router.register(r'rates', TaxRateViewSet, basename='tax-rate')
router.register(r'groups', TaxGroupViewSet, basename='tax-group')
router.register(r'rules', TaxRuleViewSet, basename='tax-rule')
router.register(r'withholding', WithholdingTaxViewSet, basename='withholding-tax')
router.register(r'declarations', TaxDeclarationViewSet, basename='tax-declaration')
router.register(r'calculations', TaxCalculationViewSet, basename='tax-calculation')

declarations_router = routers.NestedDefaultRouter(router, r'declarations', lookup='declaration')
declarations_router.register(r'lines', TaxDeclarationLineViewSet, basename='tax-declaration-lines')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(declarations_router.urls)),
]
