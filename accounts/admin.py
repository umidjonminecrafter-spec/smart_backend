from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from accounts.models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'organization', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'organization')
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'organization', 'phone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Custom Fields', {'fields': ('role', 'organization', 'phone')}),
    )
