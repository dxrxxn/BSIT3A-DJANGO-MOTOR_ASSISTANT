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
    'bajaj ct 100': {
        'make': 'Bajaj', 'model': 'CT 100', 'type': 'motorcycle',
        'fuel': 'Carburetor', 'drive': 'Chain',
        'brakes': 'front drum / rear drum',
        'focus': [
            'Carburetor cleanliness, idle screw, and fuel petcock flow.',
            'Spark plug gap and condition.',
            'Drive chain slack, lubrication, and drum brake shoe wear.',
        ],
    },
    'bajaj ct100': {
        'make': 'Bajaj', 'model': 'CT 100', 'type': 'motorcycle',
        'fuel': 'Carburetor', 'drive': 'Chain',
        'brakes': 'front drum / rear drum',
        'focus': [
            'Carburetor cleanliness, idle screw, and fuel petcock flow.',
            'Spark plug gap and condition.',
            'Drive chain slack, lubrication, and drum brake shoe wear.',
        ],
    },
    'ct 100': {
        'make': 'Bajaj', 'model': 'CT 100', 'type': 'motorcycle',
        'fuel': 'Carburetor', 'drive': 'Chain',
        'brakes': 'front drum / rear drum',
        'focus': [
            'Carburetor cleanliness, idle screw, and fuel petcock flow.',
            'Spark plug gap and condition.',
            'Drive chain slack, lubrication, and drum brake shoe wear.',
        ],
    },
    'ct100': {
        'make': 'Bajaj', 'model': 'CT 100', 'type': 'motorcycle',
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
                'text_tl': 'Ano ang nangyayari pag pinipindot mo ang starter button?',
                'text_hil': 'Ano ang nagakatabo kon ginapindot mo ang starter button?',
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
                'text_tl': 'Kung na-check mo ang spark plug, ano ang nakita mo?',
                'text_hil': 'Kon na-check mo ang spark plug, ano ang nakita mo?',
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
        'verdict_chips': "Begin procedure | It worked | Still not fixed | Another check | Start over",
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
        'verdict_chips': "Simulan ang procedure | Nagana na | Hindi pa | Ibang check | Simula ulit",
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
        'verdict_chips': "Suguran ang procedure | Nagana na | Indi gihapon | Iban nga check | Sugod liwat",
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

# Phrases that mean the user does not know where a part/step is located.
LOCATION_UNKNOWN_PHRASES = [
    "don't know where", "dont know where", "not sure where", "i don't know where",
    "i dont know where", "where is it", "where can i find", "where do i find",
    "how do i find", "can't find", "cant find", "cannot find", "i can't find",
    "i cant find", "i cannot find", "where to look", "saan ko mahahanap",
    "saan matatagpuan", "saan ito", "hindi ko alam saan", "indi ko alam diin",
    "diin ko maabot", "wala ko kabalo diin", "where is the", "where's the",
    "how to locate", "how to find", "find the", "locate the",
    "hindi ko alam", "di ko alam saan",
]

# Phrases meaning "yes, continue / resume the session".
CONTINUE_SESSION_PHRASES = [
    'can we continue', 'continue please', 'lets continue', "let's continue",
    'continue the session', 'continue diagnosis', 'resume', 'go on', 'go ahead',
    'oo continue', 'sige continue', 'tuloy na', 'padayon na', 'tuloy',
    'yes continue', 'yeah continue', 'ok continue', 'okay continue',
    'sige na', 'proceed', 'continue from where', 'where were we',
    'magpatuloy', 'ituloy natin', 'saan tayo', 'ano ulit', 'ano yung sinabi mo',
    'ano na yung next', 'oo sige', 'yes sige', 'oo padayon', 'continue to next step',
    'can we continue in that session', 'continue in that session', 'continue the procedure',
]

# Phrases for beginners asking HOW to do a procedure step or fix
HOWTO_UNKNOWN_PHRASES = [
    'how to do this', 'how do i do this', 'how do i do it', 'how can we fix it',
    'how to fix it', 'how to fix', 'how can i fix', 'how do we fix',
    'teach me how', 'teach me step by step', 'teach me', 'how to check',
    'how do i check', 'how can i check', 'how do i test', 'how to test',
    "i don't know how", 'i dont know how', 'i am a beginner', 'im a beginner',
    "i'm a beginner", 'not good at motorcycle', 'not good with bikes',
    'explain how', 'how does it work', 'step by step how', 'guide me how',
    'paano gawin', 'paano ito ayusin', 'paano ayusin', 'paano ko aayusin', 'paano i-check',
    'paano i check', 'turo mo paano', 'tudlui ko', 'diin paagi',
    'how to do step', 'how to do this step', 'how', 'what do i do',
    'what should i do', 'what do we do', 'paano', 'ano gagawin', 'ano gagawin ko',
    'how to perform', 'how do i perform', 'teach how', 'teach me how to fix it',
    'teach step by step', 'how to do',
]

# Phrases when user asks again to be sure
REASSURE_CONFIRM_PHRASES = [
    'just to be sure', 'are you sure', 'sure ba', 'sigurado ka', 'is that right',
    'is this right', 'will this work', 'to be sure', 'sigurado ka ba', 'sure ka ba',
    'are we sure', 'ask again', 'tanong lang ulit', 'are you really sure',
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
        'engine wont start', "engine won't start", 'engine will not start',
        'engine does not start', 'engine doesnt start',
        'wont crank', "won't crank", 'does not crank', 'not cranking', 'no crank',
        'wont turn over', "won't turn over", 'not turning over',
        'wont fire up', "won't fire up", 'wont run', "won't run",
        'starter click', 'starter clicking', 'starter dead', 'relay clicking',
        'starting problem', 'starter problem',
        'di nagstart', 'di mag-start', 'di magstart', 'hindi magstart',
        'ayaw mag start', 'ayaw magpaandar', 'hindi umaandar', 'di umaandar',
        'indi mag andar', 'ayaw umilaw ang dash',
    ],
    'brakes': [
        'brake', 'brakes', 'preno', 'spongy', 'soft lever', 'malambot', 'humok',
        'stopping', 'caliper', 'brake pad', 'walang preno', 'mahina preno',
        'di kumakagat', 'hindi kumakagat',
    ],
    'overheat': [
        'overheat', 'overheating', 'radiator', 'coolant', 'steam', 'boiling',
        'nag-o-overheat', 'nagabukal', 'singaw', 'temp light', 'temperature',
        'sobrang init', 'mainit ang makina',
    ],
    'noise': [
        'noise', 'noisy', 'knock', 'knocking', 'ticking', 'rattle', 'rattling',
        'ingay', 'maingay', 'katok', 'kumatok', 'lagabog', 'ticking sound',
        'tingog', 'kakaiba nga tingog', 'kumakaluskos', 'kumakatok',
    ],
    'smoke': [
        'smoke', 'smoking', 'usok', 'umuusok', 'aso', 'mausok', 'ma-aso',
    ],
    'power': [
        'no power', 'lose power', 'loss of power', 'slow', 'sluggish', 'bog',
        'sputter', 'hesitate', 'jerking', 'won\'t accelerate', 'wont accelerate',
        'nawawalan ng power', 'nawad-an power', 'walang power', 'wala power',
        'mabagal', 'hindi bumibilis', 'walang hatak', 'mahina hatak', 'pumapalya',
    ],
    'electrical': [
        'battery', 'baterya', 'charging', 'alternator', 'stator', 'rectifier',
        'dim light', 'no lights', 'electrical', 'kuryente', 'dead battery',
        'walang kuryente', 'palit baterya',
    ],
    'chassis': [
        'tyre', 'tire', 'gulong', 'chain', 'sprocket', 'suspension', 'wobble',
        'steering', 'shock', 'fork', 'bearing', 'alambre', 'kadena', 'manibela',
        'kumakalog', 'gewang', 'gumegewang',
    ],
    'maintenance': [
        'oil change', 'change oil', 'oil', 'maintenance', 'tune up', 'tune-up',
        'langis', 'change oil', 'filter', 'pms', 'regular service',
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


def _user_history_texts(history):
    """Return text list from user turns only, in reverse chronological order (newest first)."""
    if not history:
        return []
    if isinstance(history, str):
        return [history.strip()] if history.strip() else []
    texts = []
    for turn in reversed(list(history)):
        if isinstance(turn, dict):
            role = str(turn.get('role', '')).lower()
            if role in ('bot', 'assistant', 'system'):
                continue
            txt = str(turn.get('text') or turn.get('message') or turn.get('content') or '').strip()
            if txt:
                texts.append(txt)
        elif isinstance(turn, str) and turn.strip():
            texts.append(turn.strip())
    return texts


def detect_area_from_history(history):
    """Finds the most recent diagnostic symptom area mentioned by the user in history."""
    for text in _user_history_texts(history):
        area = detect_area(text)
        if area:
            return area
    return None


def _symptom_ack(area, lang, sir='sir'):
    """Provides a warm, reassuring acknowledgement of the user's issue before vehicle intake."""
    if not area:
        return ""
    acks = {
        'english': {
            'starting': f"I can help diagnose why your motorcycle won't start, {sir}. ",
            'brakes': f"Let us check the brakes right away, {sir} — safety first. ",
            'overheat': f"I can help diagnose that overheating issue, {sir}. ",
            'noise': f"I can help you pinpoint that engine noise, {sir}. ",
            'smoke': f"I can help inspect that exhaust smoke issue, {sir}. ",
            'power': f"I can help find why your motorcycle is losing power, {sir}. ",
            'electrical': f"I can help check your electrical and battery system, {sir}. ",
            'chassis': f"I can help diagnose that handling and chassis issue, {sir}. ",
            'maintenance': f"I can guide you through the maintenance checks, {sir}. ",
        },
        'tagalog': {
            'starting': f"Tutulungan kitang alamin kung bakit ayaw mag-start ng motor mo, {sir}. ",
            'brakes': f"Tingnan natin agad ang preno mo, {sir} — unahin natin ang kaligtasan. ",
            'overheat': f"Tutulungan kitang tingnan ang overheat ng makina, {sir}. ",
            'noise': f"Tutulungan kitang hanapin kung saan nanggagaling ang ingay, {sir}. ",
            'smoke': f"Tutulungan kitang alamin ang sanhi ng usok, {sir}. ",
            'power': f"Tutulungan kitang alamin kung bakit mahina ang hatak, {sir}. ",
            'electrical': f"Tutulungan kitang i-check ang kuryente at baterya, {sir}. ",
            'chassis': f"Tutulungan kitang i-check ang gulong, kadena, at tindig, {sir}. ",
            'maintenance': f"Tutulungan kitang mag-maintenance check, {sir}. ",
        },
        'hiligaynon': {
            'starting': f"Buligan ta ka usisa kon ngaa indi mag-start ang motor mo, {sir}. ",
            'brakes': f"Tan-awon ta dayon ang preno mo, {sir} — unahon naton ang kaluwasan. ",
            'overheat': f"Buligan ta ka usisa sang pag-init sang makina, {sir}. ",
            'noise': f"Buligan ta ka pangita kon diin nagahalin ang gahod, {sir}. ",
            'smoke': f"Buligan ta ka usisa sang aso, {sir}. ",
            'power': f"Buligan ta ka kon ngaa nagaluya ang karga, {sir}. ",
            'electrical': f"Buligan ta ka i-check ang kuryente kag baterya, {sir}. ",
            'chassis': f"Buligan ta ka i-check ang ligid kag kadena, {sir}. ",
            'maintenance': f"Buligan ta ka sa maintenance check, {sir}. ",
        },
    }
    lang_key = _lang_key(lang)
    return acks.get(lang_key, acks['english']).get(area, "")


def resolve_profile(vehicle_info, message='', history=None):
    """Returns a bike profile dict for the extracted vehicle info."""
    corpus = _norm(message)
    user_turns = _user_history_texts(history)
    history_corpus = " ".join(_norm(t) for t in user_turns)

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


# ---------------------------------------------------------------------------
# General motorcycle Q&A detection
# ---------------------------------------------------------------------------
# Maintenance, how-to, service-interval and "what should I check" questions
# deserve a direct answer. They must not be forced through the diagnostic
# intake, which asks for make/model/year before helping.

GENERAL_DOMAIN_RE = re.compile(
    r"""
    \b(?:
        motorcycles?|motorbikes?|motor|scooters?|underbones?|mopeds?|tricycles?|bikes?|
        engines?|makina|oil|langis|lana|oil\s+filters?|air\s+filters?|filters?|
        tyres?|tires?|gulong|wheels?|rims?|spokes?|hubs?|chains?|kadena|sprockets?|
        brakes?|preno|batter(?:y|ies)|baterya|spark\s+plugs?|plugs?|coolant|radiators?|
        suspension|forks?|shocks?|clutch|cvt|belts?|rollers?|valves?|tappets?|
        throttle|carburetors?|carbs?|fuel|gas|gasoline|petrol|exhaust|mufflers?|tambutso|
        headlights?|tail\s?lights?|bulbs?|fuses?|stator|rectifier|alternators?|
        bearings?|axles?|calipers?|discs?|drums?|pads?|shoes?|fluids?|grease|lube|psi|
        leak(?:s|ing)?|smoke|smoking|noise|sounds?|
        tyre\s+pressure|tire\s+pressure|maintenance|service|pms|tune[- ]?up|
        ride|riding|long\s+ride|trips?|
        helmet|helmets?|visor|gear|gears?|jacket|gloves?|boots?|protector|
        riding\s+gear|safety\s+gear|apparel|atgatt|
        buy(?:ing)?|purchas(?:e|ing)|beginner|starter|commut(?:e|er|ing)|
        review|comparison|compare|versus|recommend(?:ation)?s?|
        abs|efi|displacement|horsepower
    )\b
    """,
    re.I | re.X,
)

# A question word only counts at the START of the message. Otherwise a symptom
# report like "... clicking sound when pressing the starter" would be mistaken
# for a general "when" question.
GENERAL_QUESTION_START_RE = re.compile(
    r"^\s*(?:"
    r"how|what|when|where|which|who|why|"
    r"paano|papaano|kailan|gaano|ilan|pila|unsa|ano|saan|san-o|magkano|pwede|dapat|tama|"
    r"can|could|should|do|does|is|are|will|would"
    r")\b",
    re.I,
)

# Action/how-to cues. A bare system noun ("Brakes", "Oil") is deliberately not
# enough: during a guided session those are area answers, not general questions.
GENERAL_ACTION_RE = re.compile(
    r"""
    \b(?:
        tips?|guide|procedure|steps?|checklist|interval|schedule|frequency|
        recommended|recommendation|best|advice|maintenance|service|tune[- ]?up|pms|preventive|care|
        chang(?:e|ing)|replac(?:e|ing)|clean(?:ing)?|lub(?:e|ing|ricate|ricating)|
        adjust(?:ing)?|inspect(?:ing)?|check(?:ing)?|flush(?:ing)?|bleed(?:ing)?|
        tighten(?:ing)?|measur(?:e|ing)|choos(?:e|ing)|buy(?:ing)?|upgrad(?:e|ing)|
        tell\s+me|explain|describe|
        psi|pressure|slack|gap|spec(?:s|ification)?|size|type|capacity|torque|
        viscosity|weight|length|price|cost|difference|vs|versus|fitment|compatible|
        compar(?:e|ing|ison)|recommend(?:ation)?s?|review|better|best\s+for|
        beginner|starter|commuter|buying|purchase|tell\s+me\s+about|
        feature|pros?\s+and\s+cons?|advantage|disadvantage
    )\b
    """,
    re.I | re.X,
)

# Maintenance/how-to words plus system nouns, used to tell a bare vehicle
# identification from a vehicle + topic message.
GENERAL_MAINTENANCE_RE = re.compile(
    r"""
    \b(?:
        tips?|guide|procedure|steps?|checklist|interval|schedule|frequency|
        recommended|recommendation|best|advice|maintenance|service|tune[- ]?up|pms|preventive|care|
        chang(?:e|ing)|replac(?:e|ing)|clean(?:ing)?|lub(?:e|ing|ricate|ricating)|
        adjust(?:ing)?|inspect(?:ing)?|check(?:ing)?|flush(?:ing)?|bleed(?:ing)?|
        tighten(?:ing)?|measur(?:e|ing)|choos(?:e|ing)|buy(?:ing)?|upgrad(?:e|ing)|
        tell\s+me|explain|describe|
        oils?|langis|tyres?|tires?|gulong|chains?|kadena|brakes?|preno|batter(?:y|ies)|baterya|
        fluids?|filters?|spark\s+plugs?|coolant|radiators?|suspension|forks?|shocks?|cvt|belts?|
        psi|pressure|slack|gap|spec(?:s|ification)?|size|type|capacity|torque|
        viscosity|weight|length|price|cost|difference|vs|versus|fitment|compatible
    )\b
    """,
    re.I | re.X,
)


def _has_general_topic_cue(msg):
    return bool(
        GENERAL_QUESTION_START_RE.search(msg)
        or GENERAL_ACTION_RE.search(msg)
    )


VISUAL_PART_TERMS = (
    'caliper', 'disc brake', 'brake pad', 'sprocket', 'drive chain', 'chain',
    'spark plug', 'carburetor', 'battery', 'starter motor', 'cvt', 'radiator',
    'piston', 'headlight', 'tail light', 'air filter', 'oil filter',
    'shock absorber', 'fuel injector', 'throttle body', 'fork',
)

VISUAL_REQUEST_RE = re.compile(
    r"\b(?:what\s+is|what\s+are|show\s+me|show|picture|photo|image|"
    r"look\s+like|looks\s+like|ano\s+ang|unsa\s+ang)\b",
    re.I,
)

# "Where is the oil filter?" / "Where can I find the CDI?" / "Saan
# matatagpuan ang battery?" are location questions, not fault reports. They
# need a direct answer instead of the guided intake or a generic fallback.
LOCATION_QUERY_RE = re.compile(
    r"^\s*(?:where|saan|asa|diin|ha)\b"
    r"|\b(?:location\s+of|whereabouts\s+of|where\s+to\s+locate|"
    r"where\s+can\s+i\s+(?:locate|find)|where\s+do\s+i\s+(?:locate|find))\b",
    re.I,
)

# Parts that users commonly ask to locate. This deliberately excludes
# symptom words such as noise, leak, smoke, and vibration so that "where is
# the noise coming from?" stays a diagnostic question.
PART_LOCATION_RE = re.compile(
    r"\b(?:parts?|components?|assembl(?:y|ies)|modules?|units?|"
    r"ecu|ecm|cdi|tci|ignition\s+coil|coil|spark\s+plug|"
    r"horn|relay|solenoid|fuses?|fuse\s+box|battery|rectifier|regulator|stator|alternator|"
    r"oil\s+filter|air\s+filter|fuel\s+filter|fuel\s+pump|fuel\s+tank|petcock|"
    r"carburetor|throttle\s+body|injector|injection|radiator|coolant|reservoir|"
    r"hose|clamp|gasket|seal|bearing|axle|swingarm|shock|fork|suspension|"
    r"chain|sprocket|belt|cvt|variator|rollers?|clutch|brake|caliper|master\s+cylinder|"
    r"pads?|disc|rotor|drum|wheel|tyre|tire|rim|spoke|"
    r"headlight|tail\s?light|signal\s+light|bulb|switch|wiring|harness|connector|terminal|"
    r"sensor|tps|map\s+sensor|o2\s+sensor|oxygen\s+sensor|speedometer|cluster|dashboard|"
    r"handlebar|throttle|grip|lever|pedal|sidestand|kickstand|footpeg|seat|"
    r"exhaust|muffler|pipe|engine|motor|makina|transmission|gearbox|"
    r"oil|langis|filter|pump|valve|tappet|camshaft|cam|piston|cylinder|"
    r"cable|wire|tube|line|mirror|rack|cap|plug|bolt|nut|screw)\b",
    re.I,
)

LOCATION_FLOW_RE = re.compile(
    r"\b(?:coming|leaking|dripping|oozing|seeping|spraying|squirting|pouring)\s+from\b",
    re.I,
)

LOCATION_SYMPTOM_RE = re.compile(
    r"\b(?:noise|sound|rattle|knock|vibration|leak|smoke|smell|problem|issue|fault)\b",
    re.I,
)

PRONOUN_LOCATION_RE = re.compile(
    r"\b(?:it|that|this|they|them|those|these)\b",
    re.I,
)

LOCATION_ACTION_RE = re.compile(
    r"\b(?:locate|located|location|find|found|whereabouts)\b",
    re.I,
)


def _history_texts(history):
    """Return recent history text without assuming one client shape."""
    if not history:
        return []
    if isinstance(history, str):
        return [history]
    texts = []
    for turn in list(history)[-8:]:
        if isinstance(turn, dict):
            role = str(turn.get('role', '')).lower()
            if role in ('bot', 'assistant', 'system'):
                continue
            texts.append(
                str(
                    turn.get('text')
                    or turn.get('message')
                    or turn.get('content')
                    or ''
                )
            )
        else:
            texts.append(str(turn))
    return [text for text in texts if text]


def _history_mentions_part(history):
    for text in reversed(_history_texts(history)):
        norm = _norm(text)
        if _has_active_fault(norm):
            continue
        if PART_LOCATION_RE.search(norm):
            return True
    return False

SPEC_CUE_RE = re.compile(
    r"\b(?:gap|interval|best|how\s+often|when\s+to|how\s+to|change|changing|"
    r"replace|replacing|clean|cleaning|check|checking|maintenance|spec|"
    r"specification|size|type|price|cost|difference|vs|versus|capacity|"
    r"torque|pressure|psi|weight|viscosity|slack|adjust|adjusting)\b",
    re.I,
)

# "Check for leaks" / "look for signs of wear" are maintenance questions, not
# fault reports. Remove those inspection phrases before looking for faults.
GENERAL_INSPECTION_RE = re.compile(
    r"\b(?:how\s+to\s+)?(?:check|checking|inspect|inspecting|look|looking|watch|test|testing)\s+"
    r"(?:"
    r"(?:for|out\s+for)\s+(?:any\s+)?(?:signs?\s+of\s+)?(?:\w+\s+){0,3}"
    r"(?:leaks?|smoke|noise|sounds?|cracks?|wear|damage|problems?|issues?|"
    r"punctures?|punctured|dead|weak|flat|worn|loose|stuck|broken|faulty|seized|overheating)"
    r"|"
    r"(?:if|whether)\s+.{0,60}?\b(?:dead|weak|flat|worn|loose|stuck|broken|"
    r"damaged|faulty|leaking|overheating|seized|punctured)"
    r")\b",
    re.I,
)

FAULT_PATTERNS = [
    re.compile(pattern, re.I) for pattern in (
        r"\bwon'?t\s+(?:start|run|idle|crank|charge|fire)\b",
        r"\bwill\s+not\s+(?:start|run|idle|crank|charge|fire)\b",
        r"\b(?:can'?t|cannot|doesn'?t|doesnt|isn'?t|isnt|not)\s+"
        r"(?:start|starting|run|running|idle|crank|cranking|charge|charging|"
        r"work|working|respond|responding|fire|firing)\b",
        r"\bno\s+(?:start|power|lights?|spark|compression|charge)\b",
        r"\bhard\s+to\s+start\b",
        r"\b(?:dead|flat|punctured|seized|stuck|broken|damaged|faulty)\b",
        r"\b(?:overheat|overheating|overheated)\b",
        r"\b(?:smoke|smoking|smoky)\b",
        r"\b(?:leak|leaking|leaks|dripping|drip)\b",
        r"\b(?:grind|grinding|squeal|squealing|squeak|squeaking|"
        r"knock|knocking|rattle|rattling|tick|ticking|clicking|clicked|clicks|noisy)\b",
        r"\b(?:oil|battery|temperature|check\s+engine|engine)\s+"
        r"(?:warning\s+)?light\s+(?:is\s+)?on\b",
        r"\b(?:stall|stalling|misfire|misfiring|backfire|backfiring|"
        r"slipping|bogging|bogs|hesitating|jerking)\b",
        r"\b(?:wobble|wobbling|shaking|vibrating|vibration)\b",
        r"\b(?:soft|spongy|mushy)\s+(?:brakes?|lever|pedal|preno)\b",
        r"\b(?:brakes?|lever|pedal|preno)\s+(?:is|are|feels?|feeling)?\s*"
        r"(?:soft|spongy|mushy|weak|failing|failed)\b",
        r"\b(?:weak|failing|failed)\s+(?:brakes?|battery|baterya|preno)\b",
        r"\b(?:battery|baterya)\s+(?:is\s+)?(?:weak|dead|flat|dying)\b",
        r"\b(?:lights?|headlight|ilaw)\s+(?:are|is|seem|seems|look|looks)?\s*"
        r"(?:dim|flickering|dead|not\s+working)\b",
        r"\b(?:not\s+working|doesn'?t\s+work|won'?t\s+work|no\s+longer\s+works?)\b",
        r"\b(?:making|makes|made|has|have|there'?s|there\s+is)\b"
        r".{0,40}\b(?:noise|sound|rattle|knock|tick|click|squeal|grind)\b",
        r"\b(?:bike|motorcycle|scooter|engine|motor)\s+(?:is\s+)?"
        r"(?:slow|sluggish|underpowered)\b",
        r"\b(?:lose|loses|losing|loss\s+of)\s+power\b",
        r"\b(?:burning|burns|burn)\s+oil\b",
        r"\b(?:nail|screw)\s+(?:in|on)\s+(?:the\s+)?(?:tyre|tire)\b",
        r"\b(?:tyre|tire)\s+(?:has|with)\s+(?:a\s+)?(?:nail|screw|puncture)\b",
        r"\b(?:ayaw|hindi|indi)\s+(?:mag-?start|umandar|mag-?andar|gumana|"
        r"mag-?function|mag-?crank|umiikot|tumutunog)\b",
        r"\b(?:guba|sira|basag|patay)\b",
        r"\b(?:may|naa)\s+(?:tagas|tulo|usok|aso|ingay|tunog|tingog)\b",
        r"\b(?:nag-?iinit|uminit|nag-?o-?overheat|nagabukal|nagasiga)\b",
        r"\b(?:umuusok|tumutulo|lumulubog|malambot|humok)\b",
        r"\b(?:maingay|kumatok|nagapiti|nagagrind|umaalingawngaw)\b",
        r"\b(?:walang|wala)\s+(?:kuryente|ilaw|power)\b",
    )
]


def _has_active_fault(msg):
    """True when the message reports a live fault (not a how-to/check question)."""
    probe = GENERAL_INSPECTION_RE.sub(' ', msg)
    return any(pattern.search(probe) for pattern in FAULT_PATTERNS)


def _looks_like_part_visual_query(msg):
    """True for "what is a caliper?" / "show me a sprocket" style queries."""
    if not VISUAL_REQUEST_RE.search(msg):
        return False
    if SPEC_CUE_RE.search(msg):
        return False
    return any(
        re.search(r'\b' + re.escape(term) + r'\b', msg)
        for term in VISUAL_PART_TERMS
    )


def _looks_like_part_location_query(msg, history=None):
    """True for "where is the oil filter?" style location questions."""
    if not LOCATION_QUERY_RE.search(msg):
        return False
    if LOCATION_FLOW_RE.search(msg):
        return False
    if _has_active_fault(msg):
        return False
    if PART_LOCATION_RE.search(msg):
        return True
    # "Where is it located?" is general only when the previous turns mention
    # a component; otherwise it stays in the diagnostic flow.
    if LOCATION_ACTION_RE.search(msg) and PRONOUN_LOCATION_RE.search(msg):
        return _history_mentions_part(history)
    return False


def _looks_like_vehicle_identification(msg):
    """True for a bare vehicle answer such as "2022 Honda Click 125i"."""
    if not _mentions_bike_name(msg):
        return False
    if GENERAL_MAINTENANCE_RE.search(msg):
        return False
    return len(msg.split()) <= 10



# Comparison, review, buying advice, and "tell me about" queries are
# informational and must be answered directly, not forced into the guided
# diagnostic intake even when a bike name is mentioned.
COMPARISON_INFO_RE = re.compile(
    r"""
    \b(?:
        (?:what\s+is\s+(?:the\s+)?)?better(?:\s+(?:than|or))?|
        compar(?:e|ed|ing|ison)|versus|\bvs\b|
        (?:tell|talk|ask)\s+(?:me|us)\s+about|
        (?:which\s+(?:is|one|would)\b)|
        (?:should\s+i\s+(?:buy|get|choose|pick))|
        (?:pros?\s+(?:and|or)\s+cons?)|
        (?:review|overview|buying\s+guide)
    )\b
    """,
    re.I | re.X,
)

def is_general_motorcycle_query(message, history=None):
    """True for motorcycle maintenance/how-to/service/info questions.

    Active fault reports are deliberately excluded so they keep using the
    guided diagnostic flow. Visual part queries are also excluded.
    """
    msg = _norm(message)
    if not msg:
        return False
    if re.search(
        r'\b(?:picture|pictures|photo|photos|image|images|larawan|litrato|hulagway)\b',
        msg,
    ):
        return False
    if LOCATION_FLOW_RE.search(msg):
        # "Where is the noise/oil coming from?" is a fault question, not a
        # request for the physical location of a component.
        return False
    if LOCATION_QUERY_RE.search(msg) and LOCATION_SYMPTOM_RE.search(msg):
        # "Where is the brake noise?" / "Where is the oil leak?" are symptom
        # questions even though they contain a component name.
        return False
    if _looks_like_part_visual_query(msg):
        return False
    if _looks_like_part_location_query(msg, history):
        return True
    # Comparison, buying-advice, and "tell me about" queries get a direct
    # informational answer even when a bike name appears in the message.
    if COMPARISON_INFO_RE.search(msg):
        return True
    if _has_active_fault(msg):
        return False
    if _looks_like_vehicle_identification(msg):
        return False
    if not GENERAL_DOMAIN_RE.search(msg):
        return False
    if not _has_general_topic_cue(msg) and not msg.rstrip().endswith('?'):
        return False
    return True


def _is_guided_chip_answer(msg):
    """True when the text is one of the guided flow's own chip labels."""
    for area in AREAS.values():
        if _norm(area.get('chips', '')) == msg:
            return True
        for question in area.get('questions', []):
            if any(_norm(label) == msg for _, label in question.get('options', [])):
                return True
    return False


GUIDED_AREA_WORDS = [
    'brake', 'preno', 'engine', 'makina', 'oil', 'langis', 'maintenance',
    'tire', 'tyre', 'gulong', 'chain', 'kadena', 'battery', 'baterya',
    'electrical', 'overheat', 'init', 'noise', 'ingay', 'smoke', 'usok',
    'power', 'accelerat', 'suspension', 'chassis', 'starting', 'start',
]

GUIDED_GENERAL_CUE_RE = re.compile(
    r"\b(?:interval|schedule|frequency|how\s+often|how\s+many|best|recommended|"
    r"procedure|steps?|guide|tips?|checklist|spec|price|cost|pressure|psi|slack)\b",
    re.I,
)

# Maintenance chips/options are requests for a direct answer, not fault-area
# answers. They should leave the guided diagnostic flow even mid-session.
GUIDED_MAINTENANCE_RE = re.compile(
    r"\b(?:oil|langis|maintenance|service|pms|tune[- ]?up|chain|kadena|"
    r"brake\s+pads?|fluids?|clean(?:ing)?|lubricat(?:e|ing|ion)|"
    r"replace|changing|change|inspect(?:ing)?|check(?:ing)?)\b",
    re.I,
)


def _is_guided_area_choice(msg):
    """True for a short area answer such as "Brakes" during a guided session."""
    if len(msg.split()) > 4 or '?' in msg or GENERAL_QUESTION_START_RE.search(msg):
        return False
    if GUIDED_GENERAL_CUE_RE.search(msg):
        return False
    return bool(detect_area(msg)) or _has_any(msg, GUIDED_AREA_WORDS)


def _is_procedure_or_step_msg(msg):
    """True for commands that continue, request, or report on a diagnostic procedure."""
    if re.search(r'\b(?:step|hakbang|tikang)\s*\d+\b', msg):
        return True
    if re.search(r'\b(?:next\s*step|susunod\s*na\s*step|sunod\s*nga\s*tikang)\b', msg):
        return True
    if _has_any(msg, [
        'what next', "what's next", 'what do i do next', 'what to do next', 'what now',
        'ano susunod', 'ano na', 'ano sunod', 'paano ang step', 'paano susunod',
        'next', 'proceed', 'continue', 'tuloy', 'padayon',
        'begin', 'start', 'commence', 'ready to start', 'yes, ready', 'ready',
        'begin procedure', 'start procedure', 'simulan', 'umpisahan', 'suguran',
        'it worked', 'that worked', 'worked', 'fixed', 'okay now', 'nagana na', 'ok na', 'naayos na',
        'still not fixed', 'not fixed', "didn't work", 'did not work', 'didnt work',
        'hindi pa', 'hindi gumana', 'ayaw pa rin', 'wala pa rin', 'wala nagbago', 'indi gihapon',
        'failed', 'wala epekto', 'show all steps', 'all steps',
    ]):
        return True
    # Continuation / resume phrases
    if _has_any(msg, CONTINUE_SESSION_PHRASES):
        return True
    # Location-unknown signals during a procedure
    if _has_any(msg, LOCATION_UNKNOWN_PHRASES):
        return True
    # Beginner how-to requests during a procedure
    if _has_any(msg, HOWTO_UNKNOWN_PHRASES):
        return True
    # User asking again to be sure
    if _has_any(msg, REASSURE_CONFIRM_PHRASES):
        return True
    return False


def is_guided_intent(message, history=None, state=None):
    """True when the guided flow should handle this turn."""
    msg = _norm(message)
    if _has_any(msg, RESET_PHRASES):
        return True
    # General maintenance/how-to questions get a direct answer, not an intake
    # form. The exception is a guided chip/area answer mid-session, which must
    # continue the flow the user is already in.
    if is_general_motorcycle_query(message, history):
        if state and state.get('stage') in ('area', 'checks', 'narrow', 'verdict', 'procedure'):
            # Comparison/info queries always escape the guided flow.
            if COMPARISON_INFO_RE.search(msg):
                return False
            if GUIDED_MAINTENANCE_RE.search(msg):
                # "Oil change / maintenance" and similar chips are general
                # questions; answer them instead of restarting the intake.
                return False
            if _is_guided_chip_answer(msg) or _is_guided_area_choice(msg):
                return True
        return False
    # Let the existing handlers own greetings, help, visuals and catalogues,
    # even in the middle of a guided session.
    if _is_greeting(msg):
        return False
    if _has_any(msg, ['what can you do', 'help', 'list parts', 'list symptoms',
                      'how many', 'what is a', 'what is an', 'show me', 'picture',
                      'image', 'photo', 'who are you']):
        return False
    if state and state.get('stage') not in (None, '', 'done'):
        # Step/procedure progression commands and how-to requests in procedure stay in guided flow
        if _is_procedure_or_step_msg(msg):
            return True
        # If currently in procedure stage, beginner how-to and location questions must be handled here
        if state.get('stage') == 'procedure' and (_has_any(msg, HOWTO_UNKNOWN_PHRASES) or _has_any(msg, LOCATION_UNKNOWN_PHRASES) or _has_any(msg, REASSURE_CONFIRM_PHRASES)):
            return True
        # A real standalone question ("how do I bleed the brakes?") deserves the full
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
            'year_skipped': False,
            # procedure tracking (Bug 1): steps list and current index
            'procedure_steps': [], 'procedure_index': 0,
            # issue resolution tracking (Bug 2): was the current problem confirmed fixed?
            'issue_resolved': False}


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


def _get_procedure_steps_for_area(area, answers):
    v = pick_verdict(area, answers)
    free = v.get('free', [])
    if len(free) > 1 and free[0] != 'Work through the free checks above and tell me what you find.':
        return free
    if area in AREAS and AREAS[area].get('checks'):
        return [f"{c[0]} — {c[1]} ({c[2]})" for c in AREAS[area]['checks']]
    return free or ["Inspect the affected assembly for wear, damage, or loose connections."]


# ---------------------------------------------------------------------------
# Step-by-step location guides for common parts referenced in procedures
# ---------------------------------------------------------------------------

PART_LOCATION_GUIDES = {
    'battery': {
        'title': 'How to Find the Battery',
        'steps': [
            "Stand beside your motorcycle.",
            "Look under the seat — lift the seat latch or key slot to open it.",
            "The battery is usually a rectangular black or grey box with two cable terminals (red = positive, black = negative).",
            "On some scooters it may be behind a side panel: look for a plastic panel on either side of the bike secured by screws or push-clips.",
            "On underbone/backbone bikes, it is often under a side cover near the frame.",
            "Once found, check the terminals for white or green corrosion.",
        ],
    },
    'spark plug': {
        'title': 'How to Find the Spark Plug',
        'steps': [
            "The spark plug sits at the top or center of the engine cylinder head.",
            "On scooters: lift the seat, then look for a rubber boot or wire going into the engine block — follow it down.",
            "On underbones/standard bikes: look at the top of the engine. There is a thick rubber plug cap connected to a wire — the spark plug is directly under it.",
            "On some bikes a plastic cover or shroud may hide it; remove the two or three screws to expose it.",
            "Use a spark plug socket (usually 16mm or 21mm) to remove it after disconnecting the plug cap.",
        ],
    },
    'fuse': {
        'title': 'How to Find the Fuse / Fuse Box',
        'steps': [
            "The main fuse or fuse box is almost always near the battery.",
            "Open the seat or side panel to expose the battery area.",
            "Look for a small rubber or plastic box with a lid — it is often zip-tied to the wiring harness near the battery.",
            "Some bikes have a single inline fuse holder clipped directly onto the positive battery cable (red cable).",
            "Open the fuse box lid; the fuses look like small coloured plastic plugs with metal legs.",
            "A blown fuse will have a broken wire inside visible through the clear plastic body.",
        ],
    },
    'oil filter': {
        'title': 'How to Find the Oil Filter',
        'steps': [
            "The oil filter is on the engine crankcase — typically on the side or bottom.",
            "Crouch or kneel beside the motorcycle and look at the lower sides of the engine block.",
            "On many bikes it looks like a round metal canister (spin-on type) or a circular cover with bolts (cartridge type).",
            "It is usually near the oil drain bolt, which is at the very bottom of the engine.",
            "Look for oil staining or a different-coloured round cap — that is the filter cover.",
            "Always use your owner's manual to confirm its exact location for your model.",
        ],
    },
    'air filter': {
        'title': 'How to Find the Air Filter',
        'steps': [
            "The air filter lives inside the airbox — a plastic box connected to the engine via a rubber intake tube.",
            "On scooters: open the seat; the airbox is usually visible near the engine with a cover held by screws.",
            "On underbones/standard bikes: the airbox is on the right or left side of the frame, often behind a side panel.",
            "Remove the side panel (push-clips or screws), then unscrew the airbox cover.",
            "Inside you will see the air filter element — a folded paper or foam block.",
            "Hold it up to light; if it blocks light, it needs cleaning or replacement.",
        ],
    },
    'brake fluid': {
        'title': 'How to Find the Brake Fluid Reservoir',
        'steps': [
            "The front brake fluid reservoir is at the handlebar, on the right side (where the brake lever is).",
            "Look at the master cylinder — a small rectangular or round container attached to the handlebar near the brake lever.",
            "It has a rubber cap or screw cap on top. Remove it only when the engine is cold and the bike is level.",
            "The rear brake reservoir (if separate) is near the rear brake pedal — look for a small bottle near the foot area or frame.",
            "On scooters without a separate rear reservoir, rear brake fluid is in the same unit as the lever.",
            "The fluid level is visible through the translucent side of the container.",
        ],
    },
    'brake pad': {
        'title': 'How to Find and Inspect the Brake Pads',
        'steps': [
            "The brake pads sit inside the brake caliper, which clamps onto the brake disc (rotor).",
            "For the front brake: look at the wheel hub — the silver disc is the rotor, and the caliper (metal block gripping the disc) is the front caliper.",
            "Look through the open side of the caliper; you will see the pads pressing against the disc.",
            "The pads have a friction lining on one side. If only about 2 mm or less of lining remains, replace them.",
            "For the rear brake disc: look at the rear wheel in the same way.",
            "For rear drum brakes: the shoes are inside the drum — look for a small inspection window, or have the drum removed to check.",
        ],
    },
    'fuel pump': {
        'title': 'How to Find the Fuel Pump',
        'steps': [
            "On fuel-injected (FI) bikes, the fuel pump is inside the fuel tank.",
            "Look at the top of the fuel tank — there is a round or square access cover secured by bolts.",
            "The pump module sits directly below that cover inside the tank.",
            "To confirm the pump is running: turn the key ON (do not start). You should hear a faint whirring or clicking for about 2 seconds — that is the pump priming.",
            "On carbureted bikes, the fuel pump (if electric) is usually mounted on the frame near the tank or along the fuel line.",
            "Follow the fuel hose from the petcock at the tank bottom to find any inline fuel pump.",
        ],
    },
    'starter relay': {
        'title': 'How to Find the Starter Relay (Solenoid)',
        'steps': [
            "The starter relay is a small box (about the size of a matchbox) near the battery.",
            "Open the seat to access the battery area.",
            "Look for a cube-shaped component with two large cables (going to the battery and to the starter motor) and two thin wires.",
            "It is often mounted on a rubber grommet near the battery or on the inner fender.",
            "You can test it: when you press the starter button, a healthy relay makes ONE solid click. Rapid clicking = weak battery; no click = relay, fuse, or circuit.",
        ],
    },
    'chain': {
        'title': 'How to Find and Check the Drive Chain',
        'steps': [
            "The drive chain runs along the left side of the rear wheel and swingarm.",
            "Stand on the left side of the motorcycle and look at the rear wheel area.",
            "You will see the metal chain linking the engine sprocket (small gear near the footpeg) to the rear wheel sprocket (large gear at the wheel center).",
            "Push up at the middle of the chain with your finger — correct slack is typically 20–35 mm (about one finger width up and down).",
            "The chain should feel smooth to the touch — a dry or rusty chain needs lubrication.",
            "Check the sprocket teeth: worn teeth look like shark fins or hooks instead of straight peaks.",
        ],
    },
    'cvt': {
        'title': 'How to Find the CVT (on Scooters)',
        'steps': [
            "The CVT is inside the large plastic casing on the left side of the rear wheel.",
            "Stand on the left side of the scooter and look at the engine/rear wheel area.",
            "The CVT cover is the large oval or rectangular black/grey casing behind the left footboard.",
            "It is held on by several bolts around its edge.",
            "Signs of a worn CVT: slipping (engine revs high but speed doesn't increase), squealing, or shuddering on acceleration.",
            "CVT inspection requires removing the cover — only proceed if you have the tools or visit a mechanic.",
        ],
    },
    'kill switch': {
        'title': 'How to Find the Kill Switch',
        'steps': [
            "The kill switch is on the right handlebar, near your right thumb.",
            "Look for a small red or black switch on the right side of the handlebar controls.",
            "It is usually labelled 'RUN / OFF' or has a red indicator.",
            "Make sure it is set to RUN (not OFF) before trying to start.",
            "On some scooters it is combined with the starter button in one unit.",
        ],
    },
    'side stand switch': {
        'title': 'How to Find the Side Stand Switch',
        'steps': [
            "The side stand switch is at the base of the side stand (kickstand) pivot.",
            "Look at the left side of the motorcycle near the footpeg.",
            "The side stand is the metal arm that props the bike up when parked.",
            "At the top of the pivot point you will see a small electrical switch or plunger.",
            "The switch cuts ignition when the stand is down and a gear is selected.",
            "Make sure the stand is fully UP before starting — the switch should release automatically.",
        ],
    },
    'coolant reservoir': {
        'title': 'How to Find the Coolant Reservoir',
        'steps': [
            "The coolant reservoir is a translucent plastic bottle connected to the radiator by a hose.",
            "On scooters: it is usually behind the front panel or inside the body near the engine — open the panel carefully.",
            "On underbones/standard bikes: look along the frame near the radiator for a small bottle secured with a bracket.",
            "The bottle has LOW and FULL markings on the side — check the level only when the engine is completely cold.",
            "Never open the radiator cap while the engine is hot — coolant is under pressure and extremely hot.",
            "If the reservoir is empty or has an oily film, stop riding and have the cooling system inspected.",
        ],
    },
        'banjo bolts': {
        'title': 'How to Find Banjo Bolts and Bleeder Valve',
        'steps': [
            "The bleeder valve is located on the brake caliper at the wheel (front fork or rear swingarm). It has a small hex nut with a rubber cap or hole in the center.",
            "The banjo bolts connect the flexible brake fluid hose to the master cylinder (at the handlebar) and to the caliper (at the wheel).",
            "Inspect both ends of the brake hose: look around the bolt heads and copper crush washers for any wetness or weeping brake fluid.",
            "Wipe the area clean with a dry cloth and pump the brake lever to see if any fresh fluid escapes.",
        ],
    },
    'radiator': {
        'title': 'How to Find the Radiator',
        'steps': [
            "The radiator is in the front of the engine, behind the front fairing or panel.",
            "It looks like a metal grid with many thin fins — similar to a car radiator but smaller.",
            "On scooters: remove the front inner panel or look through the grille opening at the front.",
            "The radiator cap is usually on top. The fan (electric motor with blades) is behind the radiator.",
            "Check that the fins are not clogged with mud or leaves — a blocked radiator causes overheating.",
            "The cooling fan should spin automatically when the engine reaches operating temperature.",
        ],
    },
}


def _extract_part_from_step(step_text):
    """Try to identify the main part being checked in a procedure step."""
    step_lower = step_text.lower()
    # Order matters: more specific patterns first
    part_patterns = [
        ('spark plug', ['spark plug']),
        ('oil filter', ['oil filter']),
        ('air filter', ['air filter']),
        ('fuel pump', ['fuel pump']),
        ('starter relay', ['starter relay', 'solenoid', 'relay']),
        ('banjo bolts', ['banjo', 'bleeder']),
        ('brake fluid', ['brake fluid', 'master cylinder', 'reservoir', 'bleed']),
        ('brake pad', ['brake pad', 'caliper', 'brake disc', 'pad']),
        ('kill switch', ['kill switch']),
        ('side stand switch', ['side stand', 'side-stand', 'kickstand']),
        ('chain', ['chain']),
        ('cvt', ['cvt', 'belt', 'variator']),
        ('coolant reservoir', ['coolant reservoir', 'coolant level', 'coolant']),
        ('radiator', ['radiator', 'fan']),
        ('battery', ['battery', 'terminal']),
        ('fuse', ['fuse']),
    ]
    for part_key, keywords in part_patterns:
        if any(kw in step_lower for kw in keywords):
            return part_key
    return None


STEP_HOWTO_GUIDES = {
    'battery': {
        'title': 'How to Test Battery Voltage & Clean Terminals',
        'tools': '10 mm wrench or socket, clean dry rag, digital multimeter (if available), wire brush or toothbrush',
        'safety': 'Always turn the ignition key OFF. Disconnect the black negative (-) cable first when removing, and connect the red positive (+) cable first when reinstalling.',
        'steps': [
            'Locate the battery under your seat or side panel.',
            'Inspect the two terminals: if you see white, green, or blue powdery corrosion, wipe it clean with a rag dipped in baking soda water or scrub gently with a brush.',
            'Tighten terminal bolts: use your 10 mm wrench to verify both bolt connections are completely snug. A loose ground cable frequently prevents the bike from starting.',
            'Voltage check with a multimeter: set the dial to DC Volts (20V range). Place the RED probe on (+) positive and BLACK probe on (-) negative.',
            'Cranking load test: have a friend watch the meter while you press the starter button.',
        ],
        'good': '12.6V or higher at rest. When cranking the starter, the voltage stays above 9.6V and the engine spins vigorously.',
        'bad': 'Below 12.0V at rest (discharged/dead). During cranking, voltage plunges below 9.0V with rapid relay clicking chatter.',
    },
    'starter relay': {
        'title': 'How to Check the Starter Relay (Solenoid)',
        'tools': 'Flashlight, clean rag, screwdriver',
        'safety': 'Keep your hands clear of moving parts. Make sure motorcycle is in NEUTRAL and on its center stand.',
        'steps': [
            'Locate the starter relay near the battery (the small box with two heavy-gauge cables).',
            'Turn the ignition key ON, make sure the kill switch is set to RUN, and hold the brake lever (scooter) or clutch (manual).',
            'Listen closely to the relay while pressing the starter button.',
            'Check the small trigger wiring connector on top of the relay: pull it off, check for green corrosion, and push it firmly back on.',
        ],
        'good': 'A single, crisp, authoritative "CLICK" sound every time the starter button is pressed, sending full power to the starter motor.',
        'bad': 'Rapid machine-gun chattering (click-click-click), or absolute dead silence with no click at all.',
    },
    'spark plug': {
        'title': 'How to Remove, Inspect & Test the Spark Plug',
        'tools': 'Spark plug wrench or 16 mm deep socket, clean dry rag',
        'safety': 'Allow the engine to cool down completely before touching the spark plug to prevent thread damage in the aluminum cylinder head.',
        'steps': [
            'Locate the spark plug on the cylinder head and firmly pull off the thick rubber plug cap by hand.',
            'Fit your spark plug wrench over the hex body and turn counter-clockwise (lefty-loosey) until unscrewed.',
            'Inspect the electrode tip: clean off any loose soot with a dry cloth.',
            'Spark test: push the spark plug firmly back into the rubber cap. Hold the metal threaded outer shell securely against bare, unpainted metal on the engine block.',
            'Turn key ON and tap the starter button for 1 second while watching the tiny gap between the electrodes.',
            'Carefully reinstall the plug by turning it with your fingers first to prevent cross-threading, then tighten gently with the wrench until snug.',
        ],
        'good': 'Clean light-tan or grey tip. When tested against the engine, a bright, snappy blue/white spark jumps across the gap.',
        'bad': 'Tip is wet black with oil/fuel, or no spark appears at all (failing plug, ignition coil, or side-stand switch cutoff).',
    },
    'brake fluid': {
        'title': 'How to Inspect & Bleed Brake Fluid and Caliper',
        'tools': '8 mm or 10 mm box wrench, clear plastic hose (aquarium tubing), small clean jar, Philips screwdriver, fresh DOT 4 brake fluid, rag',
        'safety': 'Brake fluid instantly damages motorcycle paint and fairings. Wrap a clean cloth around the handlebar reservoir and immediately rinse any spills with clean water.',
        'steps': [
            'Level the motorcycle on its center stand so the handlebar reservoir is flat.',
            'Unscrew the two Philips screws on the reservoir cap and lift off the metal plate and rubber diaphragm.',
            'Inspect fluid level and color: top up with fresh DOT 4 fluid if below the MIN mark.',
            'Slip your clear plastic tubing over the caliper bleeder nipple at the wheel and put the other end into a jar with a little fluid.',
            'Perform the 4-step bleed cycle: (1) Pump brake lever 3 times and HOLD it tight; (2) Crack bleeder nut open 1/4 turn (lever will sink to grip); (3) Snug bleeder nut closed; (4) Release brake lever.',
            'Repeat until no air bubbles are seen entering the tube, keeping the reservoir topped up so air does not enter from the top.',
        ],
        'good': 'Clear amber fluid without trapped air bubbles. The brake lever becomes firm and resists movement well before touching the handlebar grip.',
        'bad': 'Fluid is black/muddy, or bubbles keep appearing while the lever feels squishy and spongy all the way to the grip.',
    },
    'banjo bolts': {
        'title': 'How to Check Banjo Bolts & Brake Line Fittings',
        'tools': '12 mm box wrench, clean dry rag, flashlight',
        'safety': 'Do NOT overtighten banjo bolts — they are hollow brass/steel bolts and will snap if forced. Tighten gently.',
        'steps': [
            'Locate the banjo bolts: one at the handlebar master cylinder and one at the wheel brake caliper.',
            'Wipe both bolt fittings, copper crush washers, and the hose joints completely dry with a rag.',
            'Firmly squeeze and hold the brake lever for 30 seconds.',
            'Inspect closely with a flashlight: run a clean dry finger under the bolt head and washers.',
            'If you see or feel any wet brake fluid, gently snug the bolt with your 12 mm wrench, or replace the copper crush washers.',
        ],
        'good': 'Fittings and copper washers remain bone dry with no weeping or moisture under heavy brake pressure.',
        'bad': 'A wet sheen or active dripping around the crush washers or crimped hose collar, causing lever pressure loss.',
    },
    'brake pad': {
        'title': 'How to Inspect & Clean Brake Pads and Disc',
        'tools': 'Flashlight, can of brake cleaner spray, clean rag',
        'safety': 'Never spray WD-40, motor oil, or grease anywhere near brake discs or pads. Use dedicated automotive brake cleaner only.',
        'steps': [
            'Crouch next to the wheel and shine your flashlight into the open slot of the brake caliper.',
            'Observe the friction lining pressed against the shiny steel brake disc.',
            'Check the thickness of the friction material remaining on the metal backing plate.',
            'Clean road grit and brake dust: spray generously with brake cleaner through the caliper gap and wipe the steel disc with a clean rag.',
            'Spin the wheel by hand: it should turn smoothly without severe rubbing or metal grinding.',
        ],
        'good': 'At least 3 mm to 5 mm of friction material with visible wear indicator grooves. Wheel spins freely with light brush against pads.',
        'bad': 'Less than 1.5 mm of pad left, or bare metal backing plate grinding against the rotor with deep grooves.',
    },
    'chain': {
        'title': 'How to Clean, Measure Slack & Lubricate the Drive Chain',
        'tools': 'Ruler or tape measure, chain cleaner or kerosene, chain lubricant spray, clean cloth',
        'safety': 'ALWAYS keep the engine OFF. Spin the rear wheel by hand only. Never run the motorcycle in gear while your hands are near the chain.',
        'steps': [
            'Prop the motorcycle on its center stand so the rear wheel can turn freely.',
            'Measure chain slack: find the midpoint of the bottom chain run. Push down, then push up with your finger and measure total movement with a ruler.',
            'Normal slack is 20 mm to 35 mm (about one thumb width). If touching the swingarm or tight like a guitar string, it needs adjustment.',
            'Cleaning: spray chain cleaner onto the chain and wipe off heavy road grime with a rag.',
            'Lubricating: slowly rotate the wheel backwards by hand while spraying chain lube along the inside edges of the rollers where the teeth contact.',
            'Allow the lubricant to dry for 10-15 minutes before riding.',
        ],
        'good': 'Clean, moist with lubricant, 25-30 mm flexible slack, and sprocket teeth straight and symmetrical.',
        'bad': 'Dry, red rust patches, stiff links that kink, loose enough to slap the swingarm, or sprocket teeth hooked like shark fins.',
    },
    'cvt': {
        'title': 'How to Inspect the Scooter CVT Belt & Rollers',
        'tools': '8 mm socket or T-wrench, dry clean cloth, flashlight',
        'safety': 'Ensure engine is switched off and completely cold before opening the CVT cover.',
        'steps': [
            'Stand on the left side of the scooter and remove the 8 mm bolts around the CVT transmission cover.',
            'Pull the cover off carefully to reveal the rubber drive belt and front/rear pulley assemblies.',
            'Twist and inspect the drive belt: check the inner rubber teeth for cracks, missing chunks, or fraying side threads.',
            'Check for belt slip: look for black rubber dust accumulated on the floor of the case or glazed shiny pulley faces.',
            'Wipe the inside clean with a dry cloth (never apply any grease or solvent to the belt or pulley faces).',
        ],
        'good': 'Belt is flexible with deep, sharp teeth and no cracks. Case is clean and dry.',
        'bad': 'Cracks in the cog valleys, fraying cords, or belt is excessively narrow causing sluggish uphill take-off.',
    },
    'coolant': {
        'title': 'How to Check & Top Up Engine Coolant',
        'tools': 'Pre-mixed 50/50 motorcycle coolant, clean funnel, clean rag',
        'safety': 'NEVER open the radiator cap when the engine is warm or hot. Pressurized boiling coolant will spray and cause serious burns.',
        'steps': [
            'Allow the engine to cool for at least 45 minutes.',
            'Locate the translucent coolant expansion reservoir.',
            'With the bike standing upright on level ground, check the fluid level against the LOW and FULL lines on the bottle.',
            'If below LOW, remove the reservoir cap and slowly add pre-mixed coolant through a clean funnel up to the FULL line.',
            'Inspect radiator fins from the front: remove trapped mud or leaves with gentle water spray.',
            'Inspect rubber hoses for swelling, cracks, or green/white dried crust at clamp fittings.',
        ],
        'good': 'Coolant level between LOW and FULL, bright green, blue, or pink color with no oil residue or milky foam.',
        'bad': 'Reservoir bone dry, brown cloudy coolant, milky emulsion in engine oil, or active dripping under the water pump.',
    },
    'air filter': {
        'title': 'How to Inspect & Clean the Air Filter',
        'tools': 'Philips (+) screwdriver, clean cloth',
        'safety': 'Never ride the motorcycle without an air filter element installed, as road dust will score the cylinder bore.',
        'steps': [
            'Locate the plastic airbox under the seat or behind the side panel.',
            'Unscrew the 4 to 6 Philips screws and remove the airbox lid.',
            'Extract the filter cartridge (paper pleats or foam element).',
            'Hold the filter up toward daylight or a flashlight: light should easily pass through the pleats.',
            'Tap it gently face-down against a hard surface to shake loose heavy dust.',
            'Wipe out any dust or moisture inside the airbox housing with a clean damp rag before reassembling.',
        ],
        'good': 'Clean paper or foam element allowing light through with no engine oil saturation.',
        'bad': 'Clogged with thick black dirt, wet with engine oil blow-by, or torn paper pleats allowing unfiltered air into the engine.',
    },
    'fuse': {
        'title': 'How to Inspect & Replace Blown Fuses',
        'tools': 'Fuse puller or small needle-nose pliers, spare fuse of exact same amp rating (e.g. 10A, 15A, 20A)',
        'safety': 'Turn ignition OFF. Never install a fuse with a higher amp rating or bridge with wire, as this can cause an electrical fire.',
        'steps': [
            'Locate the fuse box near the battery under the seat and flip open the plastic latch cover.',
            'Identify the fuse for the affected circuit (e.g. MAIN, IGNITION, LIGHTS).',
            'Grip the fuse and pull it straight upward.',
            'Hold the fuse up to the light and examine the S-shaped or U-shaped metal wire inside the clear colored plastic.',
            'If the wire is broken or has a dark burn mark, replace it with a spare of the identical amp rating.',
            'Press the new fuse firmly into the socket and snap the lid closed.',
        ],
        'good': 'Metal wire inside is continuous and unbroken.',
        'bad': 'Wire inside is separated, melted, or blackened, cutting all power to that circuit.',
    },
    'kill switch': {
        'title': 'How to Check & Free the Kill Switch and Side-Stand Switch',
        'tools': 'Electrical contact cleaner or WD-40, clean rag',
        'safety': 'Engine off and bike on center stand in neutral.',
        'steps': [
            'Handlebar kill switch: click the red rocker switch back and forth firmly between RUN and OFF several times.',
            'If sticky, spray a 1-second burst of electrical contact cleaner into the switch crevices.',
            'Side stand: crouch on the left side and locate the small spring-loaded plunger switch at the kickstand pivot point.',
            'Road grit and chain lube often cake around the plunger: spray with contact cleaner and wipe with a rag.',
            'Flick the stand up and down: verify the spring snaps the stand all the way up so the plunger releases fully.',
        ],
        'good': 'Switches click crisply and the side-stand plunger extends smoothly when the stand is raised.',
        'bad': 'Plunger is jammed with dried mud/grit, tricking the motorcycle into thinking the kickstand is down and cutting spark.',
    },
    'oil': {
        'title': 'How to Check Engine Oil Level and Condition',
        'tools': 'Clean cloth or paper towel',
        'safety': 'Check on level ground with engine stopped for 5 minutes after running.',
        'steps': [
            'Place the bike on its center stand on flat, level ground.',
            'Locate the oil dipstick or sight glass on the right side of the engine crankcase.',
            'Unscrew the dipstick, wipe the oil off with a clean rag.',
            'Insert the dipstick back in WITHOUT screwing it in (standard motorcycle procedure), then withdraw it.',
            'Check where the oil film sits on the crosshatched tip.',
        ],
        'good': 'Oil level sits squarely between the upper (MAX) and lower (MIN) marks. Color is clear amber to light brown.',
        'bad': 'Below the MIN mark (engine running dry), pitch black with strong burnt odor, or milky light-brown (coolant mixing with oil).',
    },
}


def _build_howto_guide(part_key, step_text, step_number, sir='sir', lang='english'):
    """Build a comprehensive, beginner-friendly how-to tutorial for a procedure step."""
    guide = STEP_HOWTO_GUIDES.get(part_key)
    if not guide:
        # Build tailored 4-step beginner guide based on the step text
        lines = [
            f"No problem, {sir}! Here is a beginner-friendly, step-by-step guide on how to perform **Step {step_number}**:\n",
            f"**🛠️ Step {step_number} Task:** {step_text}\n",
            f"**🧰 What you need:** Basic hand tools (wrench or screwdriver), a clean rag, and a flashlight.\n",
            f"**⚠️ Safety Note:** Ensure the motorcycle engine is turned OFF and cool to the touch before starting.\n",
            f"**📋 How to do it step-by-step:**\n",
            f"1. **Position the bike:** Place the motorcycle upright on its center stand on flat ground with good lighting.\n",
            f"2. **Inspect the component:** Carefully observe the assembly mentioned: *{step_text}*. Look for obvious loose screws, cracks, or fluid weeping.\n",
            f"3. **Perform the test/cleaning:** Follow the task action carefully without applying excessive force.\n",
            f"4. **Observe the result:** Check if the component responds smoothly or remains stuck/abnormal.\n",
            f"\n**🔍 Expected Benchmark:**\n",
            f"- **Normal:** Component is secure, clean, and operates without unusual noise, stiffness, or fluid leaks.\n",
            f"- **Abnormal:** Loose, corroded, leaking, or fails to operate.\n",
            f"\nTry this out, {sir}, and let me know what you observe!\n\n",
            f"[chips: Step {step_number} passed (normal) | Step {step_number} failed (abnormal) | Where is it? | Next step | It worked]",
        ]
        return "\n".join(lines)

    lines = [
        f"No problem at all, {sir}! Here is a complete beginner-friendly tutorial for **Step {step_number}**:\n",
        f"**🎓 {guide['title']}**\n",
        f"**Task:** {step_text}\n",
        f"**🧰 Tools Needed:** {guide['tools']}\n",
        f"**⚠️ Safety First:** {guide['safety']}\n",
        f"\n**📋 Step-by-Step Instructions:**\n",
    ]
    for idx, inst in enumerate(guide['steps'], 1):
        lines.append(f"{idx}. {inst}")

    lines.append(f"\n**🔍 What to Look For (Good vs. Bad):**\n")
    lines.append(f"- **✅ Good (Normal):** {guide['good']}")
    lines.append(f"- **❌ Bad (Faulty):** {guide['bad']}\n")
    lines.append(f"Take your time, {sir}. Once you have tested this, tell me what you found!\n\n")
    lines.append(f"[chips: Step {step_number} passed (normal) | Step {step_number} failed (abnormal) | Where is it? | Next step | It worked]")
    return "\n".join(lines)
def _build_location_guide(part_key, step_number, sir='sir'):
    """Build a formatted location guide for a part, ready to send to the user."""
    guide = PART_LOCATION_GUIDES.get(part_key)
    if not guide:
        # Generic fallback using part_locations.py
        from .part_locations import location_hint
        hint = location_hint(part_key)
        if hint:
            return (
                f"No problem, {sir}! Let me show you where to find it.\n\n"
                f"**Location:** {hint}\n\n"
                f"Always confirm the exact position in your owner's manual, as it varies by model.\n\n"
                f"[chips: Found it, continue | Still can't find it | Show all steps | Start over]"
            )
        return None

    lines = [
        f"No problem, {sir}! Here is a step-by-step guide to find the **{guide['title'].replace('How to Find the ', '')}** "
        f"before we continue with Step {step_number}:\n",
        f"**📍 {guide['title']}**\n",
    ]
    for i, loc_step in enumerate(guide['steps'], 1):
        lines.append(f"{i}. {loc_step}")
    lines.append(
        f"\nOnce you've located it, come back and tell me what you see — we'll continue with **Step {step_number}**.\n\n"
        f"[chips: Found it, continue Step {step_number} | Still can't find it | Ask a mechanic | Show all steps]"
    )
    return "\n".join(lines)


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

    # --- Detect mid-session motorcycle switch ---
    from .views import _extract_vehicle_info
    cur_veh = _extract_vehicle_info(message)
    if cur_veh.get('make') or cur_veh.get('model'):
        cur_prof = resolve_profile(cur_veh, message)
        prev_bike = state.get('bike') or {}
        prev_name = f"{prev_bike.get('make', '')} {prev_bike.get('model', '')}".strip().lower()
        new_name = f"{cur_prof.get('make', '')} {cur_prof.get('model', '')}".strip().lower()
        if prev_name and new_name and prev_name != new_name:
            prev_area = state.get('area')
            state.clear()
            state.update(start_state())
            state['bike'] = cur_prof
            state['fresh'] = False
            new_area = detect_area(message) or prev_area
            if new_area:
                state['area'] = new_area
                return _enter_checks(state, cur_prof, new_area, lang, message)
            state['stage'] = 'area'
            return (
                f"Understood, {sir}. Switching diagnostic focus to the **{bike_label(cur_prof)}**.\n\n"
                f"{focus_block(cur_prof, lang)}\n\n"
                f"{_tr(lang, 'area_ask')}\n\n"
                f"[chips: {_tr(lang, 'area_chips')}]"
            )

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
        state['issue_resolved'] = True
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

    # --- User asks to continue / resume the current session ---------------
    # Use ONLY unambiguous resume phrases here. Action words like "proceed",
    # "begin", "yes", "start" stay handled in the stage-specific blocks below
    # so they correctly advance the diagnostic flow (e.g. verdict → procedure).
    _RESUME_ONLY_PHRASES = [
        'can we continue', 'continue the session', 'continue diagnosis',
        'resume', 'where were we', 'magpatuloy', 'ituloy natin',
        'saan tayo', 'let us continue', 'can we go on',
        'tuloy na natin', 'ituloy na',
    ]
    if _has_any(msg, _RESUME_ONLY_PHRASES) or (
        _has_any(msg, CONTINUE_SESSION_PHRASES) and state.get('stage') == 'procedure'
    ):
        cur_stage = state.get('stage', '')
        area = state.get('area')
        bike = state.get('bike')
        if cur_stage == 'procedure' and area and bike:
            steps = state.get('procedure_steps', [])
            idx = state.get('procedure_index', 0)
            state.pop('awaiting_location_confirm', None)
            curr_step = steps[idx] if idx < len(steps) else "Inspect the affected assembly."
            return (
                f"Of course, {sir}! We were on **Step {idx + 1}** of the {area} diagnosis. "
                f"Let's pick up right where we left off.\n\n"
                f"**Step {idx + 1}:** {curr_step}\n\n"
                f"Perform this check and tell me what you find.\n\n"
                f"[chips: Step {idx + 1} done | How to do this step | Where is it? | Next step | It worked]"
            )
        if cur_stage in ('narrow', 'verdict', 'checks') and area and bike:
            # Resume from narrow/verdict — re-ask the current question
            q_index = int(state.get('q_index', 0))
            questions = AREAS.get(area, {}).get('questions', [])
            if q_index < len(questions):
                return (
                    f"Of course, {sir}! We were narrowing down the **{area}** issue. Here's where we were:\n\n"
                    f"{question_block(area, q_index, lang)}"
                )
            # If past all questions, remind of verdict stage
            return (
                f"Of course, {sir}! We have all the information needed. Let me show you the diagnosis.\n\n"
                f"[chips: Begin procedure | Start over | Another check]"
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

        # Detect and persist symptom area if mentioned by the user
        detected_area = detect_area(message) or state.get('area') or detect_area_from_history(history)
        if detected_area:
            state['area'] = detected_area

        profile = resolve_profile(vehicle, message, history)
        if vehicle.get('make') or vehicle.get('model'):
            state['bike'] = profile
            state['fresh'] = False
            area = state.get('area') or detect_area(message) or detect_area_from_history(history)
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
        # Provide a warm acknowledgment if the user already stated their symptom
        prefix = _safety_prefix(message, lang, force_brake=(state.get('area') == 'brakes'))
        ack = _symptom_ack(state.get('area'), lang, sir)
        return (
            f"{prefix}"
            f"{ack}"
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

        area = detect_area(message) or state.get('area') or detect_area_from_history(history)
        if area:
            state['area'] = area
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
        area = new_area or state.get('area') or detect_area(state.get('year_context', '')) or detect_area_from_history(history)
        state.pop('year_context', None)
        if area:
            state['area'] = area

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
            area = state.get('area') or detect_area_from_history(history)
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

            # User doesn't know where a part is — give a location guide
            if _has_any(msg, LOCATION_UNKNOWN_PHRASES):
                # Find the part from the current check
                checks = AREAS[area].get('checks', [])
                part_key = None
                if q_index < len(checks):
                    part_key = _extract_part_from_step(checks[q_index][0])
                if part_key is None:
                    # Try from the question text
                    q_text = AREAS[area]['questions'][q_index].get('text', '')
                    part_key = _extract_part_from_step(q_text)
                if part_key:
                    guide = _build_location_guide(part_key, q_index + 1, sir)
                    if guide:
                        state['awaiting_location_confirm'] = True
                        return guide
                # Generic fallback
                return (
                    f"No problem, {sir}. Here are the checks with location hints:\n\n"
                    f"{checks_block(area, profile, lang)}\n\n"
                    f"{question_block(area, q_index, lang)}"
                )

            # User says "continue / found it / ok" after a location guide
            if state.get('awaiting_location_confirm') and _has_any(msg, [
                'found it', 'found', 'i see it', 'i found it', 'ok continue', 'continue',
                'nakita ko', 'nandito', 'nahanap ko', 'okay', 'got it', 'i see',
                'continue step', 'yes', 'sige', 'oo',
            ] + CONTINUE_SESSION_PHRASES):
                state.pop('awaiting_location_confirm', None)
                return (
                    f"Great, {sir}! Now let us continue.\n\n"
                    f"{question_block(area, q_index, lang)}"
                )

            answer = _match_option(area, q_index, message)
            if answer:
                state.pop('awaiting_location_confirm', None)
                state.setdefault('answers', {})[questions[q_index]['key']] = answer
                state['q_index'] = q_index + 1

                if state['q_index'] < len(questions):
                    return question_block(area, state['q_index'], lang)
                state['stage'] = 'verdict'
            else:
                # Also accept a direct "show verdict" request.
                if _has_any(msg, ['likely cause', 'what is the cause', 'diagnose it', 'just tell me']):
                    state['stage'] = 'verdict'
                elif _has_any(msg, [
                    'begin', 'start', 'proceed', 'commence', 'step 1', 'step one', 'first step',
                    'ready to start', 'ready', 'yes, ready', 'start procedure', 'begin procedure',
                    'simulan', 'umpisahan', 'gawin natin', 'read step 1',
                ]):
                    answers = state.get('answers', {})
                    state['procedure_steps'] = _get_procedure_steps_for_area(area, answers)
                    state['stage'] = 'procedure'
                    state['procedure_index'] = 0
                    steps = state['procedure_steps']
                    step_1 = steps[0] if steps else "Inspect the affected assembly."
                    return (
                        f"**Step 1:** {step_1}\n\n"
                        f"Perform this check, {sir}, and let me know what you find.\n\n"
                        f"[chips: Step 1 done | How to do this step | Where is it? | Next step | It worked]"
                    )
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
        state['procedure_steps'] = _get_procedure_steps_for_area(area, answers)

        # If user asks to start/commence procedure from verdict
        if _has_any(msg, [
            'begin', 'start', 'proceed', 'commence', 'step 1', 'step one', 'first step',
            'yes', 'oo', 'sige', 'umpisahan', 'simulan', 'suguran', "let's start",
            "lets start", "let's do it", "lets do it", 'cge', 'padayon', 'tuloy',
            'begin procedure', 'start procedure', 'gawin natin', 'read step 1',
            'ready to start', 'yes, ready', 'ready',
        ] + CONTINUE_SESSION_PHRASES):
            state['stage'] = 'procedure'
            state['procedure_index'] = 0
            steps = state['procedure_steps']
            step_1 = steps[0] if steps else "Inspect the affected assembly."
            return (
                f"**Step 1:** {step_1}\n\n"
                f"Perform this check, {sir}, and let me know what you find.\n\n"
                f"[chips: Step 1 done | How to do this step | Where is it? | Next step | It worked]"
            )

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

    # --- Stage: procedure --------------------------------------------------
    if state.get('stage') == 'procedure':
        new_area = detect_area(message)
        if new_area:
            state['answers'] = {}
            return _enter_checks(state, profile, new_area, lang, message)

        steps = state.get('procedure_steps', [])
        idx = state.get('procedure_index', 0)

        # Did user say "show all steps"?
        if _has_any(msg, ['show all steps', 'all steps', 'ipakita lahat', 'tanan nga tikang']):
            lines = [f"**All Procedure Steps for {bike_label(profile)}:**", ""]
            for i, st in enumerate(steps, start=1):
                lines.append(f"**Step {i}:** {st}")
            lines.append("")
            lines.append(f"[chips: Step 1 | It worked | Still not fixed | Start over]")
            return "\n".join(lines)

        # Did user confirm fix?
        if _has_any(msg, ['it worked', 'that worked', 'worked', 'fixed', 'okay now', 'nagana na', 'ok na', 'naayos na']):
            state['issue_resolved'] = True
            state.clear()
            state.update({'stage': 'done'})
            return (
                f"Outstanding, {sir}! The problem is resolved and the motorcycle is back in service.\n\n"
                "Ride safely, and reach out any time you need diagnostic assistance.\n\n"
                "[chips: Start over | Engine will not start | Brakes weak or spongy | Oil change / maintenance]"
            )

        # Did user ask for a specific step number? (e.g. "step 2", "what is step 2", "step 3", "step 1")
        step_match = re.search(r'\b(?:step|hakbang|tikang)\s*(\d+)\b', msg)
        if step_match:
            target_step = int(step_match.group(1)) - 1
            if 0 <= target_step < len(steps):
                state['procedure_index'] = target_step
                state.pop('awaiting_location_confirm', None)
                return (
                    f"**Step {target_step + 1}:** {steps[target_step]}\n\n"
                    f"Perform this check, {sir}, and let me know what you find.\n\n"
                    f"[chips: Step {target_step + 1} done | It worked | Still not fixed | Next step | Show all steps]"
                )

        # User asks again just to be sure: reassure with technical clarity and offer to continue
        if _has_any(msg, REASSURE_CONFIRM_PHRASES):
            curr_step = steps[idx] if idx < len(steps) else "Inspect the affected assembly."
            return (
                f"Yes, {sir}! Rest assured, this is the safest and most reliable manufacturer-standard diagnostic check for your motorcycle's {area} system. "
                f"We always rule out the free, simple mechanical and electrical causes first before touching any expensive replacement parts.\n\n"
                f"Whenever you are ready, we can continue on what we are trying to fix:\n\n"
                f"**Step {idx + 1}:** {curr_step}\n\n"
                f"[chips: How to do this step | Where is it? | Can we continue in that session | Next step | Start over]"
            )

        # User asks HOW to perform the current step or how to fix it (beginner tutorial)
        if _has_any(msg, HOWTO_UNKNOWN_PHRASES):
            curr_step_text = steps[idx] if idx < len(steps) else ""
            part_key = _extract_part_from_step(curr_step_text)
            state['awaiting_howto_confirm'] = True
            return _build_howto_guide(part_key, curr_step_text, idx + 1, sir=sir, lang=lang)

        # User doesn't know where to find the part for the current step
        if _has_any(msg, LOCATION_UNKNOWN_PHRASES):
            curr_step_text = steps[idx] if idx < len(steps) else ""
            part_key = _extract_part_from_step(curr_step_text)
            if part_key:
                guide = _build_location_guide(part_key, idx + 1, sir)
                if guide:
                    state['awaiting_location_confirm'] = True
                    return guide
            # Generic fallback — describe the current step in more detail
            return (
                f"No problem, {sir}! Here is a step-by-step location guide on what to look for in Step {idx + 1}:\n\n"
                f"**📍 Location & Inspection for Step {idx + 1}:**\n"
                f"1. Stand near the assembly: {curr_step_text}.\n"
                f"2. Inspect the component for loose fittings, weeping fluid, or wear.\n"
                f"3. Confirm the exact position in your owner's manual diagram.\n\n"
                f"Once you've found it, let me know what you see!\n\n"
                f"[chips: Found it, continue | Still can't find it | Ask a mechanic | Show all steps]"
            )

        # User confirmed they found the part / ready to continue after location guide
        if state.get('awaiting_location_confirm') and _has_any(msg, [
            'found it', 'found', 'i see it', 'i found it', 'ok continue', 'continue',
            'nakita ko', 'nandito', 'nahanap ko', 'okay', 'got it', 'i see',
            'continue step', 'yes', 'sige', 'oo',
        ] + CONTINUE_SESSION_PHRASES):
            state.pop('awaiting_location_confirm', None)
            curr_step = steps[idx] if idx < len(steps) else "Inspect the affected assembly."
            return (
                f"Great, {sir}! Now that you've found it, let's continue.\n\n"
                f"**Step {idx + 1}:** {curr_step}\n\n"
                f"Perform this check and tell me what you find.\n\n"
                f"[chips: Step {idx + 1} done | How to do this step | Where is it? | Next step | It worked]"
            )

        # User says "can we continue?" / resume session after any pause
        if _has_any(msg, CONTINUE_SESSION_PHRASES):
            state.pop('awaiting_location_confirm', None)
            curr_step = steps[idx] if idx < len(steps) else "Inspect the affected assembly."
            return (
                f"Of course, {sir}! We were on Step {idx + 1}. Let's pick up right where we left off.\n\n"
                f"**Step {idx + 1}:** {curr_step}\n\n"
                f"Perform this check and tell me what you find.\n\n"
                f"[chips: Step {idx + 1} done | How to do this step | Where is it? | Next step | It worked]"
            )

        # Did user say next step / done?
        if _has_any(msg, [
            'next', 'proceed', 'done', 'susunod', 'sunod', 'tuloy', 'padayon',
            'what next', "what's next", 'what do i do next', 'what to do next', 'what now',
            'ano susunod', 'ano na', 'sunod nga tikang', 'yes'
        ]):
            state.pop('awaiting_location_confirm', None)
            idx += 1
            state['procedure_index'] = idx
            if idx < len(steps):
                return (
                    f"**Step {idx + 1}:** {steps[idx]}\n\n"
                    f"Check this and tell me the result, {sir}.\n\n"
                    f"[chips: Step {idx + 1} done | How to do this step | Where is it? | Next step | It worked]"
                )
            else:
                state['stage'] = 'verdict'
                return (
                    f"You have completed all {len(steps)} free diagnostic checks, {sir}.\n\n"
                    f"Did these steps resolve the issue with your motorcycle?\n\n"
                    f"[chips: It worked | Still not fixed | Another check | Start over]"
                )

        # Still not fixed / unsuccessful attempt
        if _has_any(msg, [
            'still not fixed', 'not fixed', "didn't work", 'did not work', 'didnt work',
            'hindi pa', 'hindi gumana', 'ayaw pa rin', 'wala pa rin', 'wala nagbago',
            'indi gihapon', 'failed', 'wala epekto', 'still having problem'
        ]):
            state.pop('awaiting_location_confirm', None)
            if idx + 1 < len(steps):
                state['procedure_index'] = idx + 1
                return (
                    f"Understood, {sir}. Since Step {idx + 1} did not resolve the {area} problem, let us move to the next check:\n\n"
                    f"**Step {idx + 2}:** {steps[idx + 1]}\n\n"
                    f"Perform this check and let me know your findings.\n\n"
                    f"[chips: Step {idx + 2} done | It worked | Next step | Where is it? | Start over]"
                )
            else:
                state['stage'] = 'narrow'
                state['q_index'] = 0
                return (
                    f"Understood, {sir}. The initial free steps did not clear the fault. Let us inspect deeper causes for the {area} issue:\n\n"
                    f"{checks_block(area, profile, lang)}\n\n"
                    f"{question_block(area, 0, lang)}"
                )

        # Default in procedure: remind current step
        curr_step = steps[idx] if idx < len(steps) else "Inspect the assembly."
        return (
            f"**Step {idx + 1} (in progress):** {curr_step}\n\n"
            f"Tell me what you find, {sir}.\n\n"
            f"[chips: Step {idx + 1} done | How to do this step | Where is it? | Next step | It worked]"
        )

    # Unknown stage -> restart cleanly.
    state.clear()
    state.update(start_state())
    return (
        f"{_tr(lang, 'reset')}\n\n"
        f"[chips: {_tr(lang, 'reset_chips')}]"
    )
