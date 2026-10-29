"""Safety assessment for motorcycle and car diagnostics.

Safety checks run before ordinary troubleshooting.  Warnings are deliberately
worded as possibilities, not confirmed diagnoses.  The module returns both a
severity and the exact user-facing text so the API and UI can pin warnings to
the top of the answer.
"""
from __future__ import annotations

import re

SEVERITY_ORDER = {'none': 0, 'caution': 1, 'warning': 2, 'critical': 3}

LANGUAGE_KEYS = {'english': 'en', 'tagalog': 'tl', 'hiligaynon': 'hil'}

RULES = [
    {
        'key': 'brake_failure',
        'severity': 'critical',
        'stop_use': True,
        'patterns': [
            r'no brakes?', r'brakes? (?:are )?not working', r"brakes? (?:don'?t|do not) work",
            r'brake failure', r'brakes? (?:failed|failing)', r'lost (?:all )?(?:my )?brakes?',
            r'lever (?:goes|sinks|drops).*(?:floor|bar|all the way)',
            r'pedal (?:goes|sinks|drops).*(?:floor|all the way)', r'spongy brake', r'soft brake',
            r'brake.{0,60}(?:spongy|soft|weak|failing|not working|no pressure|will not stop|won.t stop)',
            r'(?:spongy|soft|weak) brake', r'brake fluid leak', r'fluid leak.*brake',
            r'(?:tagas|tumutulo|nagatulo).{0,40}(?:preno|brake)',
            r'(?:preno|brake).{0,40}(?:tagas|tumutulo|nagatulo)',
            r'preno.{0,60}(?:malambot|humok|wala|guba|hindi gumagana|ayaw)',
            r'(?:malambot|humok|wala|guba).{0,60}preno',
            r'walang preno', r'wala(?:ng)? preno', r'guba (?:ang )?preno', r'preno.*guba',
            r'malambot (?:ang )?preno', r'humok (?:ang )?preno',
        ],
        'en': (
            'CRITICAL SAFETY HAZARD: Brake performance may be compromised. Do not ride or drive '
            'the vehicle. Park it on level ground and arrange inspection by a qualified brake '
            'technician. Do not test a suspected brake fault in traffic.'
        ),
        'tl': (
            'KRITIKAL NA BABALA SA KALIGTASAN: Maaaring humina o mawala ang preno. Huwag munang '
            'i-maneho o i-drive ang sasakyan. Iparada sa patag na lugar at ipasuri sa kwalipikadong '
            'mekaniko ng preno. Huwag subukan ang pinaghihinalaang sira sa preno sa trapiko.'
        ),
        'hil': (
            'KRITIKAL NGA PAHILIG-AN SA KALIGTASAN: Mahimo naguba ukon nagluya ang preno. Indi gid '
            'pagpadalagnon ukon pagmaneuhon ang salakyan. Ipundo sa patag nga lugar kag ipasuri '
            'sa kwalipikado nga mekaniko sang preno. Indi pagtilawon ang guba nga preno sa dalan.'
        ),
    },
    {
        'key': 'fuel_leak',
        'severity': 'critical',
        'stop_use': True,
        'patterns': [
            r'fuel leak', r'gas(?:oline)? leak', r'petrol leak', r'raw fuel', r'fuel (?:is )?dripping',
            r'smell(?:s)? (?:of )?(?:fuel|gas|gasoline)', r'amoy gasolina', r'nagatulo.*gas(?:olina)?',
            r'tumutulo.*gas(?:olina)?', r'gasolina.*tumutulo', r'gasolina.*nagatulo',
        ],
        'en': (
            'FIRE HAZARD: A fuel leak may be present. Stop the engine, do not smoke or use a phone '
            'near the vehicle, keep ignition and electrical loads off, and move away if vapour is '
            'strong. Have the leak inspected before starting the engine again.'
        ),
        'tl': (
            'PANGANIB SA SUNOG: Maaaring may tagas ng gasolina. Patayin ang makina, huwag manigarilyo '
            'o gumamit ng telepono malapit sa sasakyan, iwasan ang electrical load, at lumayo kung '
            'malakas ang amoy. Ipasuri ang tagas bago muling i-start.'
        ),
        'hil': (
            'KATALAGMAN SA KALAYO: Mahimo may tulo sang gasolina. Patya ang makina, indi magpanigarilyo '
            'ukon maggamit sang telepono malapit sa salakyan, likawi ang electrical load, kag magpalayo '
            'kon mabaskog ang baho. Ipasusi ang tulo antes mag-start liwat.'
        ),
    },
    {
        'key': 'fire_or_electrical_smoke',
        'severity': 'critical',
        'stop_use': True,
        'patterns': [
            r'(?:vehicle|bike|motor|car|engine|wiring|electrical).*(?:on fire|burning)',
            r'(?:on fire|burning smell|burning wire|electrical smoke|smoke from (?:wiring|battery|dashboard))',
            r'sunog', r'nagausok.*(?:wiring|baterya|dashboard)', r'usok.*(?:wiring|baterya|dashboard)',
        ],
        'en': (
            'FIRE / ELECTRICAL HAZARD: Smoke, burning smell, or fire is reported. Stop the engine, '
            'switch off the ignition, keep away from fuel vapour, and do not continue riding or '
            'driving. Call emergency help if flames are visible. Do not touch damaged high-current wiring.'
        ),
        'tl': (
            'PANGANIB SA SUNOG / KURYENTE: May usok, amoy sunog, o apoy. Patayin ang makina at '
            'ignition, lumayo sa amoy ng gasolina, at huwag ipagpatuloy ang pagmamaneho. Tumawag ng '
            'emergency help kung may apoy. Huwag hawakan ang sirang makapal na wiring.'
        ),
        'hil': (
            'KATALAGMAN SA KALAYO / KURYENTE: May aso, baho sang sunog, ukon kalayo. Patya ang makina '
            'kag ignition, magpalayo sa baho sang gasolina, kag indi magpadayon sa pagmaneho. Tawag '
            'emergency kon may kalayo. Indi pagtanduga ang guba nga dako nga wiring.'
        ),
    },
    {
        'key': 'severe_overheat',
        'severity': 'critical',
        'stop_use': True,
        'patterns': [
            r'overheat.*(?:steam|smoke|boiling|red|max|hot)', r'(?:steam|boiling).*(?:radiator|engine|overheat)',
            r'radiator.*(?:boiling|erupt)', r'temperature.*(?:red|max|hot)', r'nagabukal', r'kumukulo',
            r'singaw.*(?:radiator|makina)', r'nagasingaw.*(?:radiator|makina)',
        ],
        'en': (
            'SEVERE OVERHEATING / SCALD HAZARD: Stop the engine and do not open the radiator cap or '
            'coolant reservoir while hot. Pressurised boiling coolant can erupt and cause severe burns. '
            'Let the engine cool completely and have the cooling system checked before riding or driving.'
        ),
        'tl': (
            'MATINDING INIT / PANGANIB SA PASO: Patayin ang makina at huwag buksan ang radiator cap o '
            'coolant reservoir habang mainit. Maaaring sumabog ang kumukulong coolant at magdulot ng '
            'malubhang paso. Pahintulutang lumamig ang makina at ipasuri ang cooling system bago '
            'ipagpatuloy ang pagmamaneho.'
        ),
        'hil': (
            'GRABE NGA INIT / KATALAGMAN SA PASO: Patya ang makina kag indi pagbukas sang radiator cap '
            'ukon coolant reservoir samtang mainit. Mahimo magsabwag ang nagabukal nga coolant kag '
            'magtuga sang grabe nga paso. Pabugnawa sing bug-os ang makina kag ipasusi ang cooling '
            'system antes magpadayon sa pagmaneho.'
        ),
    },
    {
        'key': 'rod_knock_or_oil_starvation',
        'severity': 'critical',
        'stop_use': True,
        'patterns': [
            r'rod knock', r'deep (?:engine )?knock', r'bottom[- ]end knock', r'heavy knock.*engine',
            r'katok.*(?:makina|ilalim)', r'lagabog.*(?:makina|ilalim)', r'oil (?:pressure )?(?:light|warning).*knock',
            r'no oil', r'dry dipstick', r'ubos.*langis', r'wala(?:ng)? langis',
        ],
        'en': (
            'POSSIBLE SEVERE ENGINE DAMAGE: A deep bottom-end knock or oil-pressure warning may indicate '
            'bearing damage or oil starvation. Shut the engine down immediately and do not restart it. '
            'Continued operation can destroy the engine and increase crash risk. Have it transported.'
        ),
        'tl': (
            'POSIBLENG MALUBHANG SIRA NG MAKINA: Ang malalim na katok sa ilalim o oil-pressure warning '
            'ay maaaring senyales ng sira sa bearing o kawalan ng langis. Patayin agad ang makina at '
            'huwag itong i-restart. Maaaring masira ang makina at magdulot ng panganib sa pagmamaneho. '
            'Ipatow ito.'
        ),
        'hil': (
            'MAHIMO GRABE NGA GUBANG MAKINA: Ang madalom nga lagabog sa idalom ukon oil-pressure warning '
            'mahimo senyales sang guba sa bearing ukon kakulang sang langis. Patya gilayon ang makina kag '
            'indi pag-start liwat. Mahimo maguba ang makina kag magdugang katalagman. Ipatow ini.'
        ),
    },
    {
        'key': 'steering_or_tire_failure',
        'severity': 'critical',
        'stop_use': True,
        'patterns': [
            r'steering (?:failure|failed|locked|locked up)', r'handlebar.*(?:loose|broken)',
            r'wheel.*(?:locked|seized)', r'tire.*(?:blowout|burst|bulge|sidewall tear|exposed cord)',
            r'gulong.*(?:sumabog|pumutok)', r'manubela.*(?:guba|humok)',
        ],
        'en': (
            'CRITICAL SAFETY HAZARD: A steering, wheel, or tyre fault may be present. Do not ride or '
            'drive the vehicle. Keep it stationary and have it inspected or transported by a qualified '
            'workshop. Do not test the fault on the road.'
        ),
        'tl': (
            'KRITIKAL NA BABALA SA KALIGTASAN: Maaaring may sira sa manibela, gulong, o steering. Huwag '
            'munang i-maneho ang sasakyan. Panatilihin itong nakaparada at ipasuri o ipatow sa '
            'kwalipikadong talyer. Huwag subukan ang sira sa kalsada.'
        ),
        'hil': (
            'KRITIKAL NGA PAHILIG-AN SA KALIGTASAN: Mahimo may guba sa manubela, ligid, ukon steering. '
            'Indi gid pagpadalagnon ang salakyan. Pabilin ini nga nakapundo kag ipasusi ukon ipatow sa '
            'kwalipikado nga talyer. Indi pagtilawon ang guba sa dalan.'
        ),
    },
    {
        'key': 'brake_service_caution',
        'severity': 'warning',
        'stop_use': False,
        'patterns': [
            r'\bbrake(?:s| system)?\b', r'\bpreno\b', r'caliper', r'brake pad', r'brake fluid',
        ],
        'exclude': [
            r'no brakes?', r'spongy', r'soft brake', r'brake failure', r'not working',
            r'how (?:do|to) .*bleed', r'what (?:is|are) brake', r'what is a caliper',
            r'picture', r'photo', r'image',
        ],
        'en': (
            'Brake system caution: Brake work involves hydraulic pressure and safety-critical parts. '
            'Use the correct fluid and verify the repair at low speed in a safe area before normal riding.'
        ),
        'tl': (
            'Paalala sa preno: Ang pagkukumpuni ng preno ay may hydraulic pressure at safety-critical '
            'na piyesa. Gamitin ang tamang fluid at i-verify ang repair sa mababang bilis sa ligtas na '
            'lugar bago ang normal na pagmamaneho.'
        ),
        'hil': (
            'Paalala sa preno: Ang pagkay-o sang preno may hydraulic pressure kag safety-critical nga '
            'parte. Gamita ang husto nga fluid kag i-verify ang repair sa mababa nga tulin sa hilway nga '
            'lugar antes normal nga pagmaneho.'
        ),
    },
    {
        'key': 'hot_radiator_caution',
        'severity': 'warning',
        'stop_use': False,
        'patterns': [r'radiator cap', r'coolant cap', r'open.*radiator', r'radiator.*open'],
        'exclude': [r'cold', r'cooled down'],
        'en': (
            'Scald caution: Never open a radiator or coolant cap while the engine is hot. Wait until '
            'the system is completely cool, and use the correct coolant specification for the vehicle.'
        ),
        'tl': (
            'Paalala sa paso: Huwag buksan ang radiator o coolant cap habang mainit ang makina. '
            'Maghintay hanggang ganap na lumamig at gamitin ang tamang coolant specification.'
        ),
        'hil': (
            'Paalala sa paso: Indi pagbukas sang radiator ukon coolant cap samtang mainit ang makina. '
            'Pabugnawa sing bug-os kag gamita ang husto nga coolant specification.'
        ),
    },
]

def assess_safety(message, context='', language='english'):
    """Return a safety assessment dict.

    ``context`` should contain earlier user turns so that a critical fact stated
    previously is not forgotten.  Critical rules are never downgraded because
    the current turn is phrased as a question: "engine on fire, how do I ...?"
    is still a fire report.  Exclusions are only applied to the low-severity
    informational rules; a procedure question must not erase a critical hazard
    such as "brake fluid leak, how do I bleed it?".
    """
    corpus = f'{context}\n{message}'.strip()
    lang = LANGUAGE_KEYS.get((language or 'english').lower(), 'en')
    matched = []

    for rule in RULES:
        if not any(re.search(pattern, corpus, re.IGNORECASE) for pattern in rule['patterns']):
            continue
        if rule['severity'] != 'critical' and any(
            re.search(pattern, corpus, re.IGNORECASE)
            for pattern in rule.get('exclude', [])
        ):
            continue
        matched.append({
            'key': rule['key'],
            'severity': rule['severity'],
            'stop_use': rule['stop_use'],
            'text': rule.get(lang) or rule['en'],
        })

    if not matched:
        return {
            'severity': 'none',
            'stop_use': False,
            'warnings': [],
            'keys': [],
            'summary': '',
        }

    severity = max((item['severity'] for item in matched), key=lambda value: SEVERITY_ORDER[value])
    stop_use = any(item['stop_use'] for item in matched)
    # Deduplicate while preserving order.
    warnings = list(dict.fromkeys(item['text'] for item in matched))
    return {
        'severity': severity,
        'stop_use': stop_use,
        'warnings': warnings,
        'keys': [item['key'] for item in matched],
        'summary': warnings[0] if warnings else '',
    }


def merge_safety_into_structured(structured, safety):
    """Pin local safety warnings ahead of any model-generated warnings."""
    structured = dict(structured or {})
    existing = structured.get('safety') if isinstance(structured.get('safety'), dict) else {}
    existing_warnings = existing.get('warnings') if isinstance(existing.get('warnings'), list) else []
    combined = list(dict.fromkeys(
        [str(item) for item in safety.get('warnings', []) if str(item).strip()]
        + [str(item) for item in existing_warnings if str(item).strip()]
    ))[:10]
    severity_order = ['none', 'caution', 'warning', 'critical']
    sev_candidates = [safety.get('severity', 'none'), existing.get('severity', 'none')]
    severity = max(
        (sev if sev in severity_order else 'none' for sev in sev_candidates),
        key=lambda value: severity_order.index(value),
    )
    structured['safety'] = {
        'severity': severity,
        'summary': combined[0] if combined else '',
        'warnings': combined,
        'stop_use': bool(safety.get('stop_use') or existing.get('stop_use')),
    }
    return structured
