"""
Custom DRF exception handler.
Barcha xatolar JSON formatda qaytadi — frontendga tushunarli xabar bilan.
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    DRF ning standart exception_handler'ini kengaytiradi.
    Agar standart handler None qaytarsa (ya'ni DRF taniy olmagan xato),
    biz uni ushlab, JSON formatda qaytaramiz.
    """
    # 1. DRF standart handlerini chaqiramiz
    response = exception_handler(exc, context)

    if response is not None:
        # DRF o'zi handle qildi — response ni qaytaramiz
        return response

    # 2. DRF handle qilmagan xatolar — 500 HTML sahifa o'rniga JSON qaytaramiz

    # View nomini olish (logga yozish uchun)
    view = context.get('view', None)
    view_name = view.__class__.__name__ if view else 'Unknown'

    # IntegrityError — database NOT NULL, UNIQUE constraint xatolari
    if isinstance(exc, IntegrityError):
        logger.error(f"IntegrityError in {view_name}: {str(exc)}", exc_info=True)

        error_message = str(exc).lower()

        if 'not null' in error_message:
            detail = "Majburiy maydonlardan biri to'ldirilmagan. Iltimos, barcha maydonlarni tekshiring."
        elif 'unique' in error_message:
            detail = "Bunday ma'lumot allaqachon mavjud. Takroriy yozuv yaratish mumkin emas."
        else:
            detail = "Ma'lumotlar bazasida xatolik yuz berdi. Iltimos, kiritilgan ma'lumotlarni tekshiring."

        return Response(
            {"detail": detail, "error_type": "integrity_error"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Django ValidationError
    if isinstance(exc, DjangoValidationError):
        logger.error(f"Django ValidationError in {view_name}: {str(exc)}", exc_info=True)

        if hasattr(exc, 'message_dict'):
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
        elif hasattr(exc, 'messages'):
            return Response(
                {"detail": exc.messages},
                status=status.HTTP_400_BAD_REQUEST
            )
        else:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Boshqa barcha kutilmagan xatolar
    logger.error(f"Unhandled exception in {view_name}: {str(exc)}", exc_info=True)
    return Response(
        {"detail": "Serverda kutilmagan xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
