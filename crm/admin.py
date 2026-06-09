from django.contrib import admin
from crm.models import Pipeline, Source, LostReason, Section, LeadForm, Lead

@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'order', 'organization')
    search_fields = ('name',)

@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'organization')
    search_fields = ('name',)

@admin.register(LostReason)
class LostReasonAdmin(admin.ModelAdmin):
    list_display = ('id', 'reason', 'organization')
    search_fields = ('reason',)

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'organization')
    search_fields = ('name',)

@admin.register(LeadForm)
class LeadFormAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'organization')
    search_fields = ('name',)

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone', 'status', 'pipeline', 'source', 'organization')
    list_filter = ('status', 'pipeline', 'source')
    search_fields = ('name', 'phone', 'email')
