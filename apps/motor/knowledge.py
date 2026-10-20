"""
Motor Assistant Verified Repair Knowledge Base & Retrieval Service.

Organizes structured repair knowledge into:
- Symptoms with vehicle compatibility (motorcycle, car, all) and safety urgency.
- Discriminative follow-up diagnostic questions in English, Tagalog, and Hiligaynon.
- Probable causes with explicit confidence ratings (High, Medium, Tentative).
- Concrete diagnostic tests, expected measurements, and alternative outcomes.
- Required tools, safety warnings, when-to-stop criteria, and verified citations.
- Pre-retrieval filtering before prompting the AI, preventing hallucinations.
"""
from decimal import Decimal
import json
import re

from django.db.models import Q
from .models import (
    DiagnosticQuestion,
    DiagnosticSymptom,
    GuideRequiredPart,
    Part,
    TroubleshootingGuide,
)


VERIFIED_KNOWLEDGE_SEEDS = [
    # ─────────────────────────────────────────────────────────────────────────
    # 1. MOTORCYCLE: NO START — ELECTRICAL / BATTERY / STARTER
    # ─────────────────────────────────────────────────────────────────────────
    {
        'symptom_name': 'Motorcycle will not start (Rapid clicking or completely dead)',
        'category': 'Electrical & Starting',
        'vehicle_type': 'motorcycle',
        'urgency_level': 'warning',
        'safety_warning': 'Ensure motorcycle is in Neutral on its center stand before testing electrical components.',
        'description': 'Pushing the starter button produces rapid machine-gun clicking, dimming dash lights, or complete silence.',
        'questions': [
            {
                'key': 'starter_sound',
                'order': 1,
                'en': 'What happens exactly when you press the starter button?',
                'tl': 'Ano ang eksaktong naririnig mo pag pinindot ang starter button?',
                'hil': 'Ano ang mabatian mo kon pinduton ang starter button?',
                'options': [
                    {'label': 'A. Rapid clicking from under the seat', 'value': 'rapid_clicking', 'cause_hint': 'battery_dead'},
                    {'label': 'B. Engine cranks very slowly then dies', 'value': 'slow_crank', 'cause_hint': 'weak_battery'},
                    {'label': 'C. Complete silence, no lights on dash', 'value': 'dead_silent', 'cause_hint': 'blown_fuse'},
                    {'label': 'D. Cranks strongly but does not catch fire', 'value': 'cranks_no_start', 'cause_hint': 'no_spark_or_fuel'},
                ],
            },
            {
                'key': 'sidestand_check',
                'order': 2,
                'en': 'Is your sidestand fully retracted and the kill switch set to RUN?',
                'tl': 'Nakatiklop ba nang buo ang side stand at naka-RUN ang kill switch?',
                'hil': 'Nakataklob bala sing bug-os ang side stand kag naka-RUN ang kill switch?',
                'options': [
                    {'label': 'A. Yes, stand is up and kill switch is in RUN', 'value': 'switches_ok'},
                    {'label': 'B. Not sure / stand was down', 'value': 'check_switches'},
                ],
            },
        ],
        'guides': [
            {
                'possible_cause': 'Discharged or dead 12V motorcycle battery',
                'confidence_level': 'High',
                'diagnostic_test': 'Measure DC resting voltage across battery terminals using a digital multimeter.',
                'expected_result': 'Healthy resting voltage is 12.6V to 12.8V DC. Voltage under starter cranking load must not drop below 10.0V DC.',
                'alternative_outcome': 'If voltage reads below 12.0V DC resting or plunges below 9.5V during cranking, battery cells are depleted or damaged.',
                'tools_required': 'Digital Multimeter (DC Voltage range), 8mm/10mm box wrench or JIS screwdriver, wire terminal brush.',
                'repair_instructions': (
                    "- [ ] 1. Switch motorcycle ignition OFF and set kill switch to OFF.\n"
                    "- [ ] 2. Access battery compartment (under seat or floorboard panel).\n"
                    "- [ ] 3. Inspect battery terminals for white or greenish sulfate corrosion; disconnect NEGATIVE (-) lead first, then POSITIVE (+).\n"
                    "- [ ] 4. Clean cable lugs and lead posts with wire brush and baking soda solution.\n"
                    "- [ ] 5. Reconnect POSITIVE (+) first, then NEGATIVE (-); tighten firmly and torque terminal bolts to 4–5 Nm.\n"
                    "- [ ] 6. Charge battery with a smart trickle charger at 0.8A–1.2A until fully topped at 12.8V DC.\n"
                    "- [ ] 7. Re-test starter push with headlight ON; verify engine cranks briskly."
                ),
                'advice_notes': 'Never jump-start a 125cc–150cc scooter with a running car engine; car alternators can overpower motorcycle voltage regulators.',
                'when_to_stop': 'If battery will not hold 12.5V after a full 4-hour charge or drops instantly, the internal lead-acid plates have sulfated and battery must be replaced.',
                'source_reference': 'Battery Council International (BCI) Technical Guidelines & Motorcycle Service Manual Section 16 (Electrical)',
                'difficulty_level': 'Beginner',
                'parts': [
                    {'name': '12V Motorcycle Maintenance-Free Battery (YTX5L-BS / YTZ6V)', 'cost': Decimal('1250.00'), 'category': 'Electrical', 'qty': 1},
                ],
            },
            {
                'possible_cause': 'Blown main fuse or disconnected engine ground',
                'confidence_level': 'Medium',
                'diagnostic_test': 'Locate starter relay main fuse holder (typically 15A or 20A green/yellow blade fuse) and test continuity with multimeter.',
                'expected_result': 'Continuous beep on multimeter continuity mode (0.0 to 0.1 ohms). Metal link inside transparent fuse must be intact.',
                'alternative_outcome': 'Broken metal bridge or black smoke burn inside fuse casing indicates blown circuit due to short or backwards jump.',
                'tools_required': 'Fuse puller or needle-nose pliers, replacement 15A/20A mini blade fuse, digital multimeter.',
                'repair_instructions': (
                    "- [ ] 1. Switch ignition OFF and locate fuse box near battery.\n"
                    "- [ ] 2. Pull the 15A/20A MAIN fuse using plastic fuse puller.\n"
                    "- [ ] 3. Hold fuse against light; inspect internal bridge wire.\n"
                    "- [ ] 4. If broken, inspect wiring harness for pinched or rubbed bare wires grounding against frame.\n"
                    "- [ ] 5. Insert new fuse of the EXACT same ampere rating (never bypass with foil or wire).\n"
                    "- [ ] 6. Turn ignition ON; verify gauge cluster sweeps and headlight illuminates."
                ),
                'advice_notes': 'Never substitute a larger fuse (e.g. 30A for 15A); doing so can melt wiring harness and cause vehicle fire.',
                'when_to_stop': 'If replacement fuse blows instantly when ignition turns on, a dead short circuit exists; stop and consult a qualified technician.',
                'source_reference': 'OEM Electrical Troubleshooting Guide & SAE J1284 Blade Type Fuses standard',
                'difficulty_level': 'Beginner',
                'parts': [
                    {'name': 'Mini Blade Automotive Fuse 15A / 20A', 'cost': Decimal('25.00'), 'category': 'Electrical', 'qty': 2},
                ],
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    # 2. MOTORCYCLE & CAR: SPONGY OR FAILING BRAKES (CRITICAL SAFETY)
    # ─────────────────────────────────────────────────────────────────────────
    {
        'symptom_name': 'Spongy brake lever or soft brake pedal (Loss of braking pressure)',
        'category': 'Brake System',
        'vehicle_type': 'all',
        'urgency_level': 'critical_stop',
        'safety_warning': 'CRITICAL SAFETY HAZARD: DO NOT RIDE OR DRIVE. Operating a vehicle with soft or spongy brakes can cause catastrophic collision.',
        'description': 'Brake lever or pedal travels almost to handlebar/floorboard without solid stopping resistance.',
        'questions': [
            {
                'key': 'brake_fluid_level',
                'order': 1,
                'en': 'Check the master cylinder sight glass or fluid reservoir — is fluid above the LOWER/MIN line?',
                'tl': 'Tingnan ang reservoir o sight glass ng preno — lampas ba sa LOWER o MIN line ang fluid?',
                'hil': 'Tuluka ang reservoir ukon sight glass sang preno — lampas bala sa LOWER ukon MIN mark ang fluid?',
                'options': [
                    {'label': 'A. Fluid is visible and above MIN line', 'value': 'fluid_ok', 'cause_hint': 'air_in_lines'},
                    {'label': 'B. Fluid is empty or below MIN line', 'value': 'fluid_low', 'cause_hint': 'hydraulic_leak'},
                    {'label': 'C. Fluid is dark brown / cloudy black', 'value': 'fluid_contaminated', 'cause_hint': 'moisture_contamination'},
                ],
            },
            {
                'key': 'leak_visual',
                'order': 2,
                'en': 'Do you see any wet oily seepage around the caliper bleeder nipple, banjo bolt, or rubber hose?',
                'tl': 'May nakikita ka bang tagas o basa ng langis sa caliper bleeder, hose, o fitting?',
                'hil': 'May nakita ka bala nga basa sang brake fluid sa caliper, hose, ukon fitting?',
                'options': [
                    {'label': 'A. No leaks visible, lines are dry', 'value': 'dry_lines'},
                    {'label': 'B. Yes, wet fluid dripping or weeping', 'value': 'active_leak'},
                ],
            },
        ],
        'guides': [
            {
                'possible_cause': 'Air trapped inside hydraulic brake lines or degraded brake fluid',
                'confidence_level': 'High',
                'diagnostic_test': 'Squeeze/press brake lever 5 times rapidly. If lever firms up temporarily but goes soft after resting 10 seconds, air is trapped.',
                'expected_result': 'Brake lever should become firm within 15–20mm of travel and hold solid pressure for 60 seconds without sinking.',
                'alternative_outcome': 'If lever continues to sink slowly while held under steady pressure, internal master cylinder piston cup seals are bypassing.',
                'tools_required': '8mm or 10mm flare nut/box wrench, 1/4-inch clear vinyl tubing, catch bottle, fresh DOT 4 brake fluid (unopened), lint-free shop towels.',
                'repair_instructions': (
                    "- [ ] 1. Park vehicle on flat level ground; turn handlebars to make master cylinder reservoir level.\n"
                    "- [ ] 2. Wipe reservoir cap clean of dust; remove screws, plastic plate, and rubber diaphragm.\n"
                    "- [ ] 3. Fill reservoir to UPPER line with fresh DOT 4 fluid from an unopened container.\n"
                    "- [ ] 4. Slip 8mm box wrench over caliper bleeder nipple, then firmly attach clear vinyl hose leading into catch bottle.\n"
                    "- [ ] 5. Pump brake lever 3 to 4 times smoothly, then HOLD lever squeezed firmly against grip.\n"
                    "- [ ] 6. Crack bleeder nipple open 1/4 turn for 1 second; watch fluid and air bubbles expel into hose.\n"
                    "- [ ] 7. Tighten bleeder nipple securely BEFORE releasing brake lever grip.\n"
                    "- [ ] 8. Repeat cycle: pump, hold, crack open, close nipple, release lever. Never let reservoir run empty.\n"
                    "- [ ] 9. Continue until only solid, bubble-free amber fluid emerges.\n"
                    "- [ ] 10. Top up to UPPER line, reinstall rubber diaphragm and cover. Torque bleeder nipple to 6–8 Nm."
                ),
                'advice_notes': 'Brake fluid damages painted bodywork instantly. Wash any accidental spill immediately with cold water. Never reuse expelled brake fluid.',
                'when_to_stop': 'If bleeding fails to firm up lever after 10 cycles, master cylinder piston seals or caliper internal seals are damaged and require rebuilding by a certified workshop.',
                'source_reference': 'FMVSS 116 / SAE J1704 Brake Fluids & Factory Workshop Hydraulic Service Manual',
                'difficulty_level': 'Intermediate',
                'parts': [
                    {'name': 'DOT 4 High-Performance Brake Fluid (500ml)', 'cost': Decimal('280.00'), 'category': 'Fluids & Hydraulics', 'qty': 1},
                    {'name': 'Transparent Vinyl Bleeder Tubing 1/4-inch (1 meter)', 'cost': Decimal('60.00'), 'category': 'Tools', 'qty': 1},
                ],
            },
            {
                'possible_cause': 'Worn brake pad friction material past service limit (<2.0mm)',
                'confidence_level': 'High',
                'diagnostic_test': 'Inspect brake caliper window using flashlight to measure remaining pad friction material thickness against steel backing plate.',
                'expected_result': 'Pad friction material thickness must be 3.0mm to 5.0mm. Wear indicator groove should be clearly visible.',
                'alternative_outcome': 'Friction material under 1.5mm–2.0mm or wear groove gone requires immediate pad replacement before steel plate scores rotor.',
                'tools_required': 'Hex/Allen key (5mm/6mm), 12mm/14mm caliper mount socket, brake cleaner spray, C-clamp or piston spreader, 240-grit sandpaper.',
                'repair_instructions': (
                    "- [ ] 1. Support vehicle safely; loosen caliper mounting bolts with socket wrench.\n"
                    "- [ ] 2. Slide caliper assembly carefully off the brake rotor disc.\n"
                    "- [ ] 3. Remove pad retaining pins or clips and extract worn brake pads.\n"
                    "- [ ] 4. Clean caliper piston and slide pins with dedicated residue-free brake cleaner spray.\n"
                    "- [ ] 5. Push caliper pistons gently and squarely back into bore to clear space for thicker new pads.\n"
                    "- [ ] 6. Install fresh sintered or ceramic-metallic brake pads; secure retaining pin and cotter clip.\n"
                    "- [ ] 7. Remount caliper to fork/knuckle; torque mounting bolts to OEM specification (typically 25–30 Nm for bikes, 70–90 Nm for cars).\n"
                    "- [ ] 8. PUMP BRAKE LEVER/PEDAL 5 TIMES BEFORE MOVING to reseat pads against rotor."
                ),
                'advice_notes': 'CRITICAL STEP: After installing new pads, you MUST pump the pedal/lever until firm before riding. Otherwise, first brake application will have zero pressure.',
                'when_to_stop': 'If rotor disc has deep grooving (>0.5mm lip) or is discolored blue from severe heat, rotor must be measured with micrometer and resurfaced or replaced.',
                'source_reference': 'ISO 611 Road Vehicles Braking Systems & OEM Workshop Brake Service Chapter',
                'difficulty_level': 'Beginner',
                'parts': [
                    {'name': 'Front Sintered Disc Brake Pads Set', 'cost': Decimal('450.00'), 'category': 'Brake System', 'qty': 1},
                    {'name': 'Brake System Aerosol Cleaner (450ml)', 'cost': Decimal('180.00'), 'category': 'Chemicals', 'qty': 1},
                ],
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    # 3. MOTORCYCLE & CAR: SEVERE ENGINE OVERHEATING
    # ─────────────────────────────────────────────────────────────────────────
    {
        'symptom_name': 'Engine overheating (High coolant temp light or steam)',
        'category': 'Cooling System',
        'vehicle_type': 'all',
        'urgency_level': 'critical_stop',
        'safety_warning': 'SEVERE SCALD HAZARD: NEVER OPEN A HOT RADIATOR CAP. Boiling pressurized coolant will violently erupt causing severe burns. Allow engine to cool completely for at least 45 minutes.',
        'description': 'Temperature warning lamp illuminated on dashboard, boiling coolant bubbling in expansion reservoir, or steam escaping from engine bay.',
        'questions': [
            {
                'key': 'overheat_situation',
                'order': 1,
                'en': 'When does the temperature light come on — in slow traffic/idle, or at high speed on the highway?',
                'tl': 'Kailan umiilaw ang temp light — pag traffic/idle, o pag mabilis ang takbo sa highway?',
                'hil': 'Kasan-o nagasiga ang temp light — kon traffic/idle, ukon kon madasig ang padalagan?',
                'options': [
                    {'label': 'A. In slow stop-and-go traffic or at idle', 'value': 'idle_traffic', 'cause_hint': 'cooling_fan'},
                    {'label': 'B. At cruising speeds or uphill under load', 'value': 'highway_speed', 'cause_hint': 'thermostat_or_water_pump'},
                    {'label': 'C. Immediately within 3 minutes of cold start', 'value': 'immediate', 'cause_hint': 'head_gasket_or_empty'},
                ],
            },
            {
                'key': 'fan_spinning',
                'order': 2,
                'en': 'When the engine reaches full temperature, does the electric radiator fan spin loudly?',
                'tl': 'Pag mainit na ang makina, umiikot ba nang malakas ang electric fan ng radiator?',
                'hil': 'Kon mainit na ang makina, nagatuyok bala sing mabaskog ang electric radiator fan?',
                'options': [
                    {'label': 'A. Yes, fan turns on and blows hot air', 'value': 'fan_runs'},
                    {'label': 'B. No, fan remains completely silent and still', 'value': 'fan_dead'},
                    {'label': 'C. Vehicle is air-cooled (no radiator fan)', 'value': 'air_cooled'},
                ],
            },
        ],
        'guides': [
            {
                'possible_cause': 'Cooling fan failure or radiator thermo-switch malfunction',
                'confidence_level': 'High',
                'diagnostic_test': 'With engine fully warmed at idle, disconnect fan thermo-switch connector and jump terminals with fused wire. Check if fan motor spins.',
                'expected_result': 'Fan motor should spin vigorously with full RPM and blow air backward through radiator matrix.',
                'alternative_outcome': 'If jumped fan does not spin, check 10A fan fuse in fuse box. If fuse is good, fan motor internal brushes or winding has burned out.',
                'tools_required': 'Jumper test wire, digital multimeter, 10mm socket, fresh 50/50 ethylene glycol pre-mixed coolant.',
                'repair_instructions': (
                    "- [ ] 1. SHUT OFF ENGINE IMMEDIATELY and park in shade. Wait 45–60 minutes until radiator is cold to the touch.\n"
                    "- [ ] 2. Check radiator cooling fins for dirt, mud caking, or bent fins; spray clean gently with water hose from back to front.\n"
                    "- [ ] 3. Inspect coolant expansion tank level; ensure level is between MIN and MAX marks.\n"
                    "- [ ] 4. Once cold, slowly turn radiator cap counter-clockwise to first stop to release residual vapor, then press down and remove.\n"
                    "- [ ] 5. Top up radiator neck with 50/50 pre-diluted motorcycle/automotive aluminum-safe coolant.\n"
                    "- [ ] 6. Inspect fan wiring plug; verify tight electrical connection and absence of melted pins.\n"
                    "- [ ] 7. Start engine with radiator cap off; observe coolant circulation as engine warms to bleed trapped air pockets.\n"
                    "- [ ] 8. Install radiator cap tightly past the safety detent."
                ),
                'advice_notes': 'Never add tap water or mineral drinking water to modern aluminum radiators; minerals cause scale clogging and electrolytic corrosion.',
                'when_to_stop': 'If white sweet-smelling smoke billows continuously from exhaust or oil on dipstick looks like milky coffee, cylinder head gasket has blown; tow to workshop.',
                'source_reference': 'SAE J814 Engine Coolants / ASTM D3306 & Manufacturer Liquid Cooling Service Chapter',
                'difficulty_level': 'Intermediate',
                'parts': [
                    {'name': 'Pre-mixed 50/50 Long Life Coolant (1 Liter)', 'cost': Decimal('260.00'), 'category': 'Fluids & Hydraulics', 'qty': 1},
                    {'name': 'Radiator Thermo Sensor / Switch', 'cost': Decimal('380.00'), 'category': 'Sensors & Electrical', 'qty': 1},
                ],
            },
            {
                'possible_cause': 'Stuck closed coolant thermostat valve',
                'confidence_level': 'Medium',
                'diagnostic_test': 'Feel upper vs lower radiator hoses after engine reaches operating temperature (use heat-resistant glove).',
                'expected_result': 'Both upper and lower radiator hoses should feel uniformly hot (approx 80°C–90°C), confirming thermostat opened.',
                'alternative_outcome': 'If upper engine hose is scalding hot while lower radiator hose remains cold to ambient, thermostat is stuck closed blocking coolant flow.',
                'tools_required': '10mm/12mm socket wrench, catch drain pan, new thermostat with rubber O-ring seal, torque wrench.',
                'repair_instructions': (
                    "- [ ] 1. Allow engine to cool completely (cold to touch).\n"
                    "- [ ] 2. Position drain pan below water pump drain bolt and drain coolant into clean container.\n"
                    "- [ ] 3. Unbolt thermostat housing (usually 2 bolts, 10mm head).\n"
                    "- [ ] 4. Extract old thermostat; note direction of jiggle pin / air bleed hole (points upward).\n"
                    "- [ ] 5. Bench test: place thermostat in pot of water with thermometer; valve must open noticeably at 82°C–88°C.\n"
                    "- [ ] 6. Fit new thermostat with fresh rubber gasket into housing.\n"
                    "- [ ] 7. Tighten housing bolts to 10–12 Nm; refill system with fresh coolant and burp air pockets."
                ),
                'advice_notes': 'Always replace the rubber gasket/O-ring when changing thermostat; reusing old crushed gaskets causes persistent leaks.',
                'when_to_stop': 'If engine continues to overheat after new thermostat and fan are confirmed working, water pump impeller has stripped or radiator core is calcified.',
                'source_reference': 'OEM Cooling System Service Manual & Gates Automotive Thermostat Diagnostic Guide',
                'difficulty_level': 'Intermediate',
                'parts': [
                    {'name': 'Engine Coolant Thermostat with O-Ring Gasket', 'cost': Decimal('420.00'), 'category': 'Cooling System', 'qty': 1},
                ],
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    # 4. CAR & MOTORCYCLE: BATTERY CHARGING & ALTERNATOR/STATOR FAILURE
    # ─────────────────────────────────────────────────────────────────────────
    {
        'symptom_name': 'Battery drains repeatedly / Battery warning light on dash',
        'category': 'Charging System',
        'vehicle_type': 'all',
        'urgency_level': 'warning',
        'safety_warning': 'Remove metal jewelry and wristwatches before testing alternator/stator terminals to avoid accidental dead-short burns.',
        'description': 'Battery loses charge after driving or overnight; dashboard battery icon illuminates while driving; headlights dim at idle.',
        'questions': [
            {
                'key': 'drain_timing',
                'order': 1,
                'en': 'Does the battery die while driving on the road, or overnight while parked with the key off?',
                'tl': 'Namamatay ba ang baterya habang umaandar sa kalsada, o overnight habang nakaparada?',
                'hil': 'Nagakadulaan bala sing karga ang baterya samtang nagadalagan, ukon sa gab-i samtang nakaparada?',
                'options': [
                    {'label': 'A. While driving — engine suddenly dies and lights fade', 'value': 'while_driving', 'cause_hint': 'charging_failure'},
                    {'label': 'B. Overnight or after sitting parked 2–3 days', 'value': 'overnight_drain', 'cause_hint': 'parasitic_draw'},
                ],
            },
            {
                'key': 'aftermarket_accessories',
                'order': 2,
                'en': 'Are there aftermarket accessories installed (alarm, loud horn, mini-driving lights, USB chargers)?',
                'tl': 'May mga ikinabit ka bang aftermarket accessories (alarm, mini driving lights, USB charger)?',
                'hil': 'May mga ginpakabit ka bala nga accessories (alarm, mini driving light, USB charger)?',
                'options': [
                    {'label': 'A. Yes, aftermarket auxiliary lights or alarm installed', 'value': 'has_accessories'},
                    {'label': 'B. No, completely stock factory wiring', 'value': 'stock_wiring'},
                ],
            },
        ],
        'guides': [
            {
                'possible_cause': 'Faulty alternator / motorcycle stator coil or rectifier-regulator',
                'confidence_level': 'High',
                'diagnostic_test': 'Start engine and rev to 3,000–4,000 RPM while measuring DC voltage across battery terminals.',
                'expected_result': 'Voltage must rise to between 13.8V and 14.8V DC with engine running at 3000 RPM.',
                'alternative_outcome': 'If voltage remains at battery resting level (12.2V–12.5V) or drops lower as RPM rises, the charging system is not outputting power.',
                'tools_required': 'Digital Multimeter, socket set, terminal cleaner.',
                'repair_instructions': (
                    "- [ ] 1. Check alternator drive belt tension (on cars) or stator 3-pin yellow AC output plug (on bikes).\n"
                    "- [ ] 2. For motorcycles: unplug 3-pin stator yellow wires; measure AC voltage between all 3 phase pairs (1-2, 2-3, 1-3) at 4000 RPM (expect 40V–60V AC).\n"
                    "- [ ] 3. Check resistance of stator phases to ground with engine off (must read open circuit / infinite resistance; any continuity to ground means burned stator).\n"
                    "- [ ] 4. Inspect rectifier-regulator heatsink and plug for melted plastic or corroded prongs.\n"
                    "- [ ] 5. Clean frame grounding eyelet lug to bare metal and re-torque.\n"
                    "- [ ] 6. Replace defective regulator/rectifier or rewind stator coil.\n"
                    "- [ ] 7. Retest charging voltage across battery at 3,000 RPM (must be 14.0V–14.5V DC)."
                ),
                'advice_notes': 'If charging voltage exceeds 15.2V DC, the regulator has failed open and is boiling the battery acid; discontinue riding immediately.',
                'when_to_stop': 'If stator windings show charred black insulation or copper smell, engine side cover must be removed to replace stator assembly.',
                'source_reference': 'SAE J56 Electrical Generating Systems & OEM Factory Electrical Manual',
                'difficulty_level': 'Intermediate',
                'parts': [
                    {'name': 'Solid-State Rectifier / Voltage Regulator Unit', 'cost': Decimal('680.00'), 'category': 'Electrical', 'qty': 1},
                    {'name': 'Motorcycle Stator Magneto Coil Assembly', 'cost': Decimal('1450.00'), 'category': 'Electrical', 'qty': 1},
                ],
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    # 5. MOTORCYCLE & CAR: FUEL DELIVERY & ENGINE BOGGING / ACCELERATION
    # ─────────────────────────────────────────────────────────────────────────
    {
        'symptom_name': 'Engine hesitates, sputters, or bogs down when twisting throttle / stepping on gas',
        'category': 'Fuel & Air Intake',
        'vehicle_type': 'all',
        'urgency_level': 'warning',
        'safety_warning': 'Work in well-ventilated open air away from open flames, pilot lights, and smoking materials.',
        'description': 'Engine idles smoothly but hesitates, loses power, sputters, or dies whenever throttle is opened for acceleration.',
        'questions': [
            {
                'key': 'fuel_system_type',
                'order': 1,
                'en': 'Is your engine Electronic Fuel Injection (EFI / Fi) or equipped with a traditional Carburetor?',
                'tl': 'Naka-Fuel Injection (EFI / Fi) ba ang makina o Carburetor?',
                'hil': 'Fuel Injection (EFI / Fi) bala ang makina mo ukon Carburetor?',
                'options': [
                    {'label': 'A. Fuel Injected (EFI / Fi / PGM-FI)', 'value': 'efi', 'cause_hint': 'clogged_injector_or_fuel_pump'},
                    {'label': 'B. Carburetor (with choke lever)', 'value': 'carb', 'cause_hint': 'clogged_pilot_main_jet'},
                ],
            },
            {
                'key': 'choke_reaction',
                'order': 2,
                'en': 'If carbureted, does the engine run better when the choke is engaged?',
                'tl': 'Kung de-carburetor, gumaganda ba ang andar pag binuksan ang choke?',
                'hil': 'Kon naka-carburetor, naganami bala ang andar kon ibira ang choke?',
                'options': [
                    {'label': 'A. Yes, runs much better with choke on', 'value': 'better_with_choke', 'cause_hint': 'lean_fuel_condition'},
                    {'label': 'B. No difference / engine is EFI', 'value': 'no_choke_change'},
                ],
            },
        ],
        'guides': [
            {
                'possible_cause': 'Clogged carburetor jets (lean mixture) or dirty fuel injector nozzle',
                'confidence_level': 'High',
                'diagnostic_test': 'For carb: test with choke pulled; running better confirms fuel starvation (lean mixture). For EFI: measure fuel rail pressure with pressure gauge (expect 294 kPa / 43 PSI for Honda PGM-FI).',
                'expected_result': 'Fuel spray must atomize into a micro-fine conical mist. Carburetor pilot and main brass jet orifices must show clear round pinhole of light.',
                'alternative_outcome': 'Irregular dripping spray pattern or obstructed jet pinhole confirms varnish/dirt blockage from stale ethanol blended fuel.',
                'tools_required': 'Carburetor cleaner aerosol spray, JIS screwdrivers (No. 1 & 2), 0.3mm soft copper jet cleaning wire, clean glass bowl.',
                'repair_instructions': (
                    "- [ ] 1. Shut fuel valve petcock OFF; place drain bottle under carb float bowl drain tube.\n"
                    "- [ ] 2. Loosen drain screw; inspect drained fuel for water globules, sediment, or rust particles.\n"
                    "- [ ] 3. Loosen intake manifold clamp screws and remove carburetor body.\n"
                    "- [ ] 4. Remove float bowl; carefully unscrew pilot (slow) jet and main jet using exact-fit flat screwdriver.\n"
                    "- [ ] 5. Spray carburetor cleaner through jet orifices; verify light passes cleanly through center hole and side emulsion holes.\n"
                    "- [ ] 6. Spray clean fuel inlet passageway and float needle valve seat.\n"
                    "- [ ] 7. Inspect rubber intake manifold boot for hairline dry-rot cracks that allow unmetered vacuum leak.\n"
                    "- [ ] 8. Reassemble float bowl with clean O-ring; reinstall carb and adjust fuel mixture pilot screw to factory baseline (typically 1.5 to 2.25 turns out)."
                ),
                'advice_notes': 'Never use hard steel wire or drill bits to poke carburetor brass jets; scratching the precision orifice permanently alters fuel calibration.',
                'when_to_stop': 'On EFI vehicles, if fuel pump does not prime with a 2-second hum when key turns on, test fuel pump relay and pump winding resistance before disassembling throttle body.',
                'source_reference': 'Mikuni/Keihin Carburetor Tuning Manual & Bosch Automotive Gasoline Injection Handbook',
                'difficulty_level': 'Intermediate',
                'parts': [
                    {'name': 'Carburetor / Throttle Body Cleaner Aerosol (500ml)', 'cost': Decimal('190.00'), 'category': 'Chemicals', 'qty': 1},
                    {'name': 'In-line Fuel Filter Transparent Magnet Element', 'cost': Decimal('85.00'), 'category': 'Fuel System', 'qty': 1},
                ],
            },
            {
                'possible_cause': 'Worn CVT drive belt or slipping automatic clutch pads (Scooters / Automatics)',
                'confidence_level': 'Medium',
                'diagnostic_test': 'Hold rear brake firmly on flat surface and apply smooth throttle for 2 seconds. If engine RPM races up high but scooter barely pulls forward, clutch/CVT is slipping.',
                'expected_result': 'CVT drive belt width must be within specification (e.g. Honda Click 125/150: minimum 18.5mm service limit, new 19.5mm).',
                'alternative_outcome': 'Belt width below service limit, worn pulley ramps, or clutch bell glazed with blue burn marks causes severe acceleration slippage.',
                'tools_required': '8mm T-handle, 17mm & 19mm socket, CVT variator locking holder tool or impact wrench, vernier caliper.',
                'repair_instructions': (
                    "- [ ] 1. Remove 8mm bolts securing CVT crankcase cover.\n"
                    "- [ ] 2. Remove drive face and clutch bell using variator holding tool.\n"
                    "- [ ] 3. Measure drive belt width with vernier caliper; inspect belt teeth for fraying, rubber cracks, or missing cogs.\n"
                    "- [ ] 4. Remove variator movable face; inspect roller weights for flat spots (replace if flat-spotted).\n"
                    "- [ ] 5. Inspect clutch bell interior for oil contamination or glaze; scuff lightly with 180-grit sandpaper.\n"
                    "- [ ] 6. Clean all belt dust with brake cleaner spray and lint-free towel.\n"
                    "- [ ] 7. Reassemble variator, new belt, and clutch; torque drive pulley nut to OEM spec (59 Nm) and clutch nut (49 Nm)."
                ),
                'advice_notes': 'Never get grease or oil onto CVT pulleys or belt; grease causes instant uncontrollable drive slippage.',
                'when_to_stop': 'If clutch bell has visible cracks or is warped out of round (>0.2mm), it must be replaced to prevent catastrophic disintegration at high RPM.',
                'source_reference': 'Honda V-Matic Transmission System Service Manual / Yamaha CVT Technician Guide',
                'difficulty_level': 'Intermediate',
                'parts': [
                    {'name': 'Genuine Reinforced CVT Drive Belt', 'cost': Decimal('650.00'), 'category': 'Transmission', 'qty': 1},
                    {'name': 'CVT Variator Roller Weights Set (6 pcs)', 'cost': Decimal('220.00'), 'category': 'Transmission', 'qty': 1},
                ],
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    # 6. MOTORCYCLE & CAR: ENGINE NOISES & METALLIC KNOCKING
    # ─────────────────────────────────────────────────────────────────────────
    {
        'symptom_name': 'Engine noise (Ticking, rattling, or metallic knocking)',
        'category': 'Engine Mechanical',
        'vehicle_type': 'all',
        'urgency_level': 'critical_stop',
        'safety_warning': 'IF NOISE IS A DEEP HEAVY KNOCK FROM CRANKCASE, SHUT OFF ENGINE IMMEDIATELY. Continued running will throw connecting rod through crankcase, destroying the engine and locking wheels.',
        'description': 'Abnormal acoustic sound from engine: light rhythmic ticking at top cylinder head, side-casing chain clatter, or heavy thudding knock under throttle load.',
        'questions': [
            {
                'key': 'noise_location',
                'order': 1,
                'en': 'Where is the noise coming from, and does it change with engine speed?',
                'tl': 'Saan nanggagaling ang ingay — sa itaas ng ulo ng makina, sa gilid, o sa ilalim ng crankcase?',
                'hil': 'Diin nagahalin ang huni — sa ibabaw sang makina, sa kilid, ukon sa dalom sang crankcase?',
                'options': [
                    {'label': 'A. Light ticking from top cylinder head (sounds like typewriter)', 'value': 'top_ticking', 'cause_hint': 'valve_clearance'},
                    {'label': 'B. Rattling/slapping from side cover at idle, quiets at high speed', 'value': 'side_rattle', 'cause_hint': 'cam_chain_tensioner'},
                    {'label': 'C. Heavy deep rhythmic thudding from bottom crankcase that increases with throttle', 'value': 'deep_knock', 'cause_hint': 'rod_bearing_failure'},
                ],
            },
            {
                'key': 'oil_level_check',
                'order': 2,
                'en': 'Check the oil dipstick/sight glass with engine off on level ground — what is the oil level and color?',
                'tl': 'Tingnan ang dipstick o sight glass ng langis — anong level at kulay ng langis ng makina?',
                'hil': 'Tuluka ang dipstick ukon sight glass sang langis — ano ang level kag duag sang langis?',
                'options': [
                    {'label': 'A. Oil is between MIN and MAX, amber/brown', 'value': 'oil_good'},
                    {'label': 'B. Dipstick is completely dry or below MIN mark', 'value': 'oil_dry'},
                    {'label': 'C. Oil is jet black with metallic glitter flakes', 'value': 'oil_metal_glitter'},
                ],
            },
        ],
        'guides': [
            {
                'possible_cause': 'Excessive valve tappet clearance (Loose intake/exhaust valve rocker)',
                'confidence_level': 'High',
                'diagnostic_test': 'Measure gap between valve stem tip and rocker arm screw with precision steel feeler gauge at Top Dead Center (TDC) compression stroke.',
                'expected_result': 'Typical clearance for modern 125–150cc engines: Intake 0.08mm–0.12mm; Exhaust 0.12mm–0.16mm (check exact engine spec).',
                'alternative_outcome': 'Clearance exceeding 0.20mm causes distinct sewing-machine / typewriter rhythmic ticking that doubles in frequency as RPM rises.',
                'tools_required': 'Metric feeler gauge set (0.04mm–0.30mm), 8mm/9mm tappet locknut box wrench, valve adjustment square/slotted tool, 14mm/17mm crankshaft turning socket.',
                'repair_instructions': (
                    "- [ ] 1. Ensure engine is COMPLETELY COLD (below 35°C); measuring hot valves gives dangerously incorrect clearance.\n"
                    "- [ ] 2. Remove valve tappet inspection covers or cylinder head cover.\n"
                    "- [ ] 3. Remove timing inspection plug on alternator cover; rotate crankshaft counter-clockwise until 'T' mark aligns with index notch on compression stroke.\n"
                    "- [ ] 4. Confirm both intake and exhaust rocker arms have slight free wiggle (both valves fully closed).\n"
                    "- [ ] 5. Insert feeler gauge blade between valve stem tip and adjustment screw; feeler should slide with slight drag (like pulling paper from a book).\n"
                    "- [ ] 6. If loose, loosen locknut, turn adjustment screw until correct drag is achieved, then tighten locknut while holding screw steady.\n"
                    "- [ ] 7. Re-check clearance after tightening locknut; rotate crankshaft 720 degrees and re-verify at TDC.\n"
                    "- [ ] 8. Reinstall inspection caps with clean O-rings (torque 12 Nm)."
                ),
                'advice_notes': 'A slightly noisy valve is safer than an overly tight valve. Too-tight valves will burn and destroy cylinder head compression.',
                'when_to_stop': 'If valve adjuster screw is bottomed out and clearance is still excessive, valve stem tip or rocker arm pad is severely worn and requires head disassembly.',
                'source_reference': 'OEM Factory Engine Mechanical Service Chapter & SAE Engine Valvetrain Diagnostic Guide',
                'difficulty_level': 'Intermediate',
                'parts': [
                    {'name': 'Precision Metric Feeler Gauge Blades Set (0.02 - 1.0mm)', 'cost': Decimal('190.00'), 'category': 'Tools', 'qty': 1},
                    {'name': 'Tappet Inspection Cap Rubber O-Ring Set', 'cost': Decimal('45.00'), 'category': 'Engine Seals', 'qty': 2},
                ],
            },
            {
                'possible_cause': 'Worn or collapsed Cam Chain Tensioner (CCT) / Loose timing chain',
                'confidence_level': 'High',
                'diagnostic_test': 'Listen to side cylinder casting with a mechanic stethoscope or long screwdriver pressed against ear; observe if clatter quiets under light RPM load.',
                'expected_result': 'Automatic cam chain tensioner plunger should ratchet outward and hold firm spring pressure against cam chain guide.',
                'alternative_outcome': 'If tensioner internal spring has snapped, plunger retracts under chain slap, causing rapid clattering noise against cylinder tunnel.',
                'tools_required': '8mm socket wrench, small flat screwdriver, fresh tensioner gasket, replacement OEM automatic tensioner.',
                'repair_instructions': (
                    "- [ ] 1. Clean dirt around tensioner body on rear/side of cylinder block.\n"
                    "- [ ] 2. Remove center cap bolt on tensioner; insert small flat screwdriver into internal tensioner screw.\n"
                    "- [ ] 3. Turn clockwise to retract plunger; if tensioner spring has zero counter-force, spring is broken.\n"
                    "- [ ] 4. Remove two 8mm mounting bolts and extract tensioner body.\n"
                    "- [ ] 5. Prepare new tensioner: retract plunger fully clockwise until locked.\n"
                    "- [ ] 6. Install new tensioner with fresh gasket onto cylinder block; tighten mounting bolts to 10 Nm.\n"
                    "- [ ] 7. Release internal screw (turn counter-clockwise) so plunger firmly snaps against timing chain guide.\n"
                    "- [ ] 8. Reinstall center sealing cap and start engine; verify clatter has completely disappeared."
                ),
                'advice_notes': 'Never operate engine with a loose cam chain; loose chain can skip timing teeth, causing piston to smash into open valves, destroying the engine.',
                'when_to_stop': 'If chain continues to rattle after installing new tensioner, the timing chain itself has stretched beyond wear limits and must be replaced along with sprockets.',
                'source_reference': 'OEM Valvetrain Timing & Cam Chain Service Chapter',
                'difficulty_level': 'Intermediate',
                'parts': [
                    {'name': 'Automatic Cam Chain Tensioner Assembly (Lifter)', 'cost': Decimal('450.00'), 'category': 'Engine Mechanical', 'qty': 1},
                    {'name': 'Cam Chain Tensioner Gasket', 'cost': Decimal('35.00'), 'category': 'Engine Seals', 'qty': 1},
                ],
            },
            {
                'possible_cause': 'Connecting rod big-end bearing failure (Rod Knock / Crankshaft bearing damage)',
                'confidence_level': 'High',
                'diagnostic_test': 'SHUT OFF ENGINE IMMEDIATELY. Inspect oil dipstick or drain plug magnet for brass/bronze/aluminum glitter flakes.',
                'expected_result': 'Clean engine oil without glitter, smooth quiet bottom-end rotation with zero play on connecting rod journal.',
                'alternative_outcome': 'Bronze or silver metal flakes in oil combined with dull heavy mechanical knock indicates ruined rod bearing journals.',
                'tools_required': 'Drain pan, 12mm/17mm socket, flashlight, magnet wand.',
                'repair_instructions': (
                    "- [ ] 1. DO NOT START OR RIDE THE VEHICLE. Continued operation will seize the crankshaft and fracture engine crankcase.\n"
                    "- [ ] 2. Drain 100ml of engine oil into a clean white paper cup.\n"
                    "- [ ] 3. Shine a flashlight onto oil surface; examine for metallic glitter, bronze particles, or aluminum sludge.\n"
                    "- [ ] 4. Run a clean neodymium magnet through drained oil to check for ferrous steel shavings.\n"
                    "- [ ] 5. If glitter is present, rod bearing shells or crankpin needle bearings have disintegrated.\n"
                    "- [ ] 6. Secure vehicle for transport to a qualified engine rebuilding workshop for full crankshaft overhaul."
                ),
                'advice_notes': 'There is NO chemical additive, thicker oil, or external adjustment that can fix rod bearing knock. Full engine teardown is required.',
                'when_to_stop': 'STOP IMMEDIATELY. Attempting to ride will result in thrown rod and catastrophic total loss.',
                'source_reference': 'SAE Technical Paper Series: Crankshaft Journal Bearing Wear & OEM Heavy Engine Overhaul Manual',
                'difficulty_level': 'Advanced',
                'parts': [
                    {'name': 'Connecting Rod & Crankpin Overhaul Assembly Set', 'cost': Decimal('2200.00'), 'category': 'Engine Mechanical', 'qty': 1},
                    {'name': 'Complete Engine Overhaul Gasket Kit', 'cost': Decimal('750.00'), 'category': 'Engine Seals', 'qty': 1},
                ],
            },
        ],
    },
]


def seed_default_knowledge():
    """
    Populates all verified diagnostic knowledge into database idempotently.
    Preserves all existing user records.
    """
    created_symptoms = 0
    created_guides = 0
    created_questions = 0

    for seed in VERIFIED_KNOWLEDGE_SEEDS:
        symptom, _ = DiagnosticSymptom.objects.get_or_create(
            symptom_name=seed['symptom_name'],
            defaults={
                'category': seed['category'],
                'vehicle_type': seed.get('vehicle_type', 'all'),
                'urgency_level': seed.get('urgency_level', 'routine'),
                'safety_warning': seed.get('safety_warning', ''),
                'description': seed.get('description', ''),
            }
        )
        created_symptoms += 1

        for q_data in seed.get('questions', []):
            DiagnosticQuestion.objects.update_or_create(
                symptom=symptom,
                question_key=q_data['key'],
                defaults={
                    'question_text': q_data['en'],
                    'question_text_tl': q_data.get('tl', ''),
                    'question_text_hil': q_data.get('hil', ''),
                    'options_json': json.dumps(q_data.get('options', [])),
                    'order': q_data.get('order', 1),
                }
            )
            created_questions += 1

        for g_data in seed.get('guides', []):
            guide, _ = TroubleshootingGuide.objects.get_or_create(
                symptom=symptom,
                possible_cause=g_data['possible_cause'],
                defaults={
                    'confidence_level': g_data.get('confidence_level', 'Medium'),
                    'diagnostic_test': g_data.get('diagnostic_test', ''),
                    'expected_result': g_data.get('expected_result', ''),
                    'alternative_outcome': g_data.get('alternative_outcome', ''),
                    'tools_required': g_data.get('tools_required', ''),
                    'repair_instructions': g_data.get('repair_instructions', ''),
                    'advice_notes': g_data.get('advice_notes', ''),
                    'when_to_stop': g_data.get('when_to_stop', ''),
                    'source_reference': g_data.get('source_reference', ''),
                    'is_verified': g_data.get('is_verified', True),
                    'difficulty_level': g_data.get('difficulty_level', 'Beginner'),
                }
            )
            created_guides += 1

            for p_data in g_data.get('parts', []):
                part, _ = Part.objects.get_or_create(
                    part_name=p_data['name'],
                    defaults={
                        'estimated_cost': p_data['cost'],
                        'category': p_data.get('category', 'General'),
                    }
                )
                GuideRequiredPart.objects.get_or_create(
                    guide=guide,
                    part=part,
                    defaults={'quantity_needed': p_data.get('qty', 1)}
                )

    return {
        'symptoms': created_symptoms,
        'guides': created_guides,
        'questions': created_questions,
    }


def retrieve_verified_knowledge(query, vehicle_type='all', max_results=3):
    """
    Retrieves strictly verified repair knowledge relevant to the user query and vehicle type.
    Never returns unverified user entries.
    """
    clean_q = query.lower()

    # Strip known vehicle models that might collide with mechanical terms (e.g. "Honda Click")
    stripped_q = re.sub(r'\b(?:honda\s+)?click\s+(?:125i?|150i?|160)?\b', '', clean_q, flags=re.I)

    # Keyword synonyms mapping to categories / symptom intents
    intent_keywords = {
        'brake': [r'\bbrake\b', r'\bbrakes\b', r'\bpreno\b', r'\bspongy\b', r'\bsoft\b', r'\bmalambot\b', r'\bhumok\b', r'\bcaliper\b', r'\brotor\b', r'\bdisc\b', r'\bbrake pad\b', r'\bbrake fluid\b'],
        'start': [r'\bstart\b', r'\bcrank\b', r'\bandar\b', r'\bclicking\b', r'\bclicks\b', r'\bsolenoid\b', r'\bbattery\b', r'\bbaterya\b', r'\bdead starter\b', r'\bwon\'t start\b', r'\bayaw mag-start\b'],
        'overheat': [r'\boverheat\b', r'\boverheating\b', r'\binit\b', r'\btemperature\b', r'\bradiator\b', r'\bcoolant\b', r'\bsingaw\b', r'\bsteam\b', r'\bradiator fan\b', r'\bkumukulo\b', r'\bnagabukal\b'],
        'electrical': [r'\bcharging\b', r'\balternator\b', r'\bstator\b', r'\bbattery drain\b', r'\bblown fuse\b', r'\bregulator\b', r'\brectifier\b'],
        'fuel': [r'\bfuel\b', r'\bgas\b', r'\bgasolina\b', r'\bcarb\b', r'\bcarburetor\b', r'\binjector\b', r'\bsputter\b', r'\bbog\b', r'\bhesitate\b', r'\bchoke\b', r'\bcvt\b', r'\bbelt\b', r'\bclutch\b'],
        'noise': [r'\bnoise\b', r'\btunog\b', r'\bhuni\b', r'\btick\b', r'\bticking\b', r'\bknock\b', r'\bknocking\b', r'\bclatter\b', r'\brattle\b', r'\bpiti-piti\b', r'\blagitik\b'],
    }

    category_scores = {}
    for category_key, patterns in intent_keywords.items():
        score = 0
        for pat in patterns:
            if re.search(pat, stripped_q):
                score += 1
        if score > 0:
            category_scores[category_key] = score

    # Sort categories by hit score descending
    sorted_categories = sorted(category_scores.keys(), key=lambda k: category_scores[k], reverse=True)

    symptom_filter = Q()
    if sorted_categories:
        top_cat = sorted_categories[0]
        symptom_filter = Q(symptom_name__icontains=top_cat) | Q(category__icontains=top_cat) | Q(description__icontains=top_cat)
    else:
        # Fallback to direct word match
        words = [w for w in re.findall(r'\b\w{4,}\b', stripped_q) if w not in {'motor', 'motorcycle', 'engine', 'vehicle', 'problem'}]
        for word in words:
            symptom_filter |= Q(symptom_name__icontains=word) | Q(description__icontains=word)

    v_filter = Q(vehicle_type='all')
    if vehicle_type in ('motorcycle', 'car'):
        v_filter |= Q(vehicle_type=vehicle_type)

    symptoms = DiagnosticSymptom.objects.filter(symptom_filter & v_filter).prefetch_related(
        'troubleshooting_guides__required_parts__part',
        'diagnostic_questions'
    ).distinct()[:max_results]

    if not symptoms.exists() and sorted_categories:
        # Relax vehicle type filter if specific match was not found
        symptoms = DiagnosticSymptom.objects.filter(symptom_filter).prefetch_related(
            'troubleshooting_guides__required_parts__part',
            'diagnostic_questions'
        ).distinct()[:max_results]

    results = []
    for s in symptoms:
        verified_guides = [g for g in s.troubleshooting_guides.all() if g.is_verified]
        if not verified_guides:
            continue
        results.append({
            'symptom_id': s.id,
            'symptom_name': s.symptom_name,
            'category': s.category,
            'vehicle_type': s.vehicle_type,
            'urgency_level': s.urgency_level,
            'safety_warning': s.safety_warning,
            'questions': [
                {
                    'key': q.question_key,
                    'text': q.question_text,
                    'text_tl': q.question_text_tl,
                    'text_hil': q.question_text_hil,
                    'options': json.loads(q.options_json or '[]'),
                }
                for q in s.diagnostic_questions.all()
            ],
            'guides': [
                {
                    'possible_cause': g.possible_cause,
                    'confidence_level': g.confidence_level,
                    'diagnostic_test': g.diagnostic_test,
                    'expected_result': g.expected_result,
                    'alternative_outcome': g.alternative_outcome,
                    'tools_required': g.tools_required,
                    'repair_instructions': g.repair_instructions,
                    'advice_notes': g.advice_notes,
                    'when_to_stop': g.when_to_stop,
                    'source_reference': g.source_reference,
                    'difficulty_level': g.difficulty_level,
                    'required_parts': [
                        f"{rp.part.part_name} (est. ${rp.part.estimated_cost})"
                        for rp in g.required_parts.all()
                    ],
                }
                for g in verified_guides
            ],
        })

    return results
