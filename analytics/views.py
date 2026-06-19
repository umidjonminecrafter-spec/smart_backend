from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.utils import timezone
from academics.models import Attendance, Group, GroupLesson
from crm.models import Lead  # Lead modelingiz qaysi appda bo'lsa o'sha yo'lni yozing (masalan: crm.models)
from .serializers import GlobalAttendanceSerializer


class GlobalAttendanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = getattr(request.user, 'organization_id', None)
        if not org_id:
            return Response({"detail": "Tashkilot aniqlanmadi"}, status=400)

        # Frontenddan (Abdulmajid) kelayotgan filter parametrlari
        date_param = request.query_params.get('date', timezone.now().date().isoformat())
        attendance_status = request.query_params.get('attendance_status')  # present, absent, excused
        group_id = request.query_params.get('group_id')
        teacher_id = request.query_params.get('teacher_id')

        # 🚀 Lead (CRM) bilan bog'liq filterlar
        pipeline_id = request.query_params.get('pipeline_id')  # Ranglar/Bosqichlar filtri (Lead Pipeline)
        lead_status = request.query_params.get('lead_status')  # open, won, lost, first_lesson

        # Davomat uchun asosiy so'rov
        queryset = Attendance.objects.filter(organization_id=org_id, date=date_param).select_related(
            'student', 'group', 'group__teacher'
        ).order_by('-id')

        # Dinamik filtrlash
        if attendance_status:
            queryset = queryset.filter(status=attendance_status)
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        if teacher_id:
            queryset = queryset.filter(group__teacher_id=teacher_id)

        # 🚀 CRM Lead ma'lumotlari orqali filtrlash (Telefon raqami orqali bog'lanadi)
        if pipeline_id or lead_status:
            # Mos keladigan lidlarning telefon raqamlarini olamiz
            lead_filters = Q(organization_id=org_id)
            if pipeline_id:
                lead_filters &= Q(pipeline_id=pipeline_id)
            if lead_status:
                lead_filters &= Q(status=lead_status)

            matching_phones = Lead.objects.filter(lead_filters).values_list('phone', flat=True)
            # Davomat ro'yxatini faqat shu telefon raqamli o'quvchilarga qisqartiramiz
            queryset = queryset.filter(student__phone__in=matching_phones)

        # Serializer orqali ma'lumotlarni chiqarish
        serializer = GlobalAttendanceSerializer(queryset, many=True)
        return Response(serializer.data)


class AttendanceAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = getattr(request.user, 'organization_id', None)
        if not org_id:
            return Response({"detail": "Tashkilot aniqlanmadi"}, status=400)

        date_param = request.query_params.get('date', timezone.now().date().isoformat())

        # Davomat statistikasi
        stats = Attendance.objects.filter(organization_id=org_id, date=date_param).aggregate(
            kelganlar=Count('id', filter=Q(status='present')),
            sababli=Count('id', filter=Q(status='excused')),
            sababsiz=Count('id', filter=Q(status='absent')),
        )

        # 🚀 Lead modelidan "Birinchi darsga yozilganlar" sonini hisoblash
        first_lesson_count = Lead.objects.filter(organization_id=org_id, status='first_lesson',
                                                 is_archived=False).count()

        # Davomat qilinmagan guruhlar soni
        today_lessons = GroupLesson.objects.filter(organization_id=org_id, date=date_param)
        davomat_qilinmagan_guruhlar = 0
        for lesson in today_lessons:
            if not Attendance.objects.filter(group=lesson.group, date=date_param).exists():
                davomat_qilinmagan_guruhlar += 1

        return Response({
            "summary": {
                "kelganlar": stats['kelganlar'] or 0,
                "sababli": stats['sababli'] or 0,
                "sababsiz": stats['sababsiz'] or 0,
                "birinchi_dars": first_lesson_count,  # Lead modelidan aniq keldi!
                "muzlatilgan": 0,  # Loyihada talaba statusi qo'shilganda integratsiya qilinadi
                "davomat_qilinmagan": davomat_qilinmagan_guruhlar
            }
        })


class UnmarkedGroupsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = getattr(request.user, 'organization_id', None)
        if not org_id:
            return Response({"detail": "Tashkilot aniqlanmadi"}, status=400)

        date_param = request.query_params.get('date', timezone.now().date().isoformat())

        # Bugun kalendarda darsi bor guruhlar
        today_lessons = GroupLesson.objects.filter(organization_id=org_id, date=date_param).select_related('group',
                                                                                                           'group__teacher')

        unmarked_groups = []
        for lesson in today_lessons:
            if not lesson.group:
                continue
            has_attendance = Attendance.objects.filter(group=lesson.group, date=date_param).exists()
            if not has_attendance:
                teacher = lesson.group.teacher
                teacher_name = f"{teacher.first_name or ''} {teacher.last_name or ''}".strip() or teacher.username if teacher else "O'qituvchi yo'q"

                unmarked_groups.append({
                    "group_id": lesson.group.id,
                    "group_name": lesson.group.name,
                    "teacher_name": teacher_name,
                    "date": date_param
                })

        return Response(unmarked_groups)