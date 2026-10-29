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
    list_display = ('symptom_name', 'category', 'vehicle_type', 'urgency_level', 'system', 'created_at')
    list_filter = ('category', 'vehicle_type', 'urgency_level', 'system')
    search_fields = ('symptom_name', 'category', 'description', 'system', 'component', 'aliases')


@admin.register(TroubleshootingGuide)
class TroubleshootingGuideAdmin(admin.ModelAdmin):
    list_display = (
        'possible_cause', 'symptom', 'review_status', 'confidence_level',
        'vehicle_type', 'manufacturer', 'model', 'difficulty_level',
    )
    list_filter = (
        'review_status', 'confidence_level', 'vehicle_type', 'system',
        'difficulty_level', 'is_verified',
    )
    search_fields = (
        'possible_cause', 'repair_instructions', 'advice_notes',
        'source_reference', 'source_title', 'manufacturer', 'model',
    )
    readonly_fields = ('reviewed_at',)
    fieldsets = (
        (None, {
            'fields': ('symptom', 'possible_cause', 'confidence_level', 'system', 'component'),
        }),
        ('Vehicle applicability', {
            'fields': ('vehicle_type', 'manufacturer', 'model', 'variant', 'year_from', 'year_to'),
        }),
        ('Guidance', {
            'fields': ('diagnostic_test', 'expected_result', 'alternative_outcome',
                       'tools_required', 'repair_instructions', 'advice_notes',
                       'when_to_stop', 'safety_precautions', 'verification_procedure',
                       'difficulty_level'),
        }),
        ('Source and review', {
            'fields': ('source_reference', 'source_title', 'source_date',
                       'review_status', 'reviewed_by', 'reviewed_at', 'review_notes', 'is_verified'),
        }),
    )

    def save_model(self, request, obj, form, change):
        if obj.review_status in {'approved', 'rejected'} and obj.reviewed_at is None:
            from django.utils import timezone
            obj.reviewed_at = timezone.now()
            obj.reviewed_by = request.user
        has_source = bool(
            (obj.source_reference or '').strip() or (obj.source_title or '').strip()
        )
        if obj.review_status != 'approved' or not has_source:
            obj.is_verified = False
        super().save_model(request, obj, form, change)


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ('part_name', 'part_number', 'category', 'estimated_cost')
    list_filter = ('category',)
    search_fields = ('part_name', 'part_number', 'category')
    readonly_fields = ('created_at',)


@admin.register(GuideRequiredPart)
class GuideRequiredPartAdmin(admin.ModelAdmin):
    list_display = ('guide', 'part', 'quantity_needed')
    search_fields = ('guide__possible_cause', 'part__part_name')
    autocomplete_fields = ('guide', 'part')


@admin.register(MotorAssistantUser)
class MotorAssistantUserAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'role', 'created_at')
    search_fields = ('full_name', 'email')
    list_filter = ('role',)
