"""
Treasury URLs - Router configuration for treasury API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers as nested_routers

from .views import (
    BankAccountViewSet, CashRegisterViewSet,
    BankStatementViewSet, BankStatementLineViewSet,
    BankReconciliationViewSet, CashMovementViewSet, TransferViewSet,
)

router = DefaultRouter()
router.register(r'bank-accounts', BankAccountViewSet, basename='bank-account')
router.register(r'cash-registers', CashRegisterViewSet, basename='cash-register')
router.register(r'statements', BankStatementViewSet, basename='bank-statement')
router.register(r'reconciliations', BankReconciliationViewSet, basename='bank-reconciliation')
router.register(r'cash-movements', CashMovementViewSet, basename='cash-movement')
router.register(r'transfers', TransferViewSet, basename='transfer')

statements_router = nested_routers.NestedDefaultRouter(
    router, r'statements', lookup='statement'
)
statements_router.register(r'lines', BankStatementLineViewSet, basename='statement-lines')

app_name = 'treasury'

urlpatterns = [
    path('', include(router.urls)),
    path('', include(statements_router.urls)),
]
