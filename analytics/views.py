from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.utils import timezone
from academics.models import Attendance, Group, GroupLesson,Student
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


class BranchStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = getattr(request.user, 'organization_id', None)
        if not org_id:
            return Response({"detail": "Tashkilot aniqlanmadi"}, status=400)

        # 1. CRM Lead modeli statistikasi (Faollar va Arxivlanganlarni hisobga olgan holda)
        leads_stats = Lead.objects.filter(organization_id=org_id).aggregate(
            # Faol buyurtmalar (Arxivda bo'lmagan va lost bo'lmaganlar)
            buyurtma_soni=Count('id', filter=Q(is_archived=False) & ~Q(status='lost')),
            # Birinchi darsga yozilganlar
            birinchi_dars=Count('id', filter=Q(status='first_lesson', is_archived=False)),
            # Buyurtmadan ketganlar (Lost statusidagilar yoki is_archived=True bo'lgan lidlar)
            buyurtmadan_ketgan=Count('id', filter=Q(status='lost') | Q(is_archived=True))
        )

        # 2. Real O'quvchilar (Student) soni
        total_students = Student.objects.filter(organization_id=org_id).count()

        # 3. CRM dagi muvaffaqiyatli yakunlanganlar (Won statusidagi lidlar)
        won_leads_count = Lead.objects.filter(organization_id=org_id, status='won').count()

        # Jami real o'quvchilar soni (Student modelida bo'lsa shuni, bo'lmasa Won lidlarni oladi)
        real_active_count = total_students if total_students > 0 else won_leads_count

        # 4. Qarzdorlar filtri (Student balansi yoki Lead debt_limit orqali)
        student_debtors = Student.objects.filter(organization_id=org_id, balance__lt=0.00).count()
        lead_debtors = Lead.objects.filter(organization_id=org_id, status='won', debt_limit__gt=0.00).count()
        total_debtors = student_debtors if student_debtors > 0 else lead_debtors

        # 5. Aktiv guruhlar soni
        active_groups_count = Group.objects.filter(organization_id=org_id, status='active').count()

        # Qarzdorlik foizini hisoblash
        debt_percentage = 0.0
        if real_active_count > 0:
            debt_percentage = round((total_debtors / real_active_count) * 100, 1)

        # Frontend jadvali uchun moslashtirilgan ma'lumotlar
        branch_report = [{
            "id": org_id,
            "filial": getattr(request.user.organization, 'name', "Asosiy Filial"),
            "buyurtma": leads_stats['buyurtma_soni'] or 0,
            "birinchi_darsga_keladiganlar": leads_stats['birinchi_dars'] or 0,
            "yangi_oquvchi": real_active_count,
            "aktiv_oquvchilar": real_active_count,
            "jami_real_bor": real_active_count,
            "guruh_oquvchilari": real_active_count,
            # "Buyurtmadan ketganlar" qatoriga endi arxiv oynasidagi ma'lumotlar ham qo'shildi!
            "buyurtmadan_ketganlar": leads_stats['buyurtmadan_ketgan'] or 0,
            "yangi_oquvchidan_ketganlar": 0,
            "aktiv_oquvchidan_ketganlar": 0,
            "qarzdorlar": total_debtors,
            "guruh": active_groups_count,
            "birinchi_tolovni_qilganlar": 0,
            "jami_oquvchi": real_active_count,
            "jami_aktiv": real_active_count,
            "qarzdorlarning_aktivga_nisbatan_foizi": f"{debt_percentage}%"
        }]

        return Response(branch_report)


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from datetime import datetime, time
from crm.models import Lead  # CRM ilovasidagi Lead modelini import qilamiz


class SalesFunnelView(APIView):
    """
    Sotuv voronkasi (Sales Funnel) uchun yagona analitika endpointi.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        organization_id = request.user.organization_id

        # 1. Filtorlarni query_params dan olish
        start_date_str = request.query_params.get('from_date')
        end_date_str = request.query_params.get('to_date')
        marketing_id = request.query_params.get('marketing')
        course_id = request.query_params.get('course')
        moderator_id = request.query_params.get('moderator')
        teacher_id = request.query_params.get('teacher')
        source_id = request.query_params.get('source')

        # Boshlang'ich queryset (Faqat joriy tashkilot lidlari)
        leads = Lead.objects.filter(organization_id=organization_id)

        # 2. Dinamik filtrlash qismi
        if start_date_str:
            try:
                leads = leads.filter(created_at__gte=datetime.strptime(start_date_str, '%Y-%m-%d'))
            except ValueError:
                pass
        if end_date_str:
            try:
                leads = leads.filter(
                    created_at__lte=datetime.combine(datetime.strptime(end_date_str, '%Y-%m-%d'), time.max))
            except ValueError:
                pass

        if marketing_id:
            leads = leads.filter(marketing_id=marketing_id)
        if course_id:
            leads = leads.filter(course_id=course_id)
        if moderator_id:
            leads = leads.filter(moderator_id=moderator_id)
        if teacher_id:
            # Agar lead modelida guruh yoki o'qituvchi bog'langan bo'lsa
            leads = leads.filter(group__teacher_id=teacher_id)
        if source_id:
            leads = leads.filter(source_id=source_id)

        # 3. Voronka bosqichlari bo'yicha hisoblash (Statuslaringiz nomiga qarab moslang)
        # Masalan: 'NEW', 'TRIAL_REGISTERED', 'TRIAL_ATTENDED', 'PAID', 'CANCELLED'
        stats = leads.aggregate(
            total_orders=Count('id'),
            left_before_trial=Count('id', filter=Q(status='LEFT_BEFORE_TRIAL')),
            trial_registered=Count('id', filter=Q(status='TRIAL_REGISTERED')),
            trial_missed=Count('id', filter=Q(status='TRIAL_MISSED')),
            trial_attended=Count('id', filter=Q(status='TRIAL_ATTENDED')),
            converted_to_group=Count('id', filter=Q(status='CONVERTED')),
            first_payment=Count('id', filter=Q(status='PAID')),
            first_payment_left=Count('id', filter=Q(status='PAID_BUT_LEFT')),
            finished=Count('id', filter=Q(status='FINISHED')),
            moved_to_branch=Count('id', filter=Q(status='MOVED_BRANCH')),
        )

        # 4. Jadval (Table) ko'rinishidagi ma'lumotlar ro'yxati
        funnel_table = [
            {"id": 1, "status_name": "Barcha buyurtmalar soni", "count": stats['total_orders']},
            {"id": 2, "status_name": "Buyurtmadan ketganlar", "count": stats['left_before_trial']},
            {"id": 3, "status_name": "Sinov darsiga yozilganlar", "count": stats['trial_registered']},
            {"id": 4, "status_name": "Sinov darsiga kelmay ketganlar", "count": stats['trial_missed']},
            {"id": 5, "status_name": "Sinov darsiga kelganlar", "count": stats['trial_attended']},
            {"id": 6, "status_name": "Sinov darsiga kelib ketganlar", "count": stats['converted_to_group']},
            {"id": 7, "status_name": "Birinchi to'lovni qilganlar", "count": stats['first_payment']},
            {"id": 8, "status_name": "Birinchi to'lovni qilib ketganlar", "count": stats['first_payment_left']},
            {"id": 9, "status_name": "Tugatganlar", "count": stats['finished']},
            {"id": 10, "status_name": "Boshqa filialdan ko'chirilgan", "count": stats['moved_to_branch']},
        ]

        # 5. Kunlar kesimidagi chiziqli grafik (Lidlar tahlili - Kun)
        daily_leads = (
            leads.annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(
                total=Count('id'),
                lost=Count('id', filter=Q(status__in=['LEFT_BEFORE_TRIAL', 'TRIAL_MISSED'])),
                sales=Count('id', filter=Q(status='PAID'))
            )
            .order_by('date')
        )

        chart_labels = [item['date'].strftime('%d.%m.%Y') for item in daily_leads]
        chart_total = [item['total'] for item in daily_leads]
        chart_lost = [item['lost'] for item in daily_leads]
        chart_sales = [item['sales'] for item in daily_leads]

        # 6. Kurslar kesimida buyurtmalar taqsimoti (Pie-chart/Bar-chart uchun)
        course_distribution = (
            leads.values('course__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]  # Top 5 kurs
        )
        course_data = {
            "labels": [c['course__name'] or "Noma'lum" for c in course_distribution],
            "values": [c['count'] for c in course_distribution]
        }

        return Response({
            "table_data": funnel_table,
            "funnel_chart": {
                "total_orders": stats['total_orders'],
                "trial_registered": stats['trial_registered'],
                "trial_attended": stats['trial_attended'],
                "first_payment": stats['first_payment']
            },
            "linear_chart": {
                "labels": chart_labels,
                "total_leads": chart_total,
                "lost_leads": chart_lost,
                "sales_count": chart_sales
            },
            "course_chart": course_data
        }, status=status.HTTP_200_OK)