"""Import the bundled diagnostic knowledge base.

Every bundled guide records a source reference.  Records without a source are
forced out by the model and retrieval guards, so they can never be displayed
as verified evidence.  Re-check each source for the exact model/variant before
relying on it.
"""

from django.core.management.base import BaseCommand

from apps.motor.knowledge import seed_default_knowledge


class Command(BaseCommand):
    help = 'Import the bundled diagnostic knowledge (idempotent).'

    def handle(self, *args, **options):
        result = seed_default_knowledge()
        self.stdout.write(
            'Seeded symptoms=%(symptoms)s guides=%(guides)s questions=%(questions)s.' % result
        )
        self.stdout.write(
            self.style.WARNING(
                'Bundled sources are general references. Re-check each record '
                'against the manual for the exact model and variant before '
                'relying on its measurements or part guidance.'
            )
        )
