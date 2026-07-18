from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import KPITemplateViewSet, KPIGoalViewSet, KPISubGoalViewSet, KPILogViewSet

router = DefaultRouter()
router.register(r'templates', KPITemplateViewSet, basename='kpi-template')
router.register(r'goals', KPIGoalViewSet, basename='kpi-goal')
router.register(r'sub-goals', KPISubGoalViewSet, basename='kpi-sub-goal')
router.register(r'logs', KPILogViewSet, basename='kpi-log')

urlpatterns = [
    path('', include(router.urls)),
]
