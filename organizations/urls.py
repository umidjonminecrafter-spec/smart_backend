from django.urls import path, include
from rest_framework.routers import DefaultRouter
from organizations.views import (
    OrganizationViewSet, BranchViewSet, TariffViewSet, SubscriptionViewSet, OrganizationLoginView
)

from organizations.views import send_register_code, verify_register_code

router = DefaultRouter()
router.register(r'branches', BranchViewSet, basename='branch')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')
router.register(r'tariffs', TariffViewSet, basename='tariff')
router.register(r'organizations', OrganizationViewSet, basename='organization-double')
router.register(r'', OrganizationViewSet, basename='organization')

urlpatterns = [
    path('login/', OrganizationLoginView.as_view(), name='organization-login'),
    path('billing/', include('billing.urls')),
    path('sms/send/', send_register_code, name='send_sms_code'),
    path('sms/verify/', verify_register_code, name='verify_sms_code'),
    path('', include(router.urls)),
]
