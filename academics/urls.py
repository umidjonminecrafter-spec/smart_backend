from django.urls import path, include
from rest_framework.routers import DefaultRouter
from academics.views import (
    CourseViewSet, RoomViewSet, StudentViewSet, GroupViewSet,
    StudentGroupViewSet, GroupTeacherViewSet, TeacherSalaryPaymentViewSet,
    StudentTransactionsView, GroupAttendanceView, LessonScheduleViewSet,
    StudentBalancesViewSet, BalanceHistoryViewSet, ExamViewSet, ExamResultViewSet,
    LeaveReasonViewSet, LessonTimeViewSet, OnlineLessonViewSet, StudentGroupLeaveViewSet,
    StudentPricingViewSet, StudentArchiveViewSet, AttendanceViewSet, HolidayViewSet, HomeworkViewSet
)
from .views import StudentFieldSettingViewSet
from finance.views import TeacherSalaryCalculationViewSet, TeacherSalaryRuleViewSet


student_field_settings = StudentFieldSettingViewSet.as_view({
    'get': 'list',
    'post': 'create'
})

student_field_setting_detail = StudentFieldSettingViewSet.as_view({
    'get': 'retrieve',
    'patch': 'partial_update',
    'put': 'update',
    'delete': 'destroy'
})
router = DefaultRouter()
router.register(r'students', StudentViewSet, basename='student')
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'rooms', RoomViewSet, basename='room')
router.register(r'student-groups', StudentGroupViewSet, basename='student-group')
router.register(r'group-teachers', GroupTeacherViewSet, basename='group-teacher')
router.register(r'lesson-schedules', LessonScheduleViewSet, basename='lesson-schedule')
router.register(r'student-balances', StudentBalancesViewSet, basename='student-balance')
router.register(r'attendances', AttendanceViewSet, basename='attendance')

# New ViewSets
router.register(r'holidays', HolidayViewSet, basename='holiday')
router.register(r'balance-history', BalanceHistoryViewSet, basename='balance-history')
router.register(r'exams', ExamViewSet, basename='exam')
router.register(r'exam-results', ExamResultViewSet, basename='exam-result')
router.register(r'leave-reasons', LeaveReasonViewSet, basename='leave-reason')
router.register(r'lesson-times', LessonTimeViewSet, basename='lesson-time')
router.register(r'online-lessons', OnlineLessonViewSet, basename='online-lesson')
router.register(r'student-group-leaves', StudentGroupLeaveViewSet, basename='student-group-leave')
router.register(r'student-pricings', StudentPricingViewSet, basename='student-pricing')
router.register(r'archive', StudentArchiveViewSet, basename='student-archive')
router.register(r'homeworks', HomeworkViewSet, basename='homework')

# Teachers nested routes (to match /api/v1/academics/teachers/...)
router.register(r'teachers/salary-calculations', TeacherSalaryCalculationViewSet, basename='academic-teacher-salary-calc')
router.register(r'teachers/salary-payments', TeacherSalaryPaymentViewSet, basename='academic-teacher-salary-payment')
router.register(r'teachers/salary-rules', TeacherSalaryRuleViewSet, basename='academic-teacher-salary-rule')

urlpatterns = [
    path('student-transactions/', StudentTransactionsView.as_view(), name='student-transactions'),
    path('attendences/group/<int:group_id>/', GroupAttendanceView.as_view(), name='group-attendance'),
    path('attendances/group/<int:group_id>/', GroupAttendanceView.as_view(), name='group-attendance-alt'),
    path(
        'student-field-settings/',
        student_field_settings,
        name='student-field-settings'
    ),

    path(
        'student-field-settings/<int:pk>/',
        student_field_setting_detail,
        name='student-field-setting-detail'
    ),
    path('', include(router.urls)),
]
