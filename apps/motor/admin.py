from django.contrib import admin

from .models import (
    DiagnosticSymptom,
    GuideRequiredPart,
    MotorAssistantUser,
    Part,
    TroubleshootingGuide,
)


@admin.register(DiagnosticSymptom)
class DiagnosticSymptomAdmin(admin.ModelAdmin):
    list_display = ('symptom_name', 'category', 'created_at')
    search_fields = ('symptom_name', 'category', 'description')


@admin.register(TroubleshootingGuide)
class TroubleshootingGuideAdmin(admin.ModelAdmin):
    list_display = ('possible_cause', 'symptom', 'created_at')
    search_fields = ('possible_cause', 'repair_instructions', 'advice_notes')
    list_filter = ('symptom__category',)


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ('part_name', 'part_number', 'category', 'estimated_cost')
    search_fields = ('part_name', 'part_number', 'category')
    list_filter = ('category',)


@admin.register(GuideRequiredPart)
class GuideRequiredPartAdmin(admin.ModelAdmin):
    list_display = ('guide', 'part', 'quantity_needed')
    search_fields = ('guide__possible_cause', 'part__part_name')


@admin.register(MotorAssistantUser)
class MotorAssistantUserAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'role', 'created_at')
    search_fields = ('full_name', 'email')
    list_filter = ('role',)
