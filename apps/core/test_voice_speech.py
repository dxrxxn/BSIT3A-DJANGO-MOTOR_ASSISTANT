"""Regression coverage for the J.A.R.V.I.S. 'Listen' speech path.

The structured card shows a 'Next safe action' section.  Voice replies must
read that section too instead of stopping after reply_text.
"""
from pathlib import Path

from django.conf import settings

HOME_TEMPLATE = Path(settings.BASE_DIR) / 'templates' / 'home.html'


def _script():
    return HOME_TEMPLATE.read_text(encoding='utf-8')


def test_speak_structured_reads_next_safe_action():
    script = _script()
    start = script.index('function speakStructured(')
    end = script.index('function speakGuidedOrGeneral(', start)
    body = script[start:end]

    assert 'structured.next_action' in body, (
        'speakStructured must include structured.next_action in the spoken text'
    )
    assert 'Next safe action:' in body, (
        'Spoken next action must be announced with its section label'
    )
    # An early return after reply_text silently dropped every other section.
    assert 'speakText(structured.reply_text' not in body


def test_speak_structured_honours_force_when_muted():
    script = _script()
    start = script.index('function speakStructured(')
    end = script.index('function speakGuidedOrGeneral(', start)
    body = script[start:end]

    assert '!voiceReplyEnabled && !options.force' in body


def test_speech_queue_uses_shared_force_aware_gate():
    script = _script()
    assert 'function speechStillAllowed()' in script
    start = script.index('function playNextSpeechChunk()')
    end = script.index('function speakText(', start)
    body = script[start:end]

    # All chunk-continuation paths must use the gate that understands force.
    assert 'isSpeaking && voiceReplyEnabled' not in body
    assert 'speechStillAllowed()' in body
