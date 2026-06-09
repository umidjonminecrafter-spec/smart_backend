from django.urls import path, include
from rest_framework.routers import DefaultRouter
from crm.views import (
    PipelineViewSet, SourceViewSet, LostReasonViewSet, SectionViewSet, LeadFormViewSet, LeadViewSet,
    CRMActivityViewSet, CRMLeadsHistoryViewSet, CRMLeadLostViewSet
)

router = DefaultRouter()
router.register(r'pipelines', PipelineViewSet, basename='pipeline')
router.register(r'leads', LeadViewSet, basename='lead')
router.register(r'sources', SourceViewSet, basename='source')
router.register(r'crm-lost-reasons', LostReasonViewSet, basename='lost-reason')
router.register(r'sections', SectionViewSet, basename='section')
router.register(r'lead-forms', LeadFormViewSet, basename='lead-form')
router.register(r'activities', CRMActivityViewSet, basename='activity')
router.register(r'history', CRMLeadsHistoryViewSet, basename='history')
router.register(r'lost-leads', CRMLeadLostViewSet, basename='lost-lead')

urlpatterns = [
    path('', include(router.urls)),
]
