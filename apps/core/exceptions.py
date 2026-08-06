"""
Custom exception handler — DRF uchun standartlashtirilgan xato javobi.
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        errors = response.data
        # Har doim bir xil format: {success, code, message, errors}
        if isinstance(errors, dict) and 'detail' in errors:
            message = str(errors['detail'])
            errors_detail = None
        elif isinstance(errors, list):
            message = 'Validation error'
            errors_detail = errors
        else:
            message = 'An error occurred'
            errors_detail = errors

        response.data = {
            'success': False,
            'code': response.status_code,
            'message': message,
            'errors': errors_detail,
        }
    else:
        logger.exception('Unhandled exception', exc_info=exc)
        response = Response(
            {
                'success': False,
                'code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': 'Internal server error',
                'errors': None,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
