"""
Live accuracy tests for the Jarvis AI (calls the real Gemini API — consumes quota).

Run with:  python jarvis_live_test.py
"""
import os
import re
import django

os.environ['DJANGO_SETTINGS_MODULE'] = 'mysite.settings'
django.setup()

from apps.core.views import _jarvis_response
from django.contrib.auth import get_user_model

u = get_user_model().objects.first()

TAGALOG_MARKERS = ['ang', 'ng', 'ko', 'mga', 'po', 'sir', 'makina', 'suriin', 'natin', 'inyo', 'iyong', 'hindi', 'lang']
HILIGAYNON_MARKERS = ['imo', 'makina', 'sir', 'ang', 'sang', 'kag', 'subong', 'ako', 'naton', 'salamatan', 'pagsulod']

results = []


def check(name, msg, predicates, history=None):
    reply = _jarvis_response(msg, u, history=history)
    failures = []
    if not reply or not reply.strip():
        failures.append('empty reply')
    else:
        for label, fn in predicates:
            try:
                ok, detail = fn(reply)
            except Exception as e:
                ok, detail = False, f'predicate error: {e}'
            if not ok:
                failures.append(f'{label}: {detail}')
    status = 'PASS' if not failures else 'FAIL'
    results.append((status, name, failures, reply))
    print(f'[{status}] {name}')
    if failures:
        for f in failures:
            print(f'       -> {f}')
    print(f'       reply: {reply[:140]}...')
    return reply


def has_chips(reply):
    m = re.search(r'\[chips:[^\]]+\]', reply)
    return (m is not None, 'chips tag missing')


def n_chips_between(lo, hi):
    def _f(reply):
        m = re.search(r'\[chips:\s*([^\]]+)\]', reply)
        if not m:
            return (False, 'chips tag missing')
        n = len([c for c in m.group(1).split('|') if c.strip()])
        return (lo <= n <= hi, f'{n} chips rendered')
    return _f


def no_vehicle_form(reply):
    return ('[vehicle-form:' not in reply, 'unexpected vehicle-form tag')


def has_vehicle_form(category=None):
    def _f(reply):
        m = re.search(r'\[vehicle-form:\s*([^\]]+)\]', reply)
        if not m:
            return (False, 'vehicle-form tag missing')
        if category:
            try:
                import json
                cat = json.loads(m.group(1)).get('category')
                return (cat == category, f'form category is {cat}, expected {category}')
            except Exception:
                return (False, f'unparseable form payload: {m.group(1)[:60]}')
        return (True, '')
    return _f


def contains_any(words, case_insensitive=True):
    def _f(reply):
        text = reply.lower() if case_insensitive else reply
        for w in words:
            if w.lower() in text:
                return (True, '')
        return (False, f'none of {words} found')
    return _f


def language_is(markers, min_hits=3):
    def _f(reply):
        text = reply.lower()
        hits = sum(1 for m in markers if re.search(r'\b' + re.escape(m) + r'\b', text))
        return (hits >= min_hits, f'only {hits} language markers found')
    return _f


# ─── 1. Diagnostic accuracy & format ───────────────────────────────────────
check('no-start intake', "my motorcycle won't start", [
    ('has vehicle form', has_vehicle_form('start')),
    ('chips 3-5', n_chips_between(3, 5)),
    ('helps first, no brush-off', contains_any(['battery', 'starter', 'crank', 'spark', 'fuel'])),
])

check('no-start + starter symptom (known)', 'rapid clicking sound when i press starter', [
    ('mentions solenoid/battery', contains_any(['solenoid', 'battery', 'voltage', 'relay'])),
    ('chips present', has_chips),
])

check('spongy brakes', 'my brake lever feels spongy', [
    ('mentions bleeding/air/fluid', contains_any(['bleed', 'air', 'fluid', 'brake'])),
    ('chips present', has_chips),
    ('safety awareness', contains_any(['safety', 'careful', 'do not ride', 'traffic'])),
])

check('overheat safety rule', 'my scooter is overheating in traffic', [
    ('radiator cap warning', contains_any(['never open', "don't open", 'do not open', 'cool down', 'cool completely', 'radiator cap'])),
    ('chips present', has_chips),
])

check('white smoke = coolant', 'white smoke from my exhaust and sweet smell', [
    ('mentions head gasket/coolant', contains_any(['head gasket', 'coolant', 'gasket'])),
    ('chips present', has_chips),
])

check('blue smoke = oil', 'blue smoke from exhaust of my underbone', [
    ('mentions oil/rings/seals', contains_any(['oil', 'piston', 'ring', 'seal', 'valve'])),
    ('chips present', has_chips),
])

# ─── 2. Vehicle memory (multi-turn) ────────────────────────────────────────
check('multi-turn memory: brake follow-up', 'yes it is a 2021 honda click 125i with disc brake', [
    ('chips present', has_chips),
], history=[
    {'role': 'user', 'text': 'my brake lever feels spongy'},
    {'role': 'bot', 'text': 'Let us inspect it, sir. Which vehicle is this? [chips: Scooter | Motorcycle | Car]'},
])

follow = _jarvis_response('so what should i check first?', u, history=[
    {'role': 'user', 'text': 'my brake lever feels spongy'},
    {'role': 'bot', 'text': 'Sorry to hear that, sir. Is it disc or drum brake? What make and model is your vehicle? [chips: Disc | Drum]'},
    {'role': 'user', 'text': '2021 honda click 125i disc brake'},
])
mem_ok = follow and not re.search(r'\bwhat (?:make|model|vehicle)\b.*\?', follow, re.I)
results.append(('PASS' if mem_ok else 'FAIL', 'multi-turn: no re-asking known details', [], follow or ''))
print(f"[{'PASS' if mem_ok else 'FAIL'}] multi-turn: no re-asking known details")
print(f'       reply: {(follow or "")[:140]}...')

# ─── 3. Visual queries ─────────────────────────────────────────────────────
check('what is a caliper', 'what is a caliper?', [
    ('has part image', lambda r: ('[part-image:' in r, 'part-image tag missing')),
    ('explains function', contains_any(['clamp', 'piston', 'brake', 'pad'])),
    ('no vehicle form', no_vehicle_form),
])

check('show me a sprocket', 'show me a sprocket', [
    ('has part image', lambda r: ('[part-image:' in r, 'part-image tag missing')),
    ('no vehicle form', no_vehicle_form),
])

# ─── 4. Language handling ──────────────────────────────────────────────────
check('tagalog no-start', 'bakit ayaw mag-start ng makina ko?', [
    ('answers in tagalog', language_is(TAGALOG_MARKERS)),
    ('chips present', has_chips),
])

check('hiligaynon greeting+problem', 'maayong hapon, indi mag-andar ang makina ko', [
    ('answers in hiligaynon', language_is(HILIGAYNON_MARKERS)),
    ('chips present', has_chips),
])

# ─── 5. Robustness ─────────────────────────────────────────────────────────
check('fictional part', 'can you show me the flux capacitor?', [
    ('no vehicle form', no_vehicle_form),
    ('chips present', has_chips),
])

check('gibberish stays helpful', 'asdf qwerty zzz', [
    ('non-empty', lambda r: (bool(r.strip()), 'empty')),
])

check('xss attempt', '<script>alert(1)</script> my engine wont start', [
    ('no raw script tag', lambda r: ('<script>' not in r, 'raw script tag echoed')),
    ('chips present', has_chips),
])

# ─── Report ────────────────────────────────────────────────────────────────
passed = sum(1 for s, *_ in results if s == 'PASS')
print('\n' + '=' * 60)
print(f'RESULTS: {passed}/{len(results)} passed')
for status, name, failures, _ in results:
    if status == 'FAIL':
        print(f'  FAIL {name}: {failures}')
