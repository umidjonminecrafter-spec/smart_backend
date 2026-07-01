from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django import forms
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import messages
from organizations.models import Organization, Branch, Tariff, Subscription
from communication.models import Notification


class SendNotificationForm(forms.Form):
    title = forms.CharField(
        max_length=255, 
        label="Bildirishnoma sarlavhasi (Title)", 
        required=True,
        widget=forms.TextInput(attrs={'style': 'width: 100%; max-width: 600px; padding: 8px; border-radius: 4px; border: 1px solid #ccc; font-size: 13px;'})
    )
    message = forms.CharField(
        label="Bildirishnoma matni (Message)", 
        required=True,
        widget=forms.Textarea(attrs={'rows': 5, 'style': 'width: 100%; max-width: 600px; padding: 8px; border-radius: 4px; border: 1px solid #ccc; font-size: 13px;'})
    )
    notification_type = forms.ChoiceField(
        choices=[
            ('info', 'Umumiy xabar (Info)'),
            ('subscription_expiry', 'Tarif tugashidan oldin eslatma'),
            ('balance_low', 'Balans kamligi haqida eslatma'),
        ],
        label="Bildirishnoma turi (Type)",
        required=True,
        widget=forms.Select(attrs={'style': 'width: 100%; max-width: 620px; padding: 8px; border-radius: 4px; border: 1px solid #ccc; font-size: 13px;'})
    )


# organizations/admin.py faylining pastki qismini shunday o'zgartiring:

def send_notification_to_organizations(modeladmin, request, queryset):
    """Tanlangan barcha tashkilotlarga bir vaqtda xabar yuborish."""
    if 'apply' in request.POST:
        form = SendNotificationForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            message = form.cleaned_data['message']
            notification_type = form.cleaned_data['notification_type']

            count = 0
            for org in queryset:
                Notification.objects.create(
                    organization=org,
                    title=title,
                    message=message,
                    notification_type=notification_type
                )
                count += 1

            modeladmin.message_user(
                request, 
                f"{count} ta tashkilotga bildirishnoma muvaffaqiyatli yuborildi! ✅", 
                messages.SUCCESS
            )
            
            # 🔥 TUZATILGAN JOYI: Cheksiz redirect bo'lmasligi uchun changelist sahifasiga qaytaramiz
            return HttpResponseRedirect(request.path)
            
    else:
        form = SendNotificationForm()

    return render(
        request, 
        'admin/send_notification_intermediate.html', 
        context={
            'organizations': queryset,
            'form': form,
            'opts': modeladmin.model._meta,
            'action_checkbox_name': ACTION_CHECKBOX_NAME,
        }
    )

send_notification_to_organizations.short_description = "Tanlangan tashkilotlarga bildirishnoma yuborish"


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'subdomain', 'created_at')
    search_fields = ('name', 'subdomain')
    actions = [send_notification_to_organizations]
    list_display_links = ['id', 'name']


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization', 'name', 'phone')
    search_fields = ('name', 'phone')
    list_display_links = ['id', 'organization']


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'old_price', 'months', 'discount_badge')
    search_fields = ('name',)
    list_display_links = ['id', 'name']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization', 'tariff', 'start_date', 'end_date', 'is_active', 'balance')
    list_filter = ('is_active', 'start_date', 'end_date')
    list_display_links = ['id', 'organization']
