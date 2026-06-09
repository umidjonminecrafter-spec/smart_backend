from django.urls import path
from billing.views import (
    BillingPlansView, BillingCurrentView, BillingHistoryView,
    BillingPayView, BalanceTopUpView, SubscribePreviewView, SubscribeConfirmView,
    SubscriptionRequestListView
)

urlpatterns = [
    path('plans/', BillingPlansView.as_view(), name='billing-plans'),
    path('current/', BillingCurrentView.as_view(), name='billing-current'),
    path('history/', BillingHistoryView.as_view(), name='billing-history'),
    path('pay/', BillingPayView.as_view(), name='billing-pay'),           # eski
    path('requests/', SubscriptionRequestListView.as_view(), name='billing-requests'),  # yangi
    path('topup/', BalanceTopUpView.as_view(), name='billing-topup-blanas'),     # yangi
    path('subscribe/', SubscribePreviewView.as_view(), name='billing-subscribe-preview'),    # yangi
    path('subscribe/confirm/', SubscribeConfirmView.as_view(), name='billing-subscribe-confirm'),  # yangi
]