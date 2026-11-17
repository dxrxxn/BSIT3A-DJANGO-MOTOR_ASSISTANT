# Generated for the adaptive AI response feature.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_jarvisknowledge_answer_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='experience_level',
            field=models.CharField(
                choices=[
                    ('beginner', 'Beginner'),
                    ('intermediate', 'Intermediate'),
                    ('mechanic', 'Experienced mechanic'),
                ],
                default='beginner',
                help_text='Remembered explanation depth for this conversation.',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='conversation',
            name='explanation_style',
            field=models.CharField(
                choices=[
                    ('auto', 'Adapt automatically'),
                    ('simple', 'Simple, plain language'),
                    ('detailed', 'More detail'),
                    ('step_by_step', 'Step by step'),
                    ('complete', 'Complete procedure'),
                    ('why', 'Explain why it happens'),
                ],
                default='auto',
                help_text='Remembered explanation style requested by the user.',
                max_length=20,
            ),
        ),
    ]
