from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from organizations.mixins import TenantViewSetMixin
from organizations.permissions import IsAdminOrOwnerOrReadOnly
from crm.models import Pipeline, Source, LostReason, Section, LeadForm, Lead
from crm.serializers import (
    PipelineSerializer, SourceSerializer, LostReasonSerializer,
    SectionSerializer, LeadFormSerializer, LeadSerializer
)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Lead, CRMLeadsHistory
from .serializers import CRMLeadHistorySerializer
class PipelineViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Lidlar'
    queryset = Pipeline.objects.all()
    serializer_class = PipelineSerializer

    def destroy(self, request, *args, **kwargs):
        pipeline = self.get_object()
        # Check if there are active (not won/lost/archived) leads in this pipeline
        if pipeline.leads.filter(is_archived=False).exists():
            return Response({"detail": "Naborda faol lidlar mavjudligi sababli uni o'chirish mumkin emas. Avval lidlarni boshqa naborga o'tkazing yoki arxivlang."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

class SourceViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Lidlar'
    queryset = Source.objects.all()
    serializer_class = SourceSerializer

class LostReasonViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Lidlar'
    queryset = LostReason.objects.all()
    serializer_class = LostReasonSerializer

class SectionViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Lidlar'
    queryset = Section.objects.all()
    serializer_class = SectionSerializer

    def destroy(self, request, *args, **kwargs):
        section = self.get_object()
        if section.leads.filter(is_archived=False).exists():
            return Response({"detail": "Ustunda faol lidlar mavjudligi sababli uni o'chirish mumkin emas. Avval lidlarni boshqa ustunga o'tkazing yoki arxivlang."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

class LeadFormViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Lidlar'
    queryset = LeadForm.objects.all()
    serializer_class = LeadFormSerializer

from rest_framework import status
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.decorators import action

class LeadViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Lidlar'
    serializer_class = LeadSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['pipeline', 'source', 'status']
    search_fields = ['name', 'phone', 'email']

    def perform_create(self, serializer):
        org_id = self.get_organization_id()
        if not org_id:
            from rest_framework import exceptions
            raise exceptions.ValidationError({"detail": "Organization context is required."})

        kwargs = {'organization_id': org_id}
        if self.request.user and self.request.user.is_authenticated:
            kwargs['created_by'] = self.request.user

        branch_id = self.get_branch_id()
        if branch_id:
            kwargs['branch_id'] = branch_id

        serializer.save(**kwargs)

    def get_queryset(self):
        org_id = self.get_organization_id()
        if not org_id:
            return Lead.objects.none()

        from django.db.models import Q
        branch_id = self.get_branch_id()

        # select_related orqali barcha bog'liqliklar bitta SQL JOINda olinadi
        queryset = Lead.objects.filter(organization_id=org_id).select_related(
            'pipeline', 'source', 'section', 'lost_reason', 'created_by'
        )

        # Branch filtri
        if branch_id:
            queryset = queryset.filter(Q(branch_id=branch_id) | Q(branch__isnull=True))

        if self.action == 'archived':
            return queryset.filter(is_archived=True)

        if self.action in ['destroy', 'retrieve', 'partial_update', 'update']:
            return queryset

        queryset = queryset.filter(is_archived=False)

        section_param = self.request.query_params.get('section')
        if section_param is not None:
            if section_param in ['null', 'None', '']:
                queryset = queryset.filter(section__isnull=True)
            else:
                queryset = queryset.filter(section_id=section_param)
                
        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_archived:
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            reason = request.query_params.get('reason') or request.data.get('reason') or "O'chirilgan"
            instance.is_archived = True
            instance.archive_reason = reason
            instance.archive_date = timezone.now()
            instance.archived_by = request.user.get_full_name() or request.user.username
            instance.save(update_fields=['is_archived', 'archive_reason', 'archive_date', 'archived_by'])
            return Response({"detail": "Lead archived successfully.", "id": instance.id}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='archived')
    def archived(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        leads_data = request.data.get('leads', [])
        if not isinstance(leads_data, list):
            return Response({"detail": "Leads must be a list"}, status=status.HTTP_400_BAD_REQUEST)
            
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)

        branch_id = self.get_branch_id()

        success_count = 0
        failed_count = 0
        errors = []
        
        for idx, item in enumerate(leads_data):
            row_num = item.get('row', idx + 1)
            # Use serializer to validate
            serializer = self.get_serializer(data=item)
            if serializer.is_valid():
                try:
                    kwargs = {'organization_id': org_id}
                    if request.user and request.user.is_authenticated:
                        kwargs['created_by'] = request.user
                    if branch_id:
                        kwargs['branch_id'] = branch_id
                    serializer.save(**kwargs)
                    success_count += 1
                except Exception as e:
                    failed_count += 1
                    errors.append({
                        "row": row_num,
                        "name": item.get('name', item.get('full_name', '')),
                        "detail": str(e)
                    })
            else:
                failed_count += 1
                # Format validation errors
                err_msg = ""
                for field, msgs in serializer.errors.items():
                    err_msg += f"{field}: {', '.join([str(m) for m in msgs])}; "
                errors.append({
                    "row": row_num,
                    "name": item.get('name', item.get('full_name', '')),
                    "detail": err_msg
                })
                
        return Response({
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": errors
        }, status=status.HTTP_200_OK)


from rest_framework import mixins

class CreateListRetrieveViewSet(mixins.CreateModelMixin,
                                mixins.ListModelMixin,
                                mixins.RetrieveModelMixin,
                                viewsets.GenericViewSet):
    """
    Ruxsatnomalarga ko'ra faqat yaratish, ro'yxatni olish va bittalik ko'rishga 
    ruxsat beruvchi, lekin tahrirlash (update) va o'chirishni (delete) cheklovchi maxsus ViewSet.
    """
    pass

from crm.models import CRMActivity, CRMLeadsHistory, CRMLeadLost
from crm.serializers import CRMActivitySerializer, CRMLeadsHistorySerializer, CRMLeadLostSerializer

class CRMActivityViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Lidlar'
    queryset = CRMActivity.objects.all()
    serializer_class = CRMActivitySerializer


class LeadHistoryAPIView(APIView):
    """
    Muayyan lidning tarixini (o'zgarishlar xronologiyasini) olib beruvchi API
    """

    def get(self, request):
        lead_id = request.query_params.get('lead_id')

        if not lead_id:
            return Response(
                {"error": "lead_id parametri yuborilishi majburiy!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Lid mavjudligini tekshiramiz
            lead = Lead.objects.get(id=lead_id)

            # Shunga tegishli tarixlarni vaqt bo'yicha eng yangisini tepaga saralab olamiz
            history = CRMLeadsHistory.objects.filter(lead=lead).order_by('-created_at')

            serializer = CRMLeadsHistorySerializer(history, many=True)

            return Response({
                "lead_id": lead.id,
                "lead_name": lead.name,
                "history": serializer.data
            }, status=status.HTTP_200_OK)

        except Lead.DoesNotExist:
            return Response(
                {"error": "Lid topilmadi!"},
                status=status.HTTP_404_NOT_FOUND
            )

class CRMLeadLostViewSet(TenantViewSetMixin, CreateListRetrieveViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Lidlar'
    queryset = CRMLeadLost.objects.all()
    serializer_class = CRMLeadLostSerializer


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from academics.models import BotMessageTemplate, Student
from crm.models import Lead, Section
from .serializers import SMSBotTemplateSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


# ================= 1. SHABLONLAR USTIDA CRUD (KORISH, QOSHISH, TAHRIRLASH, OCHIRISH) =================
class SMSTemplateListCreateAPIView(generics.ListCreateAPIView):
    """SMS shablonlarni ko'rish (Auditoriya bo'yicha filterlangan holda) va yangi qo'shish"""
    serializer_class = SMSBotTemplateSerializer

    def get_queryset(self):
        # /api/v1/crm/sms-templates/?audience=leads (yoki students, staff) deb filterlash uchun
        queryset = BotMessageTemplate.objects.all()
        audience = self.request.query_params.get('audience')
        if audience:
            queryset = queryset.filter(target_audience=audience)
        return queryset


class SMSTemplateRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Shablonni tahrirlash (Edit) va O'chirish (Delete) API-si"""
    queryset = BotMessageTemplate.objects.all()
    serializer_class = SMSBotTemplateSerializer


# ================= 2. BARCHAGA BIR VAQTDA KATEGORIYA BOYICHA SMS YUBORISH APISI =================
class SendBulkSMSAPIView(APIView):
    """
    Rasmda ko'rsatilgan 'SMS yuborish' tugmasi.
    Kategoriya (Section), Guruh yoki butun Auditoriyaga birdaniga SMS/Telegram xabar yuboradi.
    """

    def post(self, request):
        target = request.data.get('target')  # 'leads', 'students', 'staff'
        section_id = request.data.get('section_id')  # Agar 'leads' tanlansa, qaysi kanyatener (Section) id-si
        shablon_id = request.data.get('template_id')  # Tanlangan tayyor shablon IDsi (ixtiyoriy)
        custom_text = request.data.get('text')  # Qo'lda yozilgan matn (shablon tanlanmasa)

        if not target:
            return Response({"error": "target (leads, students, staff) yuborilishi majburiy!"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Xabar matnini aniqlab olamiz
        msg_text = custom_text
        if shablon_id:
            try:
                shablon = BotMessageTemplate.objects.get(id=shablon_id)
                msg_text = shablon.text
            except BotMessageTemplate.DoesNotExist:
                return Response({"error": "Tanlangan shablon topilmadi!"}, status=status.HTTP_404_NOT_FOUND)

        if not msg_text:
            return Response({"error": "Xabar matni bo'sh bo'lishi mumkin emas!"}, status=status.HTTP_400_BAD_REQUEST)

        # Kimlarga xabar ketishini aniqlaymiz (Auditoriya va Section bo'yicha filter)
        recipients = []

        if target == 'leads':
            leads_query = Lead.objects.filter(is_archived=False)
            if section_id:
                leads_query = leads_query.filter(section_id=section_id)  # Maxsus Section filteri

            for lead in leads_query:
                # Lid modellarida chat_id yo'qligi uchun uning telefoniga (SMS provayder orqali) xabar ketadi deb hisoblaymiz
                recipients.append({
                    "name": lead.name,
                    "phone": lead.phone,
                    "chat_id": None,
                    "context": {"{first_name}": lead.name, "{section_name}": lead.section.name if lead.section else ""}
                })

        elif target == 'students':
            students_query = Student.objects.all()
            for student in students_query:
                recipients.append({
                    "name": student.first_name,
                    "phone": student.phone,
                    "chat_id": student.telegram_chat_id,
                    "context": {"{first_name}": student.first_name, "{balance}": str(student.balance)}
                })

        elif target == 'staff':
            staff_query = User.objects.filter(is_active=True)
            for member in staff_query:
                # Xodimlarning telegram chat_id si bor deb hisoblaymiz
                chat_id = getattr(member, 'telegram_chat_id', None)
                recipients.append({
                    "name": member.get_full_name() or member.username,
                    "phone": getattr(member, 'phone', ''),
                    "chat_id": chat_id,
                    "context": {"{first_name}": member.username}
                })

        # 🚀 XABARLARNI ETKAZIB BERISH SIKLI (MASS DISPATCH)
        sent_count = 0
        for r in recipients:
            # Matndagi o'zgaruvchilarni dinamik almashtiramiz
            final_text = msg_text
            for placeholder, value in r['context'].items():
                final_text = final_text.replace(placeholder, value)

            # AGAR TELEGRAM CHAT_ID BO'LSA - TELEGRAMGA OTADI
            if r['chat_id']:
                try:
                    # Bu yerda sizning bot tokeningiz bo'ladi
                    token = "YOUR_BOT_TOKEN_HERE"
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    requests.post(url, json={'chat_id': r['chat_id'], 'text': final_text, 'parse_mode': 'HTML'},
                                  timeout=3)
                    sent_count += 1
                except Exception:
                    pass
            # CHAT ID BO'LMASA YOKI LID BO'LSA - SMS XABAR BORADI (Masalan, Eskiz SMS API orqali)
            else:
                # Logikangizga qarab shu yerda SMS gateway (Eskiz, PlayMobile) chaqiriladi
                print(f"SMS SEND TO {r['phone']}: {final_text}")
                sent_count += 1

        return Response({
            "message": "Ommaviy xabarlar muvaffaqiyatli jo'natildi!",
            "total_recipients": len(recipients),
            "successfully_sent": sent_count
        }, status=status.HTTP_200_OK)
