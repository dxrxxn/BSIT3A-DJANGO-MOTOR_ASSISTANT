"""
Guided motorcycle diagnostic flow — narrow the problem step by step.

This module makes J.A.R.V.I.S. work in the order a real mechanic does:

    1. IDENTIFY the motorcycle (make / model / year / type).
    2. FOCUS on that motorcycle (its layout, drive type, known weak points).
    3. ASK what the problem is (symptom area).
    4. Show WHERE TO LOOK and WHAT "GOOD" LOOKS LIKE (free visual checks).
    5. Ask 1-2 narrowing questions based on what the user found.
    6. Give the likely cause, free fixes, and when to stop.

Everything here is local rule-based logic: no API key, no network, no cost.
State is a plain dict saved in request.session['jarvis_guided'].
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# 1. Motorcycle library (common models in the Philippines / SE Asia)
# ---------------------------------------------------------------------------

# Each profile only describes layout facts and known wear items. It deliberately
# avoids invented torque values or clearances — the owner's manual is the source
# of truth for exact numbers.
BIKE_LIBRARY = {
    'click 125i': {
        'make': 'Honda', 'model': 'Click 125i', 'type': 'scooter',
        'fuel': 'Fuel-injected (FI)', 'drive': 'CVT belt',
        'brakes': 'front disc / rear drum',
        'focus': [
            'Battery and FI fuel pump are the usual no-start suspects.',
            'CVT belt and roller weights wear out; check them if acceleration feels lazy.',
            'Rear drum brake needs periodic adjustment; front disc needs pad checks.',
        ],
    },
    'click 150i': {
        'make': 'Honda', 'model': 'Click 150i', 'type': 'scooter',
        'fuel': 'Fuel-injected (FI)', 'drive': 'CVT belt',
        'brakes': 'front disc / rear disc',
        'focus': [
            'FI pump prime whine should last about 2 seconds at key-on.',
            'CVT belt/rollers and battery are common wear items.',
            'Check both disc brakes for pad thickness and fluid level.',
        ],
    },
    'click': {
        'make': 'Honda', 'model': 'Click', 'type': 'scooter',
        'fuel': 'Fuel-injected (FI)', 'drive': 'CVT belt',
        'brakes': 'front disc / rear drum',
        'focus': ['Battery, FI pump, and CVT belt are the usual checks.'],
    },
    'mio': {
        'make': 'Yamaha', 'model': 'Mio', 'type': 'scooter',
        'fuel': 'Carburetor or FI (depends on year)', 'drive': 'CVT belt',
        'brakes': 'front disc / rear drum',
        'focus': [
            'Older carb models: check the idle mixture and vacuum lines.',
            'CVT belt/rollers and drum brake adjustment are common maintenance points.',
        ],
    },
    'aerox': {
        'make': 'Yamaha', 'model': 'Aerox 155', 'type': 'scooter',
        'fuel': 'Fuel-injected (FI)', 'drive': 'CVT belt',
        'brakes': 'front and rear disc',
        'focus': [
            'FI pump and battery are the first no-start checks.',
            'CVT belt/rollers; check both disc brakes and fluid level.',
        ],
    },
    'nmax': {
        'make': 'Yamaha', 'model': 'NMAX 155', 'type': 'scooter',
        'fuel': 'Fuel-injected (FI)', 'drive': 'CVT belt',
        'brakes': 'front and rear disc',
        'focus': ['FI pump prime, battery health, and CVT belt wear.'],
    },
    'beat': {
        'make': 'Honda', 'model': 'Beat', 'type': 'scooter',
        'fuel': 'Fuel-injected (FI)', 'drive': 'CVT belt',
        'brakes': 'front disc or drum / rear drum',
        'focus': ['Battery, FI pump, and CVT belt are the usual checks.'],
    },
    'pcx': {
        'make': 'Honda', 'model': 'PCX', 'type': 'scooter',
        'fuel': 'Fuel-injected (FI)', 'drive': 'CVT belt',
        'brakes': 'front and rear disc',
        'focus': ['FI pump, battery, CVT belt, and coolant level (liquid-cooled).'],
    },
    'adv': {
        'make': 'Honda', 'model': 'ADV', 'type': 'scooter',
        'fuel': 'Fuel-injected (FI)', 'drive': 'CVT belt',
        'brakes': 'front and rear disc',
        'focus': ['FI pump, battery, CVT belt, and coolant level.'],
    },
    'fazzio': {
        'make': 'Yamaha', 'model': 'Fazzio', 'type': 'scooter',
        'fuel': 'Fuel-injected (FI)', 'drive': 'CVT belt',
        'brakes': 'front disc / rear drum',
        'focus': ['Battery, FI pump, and CVT belt.'],
    },
    'wave': {
        'make': 'Honda', 'model': 'Wave', 'type': 'underbone',
        'fuel': 'Carburetor', 'drive': 'Chain',
        'brakes': 'front disc or drum / rear drum',
        'focus': [
            'Check chain slack and lubrication first — a tight or dry chain causes drag and noise.',
            'Carb models: check fuel flow, air filter, and spark plug.',
        ],
    },
    'xrm': {
        'make': 'Honda', 'model': 'XRM 125', 'type': 'underbone',
        'fuel': 'Carburetor', 'drive': 'Chain',
        'brakes': 'front disc / rear drum',
        'focus': ['Chain and sprocket wear, carburetor cleanliness, and battery.'],
    },
    'raider': {
        'make': 'Suzuki', 'model': 'Raider 150', 'type': 'underbone',
        'fuel': 'Carburetor or FI (depends on year)', 'drive': 'Chain',
        'brakes': 'front and rear disc',
        'focus': ['Chain slack, clutch adjustment, and battery are common checks.'],
    },
    'sniper': {
        'make': 'Yamaha', 'model': 'Sniper', 'type': 'underbone',
        'fuel': 'Fuel-injected (FI)', 'drive': 'Chain',
        'brakes': 'front disc / rear drum',
        'focus': ['FI pump, battery, chain slack, and clutch cable free play.'],
    },
    'smash': {
        'make': 'Suzuki', 'model': 'Smash', 'type': 'underbone',
        'fuel': 'Carburetor', 'drive': 'Chain',
        'brakes': 'front drum / rear drum',
        'focus': ['Carburetor, chain, and drum brake adjustment.'],
    },
    'tmx': {
        'make': 'Honda', 'model': 'TMX 125', 'type': 'backbone',
        'fuel': 'Carburetor', 'drive': 'Chain',
        'brakes': 'front disc / rear drum',
        'focus': ['Chain, carburetor, valve noise, and battery.'],
    },
    'barako': {
        'make': 'Kawasaki', 'model': 'Barako 175', 'type': 'backbone',
        'fuel': 'Carburetor', 'drive': 'Chain',
        'brakes': 'front disc / rear drum',
        'focus': ['Chain, carburetor, and valve clearance checks.'],
    },
    'ct100': {
        'make': 'Kawasaki', 'model': 'CT100', 'type': 'underbone',
        'fuel': 'Carburetor', 'drive': 'Chain',
        'brakes': 'front drum / rear drum',
        'focus': ['Carburetor, chain, and drum brakes.'],
    },
    'burgman': {
        'make': 'Suzuki', 'model': 'Burgman Street', 'type': 'scooter',
        'fuel': 'Fuel-injected (FI)', 'drive': 'CVT belt',
        'brakes': 'front and rear disc',
        'focus': ['FI pump, battery, and CVT belt.'],
    },
    'gravis': {
        'make': 'Yamaha', 'model': 'Gravis', 'type': 'scooter',
        'fuel': 'Fuel-injected (FI)', 'drive': 'CVT belt',
        'brakes': 'front disc / rear drum',
        'focus': ['Battery, FI pump, and CVT belt.'],
    },
}

# Fallback profiles by motorcycle type.
TYPE_LIBRARY = {
    'scooter': {
        'type': 'scooter', 'drive': 'CVT belt',
        'fuel': 'Usually fuel-injected on newer units',
        'brakes': 'front disc / rear drum or disc',
        'focus': [
            'Scooters use a CVT belt and roller weights instead of a chain.',
            'Check battery, FI pump prime, CVT belt, and brake fluid.',
        ],
    },
    'underbone': {
        'type': 'underbone', 'drive': 'Chain',
        'fuel': 'Carburetor or fuel-injected',
        'brakes': 'front disc or drum / rear drum',
        'focus': [
            'Underbones use a chain drive — check slack and lubrication.',
            'Check carb/FI, battery, clutch cable, and drum brake adjustment.',
        ],
    },
    'backbone': {
        'type': 'backbone (standard)', 'drive': 'Chain',
        'fuel': 'Carburetor or fuel-injected',
        'brakes': 'front disc / rear drum',
        'focus': [
            'Standard bikes use a chain drive and often a carburetor.',
            'Check chain, valve noise, carburetor, and battery.',
        ],
    },
    'dual-sport': {
        'type': 'dual-sport', 'drive': 'Chain',
        'fuel': 'Carburetor or fuel-injected',
        'brakes': 'front disc / rear disc',
        'focus': ['Chain, spokes, suspension, and carb/FI checks.'],
    },
    'big bike': {
        'type': 'big bike', 'drive': 'Chain, belt, or shaft',
        'fuel': 'Fuel-injected',
        'brakes': 'front and rear disc',
        'focus': ['Brake fluid, tyres, chain/shaft, and battery checks.'],
    },
}


# ---------------------------------------------------------------------------
# 2. Symptom areas: where to look (free checks) and narrowing questions
# ---------------------------------------------------------------------------

AREAS = {
    'starting': {
        'title': 'Engine will not start / hard starting',
        'chips': 'Engine will not start',
        'checks': [
            ('Battery terminals and voltage',
             'Good: clean, tight, 12.6 V or more at rest.',
             'Bad: white/green corrosion, loose bolts, below 12.0 V.'),
            ('Kill switch and side-stand switch',
             'Good: kill switch on RUN, side stand fully up.',
             'Bad: switch on OFF or stand switch stuck.'),
            ('Fuel supply',
             'Good: petcock ON; FI pump primes for about 2 seconds at key-on.',
             'Bad: no prime sound, kinked hose, empty tank, clogged filter.'),
            ('Main fuse and relays',
             'Good: fuse element intact, relay clicks once.',
             'Bad: blown fuse (replace with same rating) or rapid chatter.'),
            ('Spark plug',
             'Good: light tan tip, strong blue spark when grounded and cranked.',
             'Bad: black/wet tip, no spark, cracked ceramic.'),
        ],
        'questions': [
            {
                'key': 'start_behavior',
                'text': 'What happens when you press the starter button?',
                'options': [
                    ('dead', 'Completely dead - no dashboard lights'),
                    ('click', 'Rapid clicking / relay chatter'),
                    ('slow', 'Cranks slowly'),
                    ('crank_no_fire', 'Cranks normally but will not start'),
                    ('starts_dies', 'Starts briefly, then dies'),
                ],
            },
            {
                'key': 'spark_state',
                'text': 'If you checked the spark plug, what did you see?',
                'options': [
                    ('spark_ok', 'Strong blue spark'),
                    ('spark_none', 'No spark'),
                    ('spark_not_checked', 'Havent checked yet'),
                ],
            },
        ],
    },

    'brakes': {
        'title': 'Brake problem (weak, spongy, noisy)',
        'chips': 'Brakes weak or spongy',
        'checks': [
            ('Brake fluid level and colour',
             'Good: between MIN and MAX, clear amber.',
             'Bad: below MIN, dark brown or cloudy.'),
            ('Brake pads / shoes',
             'Good: more than 2 mm lining, even wear.',
             'Bad: metal-to-metal, uneven wear, oil contamination.'),
            ('Leaks',
             'Good: dry around master cylinder, banjo bolts, caliper.',
             'Bad: wet fluid, greasy dust, dripping.'),
            ('Lever or pedal feel',
             'Good: firm after 3 pumps and holds pressure.',
             'Bad: spongy, sinks to the bar, or no resistance.'),
            ('Disc or drum condition',
             'Good: smooth disc, no deep grooves.',
             'Bad: scoring, blue heat marks, worn drum.'),
        ],
        'questions': [
            {
                'key': 'brake_symptom',
                'text': 'What is the brake doing?',
                'options': [
                    ('spongy', 'Lever/pedal feels soft or spongy'),
                    ('lever_to_bar', 'Lever goes all the way to the bar'),
                    ('weak', 'Firm lever but weak stopping power'),
                    ('noise', 'Squealing or scraping noise'),
                    ('grinding', 'Metal grinding'),
                ],
            },
            {
                'key': 'brake_fluid',
                'text': 'What is the brake fluid level?',
                'options': [
                    ('above_min', 'Above MIN and clear'),
                    ('below_min', 'Below MIN but not empty'),
                    ('empty', 'Empty or almost empty'),
                    ('dark', 'Dark brown / cloudy'),
                ],
            },
        ],
    },

    'overheat': {
        'title': 'Overheating / coolant problem',
        'chips': 'Engine overheating',
        'checks': [
            ('Coolant level (engine cold only)',
             'Good: between LOW and FULL in the reservoir.',
             'Bad: empty reservoir, oil film, milky colour.'),
            ('Radiator fan',
             'Good: spins when the engine is hot.',
             'Bad: never spins, or spins only when tapped.'),
            ('Radiator fins and hoses',
             'Good: clean fins, soft hoses, no cracks.',
             'Bad: clogged with mud, hard/brittle hoses, coolant stains.'),
            ('Engine oil',
             'Good: correct level, normal colour.',
             'Bad: low, milky (water mixed in), or burnt smell.'),
            ('Coolant leaks',
             'Good: no drips under the bike.',
             'Bad: green/pink crust at hoses or water pump.'),
        ],
        'questions': [
            {
                'key': 'overheat_when',
                'text': 'When does it overheat?',
                'options': [
                    ('idle', 'In traffic or at idle'),
                    ('high_speed', 'At high speed / long rides'),
                    ('always', 'All the time, even short rides'),
                    ('steam', 'Steam or coolant boiling over'),
                ],
            },
            {
                'key': 'fan_state',
                'text': 'Does the radiator fan spin when the engine is hot?',
                'options': [
                    ('fan_runs', 'Yes, it spins'),
                    ('fan_dead', 'No, it never spins'),
                    ('fan_unknown', 'Not sure / air-cooled engine'),
                ],
            },
        ],
    },

    'noise': {
        'title': 'Unusual engine or drivetrain noise',
        'chips': 'Strange engine noise',
        'checks': [
            ('Locate the noise',
             'Good: identify top end, bottom end, side cover, or CVT/chain area.',
             'Bad: guessing — use a long screwdriver or hose as a stethoscope (careful of moving parts).'),
            ('Engine oil level',
             'Good: between MIN and MAX, clean.',
             'Bad: low, black, or metallic flakes.'),
            ('Chain / CVT area',
             'Good: chain lubricated with correct slack; CVT cover dry.',
             'Bad: dry/tight chain, loose sprocket, belt dust, loose variator.'),
            ('Exhaust and heat shields',
             'Good: tight bolts, no black soot streaks.',
             'Bad: loose shield, cracked pipe, leaking gasket.'),
            ('Valve cover area (cold engine)',
             'Good: steady light tick that fades when warm.',
             'Bad: loud rhythmic tick that gets worse when hot.'),
        ],
        'questions': [
            {
                'key': 'noise_where',
                'text': 'Where is the noise coming from?',
                'options': [
                    ('top_end', 'Top of the engine (valve cover)'),
                    ('bottom_end', 'Deep inside / bottom of the engine'),
                    ('side_cover', 'Side cover / CVT / chain area'),
                    ('unknown_noise', 'Not sure yet'),
                ],
            },
            {
                'key': 'noise_when',
                'text': 'When is it loudest?',
                'options': [
                    ('idle', 'At idle'),
                    ('accel', 'When accelerating'),
                    ('cold', 'When the engine is cold'),
                    ('always', 'All the time'),
                ],
            },
        ],
    },

    'smoke': {
        'title': 'Exhaust smoke',
        'chips': 'Smoke from exhaust',
        'checks': [
            ('Smoke colour',
             'Good: no visible smoke when warm.',
             'Bad: blue (oil), black (rich fuel), white (coolant).'),
            ('When it appears',
             'Good: none after warm-up.',
             'Bad: only on cold start, only on acceleration, or constantly.'),
            ('Engine oil level',
             'Good: correct level, no smell of fuel.',
             'Bad: low or overfilled, milky, or thinning.'),
            ('Coolant level and colour',
             'Good: normal level, clean coolant.',
             'Bad: dropping level, oily film, milky oil.'),
            ('Air filter and spark plug',
             'Good: clean filter, tan plug.',
             'Bad: clogged filter, black sooty plug.'),
        ],
        'questions': [
            {
                'key': 'smoke_colour',
                'text': 'What colour is the smoke?',
                'options': [
                    ('blue', 'Blue / bluish-white'),
                    ('black', 'Black / dark grey'),
                    ('white', 'White and sweet-smelling'),
                    ('smoke_unknown', 'Not sure'),
                ],
            },
            {
                'key': 'smoke_when',
                'text': 'When do you see it?',
                'options': [
                    ('cold_start', 'Only on cold start'),
                    ('accel', 'When accelerating'),
                    ('idle', 'At idle'),
                    ('always', 'All the time'),
                ],
            },
        ],
    },

    'power': {
        'title': 'Poor acceleration / loss of power',
        'chips': 'Loses power or won\'t accelerate',
        'checks': [
            ('Tyre pressure',
             'Good: about 29-33 psi front, 33-36 psi rear (confirm on your manual).',
             'Bad: soft tyres — rolling drag feels like lost power.'),
            ('Brake drag',
             'Good: wheels spin freely when lifted.',
             'Bad: wheel stops quickly or pads rub.'),
            ('Air filter',
             'Good: clean and light can pass through.',
             'Bad: clogged, oily, or blocked by a rag.'),
            ('Chain or CVT',
             'Good: correct chain slack or clean CVT belt.',
             'Bad: tight/dry chain, worn belt, flat-spotted rollers.'),
            ('Fuel and spark',
             'Good: clean filter, fresh fuel, tan plug.',
             'Bad: old fuel, clogged filter, black plug.'),
        ],
        'questions': [
            {
                'key': 'power_symptom',
                'text': 'What does the bike do when you accelerate?',
                'options': [
                    ('revs_no_speed', 'Engine revs but the bike stays slow'),
                    ('bog', 'Sputters, bogs, or hesitates'),
                    ('no_power', 'Just weak, especially uphill'),
                    ('jerking', 'Jerks or vibrates on take-off'),
                ],
            },
            {
                'key': 'power_when',
                'text': 'When did it start?',
                'options': [
                    ('sudden', 'Suddenly, after a ride or repair'),
                    ('gradual', 'Gradually over weeks'),
                    ('cold_only', 'Only when the engine is cold'),
                    ('power_unknown', 'Not sure'),
                ],
            },
        ],
    },

    'electrical': {
        'title': 'Battery / charging / lights problem',
        'chips': 'Battery or electrical problem',
        'checks': [
            ('Battery voltage',
             'Good: 12.6 V+ at rest, 13.5-14.5 V while revving.',
             'Bad: below 12.0 V at rest or no rise when revving.'),
            ('Terminals and fuses',
             'Good: clean, tight, correct fuse rating.',
             'Bad: corrosion, loose bolts, blown fuse.'),
            ('Lights and horn',
             'Good: bright and steady at idle.',
             'Bad: dim, pulsing, or dead.'),
            ('Charging system',
             'Good: voltage rises when revved.',
             'Bad: voltage stays flat or drops (stator/rectifier).'),
            ('Accessories',
             'Good: none left plugged in overnight.',
             'Bad: USB chargers, alarms, or GPS draining the battery.'),
        ],
        'questions': [
            {
                'key': 'electrical_symptom',
                'text': 'What is the electrical symptom?',
                'options': [
                    ('no_power', 'No power at all'),
                    ('battery_drain', 'Battery keeps dying'),
                    ('dim_lights', 'Lights are dim or pulse'),
                    ('starter_weak', 'Starter turns slowly'),
                ],
            },
            {
                'key': 'battery_age',
                'text': 'How old is the battery?',
                'options': [
                    ('new_battery', 'Less than 1 year'),
                    ('mid_battery', '1-3 years'),
                    ('old_battery', 'More than 3 years'),
                    ('battery_unknown', 'Not sure'),
                ],
            },
        ],
    },

    'chassis': {
        'title': 'Tyres, chain, steering, or suspension',
        'chips': 'Tyres / chain / suspension',
        'checks': [
            ('Tyre pressure and tread',
             'Good: correct pressure, tread above 1.6 mm, no cracks.',
             'Bad: soft, bald centre, sidewall cracks, embedded nails.'),
            ('Chain slack and lube',
             'Good: 25-35 mm slack at the middle, lightly oiled.',
             'Bad: tight, dry, rusty, or loose enough to slap.'),
            ('Wheel bearings and spokes',
             'Good: no play when rocking the wheel, spokes tight.',
             'Bad: side-to-side play, loose or broken spokes.'),
            ('Steering head',
             'Good: turns smoothly with no notch.',
             'Bad: clunk, notch in the centre, or wobble.'),
            ('Suspension',
             'Good: no oil film on fork tubes or shock shaft.',
             'Bad: leaking seals, bottoming out, uneven damping.'),
        ],
        'questions': [
            {
                'key': 'chassis_symptom',
                'text': 'What are you feeling?',
                'options': [
                    ('wobble', 'Wobble or shaking'),
                    ('hard_steer', 'Hard or notchy steering'),
                    ('suspension', 'Bouncy or bottoming suspension'),
                    ('tyre_noise', 'Tyre or chain noise'),
                ],
            },
            {
                'key': 'chassis_when',
                'text': 'When does it happen?',
                'options': [
                    ('low_speed', 'At low speed'),
                    ('high_speed', 'At higher speed'),
                    ('braking', 'When braking'),
                    ('chassis_always', 'All the time'),
                ],
            },
        ],
    },

    'maintenance': {
        'title': 'Routine maintenance (oil, filters, adjustments)',
        'chips': 'Oil change / maintenance',
        'checks': [
            ('Engine oil level',
             'Good: between MIN and MAX on level ground.',
             'Bad: low, black, or smells burnt.'),
            ('Oil colour',
             'Good: amber to light brown.',
             'Bad: black, milky, or gritty.'),
            ('Last oil change',
             'Good: within the manual interval (often 2,000-4,000 km).',
             'Bad: unknown or overdue.'),
            ('Filter and drain bolt',
             'Good: filter clean, drain bolt dry with a fresh crush washer.',
             'Bad: leaking, rounded bolt, missing washer.'),
            ('Other fluids',
             'Good: brake fluid clear, coolant at level.',
             'Bad: dark brake fluid, low coolant.'),
        ],
        'questions': [
            {
                'key': 'maint_symptom',
                'text': 'What maintenance do you want to do?',
                'options': [
                    ('oil_change', 'Engine oil and filter change'),
                    ('chain_service', 'Chain clean and lubricate'),
                    ('brake_check', 'Brake pad and fluid check'),
                    ('tune_up', 'General tune-up'),
                ],
            },
        ],
    },
}


# Short "look here first" list. Three one-line checks keep the first reply
# readable; the full detail lives in AREAS['checks'] for the verdict text.
QUICK_CHECKS = {
    'starting': [
        ('Battery', '12.6 V at rest; terminals clean and tight.'),
        ('Kill switch / stand', 'switch on RUN, side stand fully up.'),
        ('Spark', 'strong blue spark at the plug.'),
    ],
    'brakes': [
        ('Brake fluid', 'between MIN/MAX and clear amber.'),
        ('Pads', 'at least 2 mm of lining left.'),
        ('Lever', 'firm after 3 pumps and holds.'),
    ],
    'overheat': [
        ('Coolant (cold)', 'between LOW and FULL.'),
        ('Fan', 'spins when the engine is hot.'),
        ('Oil', 'correct level, not milky.'),
    ],
    'noise': [
        ('Oil', 'correct level, no metal flakes.'),
        ('Chain / CVT', 'correct slack, no worn belt.'),
        ('Locate it', 'top, bottom, or side of the engine.'),
    ],
    'smoke': [
        ('Colour', 'blue = oil, black = fuel, white = coolant.'),
        ('Oil level', 'correct and not overfilled.'),
        ('Coolant', 'steady level, no bubbles.'),
    ],
    'power': [
        ('Tyres', '29-33 psi front, 33-36 psi rear.'),
        ('Brake drag', 'both wheels spin freely.'),
        ('Chain / CVT', 'correct slack or clean belt.'),
    ],
    'electrical': [
        ('Battery', '12.6 V rest, 13.5-14.5 V revving.'),
        ('Terminals / fuses', 'clean, tight, correct rating.'),
        ('Accessories', 'nothing left on overnight.'),
    ],
    'chassis': [
        ('Tyres', 'correct pressure, tread above 1.6 mm.'),
        ('Chain', '25-35 mm slack, lightly oiled.'),
        ('Bearings', 'no side-to-side wheel play.'),
    ],
    'maintenance': [
        ('Oil', 'between MIN/MAX, amber not black.'),
        ('Last change', 'within the manual interval.'),
        ('Leaks', 'drain bolt and filter dry.'),
    ],
}


# ---------------------------------------------------------------------------
# 3. Verdict rules per area (free fixes first, parts only if needed)
# ---------------------------------------------------------------------------

VERDICTS = {
    'starting': [
        {
            'when': {'start_behavior': 'dead'},
            'title': 'No power reaching the starter',
            'confidence': 'High',
            'why': 'A completely dead dash points to the battery, main fuse, ignition switch, or a loose ground — not the engine itself.',
            'free': [
                'Clean and tighten both battery terminals with a 10 mm wrench.',
                'Check the main fuse beside the starter relay; replace only with the same rating.',
                'Make sure the kill switch is on RUN and the side stand is up.',
            ],
            'parts': ['Battery (only if it will not hold 12.6 V)', 'Main fuse', 'Relay'],
        },
        {
            'when': {'start_behavior': 'click'},
            'title': 'Starter relay chatter / weak battery',
            'confidence': 'High',
            'why': 'The relay clicks rapidly when battery voltage collapses under the starter load. It is usually a weak battery or a bad ground, not a failed starter.',
            'free': [
                'Measure battery voltage at rest: 12.6 V is healthy, below 12.0 V is weak.',
                'Hold the starter and watch the voltage; below 9.6 V means the battery cannot carry the load.',
                'Clean the negative cable where it bolts to the engine/frame.',
                'Try a known-good battery or a jump pack before buying anything.',
            ],
            'parts': ['Battery', 'Starter relay', 'Ground cable'],
        },
        {
            'when': {'start_behavior': 'slow'},
            'title': 'Low cranking power or mechanical drag',
            'confidence': 'Medium',
            'why': 'Slow cranking is either a weak battery/starter circuit or engine oil that is too thick or overfilled.',
            'free': [
                'Check engine oil level and viscosity; overfilled or very cold oil adds drag.',
                'Clean battery terminals and the engine ground.',
                'Measure voltage at the starter during cranking (should stay above about 9.6 V).',
                'If the starter smells hot or is noisy, stop and have it tested.',
            ],
            'parts': ['Battery', 'Starter brushes', 'Engine oil'],
        },
        {
            'when': {'start_behavior': 'crank_no_fire', 'spark_state': 'spark_none'},
            'title': 'No spark (ignition side)',
            'confidence': 'High',
            'why': 'The engine turns over but there is no spark, so the ignition coil, plug cap, stator pickup, or wiring is the likely cause.',
            'free': [
                'Check the spark plug cap is fully seated and not corroded.',
                'Try a known-good plug; confirm the gap is set to the manual spec.',
                'Check the kill switch and side-stand switch again — they cut spark.',
                'Inspect the coil wires for cracks or rubbing.',
            ],
            'parts': ['Spark plug', 'Ignition coil', 'Spark plug cap'],
        },
        {
            'when': {'start_behavior': 'crank_no_fire', 'spark_state': 'spark_ok'},
            'title': 'Spark is OK — look at fuel and compression',
            'confidence': 'Medium',
            'why': 'With a strong blue spark, the missing part of the combustion triangle is fuel or compression.',
            'free': [
                'Confirm fuel reaches the carb/FI: petcock ON, pump primes, filter not clogged.',
                'Check the air filter is not blocked and the intake boot is sealed.',
                'Smell the plug: wet means flooding, bone dry means no fuel.',
                'If both fuel and spark are present, check valve clearance and compression before buying parts.',
            ],
            'parts': ['Fuel filter', 'Air filter', 'Spark plug'],
        },
        {
            'when': {'start_behavior': 'starts_dies'},
            'title': 'Starts then dies (fuel supply or idle circuit)',
            'confidence': 'Medium',
            'why': 'A brief start means the engine fires but cannot sustain idle — usually a clogged idle jet, vacuum leak, or the side-stand switch cutting in.',
            'free': [
                'Hold a little throttle: if it stays running, the idle circuit is clogged.',
                'Check the side-stand switch and clutch switch are not intermittent.',
                'Inspect vacuum hoses and the intake boot for cracks.',
                'Drain the float bowl or run fresh fuel; water in the bowl causes this.',
            ],
            'parts': ['Carburetor cleaner', 'Vacuum hose', 'Fuel filter'],
        },
    ],

    'brakes': [
        {
            'when': {'brake_symptom': 'spongy'},
            'title': 'Air in the hydraulic line',
            'confidence': 'High',
            'why': 'Air compresses, so the lever feels spongy even when the pads are fine. Bleeding the system is the fix.',
            'free': [
                'Top up the reservoir and bleed the caliper until no bubbles appear.',
                'Check banjo bolts and the bleeder for weeping before bleeding.',
                'Pump the lever and hold it: if it slowly sinks, the master cylinder seals may be worn.',
            ],
            'parts': ['DOT 4 brake fluid', 'Bleeder tubing'],
        },
        {
            'when': {'brake_symptom': 'lever_to_bar', 'brake_fluid': 'empty'},
            'priority': 100,
            'title': 'Hydraulic loss — do not ride',
            'confidence': 'High',
            'why': 'An empty reservoir with a lever that reaches the bar means fluid is escaping or air has entered. Braking cannot be trusted.',
            'free': [
                'Do not ride the bike. Park it and inspect for leaks at the caliper, hose, and master cylinder.',
                'If no leak is visible, bleed the system and refill with fresh DOT 4.',
                'If the lever still sinks, rebuild or replace the master cylinder.',
            ],
            'parts': ['Master cylinder repair kit', 'Brake hose', 'DOT 4 fluid'],
        },
        {
            'when': {'brake_symptom': 'lever_to_bar'},
            'priority': 70,
            'title': 'Air in the line or worn master-cylinder seals',
            'confidence': 'High',
            'why': 'A lever that reaches the bar while fluid is still in the reservoir usually means air in the system or worn master-cylinder cups.',
            'free': [
                'Bleed the system first — trapped air is the cheapest cause to rule out.',
                'Hold the lever for 30 seconds: if it slowly sinks, the master cylinder seals are worn.',
                'Inspect the caliper and hose for leaks before ordering parts.',
            ],
            'parts': ['Master cylinder repair kit', 'DOT 4 brake fluid', 'Bleeder tubing'],
        },
        {
            'when': {'brake_symptom': 'weak', 'brake_fluid': 'above_min'},
            'title': 'Pads or disc contamination',
            'confidence': 'Medium',
            'why': 'A firm lever with weak stopping usually means glazed pads, oil on the disc, or a worn disc surface.',
            'free': [
                'Clean the disc with brake cleaner and clean the pad surface.',
                'Measure pad thickness; replace if under 2 mm.',
                'Check the disc for deep grooves or blue heat marks.',
            ],
            'parts': ['Brake pads', 'Brake cleaner', 'Brake disc (if scored)'],
        },
        {
            'when': {'brake_symptom': 'grinding'},
            'priority': 90,
            'title': 'Metal-to-metal — stop using the brake',
            'confidence': 'High',
            'why': 'The friction material is gone and the backing plate is cutting the disc.',
            'free': [
                'Stop riding. Continued use will destroy the disc and can cause brake loss.',
                'Remove the pads and inspect the disc for deep scoring.',
            ],
            'parts': ['Brake pads', 'Brake disc (if below minimum thickness)'],
        },
        {
            'when': {'brake_symptom': 'noise'},
            'title': 'Glazed pads or dust',
            'confidence': 'Medium',
            'why': 'Squeal is usually vibration from glazed pads or road dust, not an immediate failure.',
            'free': [
                'Clean the caliper and disc with brake cleaner.',
                'Lightly scuff the pad surface and apply copper grease only to the backing plate contact points.',
                'Check pad thickness before reusing.',
            ],
            'parts': ['Brake cleaner', 'Brake pads (if thin)'],
        },
        {
            'when': {'brake_symptom': 'leak'},
            'priority': 80,
            'title': 'Brake fluid leak',
            'confidence': 'High',
            'why': 'Any active leak is a safety issue: pressure cannot build reliably.',
            'free': [
                'Do not ride. Identify the leak at the master cylinder, hose, or caliper.',
                'Tighten fittings gently; do not overtighten banjo bolts.',
                'Bleed and refill only after the leak is fixed.',
            ],
            'parts': ['Copper washers', 'Brake hose', 'Master cylinder kit'],
        },
    ],

    'overheat': [
        {
            'when': {'overheat_when': 'idle', 'fan_state': 'fan_dead'},
            'title': 'Radiator fan not working',
            'confidence': 'High',
            'why': 'No airflow at idle makes the temperature climb. The fan circuit (fuse, relay, thermo switch, motor) is the likely cause.',
            'free': [
                'Check the fan fuse and relay first.',
                'Jump the fan directly to the battery briefly: if it spins, the switch or wiring is at fault.',
                'Check the thermo switch connector for corrosion.',
            ],
            'parts': ['Fan motor', 'Thermo switch', 'Fuse/relay'],
        },
        {
            'when': {'overheat_when': 'high_speed'},
            'title': 'Cooling capacity or coolant flow issue',
            'confidence': 'Medium',
            'why': 'Overheating only at speed usually means a clogged radiator, stuck thermostat, weak pump, or wrong coolant mix.',
            'free': [
                'Clean the radiator fins from the front with low-pressure water.',
                'Check coolant level and mix (engine cold only).',
                'Feel the radiator hoses: a cold lower hose can mean a stuck thermostat.',
            ],
            'parts': ['Thermostat', 'Coolant', 'Water pump seal'],
        },
        {
            'when': {'overheat_when': 'steam'},
            'priority': 100,
            'title': 'Boiling coolant — stop and cool down',
            'confidence': 'High',
            'why': 'Steam means the system is pressurized beyond normal. Never open the cap while hot.',
            'free': [
                'Stop the engine and let it cool for at least 45 minutes before touching the cap.',
                'Check for leaks and top up only after it is cold.',
                'Look for a milky oil window or bubbles in the radiator — possible head gasket.',
            ],
            'parts': ['Coolant', 'Hose', 'Head gasket (if confirmed)'],
        },
        {
            'when': {},
            'title': 'General cooling system check',
            'confidence': 'Medium',
            'why': 'Start with the free checks before replacing parts.',
            'free': [
                'Check coolant level cold, fan operation, radiator fins, and hoses.',
                'Confirm the engine oil is at the correct level and not milky.',
            ],
            'parts': ['Coolant', 'Fan motor', 'Thermostat'],
        },
    ],

    'noise': [
        {
            'when': {'noise_where': 'top_end'},
            'title': 'Valve tappet clearance',
            'confidence': 'Medium',
            'why': 'A rhythmic top-end tick that changes with temperature is usually valve clearance, not a failing engine.',
            'free': [
                'Check engine oil level first.',
                'Inspect valve clearance cold against the manual spec before adjusting.',
                'Check the cam chain tensioner for a loose rattle at the same time.',
            ],
            'parts': ['Valve cover gasket', 'Feeler gauge'],
        },
        {
            'when': {'noise_where': 'bottom_end'},
            'priority': 100,
            'title': 'Possible bottom-end bearing wear — stop the engine',
            'confidence': 'High',
            'why': 'A deep knock from the crankcase is serious. Continued running can throw a rod.',
            'free': [
                'Shut the engine off and do not restart it.',
                'Drain the oil into a clean pan and look for metal flakes.',
                'Have the bike inspected before riding again.',
            ],
            'parts': ['Oil', 'Bearing set (workshop job)'],
        },
        {
            'when': {'noise_where': 'side_cover'},
            'title': 'CVT, chain, or side-cover noise',
            'confidence': 'Medium',
            'why': 'On scooters this is usually belt/roller wear; on chain-drive bikes it is slack, dryness, or a loose sprocket.',
            'free': [
                'For a chain: check slack (about 25-35 mm) and lubricate it.',
                'For a CVT: remove the cover and inspect belt width, glazing, and roller flats.',
                'Check the sprocket nuts and variator nut are tight.',
            ],
            'parts': ['Chain lube', 'CVT belt', 'Roller weights'],
        },
        {
            'when': {'noise_where': 'exhaust'},
            'title': 'Exhaust leak or loose shield',
            'confidence': 'Medium',
            'why': 'A loose heat shield or failed exhaust gasket sounds like a metallic buzz that follows engine speed.',
            'free': [
                'Tighten heat-shield bolts and check for cracks.',
                'Look for black soot streaks at the cylinder head pipe joint.',
            ],
            'parts': ['Exhaust gasket', 'Bolts'],
        },
        {
            'when': {},
            'title': 'Locate before replacing',
            'confidence': 'Tentative',
            'why': 'Noise travels through the frame. Identify the exact area before buying parts.',
            'free': [
                'Use a hose or long screwdriver as a stethoscope (stay clear of moving parts).',
                'Rev the engine slowly and note whether the noise follows RPM or road speed.',
            ],
            'parts': [],
        },
    ],

    'smoke': [
        {
            'when': {'smoke_colour': 'blue'},
            'title': 'Oil burning (rings or valve seals)',
            'confidence': 'Medium',
            'why': 'Blue smoke is oil entering the combustion chamber. Cold-start-only smoke points to valve seals; constant smoke points to rings.',
            'free': [
                'Check the oil level; overfilling can cause blue smoke.',
                'Do a compression test before opening the engine.',
                'Clean the crankcase breather and check the air filter is not soaked in oil.',
            ],
            'parts': ['Valve stem seals', 'Piston rings', 'Engine oil'],
        },
        {
            'when': {'smoke_colour': 'black'},
            'title': 'Rich fuel mixture',
            'confidence': 'Medium',
            'why': 'Black smoke means too much fuel or too little air.',
            'free': [
                'Clean or replace the air filter.',
                'Confirm the choke/enricher is fully off when warm.',
                'Check the spark plug for dry black soot.',
                'On carb models, check the float height and clean the jets.',
            ],
            'parts': ['Air filter', 'Spark plug', 'Carb cleaner'],
        },
        {
            'when': {'smoke_colour': 'white'},
            'title': 'Coolant entering combustion',
            'confidence': 'Medium',
            'why': 'Sweet-smelling white smoke plus a dropping coolant level suggests a head gasket or cracked head.',
            'free': [
                'Check the coolant level cold and look for bubbles in the radiator.',
                'Check the oil window for milky emulsion.',
                'Do not open the radiator cap while hot.',
            ],
            'parts': ['Head gasket', 'Coolant'],
        },
        {
            'when': {},
            'title': 'Identify the colour first',
            'confidence': 'Tentative',
            'why': 'The colour tells you which system to inspect.',
            'free': [
                'Blue = oil, black = fuel, white = coolant. Watch it on a cold start and under acceleration.',
            ],
            'parts': [],
        },
    ],

    'power': [
        {
            'when': {'power_symptom': 'revs_no_speed'},
            'title': 'Slipping clutch or worn CVT belt',
            'confidence': 'High',
            'why': 'The engine revs but road speed does not follow, so power is not reaching the wheel.',
            'free': [
                'For a manual bike: check clutch cable free play (about 2-3 mm) and adjust.',
                'For a scooter: inspect the CVT belt width and roller weights for flats.',
                'Check the rear wheel spins freely with the engine off.',
            ],
            'parts': ['Clutch plates', 'CVT belt', 'Roller weights'],
        },
        {
            'when': {'power_symptom': 'bog'},
            'title': 'Fuel or air delivery problem',
            'confidence': 'Medium',
            'why': 'Bogging or hesitation is usually a dirty air filter, clogged jet, weak pump, or vacuum leak.',
            'free': [
                'Clean or replace the air filter.',
                'Drain the float bowl; look for water or dirt.',
                'Check vacuum hoses and the intake boot for cracks.',
                'Try fresh fuel if the bike sat for months.',
            ],
            'parts': ['Air filter', 'Carb cleaner', 'Fuel filter'],
        },
        {
            'when': {'power_symptom': 'no_power'},
            'title': 'Mechanical drag or low compression',
            'confidence': 'Medium',
            'why': 'Weak power everywhere can come from brake drag, low tyre pressure, a clogged exhaust, or low compression.',
            'free': [
                'Check tyre pressure and lift each wheel to confirm it spins freely.',
                'Check the air filter and exhaust for blockage.',
                'Do a compression test before buying engine parts.',
            ],
            'parts': ['Air filter', 'Spark plug', 'Gaskets'],
        },
        {
            'when': {'power_symptom': 'jerking'},
            'title': 'Drivetrain snatch',
            'confidence': 'Medium',
            'why': 'Jerking on take-off is often a loose chain, worn CVT rollers, or a sticking clutch.',
            'free': [
                'Check chain slack and sprocket wear.',
                'Inspect CVT rollers and belt for flat spots.',
                'Check engine mounts and clutch cable adjustment.',
            ],
            'parts': ['Chain/sprocket set', 'Roller weights', 'Clutch springs'],
        },
    ],

    'electrical': [
        {
            'when': {'electrical_symptom': 'no_power'},
            'priority': 70,
            'title': 'Main fuse, battery, or ignition switch',
            'confidence': 'High',
            'why': 'A completely dead electrical system points to the main fuse, a flat battery, a loose ground, or the ignition switch — not the engine.',
            'free': [
                'Check the main fuse beside the battery/relay; replace only with the same rating.',
                'Measure battery voltage at rest: 12.6 V is healthy, below 12.0 V is flat.',
                'Clean and tighten both battery terminals and the frame ground.',
                'Confirm the ignition switch and kill switch are actually making contact.',
            ],
            'parts': ['Main fuse', 'Battery', 'Ignition switch'],
        },
        {
            'when': {'electrical_symptom': 'battery_drain', 'battery_age': 'old_battery'},
            'title': 'Battery at end of life',
            'confidence': 'High',
            'why': 'A battery over 3 years old that keeps dying is usually sulfated and cannot hold a charge.',
            'free': [
                'Charge it fully, then measure after 1 hour: below 12.4 V means it is weak.',
                'Check for accessories left on overnight.',
                'Confirm charging voltage rises to 13.5-14.5 V when revved.',
            ],
            'parts': ['Battery'],
        },
        {
            'when': {'electrical_symptom': 'battery_drain'},
            'title': 'Parasitic drain or weak charging',
            'confidence': 'Medium',
            'why': 'If the battery is good but keeps dying, something is drawing current or the charging system is weak.',
            'free': [
                'With the key off, disconnect the negative terminal and touch a test light between the cable and post; a glow means a drain.',
                'Measure charging voltage at the battery when revved.',
                'Unplug accessories one by one to find the drain.',
            ],
            'parts': ['Rectifier/regulator', 'Stator', 'Battery'],
        },
        {
            'when': {'electrical_symptom': 'dim_lights'},
            'title': 'Charging or ground problem',
            'confidence': 'Medium',
            'why': 'Dim or pulsing lights usually mean low voltage or a bad ground.',
            'free': [
                'Clean battery terminals and the frame ground.',
                'Measure voltage at idle and at 3,000 rpm.',
                'Check the headlight connector for corrosion.',
            ],
            'parts': ['Rectifier/regulator', 'Bulb/LED', 'Ground cable'],
        },
        {
            'when': {},
            'title': 'Start with voltage measurements',
            'confidence': 'Medium',
            'why': 'Measure before replacing anything.',
            'free': [
                'Resting voltage, cranking voltage, and charging voltage tell you whether the battery, starter, or charging system is at fault.',
            ],
            'parts': ['Battery', 'Fuse', 'Rectifier/regulator'],
        },
    ],

    'chassis': [
        {
            'when': {'chassis_symptom': 'wobble'},
            'title': 'Wheel, tyre, or steering play',
            'confidence': 'Medium',
            'why': 'Wobble comes from tyre pressure, unbalanced wheels, loose bearings, or a loose steering head.',
            'free': [
                'Check tyre pressure and look for bulges or uneven wear.',
                'Lift the front wheel and rock it for bearing play.',
                'Check spokes and axle nuts.',
            ],
            'parts': ['Wheel bearings', 'Tyre', 'Spokes'],
        },
        {
            'when': {'chassis_symptom': 'hard_steer'},
            'title': 'Steering head bearings',
            'confidence': 'Medium',
            'why': 'A notch or heavy feel in the centre is usually worn or overtightened steering head bearings.',
            'free': [
                'Lift the front end and turn the bars slowly; a notch means new bearings.',
                'Check tyre pressure first — low pressure feels heavy.',
            ],
            'parts': ['Steering head bearing kit', 'Grease'],
        },
        {
            'when': {'chassis_symptom': 'suspension'},
            'title': 'Fork or shock issue',
            'confidence': 'Medium',
            'why': 'Bouncy or bottoming suspension is usually low oil, worn seals, or worn springs.',
            'free': [
                'Check fork tubes and shock shafts for oil film.',
                'Set preload to the manual setting and test again.',
                'Check tyre pressure before blaming the suspension.',
            ],
            'parts': ['Fork seals', 'Fork oil', 'Shock absorber'],
        },
        {
            'when': {},
            'title': 'Check the free items first',
            'confidence': 'Medium',
            'why': 'Pressure, slack, and bearing play explain most chassis complaints.',
            'free': [
                'Tyre pressure, chain slack, wheel bearing play, and steering notch.',
            ],
            'parts': [],
        },
    ],

    'maintenance': [
        {
            'when': {'maint_symptom': 'oil_change'},
            'title': 'Engine oil and filter change',
            'confidence': 'High',
            'why': 'Fresh oil is the cheapest way to protect the engine.',
            'free': [
                'Warm the engine for 2-3 minutes, then shut it off.',
                'Drain into a clean pan, replace the crush washer, and refill with the manual-specified oil.',
                'Check the level on level ground after running for a minute.',
            ],
            'parts': ['Engine oil (JASO MA/MA2)', 'Oil filter', 'Crush washer'],
        },
        {
            'when': {'maint_symptom': 'chain_service'},
            'title': 'Chain clean and lubricate',
            'confidence': 'High',
            'why': 'A clean, correctly tensioned chain lasts longer and steals less power.',
            'free': [
                'Clean with kerosene or chain cleaner, then wipe dry.',
                'Set slack to the manual spec (often 25-35 mm at the middle).',
                'Lubricate the inside of the chain while spinning the wheel by hand.',
            ],
            'parts': ['Chain cleaner', 'Chain lube'],
        },
        {
            'when': {},
            'title': 'Routine check',
            'confidence': 'High',
            'why': 'Most maintenance is inspection and adjustment before parts are needed.',
            'free': [
                'Check oil, tyre pressure, chain/CVT, brakes, lights, and fasteners.',
            ],
            'parts': ['Engine oil', 'Chain lube', 'Brake fluid'],
        },
    ],
}


# ---------------------------------------------------------------------------
# 4. Language strings for the guided prompts
# ---------------------------------------------------------------------------

T = {
    'english': {
        'identify': "Which motorcycle are we working on?\n\nModel and year is enough (example: *Click 125i 2022*).",
        'identify_chips': "Click 125i | Mio | Wave 125 | Not sure",
        'type_ask': "No problem. What type of motorcycle is it?",
        'type_chips': "Scooter | Underbone | Standard | Big bike | Not sure",
        'year_ask': "What year is your **{bike}**?",
        'year_chips': "2024 | 2023 | 2022 | Not sure",
        'focus': "Focus vehicle",
        'area_ask': "What is the problem?",
        'area_chips': "Won't start | Brakes | Overheating | Engine noise | Smoke | No power | Electrical | Tyres / chain | Oil / service",
        'where': "Where to look first (free checks)",
        'good': "Good",
        'bad': "Bad",
        'narrow': "Narrow it down:",
        'verdict': "Most likely cause",
        'free_fix': "Try first (free)",
        'parts': "Parts only if needed",
        'stop': "Stop if",
        'reset': "Fresh diagnostic, sir. Which motorcycle are we working on?",
        'reset_chips': "Click 125i | Mio | Wave 125 | Not sure",
        'safe_stop': "If you are unsure or the bike feels unsafe, stop and have a qualified mechanic check it. Do not test faulty brakes or a knocking engine on the road.",
        'again': "Let us narrow it further. Choose the closest answer:",
        'verdict_chips': "It worked | Still not fixed | Another check | Start over",
        'checks_repeat': "Here are the free checks again. Tell me what you find:",
    },
    'tagalog': {
        'identify': "Anong motor ang aayusin natin?\n\nModelo at taon lang (halimbawa: *Click 125i 2022*).",
        'identify_chips': "Click 125i | Mio | Wave 125 | Hindi sigurado",
        'type_ask': "Sige. Anong klaseng motor ito?",
        'type_chips': "Scooter | Underbone | Standard | Big bike | Hindi sigurado",
        'year_ask': "Anong taon ang **{bike}** mo?",
        'year_chips': "2024 | 2023 | 2022 | Hindi sigurado",
        'focus': "Pokus na motor",
        'area_ask': "Ano ang problema?",
        'area_chips': "Ayaw mag-start | Preno | Nag-o-overheat | Ingay ng makina | Usok | Walang power | Kuryente | Gulong / chain | Oil / service",
        'where': "Saan titingin muna (libreng checks)",
        'good': "Maayos",
        'bad': "May problema",
        'narrow': "Paliitin natin:",
        'verdict': "Pinakamalamang na sanhi",
        'free_fix': "Gawin muna (libre)",
        'parts': "Parts lang kung kailangan",
        'stop': "Huminto kung",
        'reset': "Bagong diagnosis, sir. Anong motor ang aayusin natin?",
        'reset_chips': "Click 125i | Mio | Wave 125 | Hindi sigurado",
        'safe_stop': "Kung hindi ka sigurado o parang delikado ang motor, huminto at ipatingin sa kwalipikadong mekaniko. Huwag subukan ang sira na preno o kumatok na makina sa kalsada.",
        'again': "Paliitin pa natin. Piliin ang pinakamalapit na sagot:",
        'verdict_chips': "Nagana na | Hindi pa | Ibang check | Simula ulit",
        'checks_repeat': "Ito ulit ang libreng checks. Sabihin kung ano ang nakita mo.",
    },
    'hiligaynon': {
        'identify': "Ano nga motor ang aayusin naton?\n\nModelo kag tuig lang (halimbawa: *Click 125i 2022*).",
        'identify_chips': "Click 125i | Mio | Wave 125 | Indi sigurado",
        'type_ask': "Sige. Ano nga klase sang motor ini?",
        'type_chips': "Scooter | Underbone | Standard | Big bike | Indi sigurado",
        'year_ask': "Ano nga tuig ang **{bike}** mo?",
        'year_chips': "2024 | 2023 | 2022 | Indi sigurado",
        'focus': "Pokus nga motor",
        'area_ask': "Ano ang problema?",
        'area_chips': "Indi mag-start | Preno | Nag-overheat | Tingog sang makina | Aso | Wala power | Kuryente | Gulong / chain | Oil / service",
        'where': "Diin kitaon una (libre nga checks)",
        'good': "Maayo",
        'bad': "May problema",
        'narrow': "Paliiton naton:",
        'verdict': "Pinakamahimo nga kabangdanan",
        'free_fix': "Himuaon una (libre)",
        'parts': "Parts lang kon kinahanglan",
        'stop': "Magpundo kon",
        'reset': "Bag-o nga diagnosis, sir. Ano nga motor ang aayuhon naton?",
        'reset_chips': "Click 125i | Mio | Wave 125 | Indi sigurado",
        'safe_stop': "Kon indi ka sigurado ukon mabudlay ang motor, magpundo kag ipatan-aw sa kwalipikado nga mekaniko. Indi pagtestingi ang guba nga preno ukon nagakatok nga makina sa dalan.",
        'again': "Paliiton pa naton. Pilia ang pinakamalapit nga sabat:",
        'verdict_chips': "Nagana na | Indi gihapon | Iban nga check | Sugod liwat",
        'checks_repeat': "Ari liwat ang libre nga checks. Sabta ako kon ano ang nakita mo.",
    },
}


# ---------------------------------------------------------------------------
# 5. Helpers
# ---------------------------------------------------------------------------

RESET_PHRASES = [
    'start over', 'start again', 'new problem', 'another problem', 'reset',
    'simula ulit', 'bagong problema', 'sugod liwat', 'clear chat',
    'clear history', 'clear conversation',
]

SKIP_PHRASES = [
    'not sure', 'no idea', 'dont know', "don't know", 'idk', 'unknown',
    'hindi sigurado', 'ewan', 'indi sigurado', 'wala ko kabalo', 'skip',
]

GREETING_PREFIXES = [
    'hello', 'hi ', 'hi', 'hey', 'good morning', 'good afternoon',
    'good evening', 'kamusta', 'kumusta', 'maayong',
]

# Keywords that tell us the user is reporting a symptom (not chatting).
SYMPTOM_KEYWORDS = {
    'starting': [
        "won't start", 'wont start', "can't start", 'cannot start', "doesn't start",
        'doesnt start', 'not starting', 'hard to start', 'will not start',
        'wont fire', "won't fire", 'refuses to start', 'ayaw mag-start',
        'ayaw umandar', 'indi mag-andar', 'indi magstart', 'hindi mag-start',
        'no start', 'mag-start', 'mag-andar', 'magstart', 'ayaw mag-andar',
    ],
    'brakes': [
        'brake', 'brakes', 'preno', 'spongy', 'soft lever', 'malambot', 'humok',
        'stopping', 'caliper', 'brake pad',
    ],
    'overheat': [
        'overheat', 'overheating', 'radiator', 'coolant', 'steam', 'boiling',
        'nag-o-overheat', 'nagabukal', 'singaw', 'temp light', 'temperature',
    ],
    'noise': [
        'noise', 'noisy', 'knock', 'knocking', 'ticking', 'rattle', 'rattling',
        'ingay', 'maingay', 'katok', 'kumatok', 'lagabog', 'ticking sound',
        'tingog', 'kakaiba nga tingog',
    ],
    'smoke': [
        'smoke', 'smoking', 'usok', 'umuusok', 'aso',
    ],
    'power': [
        'no power', 'lose power', 'loss of power', 'slow', 'sluggish', 'bog',
        'sputter', 'hesitate', 'jerking', 'won\'t accelerate', 'wont accelerate',
        'nawawalan ng power', 'nawad-an power', 'walang power', 'wala power',
        'mabagal', 'hindi bumibilis',
    ],
    'electrical': [
        'battery', 'baterya', 'charging', 'alternator', 'stator', 'rectifier',
        'dim light', 'no lights', 'electrical', 'kuryente', 'dead battery',
    ],
    'chassis': [
        'tyre', 'tire', 'gulong', 'chain', 'sprocket', 'suspension', 'wobble',
        'steering', 'shock', 'fork', 'bearing',
    ],
    'maintenance': [
        'oil change', 'change oil', 'oil', 'maintenance', 'tune up', 'tune-up',
        'langis', 'change oil', 'filter',
    ],
}


def _norm(text):
    return (text or '').lower().strip()


def _has_any(text, phrases):
    return any(p in text for p in phrases)


def _lang_key(lang):
    if lang in T:
        return lang
    return 'english'


def _tr(lang, key):
    return T[_lang_key(lang)].get(key, T['english'].get(key, ''))


def _flag(lang, key):
    # For labels like GOOD/BAD we keep it simple and localized where available.
    return _tr(lang, key)


def resolve_profile(vehicle_info, message='', history=None):
    """Returns a bike profile dict for the extracted vehicle info."""
    corpus = _norm(message)
    history_corpus = ''
    if history:
        for turn in history:
            history_corpus += " " + _norm(turn.get('text', ''))

    # Prefer a model named in the CURRENT message; only then look at history,
    # so an old bike in the chat log can never override a new one.
    profile = None
    for source in (corpus, corpus + " " + history_corpus):
        for key in sorted(BIKE_LIBRARY, key=len, reverse=True):
            if re.search(r'\b' + re.escape(key) + r'\b', source):
                profile = dict(BIKE_LIBRARY[key])
                profile['key'] = key
                break
        if profile:
            break

    if profile is None:
        v_type = (vehicle_info or {}).get('type') or ''
        if 'scooter' in v_type:
            profile = dict(TYPE_LIBRARY['scooter'])
            profile['key'] = 'generic-scooter'
        elif 'tricycle' in v_type:
            profile = dict(TYPE_LIBRARY['underbone'])
            profile['key'] = 'generic-tricycle'
        elif 'car' in v_type:
            profile = {
                'type': 'car', 'drive': 'varies', 'fuel': 'varies',
                'brakes': 'front disc / rear drum or disc',
                'focus': ['This module is tuned for motorcycles; car checks are generic.'],
                'key': 'generic-car',
            }
        else:
            profile = dict(TYPE_LIBRARY['underbone'])
            profile['key'] = 'generic-underbone'

    # Fill in extracted details.
    for field in ('make', 'model', 'year'):
        if (vehicle_info or {}).get(field):
            profile[field] = vehicle_info[field]
    profile.setdefault('make', '')
    profile.setdefault('model', '')
    profile.setdefault('year', '')
    return profile


def bike_label(profile):
    return " ".join(filter(None, [
        profile.get('year'), profile.get('make'), profile.get('model')
    ])).strip() or "your motorcycle"


YEAR_RE = re.compile(r'\b(19[5-9]\d|20[0-2]\d)\b')


def _extract_year(text):
    match = YEAR_RE.search(text or '')
    return match.group(1) if match else ''


def _needs_year(profile, state):
    """Only ask when the model is known and the year is still missing."""
    return bool(
        profile
        and profile.get('model')
        and not profile.get('year')
        and not state.get('year_skipped')
    )


def year_prompt(profile, lang):
    ask = _tr(lang, 'year_ask').format(bike=bike_label(profile))
    return f"{ask}\n\n[chips: {_tr(lang, 'year_chips')}]"


def focus_block(profile, lang):
    """Just the identified motorcycle — no spec dump, no model essay."""
    return f"**{_tr(lang, 'focus')}:** {bike_label(profile)}"


def detect_area(message):
    """Best-effort area detection from a free-text message."""
    msg = _norm(message)
    scores = {}
    for area, words in SYMPTOM_KEYWORDS.items():
        score = sum(1 for w in words if w in msg)
        if score:
            scores[area] = score
    if not scores:
        return None
    # Prefer the most specific match; ties follow a sensible mechanic priority.
    priority = ['brakes', 'starting', 'overheat', 'noise', 'smoke', 'electrical', 'power', 'chassis', 'maintenance']
    return sorted(scores, key=lambda a: (-scores[a], priority.index(a) if a in priority else 99))[0]


def checks_block(area, profile, lang):
    lines = [f"**{_tr(lang, 'where')}**", ""]
    for idx, (name, text) in enumerate(QUICK_CHECKS.get(area, []), 1):
        lines.append(f"{idx}. **{name}** — {text}")
    return "\n".join(lines)


def question_block(area, q_index, lang):
    q = AREAS[area]['questions'][q_index]
    text = q['text']
    if lang == 'tagalog':
        text = q.get('text_tl', text)
    elif lang == 'hiligaynon':
        text = q.get('text_hil', text)
    chips = " | ".join(label for _, label in q['options'])
    return f"**{text}**\n\n[chips: {chips}]"


def _match_option(area, q_index, message):
    """Matches a free-text reply or a clicked chip to one question option."""
    msg = _norm(message)
    q = AREAS[area]['questions'][q_index]
    options = q['options']
    valid = {value for value, _ in options}

    # 1. A clicked chip sends the label verbatim — match it exactly first.
    for value, label in options:
        if _norm(label) == msg:
            return value

    # 2. Common ways of saying the same answer.
    syn = {
        'dead': ['no lights', 'no dash', 'walang ilaw', 'wala ilaw', 'patay'],
        'click': ['clicking', 'click', 'relay'],
        'slow': ['slowly', 'slow crank', 'mabagal', 'sluggish'],
        'crank_no_fire': ['cranks normally', 'turns over but', 'cranks but',
                          'ayaw mag-start', 'ayaw umandar'],
        'starts_dies': ['starts then dies', 'starts briefly', 'namamatay agad'],
        'spark_ok': ['blue spark', 'may spark', 'spark ok'],
        'spark_none': ['no spark', 'walang spark'],
        'spongy': ['spongy', 'soft', 'malambot', 'humok'],
        'lever_to_bar': ['to the bar', 'lumulubog', 'sinks'],
        'weak': ['weak', 'mahina', 'maluya'],
        'noise': ['squeal', 'squeak', 'scrape', 'maingay'],
        'grinding': ['grind', 'metal'],
        'leak': ['leak', 'tagas', 'tulo'],
        'above_min': ['above min', 'full', 'puno'],
        'below_min': ['below min', 'kulang'],
        'empty': ['empty', 'ubos', 'wala'],
        'dark': ['dark', 'black', 'itim'],
        'idle': ['idle', 'traffic'],
        'high_speed': ['high speed', 'highway'],
        'always': ['all the time', 'always', 'every ride', 'laging'],
        'steam': ['steam', 'boiling', 'singaw'],
        'fan_runs': ['fan spins', 'fan works', 'umiikot'],
        'fan_dead': ['fan not', 'not spinning', 'hindi umiikot'],
        'fan_unknown': ['air-cooled', 'air cooled', 'not sure'],
        'top_end': ['top end', 'valve'],
        'bottom_end': ['bottom end', 'crankcase', 'deep inside'],
        'side_cover': ['side cover', 'cvt', 'chain'],
        'exhaust': ['exhaust', 'pipe', 'tambutso'],
        'blue': ['blue'],
        'black': ['black'],
        'white': ['white'],
        'cold_start': ['cold start', 'cold engine'],
        'revs_no_speed': ['revs', 'high rpm', 'slipping'],
        'bog': ['bog', 'sputter', 'hesitate'],
        'no_power': ['no power', 'weak', 'sluggish'],
        'jerking': ['jerk', 'vibrate'],
        'battery_drain': ['drain', 'dying'],
        'dim_lights': ['dim', 'pulse'],
        'starter_weak': ['slow starter', 'weak crank', 'turns slowly'],
        'new_battery': ['less than 1', 'new battery', 'brand new'],
        'mid_battery': ['1-3', '2 year', '3 year', 'two year', 'three year'],
        'old_battery': ['more than 3', '4 year', '5 year', 'old battery'],
        'wobble': ['wobble', 'shake'],
        'hard_steer': ['hard steer', 'notchy'],
        'suspension': ['bounce', 'bottom'],
        'tyre_noise': ['tyre noise', 'tire noise'],
        'oil_change': ['oil change', 'change oil'],
        'chain_service': ['chain'],
        'brake_check': ['brake'],
        'tune_up': ['tune'],
    }
    for value, words in syn.items():
        if value in valid and any(w in msg for w in words):
            return value

    # 3. Score label overlap (two shared words beat one shared word).
    best_value, best_score = None, 0
    for value, label in options:
        words = [w for w in re.split(r'[^a-z0-9]+', _norm(label)) if len(w) > 2]
        score = sum(1 for w in words if w in msg)
        if value.replace('_', ' ') and value.replace('_', ' ') in msg:
            score += 5
        if score > best_score:
            best_value, best_score = value, score
    return best_value


AREA_STOP = {
    'starting': 'the engine makes a hard metallic bang, you smell fuel, or the starter stays engaged.',
    'brakes': 'the lever sinks, fluid is leaking, or you hear metal grinding. Do not ride.',
    'overheat': 'steam or coolant is escaping, or the temperature light stays on. Let it cool first.',
    'noise': 'you hear a deep knock from the crankcase or find metal flakes in the oil. Stop the engine.',
    'smoke': 'the smoke is thick and constant, the oil level drops fast, or the engine runs rough.',
    'power': 'the bike loses power suddenly, the engine stalls in traffic, or you smell burning.',
    'electrical': 'you smell burning plastic, see smoke from the battery, or a fuse blows repeatedly.',
    'chassis': 'you feel a wobble at speed, the steering locks, or a wheel bearing has play.',
    'maintenance': 'you find metal flakes in the oil, a leaking drain bolt, or a bolt you cannot remove safely.',
}


def pick_verdict(area, answers):
    rules = VERDICTS.get(area, [])
    matched = []
    for index, rule in enumerate(rules):
        when = rule.get('when') or {}
        if when and all(answers.get(k) == v for k, v in when.items()):
            matched.append((rule.get('priority', 0), -index, rule))
    if matched:
        matched.sort(reverse=True)
        return matched[0][2]
    for rule in rules:
        if not rule.get('when'):
            return rule
    return {
        'title': 'General check',
        'confidence': 'Tentative',
        'why': 'Not enough detail yet — the free checks above are still the best next step.',
        'free': ['Work through the free checks above and tell me what you find.'],
        'parts': [],
    }


# ---------------------------------------------------------------------------
# 6. Public entry points
# ---------------------------------------------------------------------------

def _is_greeting(msg):
    """True only when the message *starts* with a greeting and has no symptom.

    Substring checks would misfire on words like "which" or "this".
    """
    text = msg.strip()
    for greeting in GREETING_PREFIXES:
        if text == greeting or text.startswith(greeting + ' ') \
                or text.startswith(greeting + ',') or text.startswith(greeting + '!'):
            if not detect_area(text):
                return True
    return False


def _mentions_bike_name(msg):
    """True when the message names a known model (word-boundary match)."""
    for key in BIKE_LIBRARY:
        if re.search(r'\b' + re.escape(key) + r'\b', msg):
            return True
    return False


def _is_followup_question(msg):
    """True for genuine questions asked mid-diagnosis (not chip answers)."""
    starters = (
        'how ', 'why ', 'what ', 'where ', 'when ', 'which ', 'who ',
        'can i ', 'should i ', 'do i ', 'is it ', 'will it ',
        'paano', 'bakit', 'ano ', 'saan ', 'kailan ', 'pwede',
    )
    return msg.endswith('?') or msg.startswith(starters)


def is_guided_intent(message, history=None, state=None):
    """True when the guided flow should handle this turn."""
    msg = _norm(message)
    if _has_any(msg, RESET_PHRASES):
        return True
    # Let the existing handlers own greetings, help, visuals and catalogues,
    # even in the middle of a guided session.
    if _is_greeting(msg):
        return False
    if _has_any(msg, ['what can you do', 'help', 'list parts', 'list symptoms',
                      'how many', 'what is a', 'what is an', 'show me', 'picture',
                      'image', 'photo', 'who are you']):
        return False
    if state and state.get('stage') not in (None, '', 'done'):
        # A real question ("how do I bleed the brakes?") deserves the full
        # knowledge engine; the diagnostic state is kept for the next turn.
        if _is_followup_question(msg):
            return False
        return True
    # A short "not sure" answer to the identification question.
    if _has_any(msg, SKIP_PHRASES) and len(msg) < 25:
        return True
    if _mentions_bike_name(msg):
        return True
    if detect_area(msg):
        return True
    # A bare vehicle answer while waiting for identification.
    if state and state.get('stage') == 'identify':
        return True
    return False


def start_state():
    return {'stage': 'identify', 'bike': None, 'area': None, 'answers': {},
            'q_index': 0, 'checks_shown': False, 'fresh': True,
            'year_skipped': False}


def _safety_prefix(message, lang, force_brake=False):
    try:
        from .diagnostic_engine import evaluate_safety_hazards
        probe = message
        if force_brake or _has_any(_norm(message), [
            'brake not working', 'brakes not working', 'no front brake',
            'no rear brake', 'brakes failed', 'hindi gumagana ang preno',
            'ayaw gumana ang preno',
        ]):
            # A brake problem is a critical stop even when the shortcut phrase
            # does not contain one of the engine's standard tripwire words.
            probe = f"{message} spongy"
        hazard = evaluate_safety_hazards(probe, lang)
    except Exception:
        hazard = None
    if hazard:
        return f"> [!CAUTION]\n> **SAFETY ALERT:** {hazard['alert_text']}\n\n"
    return ""


def _checks_reply(profile, area, lang, safety_message='', suppress_safety=False):
    prefix = ''
    if not suppress_safety and (safety_message or area == 'brakes'):
        prefix = _safety_prefix(
            safety_message or 'brakes', lang, force_brake=(area == 'brakes')
        )
    return (
        f"{prefix}{focus_block(profile, lang)}\n\n"
        f"{checks_block(area, profile, lang)}\n\n"
        f"{question_block(area, 0, lang)}"
    )


def _enter_checks(state, profile, area, lang, safety_message='', suppress_safety=False):
    state['area'] = area
    state['stage'] = 'narrow'
    state['q_index'] = 0
    state['checks_shown'] = True
    return _checks_reply(
        profile, area, lang,
        safety_message=safety_message,
        suppress_safety=suppress_safety,
    )


def handle_guided_turn(message, user, history, state, lang='english', sir='sir'):
    """
    Runs one turn of the guided flow.

    `state` is a dict owned by the caller (request.session) and is updated
    in place, so the next turn continues where this one stopped.
    Returns the reply text.
    """
    state = state if isinstance(state, dict) else {}
    msg = _norm(message)

    # --- Reset -------------------------------------------------------------
    if _has_any(msg, RESET_PHRASES):
        state.clear()
        state.update(start_state())
        return (
            f"{_tr(lang, 'reset')}\n\n"
            f"[chips: {_tr(lang, 'reset_chips')}]"
        )

    # First run: no stage yet (or a finished session).
    if not state.get('stage') or state.get('stage') == 'done':
        state.clear()
        state.update(start_state())

    stage = state['stage']

    # --- User says it is still broken (must be checked before "fixed") ------
    if _has_any(msg, ['still not', 'not fixed', 'same problem', 'hindi pa', 'indi gihapon',
                      'ganun pa rin', 'wala pa rin', 'still broken', 'still the same']):
        area = state.get('area')
        if area and state.get('bike'):
            # Go back to the free checks and re-run the narrowing questions;
            # answers may have changed since the first pass.
            state['stage'] = 'narrow'
            state['q_index'] = 0
            return (
                f"Understood, {sir}. Let us go one level deeper instead of replacing parts blindly.\n\n"
                f"{checks_block(area, state['bike'], lang)}\n\n"
                f"**What changed after the last check?**\n\n"
                f"{question_block(area, 0, lang)}"
            )
        state.clear()
        state.update(start_state())
        return (
            f"Understood, {sir}. Let us restart the narrowing from the top.\n\n"
            f"[chips: {_tr(lang, 'reset_chips')}]"
        )

    # --- User confirms the fix --------------------------------------------
    if _has_any(msg, ['it worked', 'that worked', 'worked, thanks', 'problem solved',
                      'fixed it', 'it is fixed', "it's fixed", 'feel better',
                      'feels better', 'okay now', 'ok now', 'noise is gone',
                      'smoke is gone', 'nagana na', 'naayos na', 'ok na', 'ayos na']):
        state.clear()
        state.update({'stage': 'done'})
        return (
            f"Excellent, {sir}. The diagnosis is closed and the motorcycle is back in service.\n\n"
            "Ride safe, and start a new diagnostic any time something feels off.\n\n"
            "[chips: Start over | Engine will not start | Brakes weak or spongy | Oil change / maintenance]"
        )

    # --- User asks for another inspection step ----------------------------
    if _has_any(msg, ['another check', 'next check', 'show another', 'other checks',
                      'what next', 'next step', 'ibang check', 'iban nga check',
                      'ano ang susunod', 'ano sunod']):
        area = state.get('area')
        bike = state.get('bike')
        if area and bike:
            state['stage'] = 'narrow'
            state['q_index'] = 0
            return (
                f"{checks_block(area, bike, lang)}\n\n"
                f"{question_block(area, 0, lang)}"
            )

    # --- Stage: identify the motorcycle -----------------------------------
    if stage == 'identify':
        from .views import _extract_vehicle_info
        current_vehicle = _extract_vehicle_info(message)
        if current_vehicle.get('make') or current_vehicle.get('model'):
            vehicle = current_vehicle
        elif state.get('fresh'):
            # A fresh session/restart must not inherit an old bike from the
            # saved chat log; wait for the user to name this motorcycle.
            vehicle = current_vehicle
        else:
            vehicle = _extract_vehicle_info(message, history)

        # "Not sure" -> ask the type instead.
        if _has_any(msg, SKIP_PHRASES) and not (current_vehicle.get('make') or current_vehicle.get('model')):
            state['stage'] = 'type'
            return (
                f"{_tr(lang, 'type_ask')}\n\n"
                f"[chips: {_tr(lang, 'type_chips')}]"
            )

        profile = resolve_profile(vehicle, message, history)
        if vehicle.get('make') or vehicle.get('model'):
            state['bike'] = profile
            state['fresh'] = False
            area = detect_area(message) or detect_area(" ".join(
                t.get('text', '') for t in (history or [])
            ))
            if area:
                state['area'] = area

            if _needs_year(profile, state):
                state['stage'] = 'year'
                state['year_context'] = message
                return (
                    f"{_safety_prefix(message, lang, force_brake=(area == 'brakes'))}"
                    f"{year_prompt(profile, lang)}"
                )

            if area:
                return _enter_checks(state, profile, area, lang, message)
            state['stage'] = 'area'
            return (
                f"{focus_block(profile, lang)}\n\n"
                f"{_tr(lang, 'area_ask')}\n\n"
                f"[chips: {_tr(lang, 'area_chips')}]"
            )

        # No vehicle yet: ask for it.
        return (
            f"{_safety_prefix(message, lang)}"
            f"{_tr(lang, 'identify')}\n\n"
            f"[chips: {_tr(lang, 'identify_chips')}]"
        )

    # --- Stage: ask motorcycle type ---------------------------------------
    if stage == 'type':
        profile = resolve_profile({}, message, history)
        if _has_any(msg, ['scooter', 'cvt', 'click', 'mio', 'aerox', 'nmax', 'beat', 'pcx', 'adv']):
            profile = dict(TYPE_LIBRARY['scooter']); profile['key'] = 'generic-scooter'
        elif _has_any(msg, ['underbone', 'chain', 'wave', 'xrm', 'raider', 'sniper', 'smash']):
            profile = dict(TYPE_LIBRARY['underbone']); profile['key'] = 'generic-underbone'
        elif _has_any(msg, ['standard', 'backbone', 'tmx', 'barako']):
            profile = dict(TYPE_LIBRARY['backbone']); profile['key'] = 'generic-backbone'
        elif _has_any(msg, ['dual', 'trail', 'off-road', 'offroad']):
            profile = dict(TYPE_LIBRARY['dual-sport']); profile['key'] = 'generic-dual-sport'
        elif _has_any(msg, ['big bike', 'bigbike', 'sport', 'cruiser']):
            profile = dict(TYPE_LIBRARY['big bike']); profile['key'] = 'generic-big-bike'
        state['bike'] = profile
        state['stage'] = 'area'

        area = detect_area(message)
        if area:
            return _enter_checks(state, profile, area, lang, message)
        return (
            f"{focus_block(profile, lang)}\n\n"
            f"{_tr(lang, 'area_ask')}\n\n"
            f"[chips: {_tr(lang, 'area_chips')}]"
        )

    # --- Stage: fill in the missing model year ----------------------------
    if stage == 'year':
        profile = state.get('bike') or resolve_profile({}, message, history)
        year = _extract_year(message)
        if year:
            profile['year'] = year
            state['bike'] = profile
        else:
            # The year is useful, not mandatory. Any other answer moves on;
            # never trap the user in a year loop.
            state['year_skipped'] = True

        new_area = detect_area(message)
        area = new_area or state.get('area') or detect_area(state.get('year_context', ''))
        state.pop('year_context', None)

        if area:
            return _enter_checks(
                state, profile, area, lang,
                safety_message=message if new_area else '',
                suppress_safety=not new_area,
            )

        state['stage'] = 'area'
        return (
            f"{focus_block(profile, lang)}\n\n"
            f"{_tr(lang, 'area_ask')}\n\n"
            f"[chips: {_tr(lang, 'area_chips')}]"
        )

    # At this point we should have a bike profile.
    profile = state.get('bike') or resolve_profile({}, message, history)

    # --- Stage: choose the problem area -----------------------------------
    if stage == 'area':
        area = detect_area(message)
        if not area:
            # Try to match the chip labels.
            mapping = {
                'starter': 'starting', 'start': 'starting',
                'preno': 'brakes', 'brake': 'brakes',
                'overheat': 'overheat', 'init': 'overheat',
                'ingay': 'noise', 'noise': 'noise',
                'usok': 'smoke', 'smoke': 'smoke',
                'power': 'power', 'accelerat': 'power',
                'baterya': 'electrical', 'battery': 'electrical', 'electrical': 'electrical',
                'gulong': 'chassis', 'tyre': 'chassis', 'tire': 'chassis',
                'chain': 'chassis', 'suspension': 'chassis',
                'oil': 'maintenance', 'maintenance': 'maintenance',
            }
            for key, value in mapping.items():
                if key in msg:
                    area = value
                    break
        if not area:
            return (
                f"I can help with that, {sir}, but I need the system. Which one matches best?\n\n"
                f"[chips: {_tr(lang, 'area_chips')}]"
            )
        return _enter_checks(state, profile, area, lang, message)

    area = state.get('area')
    if not area:
        state['stage'] = 'area'
        return (
            f"{_tr(lang, 'area_ask')}\n\n"
            f"[chips: {_tr(lang, 'area_chips')}]"
        )

    # --- Stage: checks shown, ask the narrowing question ------------------
    if stage == 'checks':
        state['stage'] = 'narrow'
        state['q_index'] = 0
        stage = 'narrow'
        # Fall through to narrow so a volunteered answer is captured.

    if stage == 'narrow':
        q_index = int(state.get('q_index', 0))
        questions = AREAS[area]['questions']
        if q_index >= len(questions):
            state['stage'] = 'verdict'
        else:
            # Let the user ask to see the checks again.
            if _has_any(msg, ['where to look', 'what to check', 'what next', 'next step',
                              'saan titingin', 'diin kitaon', 'checks']):
                return (
                    f"{checks_block(area, profile, lang)}\n\n"
                    f"{question_block(area, q_index, lang)}"
                )

            answer = _match_option(area, q_index, message)
            if answer:
                state.setdefault('answers', {})[questions[q_index]['key']] = answer
                state['q_index'] = q_index + 1

                if state['q_index'] < len(questions):
                    return question_block(area, state['q_index'], lang)
                state['stage'] = 'verdict'
            else:
                # Also accept a direct "show verdict" request.
                if _has_any(msg, ['likely cause', 'what is the cause', 'diagnose it', 'just tell me']):
                    state['stage'] = 'verdict'
                else:
                    return (
                        f"{_tr(lang, 'again')}\n\n"
                        f"{question_block(area, q_index, lang)}"
                    )

    # --- Stage: verdict ----------------------------------------------------
    if state.get('stage') == 'verdict':
        # If the user reports a new/changed symptom, start narrowing that
        # instead of repeating the previous conclusion.
        new_area = detect_area(message)
        if new_area:
            state['answers'] = {}
            return _enter_checks(state, profile, new_area, lang, message)

        answers = state.get('answers', {})
        verdict = pick_verdict(area, answers)

        lines = [
            f"**{_tr(lang, 'verdict')}: {verdict['title']}**",
            verdict['why'],
            "",
            f"**{_tr(lang, 'free_fix')}**",
        ]
        for item in verdict.get('free', [])[:3]:
            lines.append(f"- {item}")

        if verdict.get('parts'):
            lines.append("")
            lines.append(f"**{_tr(lang, 'parts')}:** " + ", ".join(verdict['parts']))

        lines.append("")
        lines.append(
            f"**{_tr(lang, 'stop')}:** "
            f"{verdict.get('stop') or AREA_STOP.get(area) or _tr(lang, 'safe_stop')}"
        )
        lines.append("")
        lines.append(f"[chips: {_tr(lang, 'verdict_chips')}]")
        return "\n".join(lines)

    # Unknown stage -> restart cleanly.
    state.clear()
    state.update(start_state())
    return (
        f"{_tr(lang, 'reset')}\n\n"
        f"[chips: {_tr(lang, 'reset_chips')}]"
    )
