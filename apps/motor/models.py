from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class DiagnosticSymptom(models.Model):
    id = models.AutoField(primary_key=True)
    symptom_name = models.CharField(max_length=150)
    category = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    vehicle_type = models.CharField(
        max_length=20,
        choices=[('all', 'All Vehicles'), ('motorcycle', 'Motorcycle'), ('car', 'Car')],
        default='all'
    )
    urgency_level = models.CharField(
        max_length=20,
        choices=[('routine', 'Routine'), ('warning', 'Warning'), ('critical_stop', 'Critical Stop')],
        default='routine'
    )
    safety_warning = models.TextField(blank=True, null=True)
    system = models.CharField(max_length=100, blank=True, default='', help_text='e.g. Brakes, Starting, Cooling')
    component = models.CharField(max_length=120, blank=True, default='')
    aliases = models.TextField(blank=True, default='', help_text='Optional search aliases, one per line')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'diagnostic_symptoms'

    def __str__(self):
        return self.symptom_name


class Part(models.Model):
    id = models.AutoField(primary_key=True)
    part_name = models.CharField(max_length=100)
    part_number = models.CharField(max_length=50, blank=True, null=True)
    category = models.CharField(max_length=50, blank=True, null=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'parts'

    def __str__(self):
        return self.part_name


class TroubleshootingGuide(models.Model):
    id = models.AutoField(primary_key=True)
    symptom = models.ForeignKey(
        DiagnosticSymptom,
        related_name='troubleshooting_guides',
        on_delete=models.CASCADE,
    )
    possible_cause = models.CharField(max_length=255)
    confidence_level = models.CharField(
        max_length=20,
        choices=[('High', 'High'), ('Medium', 'Medium'), ('Tentative', 'Tentative')],
        default='Medium'
    )
    diagnostic_test = models.TextField(blank=True, null=True, help_text="Specific test to differentiate this cause")
    expected_result = models.TextField(blank=True, null=True, help_text="Expected test reading / normal condition")
    alternative_outcome = models.TextField(blank=True, null=True, help_text="What to check if test reading differs")
    tools_required = models.TextField(blank=True, null=True, help_text="List of tools and materials required")
    repair_instructions = models.TextField()
    advice_notes = models.TextField(blank=True, null=True)
    when_to_stop = models.TextField(blank=True, null=True, help_text="When to stop and seek a professional mechanic")
    source_reference = models.CharField(max_length=255, blank=True, null=True, help_text="Service manual or verified reference")
    source_title = models.CharField(max_length=255, blank=True, default='')
    source_date = models.DateField(null=True, blank=True)
    review_status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft / unreviewed'),
            ('pending', 'Pending review'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected / not reliable'),
        ],
        default='draft',
        help_text='Only approved guides are retrieved for AI or offline answers.',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_troubleshooting_guides',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, default='')
    system = models.CharField(max_length=100, blank=True, default='', help_text='e.g. Brakes, Starting, Cooling')
    component = models.CharField(max_length=120, blank=True, default='')
    vehicle_type = models.CharField(
        max_length=20,
        choices=[('all', 'All Vehicles'), ('motorcycle', 'Motorcycle'), ('car', 'Car'), ('tricycle', 'Tricycle')],
        default='all',
    )
    manufacturer = models.CharField(max_length=80, blank=True, default='')
    model = models.CharField(max_length=120, blank=True, default='')
    variant = models.CharField(max_length=120, blank=True, default='')
    year_from = models.PositiveSmallIntegerField(null=True, blank=True)
    year_to = models.PositiveSmallIntegerField(null=True, blank=True)
    safety_precautions = models.TextField(blank=True, default='')
    verification_procedure = models.TextField(blank=True, default='', help_text='How to verify the repair safely')
    updated_at = models.DateTimeField(auto_now=True)
    is_verified = models.BooleanField(
        default=False,
        help_text="Only approved guides with a checked source are retrieved.",
    )
    difficulty_level = models.CharField(
        max_length=20,
        choices=[('Beginner', 'Beginner'), ('Intermediate', 'Intermediate'), ('Advanced', 'Advanced')],
        default='Beginner'
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'troubleshooting_guides'

    def __str__(self):
        return self.possible_cause

    def save(self, *args, **kwargs):
        # Verified status is meaningless without an approved review and a
        # recorded source.  Enforce that here as well as in the admin.
        has_source = bool((self.source_reference or '').strip() or (self.source_title or '').strip())
        if self.review_status != 'approved' or not has_source:
            self.is_verified = False
        super().save(*args, **kwargs)


class DiagnosticQuestion(models.Model):
    id = models.AutoField(primary_key=True)
    symptom = models.ForeignKey(
        DiagnosticSymptom,
        related_name='diagnostic_questions',
        on_delete=models.CASCADE,
    )
    question_key = models.CharField(max_length=50, help_text="Identifier for tracking answer state, e.g., 'starter_sound'")
    question_text = models.CharField(max_length=300)
    question_text_tl = models.CharField(max_length=300, blank=True, null=True)
    question_text_hil = models.CharField(max_length=300, blank=True, null=True)
    options_json = models.TextField(
        default='[]',
        help_text='JSON list of multiple-choice options [{"label": "A. Rapid clicking", "value": "clicking", "leads_to": "battery"}]'
    )
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'diagnostic_questions'
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.symptom.symptom_name} - {self.question_key}"


class GuideRequiredPart(models.Model):
    id = models.AutoField(primary_key=True)
    guide = models.ForeignKey(
        TroubleshootingGuide,
        related_name='required_parts',
        on_delete=models.CASCADE,
    )
    part = models.ForeignKey(
        Part,
        related_name='guide_requirements',
        on_delete=models.CASCADE,
    )
    quantity_needed = models.IntegerField(default=1, null=True)

    class Meta:
        db_table = 'guide_required_parts'

    def __str__(self):
        return f'{self.part} for {self.guide}'


class MotorAssistantUser(models.Model):
    id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=100)
    email = models.CharField(max_length=100, unique=True)
    role = models.CharField(max_length=20, default='Mechanic', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.full_name
