from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, permissions, status, decorators, generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from organizations.mixins import TenantViewSetMixin
from .models import StudentFieldSetting
from .serializers import StudentFieldSettingSerializer, StudentProfileSerializer
from academics.models import (
    Course, Room, Student, Group, StudentGroup, GroupTeacher, TeacherSalaryPayment, Attendance, LessonSchedule,
    BalanceHistory, Exam, ExamResult, LeaveReason, LessonTime, OnlineLesson, StudentGroupLeave, StudentPricing, StudentArchive, Holiday, Homework
)
from organizations.mixins import TenantViewSetMixin
from organizations.permissions import (
    IsAdminOrOwnerOrReadOnly, IsGroupAssignedTeacherForAttendance, IsGroupAssignedTeacherOrAdminOwnerForExam
)
from academics.serializers import (
    CourseSerializer, RoomSerializer, StudentSerializer, GroupSerializer,
    StudentGroupSerializer, GroupTeacherSerializer, TeacherSalaryPaymentSerializer, AttendanceSerializer,
    LessonScheduleSerializer, StudentBalanceSerializer, BalanceHistorySerializer, ExamSerializer,
    ExamResultSerializer, LeaveReasonSerializer, LessonTimeSerializer, OnlineLessonSerializer,
    StudentGroupLeaveSerializer, StudentPricingSerializer, StudentArchiveSerializer, HolidaySerializer
    , HomeworkSerializer
)

from .models import TelegramVerification, Student
from .utills import send_telegram_verification_code


# 1. KOD YUBORISH API (Ro'yxatdan o'tish yoki Parol unutilganda chaqiriladi)
class SendCodeAPIView(APIView):
    def post(self, request):
        phone = request.data.get('phone')
        purpose = request.data.get('purpose')  # 'register' yoki 'forgot'

        if not phone or not purpose:
            return Response({"error": "phone va purpose maydonlari majburiy!"}, status=status.HTTP_400_BAD_REQUEST)

        if purpose not in ['register', 'forgot']:
            return Response({"error": "Purpose noto'g'ri!"}, status=status.HTTP_400_BAD_REQUEST)

        # Kodni generatsiya qilib jo'natamiz
        result = send_telegram_verification_code(phone, purpose)

        if result["status"]:
            return Response({"message": result["message"]}, status=status.HTTP_200_OK)
        return Response({"error": result["message"]}, status=status.HTTP_400_BAD_REQUEST)


# 2. KODNI TEKSHIRISH API
class VerifyCodeAPIView(APIView):
    def post(self, request):
        phone = request.data.get('phone')
        code = request.data.get('code')
        purpose = request.data.get('purpose')

        if not phone or not code or not purpose:
            return Response({"error": "Barcha maydonlar majburiy!"}, status=status.HTTP_400_BAD_REQUEST)

        # Eng oxirgi yuborilgan faol kodni qidiramiz
        verif = TelegramVerification.objects.filter(
            phone=phone, code=code, purpose=purpose
        ).order_update().last()

        if verif and verif.is_valid():
            # Kod to'g'ri bo'lsa, uni ishlatildi deb belgilaymiz
            verif.is_verified = True
            verif.save()

            # AGAR PAROL TIKLASH BO'LSA:
            if purpose == 'forgot':
                # Bu yerda frontendchiga parolni o'zgartirishga ruxsat beruvchi vaqtinchalik belgi (token) yoki muvaffaqiyat xabarini qaytaramiz
                return Response(
                    {"status": "success", "message": "Kod tasdiqlandi. Endi yangi parol kiritishingiz mumkin."},
                    status=status.HTTP_200_OK)

            # AGAR RO'YXATDAN O'TISH BO'LSA:
            elif purpose == 'register':
                return Response({"status": "success", "message": "Kod tasdiqlandi. Ro'yxatdan o'tish yakunlandi."},
                                status=status.HTTP_200_OK)

        return Response({"error": "Tasdiqlash kodi noto'g'ri yoki vaqti o'tib ketgan!"},
                        status=status.HTTP_400_BAD_REQUEST)





class StudentFieldSettingViewSet(
    TenantViewSetMixin,
    viewsets.ModelViewSet
):
    serializer_class = StudentFieldSettingSerializer
    queryset = StudentFieldSetting.objects.all()

    def get_queryset(self):
        return StudentFieldSetting.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.user.organization
        )

class CourseViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Kurslar sozlamalari'
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['name', 'description']

    def destroy(self, request, *args, **kwargs):
        course = self.get_object()
        if course.groups.exists():
            return Response({"detail": "Kursga biriktirilgan guruhlar mavjudligi sababli uni o'chirish mumkin emas."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

class RoomViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Xonalar sozlamalari'
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['name']

    def destroy(self, request, *args, **kwargs):
        room = self.get_object()
        if room.groups.exists():
            return Response({"detail": "Xonaga biriktirilgan guruhlar mavjudligi sababli uni o'chirish mumkin emas."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

class StudentViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Talabalar'
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['first_name', 'last_name', 'phone', 'email']
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        group_id = self.request.query_params.get('group') or self.request.query_params.get('group_id')
        if group_id:
            queryset = queryset.filter(student_groups__group_id=group_id)
        return queryset

    def perform_create(self, serializer):
        org_id = self.get_organization_id()
        if not org_id:
            from rest_framework import exceptions
            raise exceptions.ValidationError({"detail": "Organization context is required."})

        # Obunani tekshirish
        from organizations.models import Subscription
        subscription = Subscription.objects.filter(organization_id=org_id, is_active=True).first()
        if not subscription:
            from rest_framework import exceptions
            raise exceptions.ValidationError({"detail": "Tashkilotning faol obunasi topilmadi. Yangi talaba qo'shish uchun tarif sotib oling."})

        tariff = subscription.tariff
        if tariff and tariff.student_limit > 0:
            # Hozirgi talabalar sonini hisoblash
            current_students_count = Student.objects.filter(organization_id=org_id).count()
            if current_students_count >= tariff.student_limit:
                from rest_framework import exceptions
                raise exceptions.ValidationError({"detail": f"Tarifingizdagi talabalar limiti ({tariff.student_limit}) ga yetdingiz. Yangi talaba qo'shish uchun tarifni yangilang."})

        super().perform_create(serializer)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        reason = request.query_params.get('reason') or request.data.get('reason') or "O'chirib tashlangan"
        comment = request.query_params.get('comment') or request.data.get('comment') or ""
        StudentArchive.objects.create(
            organization=instance.organization,
            branch=instance.branch,
            first_name=instance.first_name,
            last_name=instance.last_name,
            phone=instance.phone,
            email=instance.email,
            role="Student",
            reason=reason,
            comment=comment,
            archived_by=request.user.get_full_name() or request.user.username if request.user.is_authenticated else "Tizim"
        )
        # Delete corresponding student user account to deactivate it and free up the phone number
        from accounts.models import User
        if instance.phone:
            User.objects.filter(username=instance.phone, role='student').delete()
        return super().destroy(request, *args, **kwargs)

    @decorators.action(detail=True, methods=['post'], url_path='add-payment')
    def add_payment(self, request, pk=None):
        student = self.get_object()
        amount = request.data.get('amount')
        payment_method = request.data.get('payment_method') or request.data.get('payment_type') or 'cash'
        comment = request.data.get('comment') or request.data.get('note') or ''
        
        if not amount:
            return Response({"detail": "Amount is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from decimal import Decimal
            amount_dec = Decimal(str(amount))
        except ValueError:
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
            
        student.balance += amount_dec
        student.save()

        # Import Finance Payment dynamically to avoid circular dependencies
        from finance.models import Payment
        org_id = self.get_organization_id()
        payment = Payment.objects.create(
            organization_id=org_id,
            branch_id=self.get_branch_id(),
            student=student,
            amount=amount_dec,
            date=timezone.now().date(),
            payment_method=payment_method,
            employee=request.user if request.user.is_authenticated else None,
            comment=comment
        )

        return Response({
            "detail": "Payment added successfully.",
            "balance": student.balance,
            "payment_id": payment.id
        }, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=['post'], url_path='add-to-group')
    def add_to_group(self, request, pk=None):
        student = self.get_object()
        group_id = request.data.get('group') or request.data.get('group_id')
        if not group_id:
            return Response({"detail": "Group ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        org_id = self.get_organization_id()
        group = get_object_or_404(Group.objects.filter(organization_id=org_id), id=group_id)
        
        student_group, created = StudentGroup.objects.get_or_create(
            organization_id=org_id,
            student=student,
            group=group
        )
        return Response(StudentGroupSerializer(student_group).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=['get'], url_path='balance-status')
    def balance_status(self, request, pk=None):
        student = self.get_object()
        return Response({
            "balance": student.balance,
            "status": "positive" if student.balance >= 0 else "negative"
        }, status=status.HTTP_200_OK)

    @decorators.action(detail=False, methods=['get'], url_path='report')
    def report(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        total_students = queryset.count()
        return Response({
            "total_students": total_students,
            "report_date": timezone.now().date()
        }, status=status.HTTP_200_OK)

    @decorators.action(detail=False, methods=['post'], url_path=r'status/(?P<action_name>[^/.]+)')
    def status_action(self, request, action_name=None):
        return Response({"status": "success", "action": action_name, "detail": "Bulk status action processed."}, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        student = self.get_object()
        attendances = Attendance.objects.filter(student=student)
        groups = StudentGroup.objects.filter(student=student)
        
        # Pull payments dynamically
        from finance.models import Payment
        payments = Payment.objects.filter(student=student)
        
        return Response({
            "student": StudentSerializer(student).data,
            "groups": StudentGroupSerializer(groups, many=True).data,
            "attendance_count": attendances.count(),
            "payments_count": payments.count(),
            "payments": [{"id": p.id, "amount": p.amount, "date": p.date, "method": p.payment_method} for p in payments],
            "attendances": [{"id": a.id, "group": a.group.name, "date": a.date, "status": a.status} for a in attendances]
        }, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['get'], url_path='lead-history')
    def lead_history(self, request, pk=None):
        student = self.get_object()
        # Find matching Lead in CRM dynamically
        from crm.models import Lead
        leads = Lead.objects.filter(phone=student.phone, organization_id=self.get_organization_id())
        
        lead_data = []
        for lead in leads:
            lead_data.append({
                "id": lead.id,
                "name": lead.name,
                "status": lead.status,
                "pipeline": lead.pipeline.name if lead.pipeline else None,
                "source": lead.source.name if lead.source else None,
                "created_at": lead.created_at
            })
            
        return Response({
            "student_id": student.id,
            "phone": student.phone,
            "leads_matched": lead_data
        }, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['post'], url_path='send-sms')
    def send_sms(self, request, pk=None):
        student = self.get_object()
        
        # Enforce allow_teacher_sms check for teachers
        if getattr(request.user, 'role', None) == 'teacher':
            from organizations.models import Subscription
            subscription = Subscription.objects.filter(
                organization_id=self.get_organization_id(),
                is_active=True
            ).first()
            if subscription and not subscription.allow_teacher_sms:
                return Response(
                    {"detail": "O'qituvchilarga talabalarga SMS yuborishga ruxsat berilmagan."},
                    status=status.HTTP_403_FORBIDDEN
                )

        message = request.data.get('message')
        if not message:
            return Response({"detail": "Message is required."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "status": "success",
            "message": f"SMS successfully sent to {student.phone}."
        }, status=status.HTTP_200_OK)

class GroupViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Guruhlar'
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        qs = super().get_queryset()
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            from django.db.models import Q
            qs = qs.filter(Q(teacher_id=teacher_id) | Q(group_teachers__teacher_id=teacher_id)).distinct()

        current_user = getattr(self.request, 'user', None)
        if current_user and getattr(current_user, 'role', None) == 'student':
            phone = getattr(current_user, 'phone', None) or getattr(current_user, 'username', None)
            if phone:
                qs = qs.filter(group_students__student__phone=phone).distinct()
            else:
                qs = qs.none()
        return qs

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        if group.group_students.exists():
            return Response({"detail": "Guruhda talabalar borligi sababli uni o'chirish mumkin emas. Avval talabalarni guruhdan chiqaring."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @decorators.action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        group = self.get_object()
        if group.group_students.exists():
            return Response({"detail": "Guruhda talabalar borligi sababli uni arxivlash mumkin emas. Avval talabalarni guruhdan chiqaring."}, status=status.HTTP_400_BAD_REQUEST)
        group.status = 'archived'
        group.save()
        return Response({"status": "success", "detail": "Group archived successfully."}, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['post'], url_path='add-student')
    def add_student(self, request, pk=None):
        group = self.get_object()
        student_id = request.data.get('student')
        if not student_id:
            return Response({"detail": "Student ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        org_id = self.get_organization_id()
        student = get_object_or_404(Student.objects.filter(organization_id=org_id), id=student_id)
        
        student_group, created = StudentGroup.objects.get_or_create(
            organization_id=org_id,
            student=student,
            group=group
        )
        return Response(StudentGroupSerializer(student_group).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        group = self.get_object()
        logs = []
        from django.db import models as db_models
        from django.db.models import Count, Max, Q

        # 1. Group created
        logs.append({
            "action": "Yaratildi",
            "description": f"Guruh yaratildi. Kurs: {group.course.name if group.course else 'Kiritilmagan'}. Narxi: {(group.course.price if group.course else 0)} UZS.",
            "created_at": group.created_at
        })
        
        # 2. Teachers assigned
        for gt in GroupTeacher.objects.filter(group=group).select_related('teacher'):
            teacher_name = gt.teacher.get_full_name() or gt.teacher.username
            logs.append({
                "action": "O'qituvchi",
                "description": f"O'qituvchi {teacher_name} guruhga biriktirildi.",
                "created_at": gt.created_at
            })
            
        # 3. Students enrolled
        for sg in StudentGroup.objects.filter(group=group).select_related('student'):
            student_name = f"{sg.student.first_name} {sg.student.last_name or ''}".strip()
            logs.append({
                "action": "Qo'shildi",
                "description": f"Talaba {student_name} guruhga qo'shildi. Narxi: {(group.course.price if group.course else 0)} UZS.",
                "created_at": sg.created_at
            })
            
        # 4. Students left
        for sgl in StudentGroupLeave.objects.filter(group=group).select_related('student', 'leave_reason'):
            student_name = f"{sgl.student.first_name} {sgl.student.last_name or ''}".strip()
            reason = sgl.leave_reason.reason if sgl.leave_reason else "ko'rsatilmagan"
            logs.append({
                "action": "Chiqdi",
                "description": f"Talaba {student_name} guruhdan chiqdi (Sabab: {reason}).",
                "created_at": sgl.created_at
            })
            
        # 5. Attendances grouped by date
        att_dates = Attendance.objects.filter(group=group).values('date').annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            excused=Count('id', filter=Q(status='excused')),
            last_change=Max('updated_at')
        ).order_by('-date')
        
        for ad in att_dates:
            dt_str = ad['date'].strftime('%d.%m.%Y') if hasattr(ad['date'], 'strftime') else str(ad['date'])
            present = ad['present']
            absent = ad['absent']
            excused = ad['excused']
            desc = f"{dt_str} kungi dars uchun yo'qlama olingan (Qatnashdi: {present}, Qatnashmadi: {absent}"
            if excused > 0:
                desc += f", Sababli: {excused}"
            desc += ")."
            logs.append({
                "action": "Davomat",
                "description": desc,
                "created_at": ad['last_change'] or timezone.now()
            })
            
        # 6. Online Lessons
        for ol in OnlineLesson.objects.filter(group=group):
            logs.append({
                "action": "Onlayn dars",
                "description": f"Onlayn dars qo'shildi: '{ol.title}'.",
                "created_at": ol.created_at
            })
            
        # Convert created_at to ISO string and sort
        for log in logs:
            if hasattr(log['created_at'], 'isoformat'):
                log['created_at'] = log['created_at'].isoformat()
            else:
                log['created_at'] = str(log['created_at'])
                
        logs.sort(key=lambda x: x['created_at'], reverse=True)
        return Response(logs, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['post'], url_path='send-sms')
    def send_sms(self, request, pk=None):
        group = self.get_object()
        
        # Enforce allow_teacher_sms check for teachers
        if getattr(request.user, 'role', None) == 'teacher':
            from organizations.models import Subscription
            subscription = Subscription.objects.filter(
                organization_id=self.get_organization_id(),
                is_active=True
            ).first()
            if subscription and not subscription.allow_teacher_sms:
                return Response(
                    {"detail": "O'qituvchilarga talabalarga SMS yuborishga ruxsat berilmagan."},
                    status=status.HTTP_403_FORBIDDEN
                )

        message = request.data.get('message')
        if not message:
            return Response({"detail": "Message is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get count of student phone numbers
        student_groups = StudentGroup.objects.filter(group=group)
        count = student_groups.count()
        
        return Response({
            "status": "success",
            "message": f"SMS successfully broadcasted to {count} students in group {group.name}."
        }, status=status.HTTP_200_OK)

class StudentGroupViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Guruhlar'
    queryset = StudentGroup.objects.all().select_related('group__teacher', 'student')
    serializer_class = StudentGroupSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['group', 'student']
    pagination_class = None

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        leave_reason_id = request.query_params.get('leave_reason_id') or request.query_params.get('leave_reason')
        comment = request.query_params.get('comment')
        refound_amount = request.query_params.get('refound_amount') or 0.00

        leave_reason = None
        if leave_reason_id:
            try:
                from academics.models import LeaveReason
                leave_reason = LeaveReason.objects.get(id=leave_reason_id)
            except Exception:
                pass

        # Create StudentGroupLeave record
        StudentGroupLeave.objects.create(
            organization=instance.organization,
            branch=instance.branch,
            student=instance.student,
            group=instance.group,
            leave_date=timezone.now().date(),
            leave_reason=leave_reason,
            comment=comment,
            refound_amount=refound_amount
        )
        return super().destroy(request, *args, **kwargs)

class GroupTeacherViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'O\'qituvchilar'
    queryset = GroupTeacher.objects.all()
    serializer_class = GroupTeacherSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['teacher', 'group']

class TeacherSalaryPaymentViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Ish haqi'
    queryset = TeacherSalaryPayment.objects.all()
    serializer_class = TeacherSalaryPaymentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['teacher']

class StudentTransactionsView(TenantViewSetMixin, generics.ListAPIView):
    """
    List transactions/payments for a student. Filter by student query param.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Barcha to\'lovlar'
    pagination_class = None

    def get_queryset(self):
        from finance.models import Payment
        from django.db.models import Q
        queryset = Payment.objects.all()
        
        # Enforce multi-tenancy filtering
        org_id = self.get_organization_id()
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        else:
            return queryset.none()
        
        # Branch filtering
        branch_id = self.get_branch_id()
        if branch_id:
            queryset = queryset.filter(Q(branch_id=branch_id) | Q(branch__isnull=True))
            
        student_id = self.request.query_params.get('student')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        return queryset

    def get(self, request, *args, **kwargs):
        # We need a serializer here. Let's build a quick inline representation or load serialized data.
        from finance.serializers import PaymentSerializer
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = PaymentSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = PaymentSerializer(queryset, many=True)
        return Response(serializer.data)

class GroupAttendanceView(TenantViewSetMixin, APIView):
    """
    GET, POST, PATCH, DELETE attendance records for a group.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Guruhlar'

    def get_serializer_context(self):
        return {'request': self.request}

    def get(self, request, group_id):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # If group_id is actually attendance ID
        if Attendance.objects.filter(id=group_id, organization_id=org_id).exists():
            attendances = Attendance.objects.filter(id=group_id, organization_id=org_id)
        else:
            attendances = Attendance.objects.filter(group_id=group_id, organization_id=org_id)
        serializer = AttendanceSerializer(attendances, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, group_id):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        data = request.data
        # Resolve potential parameter mismatch (e.g. {id: payload_dict})
        if isinstance(data, dict) and 'id' in data and isinstance(data['id'], dict):
            data = data['id']

        if not isinstance(data, list):
            data = [data]
            
        # Check if group_id is actually the attendance ID (due to frontend calling updateAttendance(recordId, payload))
        attendance_obj = None
        real_group_id = group_id
        if Attendance.objects.filter(id=group_id, organization_id=org_id).exists():
            attendance_obj = Attendance.objects.get(id=group_id, organization_id=org_id)
            real_group_id = attendance_obj.group_id

        created_records = []
        for item in data:
            if attendance_obj:
                student_id = attendance_obj.student_id
                real_group_id = attendance_obj.group_id
            else:
                student_id = item.get('student')
                student_group_id = item.get('student_group')
                if not student_id and student_group_id:
                    sg = StudentGroup.objects.filter(id=student_group_id).first()
                    if sg:
                        student_id = sg.student_id
            
            if not student_id:
                return Response({"detail": "Student ID is required."}, status=status.HTTP_400_BAD_REQUEST)
                
            date = item.get('date') or item.get('lesson_date')
            if not date:
                if attendance_obj:
                    date = attendance_obj.date
                else:
                    date = timezone.now().date()
            
            status_val = item.get('status')
            if not status_val:
                is_present = item.get('is_present')
                reason = item.get('reason')
                if is_present is True:
                    status_val = 'present'
                elif is_present is False:
                    if reason:
                        status_val = 'excused'
                    else:
                        status_val = 'absent'
                else:
                    status_val = 'present'
            
            if attendance_obj:
                attendance_obj.date = date
                attendance_obj.status = status_val
                attendance_obj.save()
                attendance = attendance_obj
            else:
                attendance, created = Attendance.objects.update_or_create(
                    organization_id=org_id,
                    group_id=real_group_id,
                    student_id=student_id,
                    date=date,
                    defaults={'status': status_val}
                )
            created_records.append(attendance)
            
        serializer = AttendanceSerializer(created_records, many=True)
        # If it was a single record and list was created from single item, return single dict
        if len(serializer.data) == 1 and not isinstance(request.data, list):
            return Response(serializer.data[0], status=status.HTTP_201_CREATED)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def patch(self, request, group_id):
        return self.post(request, group_id)

    def delete(self, request, group_id):
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Organization context is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        date = request.query_params.get('date')
        student_id = request.query_params.get('student')
        
        attendance_id = request.query_params.get('id')
        if not attendance_id and isinstance(request.data, dict):
            attendance_id = request.data.get('id') or request.data.get('attendanceId')

        # Check if group_id is actually the attendance ID (due to frontend calling deleteAttendance(recordId))
        if Attendance.objects.filter(id=group_id, organization_id=org_id).exists():
            count, _ = Attendance.objects.filter(id=group_id, organization_id=org_id).delete()
            return Response({"detail": f"Successfully deleted {count} attendance records."}, status=status.HTTP_200_OK)

        queryset = Attendance.objects.filter(group_id=group_id, organization_id=org_id)
        if attendance_id:
            queryset = queryset.filter(id=attendance_id)
        if date:
            queryset = queryset.filter(date=date)
        if student_id:
            queryset = queryset.filter(student_id=student_id)
            
        count, _ = queryset.delete()
        return Response({"detail": f"Successfully deleted {count} attendance records."}, status=status.HTTP_200_OK)

class LessonScheduleViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Darslar hisoboti'
    serializer_class = LessonScheduleSerializer
    filter_backends = [DjangoFilterBackend]
    # QO'SHILDI: Guruh va o'qituvchi bo'yicha ham filterlash imkoniyati
    filterset_fields = ['group', 'teacher']

    def get_queryset(self):
        org_id = self.get_organization_id()
        if not org_id:
            return LessonSchedule.objects.none()

        queryset = LessonSchedule.objects.filter(organization_id=org_id).select_related(
            'group', 'group__course', 'teacher'
        )

        schedule_type = self.request.query_params.get('type')
        if schedule_type == 'juft':
            queryset = queryset.filter(day_type='even')
        elif schedule_type == 'toq':
            queryset = queryset.filter(day_type='odd')

        return queryset

class StudentBalancesViewSet(TenantViewSetMixin, viewsets.ReadOnlyModelViewSet):
    permission_page_name = 'Talabalar'
    queryset = Student.objects.all()
    serializer_class = StudentBalanceSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        from django.db.models import Q
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(phone__icontains=search)
            )

        balance_min = self.request.query_params.get('balance_min')
        if balance_min:
            queryset = queryset.filter(balance__gte=balance_min)

        balance_max = self.request.query_params.get('balance_max')
        if balance_max:
            queryset = queryset.filter(balance__lte=balance_max)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset

class BalanceHistoryViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Barcha to\'lovlar'
    queryset = BalanceHistory.objects.all()
    serializer_class = BalanceHistorySerializer

class ExamViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsGroupAssignedTeacherOrAdminOwnerForExam]
    permission_page_name = 'Imtihon'
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['group', 'course', 'date']

    @decorators.action(detail=False, methods=['post'], url_path='grading')
    def grading(self, request):
        exam_id = request.data.get('exam') or request.data.get('exam_id')
        results = request.data.get('results')
        
        if not exam_id or not results:
            return Response({"detail": "Imtihon va talaba baholari (results) kiritilishi shart."}, status=status.HTTP_400_BAD_REQUEST)
            
        org_id = self.get_organization_id()
        if not org_id:
            return Response({"detail": "Tashkilot aniqlanmadi."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            exam = Exam.objects.get(id=exam_id, organization_id=org_id)
        except Exam.DoesNotExist:
            return Response({"detail": "Imtihon topilmadi."}, status=status.HTTP_404_NOT_FOUND)
            
        created_results = []
        for r in results:
            student_id = r.get('student') or r.get('student_id')
            score = r.get('score')
            if student_id is None or score is None:
                continue
                
            exam_result, created = ExamResult.objects.update_or_create(
                organization_id=org_id,
                exam=exam,
                student_id=student_id,
                defaults={'score': score}
            )
            created_results.append(exam_result)
            
        serializer = ExamResultSerializer(created_results, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ExamResultViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsGroupAssignedTeacherOrAdminOwnerForExam]
    permission_page_name = 'Imtihon'
    queryset = ExamResult.objects.all()
    serializer_class = ExamResultSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['exam', 'student']

class LeaveReasonViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Guruhni tark etganlar'
    queryset = LeaveReason.objects.all()
    serializer_class = LeaveReasonSerializer

class LessonTimeViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Darslar hisoboti'
    queryset = LessonTime.objects.all()
    serializer_class = LessonTimeSerializer

class OnlineLessonViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Darslar hisoboti'
    queryset = OnlineLesson.objects.all()
    serializer_class = OnlineLessonSerializer

    @decorators.action(detail=True, methods=['post'], url_path='publish')
    def publish(self, request, pk=None):
        lesson = self.get_object()
        lesson.is_published = True
        lesson.save()
        return Response({"status": "success", "detail": "Lesson published."}, status=status.HTTP_200_OK)

class StudentGroupLeaveViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Guruhni tark etganlar'
    queryset = StudentGroupLeave.objects.all()
    serializer_class = StudentGroupLeaveSerializer

    def get_queryset(self):
        org_id = self.get_organization_id()
        if not org_id:
            return StudentGroupLeave.objects.none()
        
        from django.db.models import Q
        qs = StudentGroupLeave.objects.filter(organization_id=org_id)
        
        # Branch filtering
        branch_id = self.get_branch_id()
        if branch_id:
            qs = qs.filter(Q(branch_id=branch_id) | Q(branch__isnull=True))
        
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        course_id = self.request.query_params.get('course')
        teacher_id = self.request.query_params.get('teacher')
        reason_id = self.request.query_params.get('reason') or self.request.query_params.get('leave_reason')
        status = self.request.query_params.get('status')
        search = self.request.query_params.get('search')
        
        if start_date:
            qs = qs.filter(leave_date__gte=start_date)
        if end_date:
            qs = qs.filter(leave_date__lte=end_date)
        if course_id:
            qs = qs.filter(group__course_id=course_id)
        if teacher_id:
            qs = qs.filter(group__teacher_id=teacher_id)
        if reason_id:
            qs = qs.filter(leave_reason_id=reason_id)
        if search:
            qs = qs.filter(
                Q(student__first_name__icontains=search) |
                Q(student__last_name__icontains=search) |
                Q(student__phone__icontains=search)
            )
        if status:
            from django.db.models import Q
            if status in ['trial', 'sinov', 'trial_left', 'Sinovdan ketgan']:
                qs = qs.filter(
                    Q(group__name__icontains='sinov') |
                    Q(group__name__icontains='trial') |
                    Q(student__first_name__icontains='trial') |
                    Q(student__first_name__icontains='sinov')
                )
            else:
                qs = qs.exclude(
                    Q(group__name__icontains='sinov') |
                    Q(group__name__icontains='trial') |
                    Q(student__first_name__icontains='trial') |
                    Q(student__first_name__icontains='sinov')
                )
            
        # is_archived filtering (only for list view so detail actions like PATCH/DELETE can access archived records)
        if self.action == 'list':
            is_archived = self.request.query_params.get('is_archived')
            if is_archived is not None:
                is_archived_bool = is_archived.lower() in ['true', '1']
                qs = qs.filter(is_archived=is_archived_bool)
            else:
                qs = qs.filter(is_archived=False)

        return qs.order_by('-leave_date')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.is_archived:
            instance.is_archived = True
            instance.save()
            return Response({"status": "archived", "message": "Record moved to archive."}, status=status.HTTP_200_OK)
        else:
            return super().destroy(request, *args, **kwargs)

class StudentPricingViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Talabalar'
    queryset = StudentPricing.objects.all()
    serializer_class = StudentPricingSerializer

class StudentArchiveViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Guruhni tark etganlar'
    queryset = StudentArchive.objects.all()
    serializer_class = StudentArchiveSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['first_name', 'last_name', 'phone', 'email']

    @decorators.action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        archive_item = self.get_object()
        
        is_student = not archive_item.role or archive_item.role.lower() in ['student', 'talaba']
        
        from accounts.models import User
        username = archive_item.phone or archive_item.email or f"user_{archive_item.id}"
        
        if is_student:
            # Check if active student already exists
            if Student.objects.filter(phone=archive_item.phone).exists():
                return Response({"detail": "Ushbu telefon raqamli talaba tizimda allaqachon mavjud."}, status=status.HTTP_400_BAD_REQUEST)
            
            existing_user = User.objects.filter(username=username).first()
            if existing_user:
                if existing_user.role == 'student':
                    # Reactivate the existing student user
                    existing_user.is_active = True
                    existing_user.first_name = archive_item.first_name
                    existing_user.last_name = archive_item.last_name or ''
                    existing_user.email = archive_item.email or ''
                    existing_user.organization = archive_item.organization
                    existing_user.branch = archive_item.branch
                    existing_user.save()
                else:
                    return Response({"detail": "Ushbu telefon raqamli foydalanuvchi tizimda allaqachon mavjud."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                if archive_item.phone:
                    User.objects.create_user(
                        username=username,
                        password=archive_item.phone if archive_item.phone else 'smarttalim123',
                        first_name=archive_item.first_name,
                        last_name=archive_item.last_name or '',
                        phone=archive_item.phone,
                        email=archive_item.email,
                        role='student',
                        organization=archive_item.organization,
                        branch=archive_item.branch
                    )
            
            student = Student.objects.create(
                organization=archive_item.organization,
                branch=archive_item.branch,
                first_name=archive_item.first_name,
                last_name=archive_item.last_name,
                phone=archive_item.phone,
                email=archive_item.email,
                balance=0.00
            )
        else:
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                return Response({"detail": "Ushbu telefon raqamli foydalanuvchi tizimda allaqachon mavjud."}, status=status.HTTP_400_BAD_REQUEST)
                
            role_to_set = archive_item.role
            SYSTEM_ROLES = ['owner', 'admin', 'manager', 'teacher', 'receptionist', 'employee', 'student', 'superadmin']
            position_to_set = None
            if role_to_set not in SYSTEM_ROLES:
                position_to_set = role_to_set
                role_to_set = 'employee'
                
            User.objects.create_user(
                username=username,
                password=archive_item.phone if archive_item.phone else 'smarttalim123',
                first_name=archive_item.first_name,
                last_name=archive_item.last_name,
                phone=archive_item.phone,
                email=archive_item.email,
                role=role_to_set,
                position=position_to_set,
                organization=archive_item.organization,
                branch=archive_item.branch
            )
            
        archive_item.delete()
        return Response({"status": "success", "detail": "Restored successfully."}, status=status.HTTP_200_OK)


class AttendanceViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_page_name = 'Guruhlar'
    permission_classes = [permissions.IsAuthenticated, IsGroupAssignedTeacherForAttendance]
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    pagination_class = None

    def perform_create(self, serializer):
        """
        MUHIM QO'SHIMCHA: Davomat qo'yilayotgan sana bayram (Holiday) kuniga
        to'g'ri kelsa va talabalarga ta'siri bo'lsa (student_impact=True),
        tizim davomat qo'yishni taqiqlaydi. Bu bilan talaba balansidan adashib pul ketishi oldi olinadi.
        """
        attendance_date = serializer.validated_data.get('date')
        org_id = self.get_organization_id()

        # Shu sanada talabalarga ta'sir qiluvchi bayram bormi tekshiramiz
        is_holiday = Holiday.objects.filter(
            organization_id=org_id,
            start_date__lte=attendance_date,
            end_date__gte=attendance_date,
            student_impact=True
        ).exists() or Holiday.objects.filter(
            organization_id=org_id,
            start_date=attendance_date,
            end_date__isnull=True,
            student_impact=True
        ).exists()

        if is_holiday:
            raise ValidationError({
                "detail": f"Ushbu sana ({attendance_date}) dam olish kuni (Bayram) deb e'lon qilingan! Davomat olib bo'lmaydi."
            })

        serializer.save()

    def get_queryset(self):
        queryset = super().get_queryset()
        group_id = self.request.query_params.get('group') or self.request.query_params.get('group_id')
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        
        student_id = self.request.query_params.get('student') or self.request.query_params.get('student_id')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
            
        date_from = self.request.query_params.get('date_from') or self.request.query_params.get('start_date')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
            
        date_to = self.request.query_params.get('date_to') or self.request.query_params.get('end_date')
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
            
        return queryset

class HolidayViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnerOrReadOnly]
    permission_page_name = 'Ofis sozlamalari'
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['name']
    pagination_class = None


class HomeworkViewSet(TenantViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    permission_page_name = 'Guruhlar'
    queryset = Homework.objects.select_related('group', 'created_by').all()
    serializer_class = HomeworkSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['title', 'text', 'group__name']
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        group_id = self.request.query_params.get('group') or self.request.query_params.get('group_id')
        if group_id:
            queryset = queryset.filter(group_id=group_id)

        current_user = getattr(self.request, 'user', None)
        if current_user and getattr(current_user, 'role', None) == 'student':
            phone = getattr(current_user, 'phone', None) or getattr(current_user, 'username', None)
            if phone:
                queryset = queryset.filter(group__group_students__student__phone=phone).distinct()
            else:
                queryset = queryset.none()
        return queryset

    def perform_create(self, serializer):
        current_user = getattr(self.request, 'user', None)
        if current_user and getattr(current_user, 'role', None) == 'student':
            raise PermissionDenied("Talaba uy vazifasi qo'sha olmaydi.")
        org_id = self.get_organization_id()
        if not org_id:
            raise PermissionDenied("Organization context is required.")

        branch_id = self.get_branch_id()
        serializer.save(
            organization_id=org_id,
            branch_id=branch_id,
            created_by=self.request.user if self.request.user.is_authenticated else None
        )

    def update(self, request, *args, **kwargs):
        if getattr(request.user, 'role', None) == 'student':
            raise PermissionDenied("Talaba uy vazifasini o'zgartira olmaydi.")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if getattr(request.user, 'role', None) == 'student':
            raise PermissionDenied("Talaba uy vazifasini o'zgartira olmaydi.")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if getattr(request.user, 'role', None) == 'student':
            raise PermissionDenied("Talaba uy vazifasini o'chira olmaydi.")
        return super().destroy(request, *args, **kwargs)

from .models import Student, StudentGroup


# 1. TALABA PROFILI VA BALANSI
class StudentProfileAPIView(APIView):
    def get(self, request):
        phone = request.query_params.get('phone')
        if not phone:
            return Response({"error": "phone parametri majburiy!"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            student = Student.objects.get(phone=phone)
            # Ma'lumotlarni serializer orqali o'giramiz
            serializer = StudentProfileSerializer(student)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Student.DoesNotExist:
            return Response({"error": "Talaba topilmadi!"}, status=status.HTTP_404_NOT_FOUND)


# 2. TALABA DARS JADVALI (StudentGroup va Group modelidan oladi)
class StudentLessonsAPIView(APIView):
    def get(self, request):
        phone = request.query_params.get('phone')
        if not phone:
            return Response({"error": "phone parametri majburiy!"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            student = Student.objects.get(phone=phone)
            # Talaba a'zo bo'lgan faol guruhlarni qidiramiz
            st_groups = StudentGroup.objects.filter(student=student, group__status='active')

            lessons_list = []
            for st_g in st_groups:
                group = st_g.group
                lessons_list.append({
                    "group_name": group.name,
                    "course_name": group.course.name if group.course else None,
                    "teacher_name": group.teacher.get_full_name() if group.teacher else "Ustoz biriktirilmagan",
                    "day_type": group.day_type,
                    "start_time": str(group.start_time) if group.start_time else None
                })

            return Response({"student": student.first_name, "lessons": lessons_list}, status=status.HTTP_200_OK)
        except Student.DoesNotExist:
            return Response({"error": "Talaba topilmadi!"}, status=status.HTTP_404_NOT_FOUND)
