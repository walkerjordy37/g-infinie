"""
Custom exceptions and exception handler for the API.
"""
from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework import status


def custom_exception_handler(exc, context):
    """Custom exception handler that adds error codes."""
    response = exception_handler(exc, context)

    if response is not None:
        response.data['status_code'] = response.status_code
        if hasattr(exc, 'error_code'):
            response.data['error_code'] = exc.error_code
        else:
            response.data['error_code'] = 'error'

    return response


class BusinessLogicError(APIException):
    """Exception for business logic violations."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Une erreur de logique métier s\'est produite.'
    default_code = 'business_logic_error'
    error_code = 'BUSINESS_LOGIC_ERROR'


class InsufficientStockError(BusinessLogicError):
    """Exception for insufficient stock."""
    default_detail = 'Stock insuffisant pour cette opération.'
    error_code = 'INSUFFICIENT_STOCK'


class InvalidStatusTransitionError(BusinessLogicError):
    """Exception for invalid status transitions."""
    default_detail = 'Transition de statut non autorisée.'
    error_code = 'INVALID_STATUS_TRANSITION'


class DocumentAlreadyPostedError(BusinessLogicError):
    """Exception when trying to modify a posted document."""
    default_detail = 'Ce document est déjà validé et ne peut plus être modifié.'
    error_code = 'DOCUMENT_ALREADY_POSTED'


class InsufficientPermissionError(APIException):
    """Exception for permission issues."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Vous n\'avez pas les permissions nécessaires.'
    error_code = 'INSUFFICIENT_PERMISSION'


class CompanyAccessError(APIException):
    """Exception for company access issues."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Accès non autorisé à cette entreprise.'
    error_code = 'COMPANY_ACCESS_DENIED'


class AccountingImbalanceError(BusinessLogicError):
    """Exception for unbalanced accounting entries."""
    default_detail = 'L\'écriture comptable n\'est pas équilibrée.'
    error_code = 'ACCOUNTING_IMBALANCE'


class FiscalPeriodClosedError(BusinessLogicError):
    """Exception when trying to post to a closed period."""
    default_detail = 'La période comptable est clôturée.'
    error_code = 'FISCAL_PERIOD_CLOSED'


class PaymentExceedsAmountError(BusinessLogicError):
    """Exception when payment exceeds invoice amount."""
    default_detail = 'Le paiement dépasse le montant dû.'
    error_code = 'PAYMENT_EXCEEDS_AMOUNT'
