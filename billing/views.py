import datetime
from decimal import Decimal, InvalidOperation

from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from billing.models import BillingHistory, BalanceTopUp, TariffPurchase, SubscriptionRequest
from billing.serializers import BillingHistorySerializer, BalanceTopUpSerializer, TariffPurchaseSerializer
from organizations.models import Subscription, Tariff
from organizations.serializers import TariffSerializer


def add_months(start_date, months):
    total_months = start_date.month + months - 1
    year = start_date.year + (total_months // 12)
    month = (total_months % 12) + 1
    day = min(start_date.day, 28)
    return datetime.date(year, month, day)


class BillingPlansView(APIView):
    """Barcha tariflarni ko'rsatadi"""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        tariffs = Tariff.objects.all()
        serializer = TariffSerializer(tariffs, many=True)
        return Response(serializer.data)


class BillingCurrentView(APIView):
    """Hozirgi balance va tarif holati"""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        org = getattr(request.user, 'organization', None)
        if not org:
            return Response({"balance": 0, "no_subscription": True})

        today = datetime.date.today()
        subscription = Subscription.objects.filter(organization=org).first()
        if not subscription:
            return Response({"balance": 0, "no_subscription": True})

        # Muddati o'tgan bo'lsa o'chirish
        if subscription.is_active and subscription.end_date < today:
            subscription.is_active = False
            subscription.save(update_fields=['is_active'])

        days_left = (subscription.end_date - today).days

        return Response({
            "balance": subscription.balance,
            "tariff": TariffSerializer(subscription.tariff).data if subscription.tariff else None,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "is_active": subscription.is_active,
            "days_left": max(days_left, 0),
            "expires_soon": 0 <= days_left <= 7,
            "expired": days_left < 0 or not subscription.is_active,
        })


class BillingHistoryView(APIView):
    """To'lov tarixi"""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        org = getattr(request.user, 'organization', None)
        if not org:
            return Response([])
        history = BillingHistory.objects.filter(organization=org).order_by('-created_at')
        return Response(BillingHistorySerializer(history, many=True).data)


class BalanceTopUpView(APIView):
    """Balance yuklash — cheksiz"""
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        org = getattr(request.user, 'organization', None)
        if not org:
            return Response({"detail": "Tashkilot topilmadi."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(request.data.get('amount', 0)))
            if amount <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            return Response({"detail": "Summa musbat bo'lishi kerak."}, status=status.HTTP_400_BAD_REQUEST)

        # Subscriptionni topish yoki yaratish
        subscription, _ = Subscription.objects.get_or_create(
            organization=org,
            defaults={
                'start_date': datetime.date.today(),
                'end_date': datetime.date.today(),
                'is_active': False,
                'balance': Decimal("0.00"),
            }
        )

        # Balancega qo'shish — cheksiz
        subscription.balance += amount
        subscription.save(update_fields=['balance'])

        # Tarix saqlash
        BalanceTopUp.objects.create(
            organization=org,
            amount=amount,
            comment=request.data.get('comment', '')
        )

        return Response({
            "detail": "Balance muvaffaqiyatli yuklandi.",
            "added": amount,
            "balance": subscription.balance,
        })


class SubscribePreviewView(APIView):
    """
    Tarif sotib olishdan OLDIN eslatma ko'rsatadi.
    Balancedan yechmaydi — faqat ma'lumot beradi.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        org = getattr(request.user, 'organization', None)
        if not org:
            return Response({"detail": "Tashkilot topilmadi."}, status=status.HTTP_400_BAD_REQUEST)

        tariff_id = request.data.get('tariff_id')
        if not tariff_id:
            return Response({"detail": "tariff_id majburiy."}, status=status.HTTP_400_BAD_REQUEST)

        tariff = Tariff.objects.filter(id=tariff_id).first()
        if not tariff:
            return Response({"detail": "Tarif topilmadi."}, status=status.HTTP_400_BAD_REQUEST)

        subscription = Subscription.objects.filter(organization=org).first()
        balance = subscription.balance if subscription else Decimal("0.00")
        price = tariff.final_price
        enough = balance >= price

        today = datetime.date.today()
        charge_date = add_months(today, tariff.months)

        return Response({
            "tariff": TariffSerializer(tariff).data,
            "price": price,
            "balance": balance,
            "balance_after": balance - price if enough else None,
            "enough_balance": enough,
            "charge_date": charge_date,  # keyingi yechish sanasi
            "warning": None if enough else f"Balancingiz yetarli emas. Kerak: {price}, Mavjud: {balance}",
            "confirm_message": f"Balancingizdan {price} UZS yechiladi. Tasdiqlaysizmi?" if enough else None,
        })


class SubscribeConfirmView(APIView):
    """
    Foydalanuvchi tasdiqlagan — balancedan yechadi va subscriptionni yangilaydi.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        org = getattr(request.user, 'organization', None)
        if not org:
            return Response({"detail": "Tashkilot topilmadi."}, status=status.HTTP_400_BAD_REQUEST)

        tariff_id = request.data.get('tariff_id')
        if not tariff_id:
            return Response({"detail": "tariff_id majburiy."}, status=status.HTTP_400_BAD_REQUEST)

        tariff = Tariff.objects.filter(id=tariff_id).first()
        if not tariff:
            return Response({"detail": "Tarif topilmadi."}, status=status.HTTP_400_BAD_REQUEST)

        subscription, _ = Subscription.objects.get_or_create(
            organization=org,
            defaults={
                'start_date': datetime.date.today(),
                'end_date': datetime.date.today(),
                'is_active': False,
                'balance': Decimal("0.00"),
            }
        )

        price = tariff.final_price

        # Balance yetarlimi?
        if subscription.balance < price:
            return Response({
                "detail": "Mablag' yetarli emas.",
                "required": price,
                "balance": subscription.balance,
                "missing": price - subscription.balance,
            }, status=status.HTTP_400_BAD_REQUEST)

        today = datetime.date.today()

        # Subscription yangilash
        if subscription.is_active and subscription.end_date >= today:
            start = subscription.end_date  # muddatga qo'shiladi
        else:
            start = today

        end = add_months(start, tariff.months)
        next_charge = end  # keyingi yechish sanasi

        # Balancedan yechish
        subscription.balance -= price
        subscription.tariff = tariff
        subscription.start_date = start
        subscription.end_date = end
        subscription.is_active = True
        subscription.save()

        # TariffPurchase saqlash
        TariffPurchase.objects.create(
            organization=org,
            tariff=tariff,
            amount=price,
            start_date=start,
            next_charge_date=next_charge,
            is_active=True,
        )

        # BillingHistory saqlash
        BillingHistory.objects.create(
            organization=org,
            amount=price,
            plan_name=tariff.name,
            months=tariff.months,
        )

        return Response({
            "detail": "Tarif muvaffaqiyatli faollashtirildi.",
            "tariff": tariff.name,
            "deducted": price,
            "balance": subscription.balance,
            "start_date": start,
            "end_date": end,
            "next_charge_date": next_charge,
        })


class BillingPayView(APIView):
    """Tarif sotib olish so'rovini yuboradi (Django Adminda tasdiqlash uchun)"""
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        org = getattr(request.user, 'organization', None)
        if not org:
            return Response({"detail": "Tashkilot topilmadi."}, status=status.HTTP_400_BAD_REQUEST)

        tariff_id = request.data.get('tariff_id')
        plan_name = request.data.get('plan')
        try:
            months = int(request.data.get('months', 1))
            if months <= 0:
                raise ValueError()
        except ValueError:
            return Response({"detail": "Months must be a positive integer."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(request.data.get('amount', 0)))
            if amount < 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            return Response({"detail": "Amount must be a positive decimal."}, status=status.HTTP_400_BAD_REQUEST)

        # Tarifni topish: avval tariff_id bo'yicha, keyin nom bo'yicha
        tariff = None
        if tariff_id:
            tariff = Tariff.objects.filter(id=tariff_id).first()
        if not tariff and plan_name:
            tariff = Tariff.objects.filter(name__iexact=plan_name, months=months).first()
            if not tariff:
                tariff = Tariff.objects.filter(name__iexact=plan_name).first()

        if not tariff:
            return Response({"detail": "Tarif rejasi topilmadi."}, status=status.HTTP_400_BAD_REQUEST)

        # Allaqachon pending so'rov borligini tekshirish
        existing_pending = SubscriptionRequest.objects.filter(
            organization=org,
            status='pending'
        ).first()
        if existing_pending:
            return Response({
                "status": "warning",
                "detail": "Sizda allaqachon ko'rib chiqilayotgan so'rov mavjud. Iltimos, javobini kuting."
            }, status=status.HTTP_400_BAD_REQUEST)

        # SubscriptionRequest yaratish (tasdiqlash kutayotgan so'rov)
        sub_request = SubscriptionRequest.objects.create(
            organization=org,
            tariff=tariff,
            months=months,
            amount=amount,
            status='pending',
            comment=f"Foydalanuvchi tomonidan tanlangan: {tariff.name} ({months} oy)"
        )

        return Response({
            "status": "success",
            "detail": "Obunani faollashtirish so'rovi qabul qilindi. Tez orada sotuvchilarimiz siz bilan bog'lanishadi.",
            "request_id": sub_request.id,
        }, status=status.HTTP_201_CREATED)


class SubscriptionRequestListView(APIView):
    """Foydalanuvchi o'z tashkilotining obuna so'rovlarini ko'radi"""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        org = getattr(request.user, 'organization', None)
        if not org:
            return Response([])
        requests = SubscriptionRequest.objects.filter(
            organization=org
        ).select_related('tariff').order_by('-created_at')
        data = []
        for req in requests:
            data.append({
                "id": req.id,
                "tariff_name": req.tariff.name if req.tariff else "-",
                "months": req.months,
                "amount": str(req.amount),
                "status": req.status,
                "status_display": req.get_status_display(),
                "comment": req.comment or "",
                "created_at": req.created_at.isoformat() if req.created_at else "",
            })
        return Response(data)