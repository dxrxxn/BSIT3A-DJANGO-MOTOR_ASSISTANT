import django
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'motor_assistant_projectv3.settings'
django.setup()

from apps.core.views import _jarvis_response
from django.contrib.auth import get_user_model

u = get_user_model().objects.first()

# Test what the AI can respond to
tests = [
    'engine wont start',
    'spongy brakes', 
    'strange engine noise',
    'smoke from exhaust',
    'battery dead',
    'oil change',
    'tyre check',
    'coolant leak',
    'spark plug foul',
    'clutch adjustment',
    'help',
    'what can you do',
    'how many symptoms',
    'how many parts',
    'how many guides',
    'list symptoms',
    'list parts',
    'thank you',
]

for msg in tests:
    try:
        r = _jarvis_response(msg, u)
        # Print first 100 chars
        print(f'"{msg}" -> {r[:80]}...')
    except Exception as e:
        print(f'"{msg}" -> ERROR: {e}')