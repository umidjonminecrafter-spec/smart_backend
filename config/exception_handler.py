"""
Custom DRF exception handler.
Barcha xatolar JSON formatda qaytadi — frontendga ANIQ xato xabari bilan.
"""
import logging
import re
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError

logger = logging.getLogger(__name__)

# Maydon nomlarini o'zbek tiliga tarjima qilish lug'ati
FIELD_TRANSLATIONS = {
    'name': 'Nomi',
    'course': 'Kurs',
    'course_id': 'Kurs',
    'room': 'Xona',
    'room_id': 'Xona',
    'teacher': "O'qituvchi",
    'teacher_id': "O'qituvchi",
    'organization': 'Tashkilot',
    'organization_id': 'Tashkilot',
    'branch': 'Filial',
    'branch_id': 'Filial',
    'student': 'Talaba',
    'student_id': 'Talaba',
    'group': 'Guruh',
    'group_id': 'Guruh',
    'days': 'Dars kunlari',
    'start_time': 'Boshlanish vaqti',
    'end_time': 'Tugash vaqti',
    'start_date': 'Boshlanish sanasi',
    'end_date': 'Tugash sanasi',
    'status': 'Status',
    'education_type': "Ta'lim turi",
    'telegram_link': 'Telegram havola',
    'phone': 'Telefon raqam',
    'first_name': 'Ism',
    'last_name': 'Familiya',
    'email': 'Elektron pochta',
    'amount': 'Summa',
    'price': 'Narx',
    'date': 'Sana',
    'password': 'Parol',
    'balance': 'Balans',
}


def _get_field_name(field):
    """Maydon nomini o'zbek tiliga tarjima qiladi."""
    return FIELD_TRANSLATIONS.get(field, field)


def _parse_integrity_error(error_str):
    """
    IntegrityError xabaridan qaysi maydon xato ekanini aniqlab,
    aniq xabar qaytaradi.
    """
    error_lower = error_str.lower()

    # NOT NULL constraint failed: academics_group.course_id
    not_null_match = re.search(r'not null constraint failed:\s*\w+\.(\w+)', error_lower)
    if not_null_match:
        field = not_null_match.group(1)
        field_name = _get_field_name(field)
        return f"'{field_name}' maydoni bo'sh bo'lishi mumkin emas. Iltimos, to'ldiring."

    # UNIQUE constraint failed: table.field1, table.field2
    unique_match = re.search(r'unique constraint failed:\s*([\w.,\s]+)', error_lower)
    if unique_match:
        fields_raw = unique_match.group(1)
        fields = [_get_field_name(f.strip().split('.')[-1]) for f in fields_raw.split(',')]
        fields_str = ", ".join(fields)
        return f"Bunday {fields_str} kombinatsiyasi allaqachon mavjud. Takroriy yozuv yaratish mumkin emas."

    # FOREIGN KEY constraint — noto'g'ri ID yuborilgan
    if 'foreign key' in error_lower:
        return "Tanlangan qiymat bazada topilmadi. Iltimos, to'g'ri qiymat tanlang."

    # CHECK constraint
    if 'check constraint' in error_lower:
        return "Kiritilgan qiymat ruxsat etilgan chegaradan tashqarida."

    return f"Ma'lumotlar bazasida xatolik: {error_str}"


def custom_exception_handler(exc, context):
    """
    DRF ning standart exception_handler'ini kengaytiradi.
    Barcha xatolar JSON formatda, ANIQ xabar bilan qaytadi.
    """
    # 1. DRF standart handlerini chaqiramiz
    response = exception_handler(exc, context)

    if response is not None:
        # DRF o'zi handle qildi — response ni qaytaramiz
        return response

    # 2. DRF handle qilmagan xatolar — 500 HTML sahifa o'rniga JSON qaytaramiz

    view = context.get('view', None)
    view_name = view.__class__.__name__ if view else 'Unknown'

    # IntegrityError — database constraint xatolari
    if isinstance(exc, IntegrityError):
        logger.error(f"IntegrityError in {view_name}: {str(exc)}", exc_info=True)
        detail = _parse_integrity_error(str(exc))
        return Response(
            {"detail": detail},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Django ValidationError
    if isinstance(exc, DjangoValidationError):
        logger.error(f"Django ValidationError in {view_name}: {str(exc)}", exc_info=True)

        if hasattr(exc, 'message_dict'):
            # Maydon nomlarini tarjima qilamiz
            translated = {}
            for field, messages in exc.message_dict.items():
                translated_field = _get_field_name(field)
                translated[translated_field] = messages
            return Response(translated, status=status.HTTP_400_BAD_REQUEST)
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

    # ValueError — noto'g'ri qiymat yuborilganda
    if isinstance(exc, ValueError):
        logger.error(f"ValueError in {view_name}: {str(exc)}", exc_info=True)
        return Response(
            {"detail": f"Noto'g'ri qiymat yuborildi: {str(exc)}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # TypeError — noto'g'ri tip yuborilganda
    if isinstance(exc, TypeError):
        logger.error(f"TypeError in {view_name}: {str(exc)}", exc_info=True)
        return Response(
            {"detail": f"Noto'g'ri ma'lumot turi yuborildi: {str(exc)}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Boshqa barcha kutilmagan xatolar
    logger.error(f"Unhandled exception in {view_name}: {type(exc).__name__}: {str(exc)}", exc_info=True)
    return Response(
        {"detail": f"Serverda xatolik yuz berdi: {str(exc)}"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
