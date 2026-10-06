from decimal import Decimal

from django.db import models
from django.utils import timezone


class DiagnosticSymptom(models.Model):
    id = models.AutoField(primary_key=True)
    symptom_name = models.CharField(max_length=150)
    category = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

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
    repair_instructions = models.TextField()
    advice_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'troubleshooting_guides'

    def __str__(self):
        return self.possible_cause


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
