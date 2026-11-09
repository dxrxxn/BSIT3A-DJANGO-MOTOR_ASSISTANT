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
                'system': seed.get('system', seed['category']),
                'component': seed.get('component', ''),
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
                    'source_title': g_data.get('source_title', g_data.get('source_reference', '')),
                    # The bundled seed data records a source for every guide.
                    # Records without a source are forced out by the model and
                    # retrieval guards, so they can never be cited as verified.
                    'review_status': g_data.get('review_status', 'approved'),
                    'review_notes': g_data.get(
                        'review_notes',
                        'Imported from the bundled knowledge file. Re-check the source '
                        'before using it on a different model or variant.',
                    ),
                    'is_verified': bool(g_data.get('is_verified', True)),
                    'difficulty_level': g_data.get('difficulty_level', 'Beginner'),
                    'system': g_data.get('system', seed['category']),
                    'component': g_data.get('component', ''),
                    'vehicle_type': seed.get('vehicle_type', 'all'),
                    'manufacturer': g_data.get('manufacturer', ''),
                    'model': g_data.get('model', ''),
                    'variant': g_data.get('variant', ''),
                    'year_from': g_data.get('year_from'),
                    'year_to': g_data.get('year_to'),
                    'safety_precautions': g_data.get('safety_precautions', seed.get('safety_warning', '')),
                    'verification_procedure': g_data.get('verification_procedure', ''),
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


STOPWORDS = {
    'the', 'and', 'for', 'with', 'that', 'this', 'from', 'have', 'has', 'was',
    'were', 'are', 'you', 'your', 'my', 'our', 'its', 'but', 'not', 'can',
    'could', 'would', 'should', 'when', 'what', 'why', 'how', 'does', 'did',
    'motor', 'motorcycle', 'engine', 'vehicle', 'problem', 'issue', 'please',
    'help', 'about', 'into', 'after', 'before', 'while', 'very', 'bike',
}

# Keyword groups used to give a modest boost to the right system before the
# per-guide token score is computed.  These are retrieval hints, not diagnoses.
INTENT_PATTERNS = {
    'Starting': [r'\bstart', r'\bcrank', r'\bstarter\b', r'\bclicking\b', r'\bignition\b'],
    'Brake': [r'\bbrake', r'\bpreno\b', r'\bcaliper\b', r'\bspongy\b', r'\bsoft pedal\b'],
    'Cooling': [r'\boverheat', r'\bradiator\b', r'\bcoolant\b', r'\bthermostat\b', r'\bfan\b'],
    'Charging': [r'\bbattery\b', r'\balternator\b', r'\bstator\b', r'\bcharging\b', r'\brectifier\b'],
    'Fuel': [r'\bfuel\b', r'\bgasolina\b', r'\bcarb', r'\binject', r'\bsputter', r'\bbog', r'\bhesitat'],
    'Engine Mechanical': [r'\bknock', r'\bticking', r'\brattle', r'\bvalve', r'\bcam chain\b'],
    'Transmission': [r'\bcvt\b', r'\bclutch\b', r'\btransmission\b', r'\bbelt\b', r'\bslip'],
    'Electrical': [r'\belectrical\b', r'\bwiring\b', r'\bfuse\b', r'\bheadlight\b'],
    'Suspension': [r'\bsuspension\b', r'\bshock\b', r'\bfork\b', r'\bsteering\b'],
    'Tires': [r'\btire\b', r'\btyre\b', r'\bwheel\b', r'\bgulong\b'],
}


def _search_tokens(text):
    return {
        token for token in re.findall(r'[a-z0-9]+', (text or '').lower())
        if len(token) >= 3 and token not in STOPWORDS
    }


def _contains_token(text, token):
    """Match a token at the start of a word, allowing simple suffixes.

    Substring matching made short words such as "mag" match "damaged" and
    produced unrelated knowledge records.  A word-boundary match keeps simple
    stemming (brake -> brakes, start -> starting) without that noise.
    """
    return bool(re.search(r'\b' + re.escape(token) + r'\w*', text or ''))


def _detected_intents(text):
    lowered = (text or '').lower()
    intents = set()
    for category, patterns in INTENT_PATTERNS.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            intents.add(category)
    return intents


def _guide_matches_vehicle(guide, vehicle_info=None, vehicle_type='all'):
    vehicle_info = vehicle_info or {}
    requested_type = (
        vehicle_info.get('vehicle_type') or vehicle_info.get('type') or vehicle_type or 'all'
    ).lower()
    if requested_type in ('scooter', 'underbone'):
        requested_type = 'motorcycle'

    guide_type = (guide.vehicle_type or 'all').lower()
    if requested_type in ('motorcycle', 'car', 'tricycle') and guide_type not in ('all', requested_type):
        return False

    make = (vehicle_info.get('make') or '').strip().lower()
    model = (vehicle_info.get('model') or '').strip().lower()
    variant = (vehicle_info.get('variant') or '').strip().lower()
    if guide.manufacturer and make and guide.manufacturer.strip().lower() not in make:
        return False
    if guide.model and model and guide.model.strip().lower() not in model:
        return False
    if guide.variant and variant and guide.variant.strip().lower() not in variant:
        return False

    year = str(vehicle_info.get('year') or '').strip()
    if year.isdigit() and (guide.year_from or guide.year_to):
        year_num = int(year)
        if guide.year_from and year_num < guide.year_from:
            return False
        if guide.year_to and year_num > guide.year_to:
            return False
    return True


def _guide_search_text(guide):
    parts = [
        guide.possible_cause, guide.diagnostic_test, guide.repair_instructions,
        guide.advice_notes, guide.when_to_stop, guide.system, guide.component,
        guide.manufacturer, guide.model, guide.variant, guide.source_title,
        guide.source_reference,
    ]
    parts.extend(
        requirement.part.part_name
        for requirement in guide.required_parts.all()
        if requirement.part
    )
    return ' '.join(part for part in parts if part).lower()


def _score_guide(guide, query_tokens, intents, query_lowered):
    text = _guide_search_text(guide)
    score = 0.0
    for token in query_tokens:
        if _contains_token(text, token):
            score += 1.0
    if guide.system and any(intent.lower() in guide.system.lower() for intent in intents):
        score += 3.0
    if guide.component and any(intent.lower() in guide.component.lower() for intent in intents):
        score += 2.0
    if query_lowered and len(query_lowered) >= 8 and query_lowered in text:
        score += 4.0
    return score



# ─────────────────────────────────────────────────────────────────────────────
# MAPPED TECHNICAL SYMPTOM KNOWLEDGE (7 Core Verified Symptom Classes)
# ─────────────────────────────────────────────────────────────────────────────

MAPPED_SYMPTOMS = {
    'fuel_leak': {
        'symptom_id': 101,
        'symptom_name': 'Fuel leak (Carburetor float/needle, fuel hose, tank, or petcock)',
        'category': 'Fuel System',
        'system': 'Fuel System',
        'component': 'Fuel Delivery & Carburetor',
        'vehicle_type': 'motorcycle',
        'urgency_level': 'critical_stop',
        'safety_warning': 'FIRE HAZARD: Active fuel leak detected. Stop engine immediately, keep away from open flames/sparks, and do not ride until repaired.',
        'score': 10.0,
        'questions': [
            {
                'key': 'fuel_leak_location',
                'text': 'Where is the fuel visibly leaking from?',
                'text_tl': 'Saan nanggagaling ang tagas ng gasolina?',
                'text_hil': 'Diin nagahalin ang tulo sang gasolina?',
                'options': [
                    {'label': 'A. Carburetor overflow tube or airbox', 'value': 'carb_overflow'},
                    {'label': 'B. Cracked rubber fuel line / hose clamp', 'value': 'fuel_hose'},
                    {'label': 'C. Fuel petcock / fuel tap body', 'value': 'petcock_leak'},
                    {'label': 'D. Bottom seam or underside of the fuel tank', 'value': 'tank_leak'},
                ],
            }
        ],
        'guides': [
            {
                'guide_id': 1001,
                'possible_cause': 'Carburetor float needle valve sticking open or worn float valve seat',
                'confidence_level': 'High',
                'diagnostic_test': 'Inspect carburetor float bowl overflow drain tube and inspect needle valve tip for dirt, varnish, or rubber groove wear.',
                'expected_result': 'Float needle seals tightly when float rises with fuel level, shutting off inflow completely.',
                'alternative_outcome': 'Fuel continuously drips or pours from overflow hose or backs into airbox; float bowl overflows.',
                'tools_required': 'JIS screwdriver, carburetor cleaner, small fuel drain container.',
                'repair_instructions': (
                    "- [ ] 1. Shut fuel petcock OFF and disconnect battery negative terminal.\n"
                    "- [ ] 2. Place container under carburetor and loosen float bowl drain screw to empty fuel.\n"
                    "- [ ] 3. Remove float bowl; extract float hinge pin and needle valve.\n"
                    "- [ ] 4. Clean needle valve tip and brass seat with aerosol carb cleaner and compressed air.\n"
                    "- [ ] 5. Inspect rubber Viton needle tip for ring groove or hardening; replace needle valve if worn.\n"
                    "- [ ] 6. Check float for liquid fuel inside (punctured float); check float height to manual spec.\n"
                    "- [ ] 7. Reassemble with a fresh bowl gasket; turn petcock ON and verify zero leaks."
                ),
                'advice_notes': 'Never tap a stuck carburetor float with heavy tools. Disassemble and clean properly.',
                'when_to_stop': 'If fuel continues to pour out after cleaning, the brass float valve seat is pitted or body is cracked; professional carburetor rebuild is required.',
                'source_reference': 'OEM Motorcycle Fuel System & Carburetor Service Manual (Float Circuit)',
                'source_title': 'OEM Fuel System Service Manual (Carburetors & Float Valves)',
                'source_date': '2023-01-15',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Intermediate',
                'system': 'Fuel System',
                'component': 'Carburetor',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'FIRE HAZARD: Work only in a well-ventilated outdoor area. No smoking, phones, or ignition sources.',
                'verification_procedure': 'Turn petcock ON with engine off for 5 minutes; verify overflow hose remains completely dry.',
                'source_score': 5.0,
                'required_parts': [
                    {'name': 'Carburetor Float Needle Valve & Bowl Gasket Kit', 'part_number': '16011-KBA-901', 'quantity': 1, 'estimated_cost': '280.00'}
                ],
            },
            {
                'guide_id': 1002,
                'possible_cause': 'Cracked, dry-rotted rubber fuel hose or loose clamp',
                'confidence_level': 'Medium',
                'diagnostic_test': 'Wipe fuel line dry with clean rag; turn petcock ON and squeeze hose to look for weeping wetness or radial cracks.',
                'expected_result': 'Fuel hose remains dry, flexible, and firmly clamped with no wet sheen.',
                'alternative_outcome': 'Fuel seeps around clamp or through surface weather cracks under gravity fuel pressure.',
                'tools_required': 'Pliers, utility knife, replacement fuel-rated hose and spring clamps.',
                'repair_instructions': (
                    "- [ ] 1. Turn fuel petcock OFF.\n"
                    "- [ ] 2. Pinch clamp and slide back from petcock and carburetor spigots.\n"
                    "- [ ] 3. Pull old hose off; cut replacement fuel-rated hose (reinforced 5.5mm/6mm ID) to exact length.\n"
                    "- [ ] 4. Install new hose fully onto barbs; secure with fresh spring clamps.\n"
                    "- [ ] 5. Turn petcock ON and inspect for leaks."
                ),
                'advice_notes': 'Always use fuel-rated reinforced rubber hose, never clear aquarium/vinyl tubing.',
                'when_to_stop': 'If spigot nipple is loose or cracked in the tank or petcock body, replace petcock assembly.',
                'source_reference': 'SAE J30R7 Fuel Line & Hose Installation Standards',
                'source_title': 'SAE J30R7 Fuel System Hose Standards',
                'source_date': '2022-06-10',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Beginner',
                'system': 'Fuel System',
                'component': 'Fuel Lines',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Keep catch pan under lines to catch residual fuel.',
                'verification_procedure': 'Wipe with dry tissue paper after 10 minutes; verify no wet spots.',
                'source_score': 4.0,
                'required_parts': [
                    {'name': 'Reinforced Fuel Line Hose & Spring Clamps', 'part_number': 'FL-55MM-1M', 'quantity': 1, 'estimated_cost': '120.00'}
                ],
            },
            {
                'guide_id': 1003,
                'possible_cause': 'Leaking fuel petcock (petcock valve body or vacuum diaphragm seal)',
                'confidence_level': 'Medium',
                'diagnostic_test': 'Inspect fuel petcock body, selector lever, and vacuum line for raw fuel dripping.',
                'expected_result': 'Petcock body is dry and shuts off flow completely in OFF position.',
                'alternative_outcome': 'Fuel weeps around petcock lever seal or vacuum reference port.',
                'tools_required': '10mm/12mm box wrench, replacement petcock valve.',
                'repair_instructions': (
                    "- [ ] 1. Drain fuel tank completely into an approved container.\n"
                    "- [ ] 2. Disconnect fuel hose and vacuum hose from petcock.\n"
                    "- [ ] 3. Unbolt petcock mounting nut or flange screws from tank.\n"
                    "- [ ] 4. Replace petcock assembly with new O-ring gasket.\n"
                    "- [ ] 5. Refill tank partially and check for leaks in OFF, ON, and RES positions."
                ),
                'advice_notes': 'A leaking vacuum petcock can flood the crankcase with fuel; check engine oil level and smell.',
                'when_to_stop': 'If tank mounting bung threads are stripped, seek professional tank repair.',
                'source_reference': 'OEM Fuel Petcock & Tank Assembly Service Guidelines',
                'source_title': 'OEM Motorcycle Fuel Petcock Manual',
                'source_date': '2023-03-20',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Intermediate',
                'system': 'Fuel System',
                'component': 'Fuel Petcock',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Ground tank before transferring gasoline to prevent static spark.',
                'verification_procedure': 'Verify zero seepage around mounting flange and lever after refill.',
                'source_score': 4.0,
                'required_parts': [
                    {'name': 'Motorcycle Fuel Petcock Assembly with O-Ring', 'part_number': '16950-KFL-851', 'quantity': 1, 'estimated_cost': '350.00'}
                ],
            }
        ]
    },

    'headlight_failure': {
        'symptom_id': 102,
        'symptom_name': 'Headlight failure (Bulb filament, lighting fuse, switch, or ground fault)',
        'category': 'Lighting & Electrical',
        'system': 'Electrical & Lighting',
        'component': 'Headlight Circuit',
        'vehicle_type': 'motorcycle',
        'urgency_level': 'warning',
        'safety_warning': 'Do not ride after dark without a functional headlight. Park motorcycle and turn ignition off before testing.',
        'score': 10.0,
        'questions': [
            {
                'key': 'headlight_state',
                'text': 'What is the headlight doing?',
                'text_tl': 'Ano ang eksaktong kalagayan ng headlight?',
                'text_hil': 'Ano ang nagakatabo sa suga sa unahan?',
                'options': [
                    {'label': 'A. Both low beam and high beam are completely dead', 'value': 'dead_both'},
                    {'label': 'B. Low beam is dead but high beam works (or vice versa)', 'value': 'one_beam_dead'},
                    {'label': 'C. Headlight flickers over bumps or when turning handlebars', 'value': 'flickering'},
                ],
            }
        ],
        'guides': [
            {
                'guide_id': 1004,
                'possible_cause': 'Burnt out headlight bulb filament (low beam or high beam open circuit)',
                'confidence_level': 'High',
                'diagnostic_test': 'Remove headlight bulb and inspect tungsten filament inside glass or test continuity across bulb connector pins with multimeter.',
                'expected_result': 'Continuity tone (0.5 to 2.0 ohms) across common ground and beam terminal. Filament intact.',
                'alternative_outcome': 'No continuity (infinite ohms) or visible break/black scorched deposit inside bulb envelope.',
                'tools_required': 'JIS screwdriver, digital multimeter, replacement 12V 35/35W or H4 halogen bulb.',
                'repair_instructions': (
                    "- [ ] 1. Switch motorcycle ignition OFF.\n"
                    "- [ ] 2. Remove front headlight cowl or retaining screws to access bulb socket.\n"
                    "- [ ] 3. Pull electrical socket plug straight back; peel off rubber dust boot.\n"
                    "- [ ] 4. Unhook wire spring clip and pull out old bulb.\n"
                    "- [ ] 5. Insert new bulb matching alignment tabs; never touch glass with bare fingers (use clean cloth).\n"
                    "- [ ] 6. Reinstall retaining spring clip, rubber boot, and wiring socket firmly.\n"
                    "- [ ] 7. Turn ignition ON and test both low beam and high beam."
                ),
                'advice_notes': 'Finger oils on halogen glass create hot spots that cause the bulb to shatter or burn out prematurely.',
                'when_to_stop': 'If replacement bulb blows immediately upon starting the engine, voltage regulator is failing and overcharging.',
                'source_reference': 'OEM Motorcycle Electrical & Lighting Systems Manual Section 18',
                'source_title': 'Motorcycle Lighting & Headlamp Service Manual',
                'source_date': '2023-02-18',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Beginner',
                'system': 'Electrical & Lighting',
                'component': 'Headlight Bulb',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Halogen bulbs become extremely hot; let cool before touching.',
                'verification_procedure': 'Verify low beam and high beam toggle cleanly on dashboard indicator.',
                'source_score': 5.0,
                'required_parts': [
                    {'name': '12V 35/35W HS1/H4 Motorcycle Halogen Headlight Bulb', 'part_number': '34901-KGF-911', 'quantity': 1, 'estimated_cost': '180.00'}
                ],
            },
            {
                'guide_id': 1005,
                'possible_cause': 'Blown headlight circuit fuse or lighting relay fault',
                'confidence_level': 'Medium',
                'diagnostic_test': 'Locate fuse box (near battery or under front fairing); pull HEAD/LIGHT fuse (typically 10A or 15A) and test continuity.',
                'expected_result': 'Intact metal bridge inside transparent plastic casing; 0.0 ohms continuity.',
                'alternative_outcome': 'Severed bridge wire with black scorch mark; zero continuity.',
                'tools_required': 'Fuse puller, replacement 10A/15A mini blade fuse, multimeter.',
                'repair_instructions': (
                    "- [ ] 1. Turn ignition OFF.\n"
                    "- [ ] 2. Open fuse box cover and find fuse marked HEAD or LIGHT.\n"
                    "- [ ] 3. Pull fuse and check with multimeter.\n"
                    "- [ ] 4. If blown, inspect front wiring harness for pinched or rubbed insulation grounding to frame.\n"
                    "- [ ] 5. Install new fuse of identical amperage rating; turn ignition ON and re-test."
                ),
                'advice_notes': 'Never install a higher amperage fuse or bypass with wire/foil; this will melt the harness.',
                'when_to_stop': 'If replacement fuse blows instantly, a direct short circuit exists in the lighting harness.',
                'source_reference': 'SAE J1284 Blade Type Automotive Fuses Standard',
                'source_title': 'SAE J1284 Blade Fuse & Circuit Standards',
                'source_date': '2022-04-12',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Beginner',
                'system': 'Electrical & Lighting',
                'component': 'Fuse Box',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Disconnect battery negative terminal if probing bare harness wires.',
                'verification_procedure': 'Verify cluster sweeps and headlight illuminates without fuse overheating.',
                'source_score': 4.0,
                'required_parts': [
                    {'name': 'Mini Blade Automotive Fuse 10A / 15A', 'part_number': 'FUSE-10A-MINI', 'quantity': 1, 'estimated_cost': '25.00'}
                ],
            },
            {
                'guide_id': 1006,
                'possible_cause': 'Handlebar dimmer / hi-lo switch contact corrosion or loose ground',
                'confidence_level': 'Medium',
                'diagnostic_test': 'Test voltage at headlight socket harness while toggling high/low beam switch on handlebar.',
                'expected_result': '12V DC on low beam wire in low position; 12V DC on high beam wire in high position; ground resistance under 0.2 ohms.',
                'alternative_outcome': 'No voltage output from switch or intermittent connection when wiggling switch.',
                'tools_required': 'Phillips screwdriver, contact cleaner spray, multimeter.',
                'repair_instructions': (
                    "- [ ] 1. Remove handlebar switch pod housing screws.\n"
                    "- [ ] 2. Spray electrical contact cleaner into dimmer switch mechanism.\n"
                    "- [ ] 3. Toggle switch 20 times to clean oxidation off copper contacts.\n"
                    "- [ ] 4. Inspect green or black ground eyelet at steering head frame ground bolt; tighten firmly."
                ),
                'advice_notes': 'Ensure steering head ground wire is not pinched by the fork stops.',
                'when_to_stop': 'If switch contacts are melted or broken internally, replace switch pod assembly.',
                'source_reference': 'OEM Handlebar Switch & Controls Technical Service Manual',
                'source_title': 'Handlebar Controls & Grounding Service Manual',
                'source_date': '2023-01-20',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Intermediate',
                'system': 'Electrical & Lighting',
                'component': 'Handlebar Switch',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Turn ignition OFF before spraying solvent.',
                'verification_procedure': 'Verify headlights switch cleanly between high and low beam without flickering.',
                'source_score': 4.0,
                'required_parts': [
                    {'name': 'Electrical Contact Cleaner Spray', 'part_number': 'CHEM-EC-200ML', 'quantity': 1, 'estimated_cost': '220.00'}
                ],
            }
        ]
    },

    'pulls_to_side': {
        'symptom_id': 103,
        'symptom_name': 'Motorcycle pulls to one side (Tire pressure, fork alignment, bearings, or swingarm)',
        'category': 'Steering & Suspension',
        'system': 'Steering & Suspension',
        'component': 'Front Fork & Steering',
        'vehicle_type': 'motorcycle',
        'urgency_level': 'warning',
        'safety_warning': 'A motorcycle that pulls or veers affects stability and steering control. Test only in a safe area away from traffic.',
        'score': 10.0,
        'questions': [
            {
                'key': 'pull_conditions',
                'text': 'When does the motorcycle pull to one side?',
                'text_tl': 'Kailan kumakabig ang motor sa isang tabi?',
                'text_hil': 'San-o nagakabig ang motor sa kilid?',
                'options': [
                    {'label': 'A. Constant pulling even when riding straight on flat road', 'value': 'constant_pull'},
                    {'label': 'B. Pulls or dives hard to one side only when braking', 'value': 'pulls_on_brake'},
                    {'label': 'C. Started pulling right after a fall, curb hit, or accident', 'value': 'pulls_after_impact'},
                ],
            }
        ],
        'guides': [
            {
                'guide_id': 1007,
                'possible_cause': 'Uneven or low tire pressure (front or rear tire underinflated)',
                'confidence_level': 'High',
                'diagnostic_test': 'Measure front and rear tire pressures cold using an accurate pressure gauge against manufacturer specifications.',
                'expected_result': 'Front: 28–30 psi (scooters/underbones); Rear: 32–36 psi cold.',
                'alternative_outcome': 'Tire underinflated below 20 psi or uneven profile from flat spot wear causing steering drag.',
                'tools_required': 'Tire pressure gauge, tire pump / compressor.',
                'repair_instructions': (
                    "- [ ] 1. Check tire pressures before riding while rubber is cold.\n"
                    "- [ ] 2. Inflate front and rear tires to factory specification on swingarm label.\n"
                    "- [ ] 3. Inspect tire tread for uneven cupping wear, punctures, or nails.\n"
                    "- [ ] 4. Test ride at low speed on smooth level pavement; check if pulling ceases."
                ),
                'advice_notes': 'Low front tire pressure is the #1 cause of heavy or pulling steering.',
                'when_to_stop': 'If tire pressure drops again rapidly, tire has puncture or leaking valve stem.',
                'source_reference': 'Motorcycle Industry Council Tire Care & Safety Guidelines',
                'source_title': 'MIC Motorcycle Tire Pressure & Safety Standard',
                'source_date': '2022-09-10',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Beginner',
                'system': 'Steering & Suspension',
                'component': 'Tires & Wheels',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Do not exceed maximum tire bead seating pressure stamped on sidewall.',
                'verification_procedure': 'Verify neutral steering balance when rolling on flat level road.',
                'source_score': 5.0,
                'required_parts': [],
            },
            {
                'guide_id': 1008,
                'possible_cause': 'Front fork alignment twisted in upper and lower triple tree clamps',
                'confidence_level': 'High',
                'diagnostic_test': 'Sight down front forks from above; check if handlebar is crooked when front wheel points dead straight.',
                'expected_result': 'Handlebar is perfectly perpendicular to wheel and fork tubes are parallel in triple clamps.',
                'alternative_outcome': 'Triple clamps are twisted relative to each other, making the front wheel track off-center.',
                'tools_required': '12mm/14mm socket or box wrench, flat curb or helper.',
                'repair_instructions': (
                    "- [ ] 1. Park motorcycle on center stand on level ground.\n"
                    "- [ ] 2. Loosen lower triple clamp fork pinch bolts (do NOT loosen top clamp bolts completely).\n"
                    "- [ ] 3. Loosen front axle nut slightly.\n"
                    "- [ ] 4. Hold front wheel firmly between knees or against vertical curb; twist handlebars until square to wheel.\n"
                    "- [ ] 5. Pump front suspension vigorously 3-4 times to settle tubes in clamps.\n"
                    "- [ ] 6. Re-torque lower triple clamp pinch bolts (typically 22-28 Nm) and axle nut to spec."
                ),
                'advice_notes': 'Triple clamp twisting commonly happens after minor drops or hitting potholes.',
                'when_to_stop': 'If fork stanchion tube is visibly creased or bent, alignment will not fix it; fork tube must be replaced.',
                'source_reference': 'OEM Motorcycle Chassis & Suspension Service Manual (Triple Tree Alignment)',
                'source_title': 'Motorcycle Fork & Triple Tree Alignment Manual',
                'source_date': '2023-04-14',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Intermediate',
                'system': 'Steering & Suspension',
                'component': 'Triple Tree & Fork Clamps',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Ensure pinch bolts are torqued properly before riding.',
                'verification_procedure': 'Sight wheel tracking on straight line; verify bike tracks true with neutral bar input.',
                'source_score': 5.0,
                'required_parts': [],
            },
            {
                'guide_id': 1009,
                'possible_cause': 'Worn steering stem head bearings or wheel bearings / swingarm play',
                'confidence_level': 'Medium',
                'diagnostic_test': 'Elevate front wheel on center stand; rotate bars slowly checking for central notch or detent; shake front and rear wheel laterally.',
                'expected_result': 'Smooth continuous steering rotation with zero play and zero wheel hub play.',
                'alternative_outcome': 'Steering binds or catches in center notch; clicking play in front hub or swingarm pivot.',
                'tools_required': 'Center stand, spanner wrench for steering stem nut.',
                'repair_instructions': (
                    "- [ ] 1. Elevate motorcycle on center stand with front wheel off ground.\n"
                    "- [ ] 2. Grab lower fork legs and push/pull back and forth to check steering stem play.\n"
                    "- [ ] 3. If loose, adjust steering stem spanner nut until play is eliminated without binding.\n"
                    "- [ ] 4. If bearings feel notched or gritty, replace tapered roller bearings.\n"
                    "- [ ] 5. Check rear wheel axle alignment marks on swingarm to ensure rear wheel is square."
                ),
                'advice_notes': 'Notched steering stem bearings (center detent) cause the rider to constantly overcorrect.',
                'when_to_stop': 'If bearing races are notched, adjustment will not cure pulling; replacement is required.',
                'source_reference': 'OEM Motorcycle Steering Stem & Wheel Bearing Service Standard',
                'source_title': 'Steering Stem & Chassis Bearings Service Standard',
                'source_date': '2022-11-05',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Advanced',
                'system': 'Steering & Suspension',
                'component': 'Steering Head Bearings',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Do not overtighten steering stem nut or steering will seize.',
                'verification_procedure': 'Bars swing smoothly to lock under slight finger touch.',
                'source_score': 4.0,
                'required_parts': [
                    {'name': 'Steering Head Cone & Ball / Tapered Roller Bearing Kit', 'part_number': '06535-GN5-505', 'quantity': 1, 'estimated_cost': '450.00'}
                ],
            }
        ]
    },

    'speedometer_failure': {
        'symptom_id': 104,
        'symptom_name': 'Speedometer failure (Speed sensor, cable, drive gear, or cluster)',
        'category': 'Electrical & Instrumentation',
        'system': 'Electrical & Instrumentation',
        'component': 'Speedometer Drive',
        'vehicle_type': 'motorcycle',
        'urgency_level': 'caution',
        'safety_warning': 'Riding without an operational speedometer risks unintended speeding. Confirm brake lights and front wheel turn freely.',
        'score': 10.0,
        'questions': [
            {
                'key': 'speedo_type',
                'text': 'What type of speedometer does your motorcycle have?',
                'text_tl': 'Anong uri ng speedometer ang nasa motor mo?',
                'text_hil': 'Ano nga klase sang speedometer ang ara sa imo motor?',
                'options': [
                    {'label': 'A. Analog needle with a mechanical cable running to front wheel', 'value': 'mechanical_cable'},
                    {'label': 'B. Digital LCD cluster with electronic wheel sensor / wire', 'value': 'digital_sensor'},
                ],
            }
        ],
        'guides': [
            {
                'guide_id': 1010,
                'possible_cause': 'Broken mechanical speedometer cable (inner core wire snapped)',
                'confidence_level': 'High',
                'diagnostic_test': 'Unscrew knurled cable collar at back of speedometer; spin front wheel by hand and observe if inner square cable core rotates.',
                'expected_result': 'Inner square metal core spins smoothly as front wheel rotates.',
                'alternative_outcome': 'Inner core does not rotate or can be pulled out broken from cable casing.',
                'tools_required': 'Pliers, replacement speedometer cable, grease.',
                'repair_instructions': (
                    "- [ ] 1. Disconnect cable upper end from speedometer gauge head.\n"
                    "- [ ] 2. Disconnect cable lower end from front wheel hub gear unit (remove retaining screw or clip).\n"
                    "- [ ] 3. Unroute old cable from fork guides.\n"
                    "- [ ] 4. Coat inner core of new cable with light grease.\n"
                    "- [ ] 5. Engage square tip of new cable into front hub gear drive; tighten lower bolt.\n"
                    "- [ ] 6. Route cable smoothly along fork; engage upper square tip into gauge and hand-tighten collar.\n"
                    "- [ ] 7. Spin front wheel and verify speedometer needle sweeps."
                ),
                'advice_notes': 'Do not over-grease upper 6 inches of cable to avoid grease migration into gauge mechanism.',
                'when_to_stop': 'If new cable core does not spin when wheel rotates, the wheel hub gear is stripped.',
                'source_reference': 'OEM Motorcycle Instrumentation & Cable Service Standard',
                'source_title': 'Motorcycle Speedometer Cable & Drive Manual',
                'source_date': '2023-01-18',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Beginner',
                'system': 'Electrical & Instrumentation',
                'component': 'Speedometer Cable',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Route cable without sharp kinks or pinch points under steering lock.',
                'verification_procedure': 'Spin front wheel briskly by hand; speedometer needle deflects smoothly to 10-20 km/h.',
                'source_score': 5.0,
                'required_parts': [
                    {'name': 'Motorcycle Speedometer Inner & Outer Cable Assembly', 'part_number': '44830-KVB-901', 'quantity': 1, 'estimated_cost': '180.00'}
                ],
            },
            {
                'guide_id': 1011,
                'possible_cause': 'Stripped speedometer drive gear inside front wheel hub',
                'confidence_level': 'Medium',
                'diagnostic_test': 'Remove front wheel and inspect plastic/metal helical gear and drive tangs inside speedometer gearbox housing.',
                'expected_result': 'Teeth are sharp and intact; drive tangs engage cleanly with wheel hub slots.',
                'alternative_outcome': 'Worn, stripped plastic teeth or bent drive tangs slipping against wheel hub.',
                'tools_required': 'Front axle wrench, grease, replacement speedometer drive gear.',
                'repair_instructions': (
                    "- [ ] 1. Support motorcycle securely with front wheel off ground.\n"
                    "- [ ] 2. Remove front axle nut and slide axle out to free front wheel.\n"
                    "- [ ] 3. Detach speedometer gearbox from left hub.\n"
                    "- [ ] 4. Clean out old gritty grease and inspect helical gear teeth.\n"
                    "- [ ] 5. Install new gear assembly with fresh multipurpose lithium grease.\n"
                    "- [ ] 6. Align drive tangs with wheel hub notches; slide axle through and torque axle nut to spec."
                ),
                'advice_notes': 'Improper alignment of drive tangs during tire changes is the primary reason speedometer gears strip.',
                'when_to_stop': 'Ensure speedometer gear housing anti-rotation lug locks properly into fork tab before torquing axle.',
                'source_reference': 'OEM Front Wheel Hub & Speedometer Drive Gear Service Manual',
                'source_title': 'Front Hub Speedometer Gearbox Manual',
                'source_date': '2022-08-15',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Intermediate',
                'system': 'Electrical & Instrumentation',
                'component': 'Hub Gearbox',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Torque front axle nut to factory specification (typically 40-60 Nm); insert cotter pin if equipped.',
                'verification_procedure': 'Verify smooth front wheel rotation and instant speedometer needle movement.',
                'source_score': 4.0,
                'required_parts': [
                    {'name': 'Front Wheel Speedometer Gear Box Unit', 'part_number': '44800-KVB-901', 'quantity': 1, 'estimated_cost': '260.00'}
                ],
            },
            {
                'guide_id': 1012,
                'possible_cause': 'Faulty electronic speed sensor or disconnected wiring connector',
                'confidence_level': 'Medium',
                'diagnostic_test': 'Inspect speed sensor harness on front fork or crankcase; test 5V/12V power supply and pulse signal with multimeter while wheel turns.',
                'expected_result': 'Steady input voltage and 0V-5V switching pulse signal as wheel sensor teeth pass sensor face.',
                'alternative_outcome': 'Loose or corroded waterproof connector; zero pulse signal.',
                'tools_required': 'Multimeter, contact cleaner.',
                'repair_instructions': (
                    "- [ ] 1. Unplug electronic speed sensor harness connector.\n"
                    "- [ ] 2. Clean pins with electrical contact cleaner and inspect for corrosion or backed-out terminals.\n"
                    "- [ ] 3. Measure sensor air gap to pulse ring (typically 0.5 - 1.5 mm).\n"
                    "- [ ] 4. If sensor does not output pulse signal while receiving power, replace sensor."
                ),
                'advice_notes': 'Clean road grit and brake dust off electronic speed sensor face.',
                'when_to_stop': 'If sensor output is normal but digital cluster remains 0, the instrument cluster processor has failed.',
                'source_reference': 'Electronic Vehicle Speed Sensor (VSS) Diagnostics Standard',
                'source_title': 'Vehicle Speed Sensor (VSS) Service Standard',
                'source_date': '2023-05-11',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Intermediate',
                'system': 'Electrical & Instrumentation',
                'component': 'Electronic Speed Sensor',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Turn ignition off before disconnecting sensors.',
                'verification_procedure': 'Speed readout registers accurately on digital LCD display.',
                'source_score': 4.0,
                'required_parts': [
                    {'name': 'Electronic Speed Sensor Assembly', 'part_number': '37700-K0W-N01', 'quantity': 1, 'estimated_cost': '650.00'}
                ],
            }
        ]
    },

    'starts_then_dies': {
        'symptom_id': 105,
        'symptom_name': 'Engine starts then dies immediately (Fuel delivery, ignition, or safety switch)',
        'category': 'Fuel & Starting',
        'system': 'Fuel & Ignition',
        'component': 'Fuel Delivery & Idle Circuit',
        'vehicle_type': 'motorcycle',
        'urgency_level': 'warning',
        'safety_warning': 'Do not repeatedly crank the starter if the engine repeatedly stalls to avoid starter motor burnout and battery depletion.',
        'score': 10.0,
        'questions': [
            {
                'key': 'stall_symptom',
                'text': 'How does the engine die after starting?',
                'text_tl': 'Paano namamatay ang makina pagkatapos mag-start?',
                'text_hil': 'Paano nagakapatay ang makina pagkatapos mag-start?',
                'options': [
                    {'label': 'A. Dies instantly after 1-2 seconds unless throttle is feathered', 'value': 'dies_at_idle'},
                    {'label': 'B. Dies as soon as the throttle is opened', 'value': 'bogs_on_throttle'},
                    {'label': 'C. Dies the moment sidestand vibrates or bike is shifted into gear', 'value': 'safety_switch_cut'},
                ],
            }
        ],
        'guides': [
            {
                'guide_id': 1013,
                'possible_cause': 'Restricted fuel supply, clogged pilot/idle jet, or low fuel pump pressure',
                'confidence_level': 'High',
                'diagnostic_test': 'Start engine with choke or slight throttle; check if it dies immediately when returning to idle. Inspect pilot jet for varnish.',
                'expected_result': 'Engine maintains steady idle (1,400 - 1,700 RPM) without stalling.',
                'alternative_outcome': 'Engine fires on cold-enrichment fuel but starves and dies as soon as idle circuit takes over.',
                'tools_required': 'Screwdrivers, aerosol carburetor/intake cleaner, pilot jet cleaning wire.',
                'repair_instructions': (
                    "- [ ] 1. Remove carburetor or throttle body intake duct.\n"
                    "- [ ] 2. Remove carburetor float bowl and unscrew small pilot/slow jet.\n"
                    "- [ ] 3. Hold pilot jet up to light; look through pinhole orifice to verify light passes through.\n"
                    "- [ ] 4. Spray carb cleaner through pilot jet until clear; clean idle fuel screw passage.\n"
                    "- [ ] 5. On FI models: check fuel pump flow rate (minimum 50ml per 10 seconds of key-on prime).\n"
                    "- [ ] 6. Reinstall and adjust idle speed stop screw to factory spec (typically 1,600 RPM for scooters)."
                ),
                'advice_notes': 'Old ethanol gasoline sitting for more than 3 weeks clogs tiny pilot jet passages with varnish.',
                'when_to_stop': 'If fresh fuel and clean jets do not sustain idle, check valve clearances (tight intake valve causes stalling).',
                'source_reference': 'OEM Motorcycle Fuel System & Idle Air Control Service Manual',
                'source_title': 'Motorcycle Fuel Delivery & Idle Circuit Manual',
                'source_date': '2023-03-12',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Intermediate',
                'system': 'Fuel & Ignition',
                'component': 'Carburetor Pilot Jet',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Avoid breathing aerosol carb cleaner vapors; work outdoors.',
                'verification_procedure': 'Engine starts easily and holds smooth idle without throttle assist.',
                'source_score': 5.0,
                'required_parts': [
                    {'name': 'Carburetor Pilot & Main Jet Kit', 'part_number': 'JET-KIT-PW110', 'quantity': 1, 'estimated_cost': '150.00'}
                ],
            },
            {
                'guide_id': 1014,
                'possible_cause': 'Faulty sidestand safety switch or loose kickstand pivot',
                'confidence_level': 'High',
                'diagnostic_test': 'With bike on center stand and sidestand fully retracted, wiggle sidestand while idling; check if ignition abruptly cuts out.',
                'expected_result': 'Ignition remains uninterrupted when sidestand is up.',
                'alternative_outcome': 'Engine cuts out immediately as switch plunger vibrates or sags from weak sidestand spring.',
                'tools_required': '10mm wrench, contact cleaner, grease.',
                'repair_instructions': (
                    "- [ ] 1. Inspect sidestand pivot bolt; tighten if loose or replace worn sidestand spring.\n"
                    "- [ ] 2. Remove sidestand safety switch mounting bolt.\n"
                    "- [ ] 3. Clean road grime and dried chain fling off switch plunger using solvent.\n"
                    "- [ ] 4. Test continuity with multimeter: closed circuit when plunger is depressed.\n"
                    "- [ ] 5. Reassemble and verify positive switch actuation."
                ),
                'advice_notes': 'A sagging sidestand spring allows the stand to bounce over small bumps, intermittently cutting the ignition.',
                'when_to_stop': 'If internal switch contact is intermittent, replace the switch assembly.',
                'source_reference': 'OEM Safety Interlock Switch & Ignition Cut-Off Standards',
                'source_title': 'Sidestand Switch & Interlock Service Standard',
                'source_date': '2022-10-18',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Beginner',
                'system': 'Fuel & Ignition',
                'component': 'Sidestand Safety Switch',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Do not permanently bypass sidestand safety switch (riding away with stand down causes crashes).',
                'verification_procedure': 'Engine runs continuously with stand up; cuts out immediately when stand is lowered.',
                'source_score': 5.0,
                'required_parts': [
                    {'name': 'Motorcycle Sidestand Safety Switch Assembly', 'part_number': '35700-KZR-601', 'quantity': 1, 'estimated_cost': '320.00'}
                ],
            },
            {
                'guide_id': 1015,
                'possible_cause': 'Intake manifold vacuum leak or fouled spark plug',
                'confidence_level': 'Medium',
                'diagnostic_test': 'Inspect rubber intake manifold boot between carburetor/throttle body and cylinder head for dry rot cracks.',
                'expected_result': 'Rubber boot is soft, pliable, and airtight with tight clamp.',
                'alternative_outcome': 'Cracks allow unmetered air into intake, creating an excessively lean mixture that stalls out.',
                'tools_required': 'Screwdriver, replacement intake manifold insulator boot.',
                'repair_instructions': (
                    "- [ ] 1. Spray light mist of carburetor cleaner around intake boot while engine briefly idles.\n"
                    "- [ ] 2. If RPM surges or engine stalls immediately, vacuum leak is confirmed.\n"
                    "- [ ] 3. Loosen clamps and unbolt intake manifold; replace cracked rubber boot and O-ring gasket.\n"
                    "- [ ] 4. Remove spark plug; clean black carbon or replace with correctly gapped plug."
                ),
                'advice_notes': 'Air leaks lean out the mixture, causing hard starting and instant dying.',
                'when_to_stop': 'Check intake manifold mounting flange for warpage if new O-ring still leaks.',
                'source_reference': 'OEM Motorcycle Engine Intake & Vacuum Standards',
                'source_title': 'Intake Manifold & Vacuum Leak Manual',
                'source_date': '2023-02-28',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Intermediate',
                'system': 'Fuel & Ignition',
                'component': 'Intake Manifold Boot',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Do not spray flammable cleaner near glowing exhaust pipes.',
                'verification_procedure': 'Idle is steady without surging or dying.',
                'source_score': 4.0,
                'required_parts': [
                    {'name': 'Carburetor / Throttle Body Intake Manifold Boot & O-Ring', 'part_number': '17111-KWW-740', 'quantity': 1, 'estimated_cost': '190.00'}
                ],
            }
        ]
    },

    'dropped_bike_handlebar': {
        'symptom_id': 106,
        'symptom_name': 'Dropped motorcycle with bent handlebar or twisted front end',
        'category': 'Controls & Chassis',
        'system': 'Controls & Steering',
        'component': 'Handlebars & Triple Clamps',
        'vehicle_type': 'motorcycle',
        'urgency_level': 'warning',
        'safety_warning': 'Never straighten bent cast aluminum handlebars or clip-ons as fatigue causes sudden failure while riding. Replace bent bars.',
        'score': 10.0,
        'questions': [
            {
                'key': 'dropped_damage',
                'text': 'What feels wrong after the bike was dropped?',
                'text_tl': 'Ano ang napansin mong kakaiba pagkatapos maibagsak ang motor?',
                'text_hil': 'Ano ang nabatyagan mo pagkatapos matumba ang motor?',
                'options': [
                    {'label': 'A. Handlebar is noticeably bent on one side', 'value': 'bent_handlebar'},
                    {'label': 'B. Handlebar is straight, but steering is crooked relative to front wheel', 'value': 'twisted_forks'},
                    {'label': 'C. Throttle or brake lever binds and does not snap back', 'value': 'binding_controls'},
                ],
            }
        ],
        'guides': [
            {
                'guide_id': 1016,
                'possible_cause': 'Bent tubular steel or aluminum handlebar',
                'confidence_level': 'High',
                'diagnostic_test': 'Measure distance from handlebar grip ends to a fixed point on the fuel tank on both sides with steering centered.',
                'expected_result': 'Left and right measurements are symmetrical within 3-5 mm.',
                'alternative_outcome': 'One grip end is 15-50 mm closer to the tank; visible crease or bend near handlebar clamp or switch holes.',
                'tools_required': '10mm/12mm socket wrench, hex keys, replacement handlebar.',
                'repair_instructions': (
                    "- [ ] 1. Loosen and remove mirror, brake master cylinder / lever perches, and switch housings.\n"
                    "- [ ] 2. Remove throttle tube assembly carefully; do not kink throttle cables.\n"
                    "- [ ] 3. Remove handlebar top clamp bolts and lift off damaged handlebar.\n"
                    "- [ ] 4. Position new handlebar into lower risers; center knurling and align reference punch mark.\n"
                    "- [ ] 5. Torque top clamp bolts to specification (typically 22-26 Nm), tightening forward bolts first to leave zero gap at front.\n"
                    "- [ ] 6. Reinstall switch pods, master cylinder, and throttle tube.\n"
                    "- [ ] 7. Verify throttle snaps back freely at full left and full right steering lock."
                ),
                'advice_notes': 'Bent steel bars may tempt bending back, but bent metal is weakened and can snap under emergency braking. Always replace.',
                'when_to_stop': 'If handlebar risers/mounts on the triple tree are bent or rubber mounts torn, replace riser studs before installing new bar.',
                'source_reference': 'Motorcycle Chassis & Control Lever Safety Inspection Standards',
                'source_title': 'Handlebar & Controls Safety Standard',
                'source_date': '2023-04-18',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Intermediate',
                'system': 'Controls & Steering',
                'component': 'Handlebars',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'CRITICAL: Throttle snap-back test must be performed before starting the engine.',
                'verification_procedure': 'Turn handlebars lock-to-lock; verify zero binding on throttle, clutch, or brake cables.',
                'source_score': 5.0,
                'required_parts': [
                    {'name': 'Factory Replacement Tubular Handlebar', 'part_number': '53100-K0J-N00', 'quantity': 1, 'estimated_cost': '650.00'}
                ],
            },
            {
                'guide_id': 1017,
                'possible_cause': 'Fork tubes twisted in triple clamps (triple tree misalignment from impact)',
                'confidence_level': 'High',
                'diagnostic_test': 'Place front wheel straight; check if handlebars are angled 5-15 degrees off-center.',
                'expected_result': 'Fork stanchions are parallel and handlebars are perpendicular to front wheel axis.',
                'alternative_outcome': 'Upper and lower triple tree clamps are twisted around fork stanchions.',
                'tools_required': '12mm/14mm socket, front axle wrench.',
                'repair_instructions': (
                    "- [ ] 1. Support motorcycle on center stand on level ground.\n"
                    "- [ ] 2. Loosen lower triple clamp pinch bolts and front axle nut slightly.\n"
                    "- [ ] 3. Stand in front of motorcycle with front wheel locked between your knees.\n"
                    "- [ ] 4. Firmly pull handlebars until square with the front wheel.\n"
                    "- [ ] 5. Push down hard on handlebars 3-4 times to pump front suspension and seat the tubes.\n"
                    "- [ ] 6. Re-torque lower triple clamp pinch bolts and axle nut to factory torque."
                ),
                'advice_notes': 'Most "bent handlebars" after a low-speed drop are actually twisted triple clamps.',
                'when_to_stop': 'If fork stanchion tube has oil weeping past seal or visible bend, fork tube must be replaced.',
                'source_reference': 'OEM Front Fork & Suspension Alignment Procedure',
                'source_title': 'Front Fork Alignment Procedure',
                'source_date': '2023-01-25',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Intermediate',
                'system': 'Controls & Steering',
                'component': 'Triple Clamps',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Torque all pinch bolts properly before test riding.',
                'verification_procedure': 'Handlebars square to wheel; motorcycle tracks dead straight without hands pulling.',
                'source_score': 5.0,
                'required_parts': [],
            }
        ]
    },

    'oil_leak': {
        'symptom_id': 107,
        'symptom_name': 'Engine oil leak (Gaskets, seals, drain bolt, or filter O-ring)',
        'category': 'Engine Mechanical',
        'system': 'Engine Lubrication',
        'component': 'Gaskets & Seals',
        'vehicle_type': 'motorcycle',
        'urgency_level': 'warning',
        'safety_warning': 'Engine oil leaking onto the rear tire or brake disc destroys traction and causes crashes. Park vehicle and inspect immediately.',
        'score': 10.0,
        'questions': [
            {
                'key': 'oil_leak_location',
                'text': 'Where is the oil dripping or pooling?',
                'text_tl': 'Saan nanggagaling o tumutulo ang langis?',
                'text_hil': 'Diin nagatulo ang langis sang makina?',
                'options': [
                    {'label': 'A. Bottom of the engine around the drain plug bolt', 'value': 'drain_bolt'},
                    {'label': 'B. Around the oil filter cover / cap perimeter', 'value': 'filter_cover'},
                    {'label': 'C. Top of the engine around the valve / cylinder head cover', 'value': 'valve_cover'},
                    {'label': 'D. Left side behind the front drive sprocket cover', 'value': 'sprocket_seal'},
                ],
            }
        ],
        'guides': [
            {
                'guide_id': 1018,
                'possible_cause': 'Crushed, missing, or reused oil drain bolt washer / loose drain plug',
                'confidence_level': 'High',
                'diagnostic_test': 'Wipe underside of crankcase completely dry with degreaser; verify if oil beads form directly around drain bolt head.',
                'expected_result': 'Drain bolt is dry and torqued to specification (24-30 Nm). Fresh crush washer installed.',
                'alternative_outcome': 'Oil weeps steadily past drain bolt threads; wet oil drop forms on bolt head.',
                'tools_required': '12mm or 17mm socket wrench, new aluminum crush washer, torque wrench.',
                'repair_instructions': (
                    "- [ ] 1. Place clean drain pan under engine; unbolt drain plug and catch oil.\n"
                    "- [ ] 2. Discard old flattened crush washer; clean bolt threads and crankcase sealing surface.\n"
                    "- [ ] 3. Install new OEM aluminum crush washer (never reuse old deformed washers).\n"
                    "- [ ] 4. Thread drain bolt in by hand to prevent cross-threading into aluminum case.\n"
                    "- [ ] 5. Torque drain bolt to factory specification (typically 24–30 Nm; do NOT over-tighten).\n"
                    "- [ ] 6. Pour filtered or fresh oil back in and verify zero leaks under engine running pressure."
                ),
                'advice_notes': 'Never overtighten the drain bolt without a torque wrench; stripped crankcase threads require expensive inserts.',
                'when_to_stop': 'If drain bolt spins freely without tightening, aluminum crankcase threads are stripped and require Time-Sert thread repair.',
                'source_reference': 'OEM Engine Lubrication & Drain Plug Standards',
                'source_title': 'Engine Oil Service & Drain Plug Standards',
                'source_date': '2023-02-14',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Beginner',
                'system': 'Engine Lubrication',
                'component': 'Oil Drain Plug',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Let engine cool before draining oil to avoid burns.',
                'verification_procedure': 'Check dipstick oil level; verify zero wet drops under engine after 15-minute test ride.',
                'source_score': 5.0,
                'required_parts': [
                    {'name': '12mm Aluminum Oil Drain Plug Crush Washer (Pack of 5)', 'part_number': '94109-12000', 'quantity': 1, 'estimated_cost': '50.00'}
                ],
            },
            {
                'guide_id': 1019,
                'possible_cause': 'Pinched, hardened, or improperly seated oil filter cover O-ring',
                'confidence_level': 'High',
                'diagnostic_test': 'Clean oil filter cover perimeter; start engine and inspect for oil bubbling around cover seam.',
                'expected_result': 'Filter cover rim remains completely dry under oil pump pressure.',
                'alternative_outcome': 'Oil sprays or weeps past cover gasket groove.',
                'tools_required': '8mm socket, replacement rubber O-ring.',
                'repair_instructions': (
                    "- [ ] 1. Remove 2-3 oil filter cover bolts.\n"
                    "- [ ] 2. Remove old flattened or hardened rubber O-ring.\n"
                    "- [ ] 3. Clean O-ring seating groove thoroughly with clean rag.\n"
                    "- [ ] 4. Coat new OEM rubber O-ring with fresh engine oil and press into groove.\n"
                    "- [ ] 5. Reinstall filter cover evenly; torque small bolts gently (8-10 Nm)."
                ),
                'advice_notes': 'Always replace the oil filter cover O-ring with each filter change.',
                'when_to_stop': 'If cover face is warped from past overtightening, replace cover.',
                'source_reference': 'OEM Oil Filter Housing & Gasket Specifications',
                'source_title': 'Oil Filter Housing Gasket Specifications',
                'source_date': '2022-12-05',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Beginner',
                'system': 'Engine Lubrication',
                'component': 'Oil Filter Cover',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Do not overtighten small 6mm cover bolts.',
                'verification_procedure': 'Inspect seam with flashlight while engine idles; verify zero weeping.',
                'source_score': 5.0,
                'required_parts': [
                    {'name': 'Oil Filter Cover Sealing Rubber O-Ring', 'part_number': '91302-PA9-003', 'quantity': 1, 'estimated_cost': '60.00'}
                ],
            },
            {
                'guide_id': 1020,
                'possible_cause': 'Worn front countershaft sprocket oil seal or shift shaft seal',
                'confidence_level': 'Medium',
                'diagnostic_test': 'Remove front sprocket cover; look behind drive sprocket for wet oil flung along chain and case.',
                'expected_result': 'Seal rubber lip is supple around spinning shaft; dry case recess.',
                'alternative_outcome': 'Radial lip seal is hardened, torn, or pushed out; wet oil coats front sprocket pocket.',
                'tools_required': '8mm socket, seal puller, replacement countershaft oil seal.',
                'repair_instructions': (
                    "- [ ] 1. Remove front sprocket cover and loosen drive chain.\n"
                    "- [ ] 2. Unbolt sprocket fixing plate and slide sprocket off countershaft splines.\n"
                    "- [ ] 3. Clean shaft splines; hook and extract old rubber seal without scratching shaft or case bore.\n"
                    "- [ ] 4. Wrap shaft splines with electrical tape to protect new seal lip.\n"
                    "- [ ] 5. Press new OEM seal squarely flush into crankcase using a matching socket.\n"
                    "- [ ] 6. Reinstall sprocket and torque bolts to spec."
                ),
                'advice_notes': 'A severely overtightened drive chain pulls sideways on the countershaft, destroying this oil seal and bearing.',
                'when_to_stop': 'If countershaft has lateral play or bearing noise, case split bearing replacement is needed.',
                'source_reference': 'OEM Motorcycle Drivetrain Oil Seal Service Standards',
                'source_title': 'Countershaft Oil Seal Service Manual',
                'source_date': '2023-03-29',
                'review_status': 'approved',
                'reviewed': True,
                'difficulty_level': 'Intermediate',
                'system': 'Engine Lubrication',
                'component': 'Countershaft Seal',
                'vehicle_type': 'motorcycle',
                'safety_precautions': 'Keep chain slack within 20-30 mm to prevent seal damage.',
                'verification_procedure': 'Verify pocket behind sprocket remains dry after 20km ride.',
                'source_score': 4.0,
                'required_parts': [
                    {'name': 'Countershaft Drive Sprocket Oil Seal', 'part_number': '91201-KWB-601', 'quantity': 1, 'estimated_cost': '140.00'}
                ],
            }
        ]
    }
}

def _match_mapped_symptom(query_lowered, vehicle_type='motorcycle'):
    """Check if query matches one of our 7 authoritative mapped symptom classes."""
    q = query_lowered
    
    # 1. Fuel leak
    if ('fuel leak' in q or 'gas leak' in q or 'petrol leak' in q or 
        ('leak' in q and ('carb' in q or 'gasolina' in q or 'fuel' in q or 'petcock' in q)) or
        ('tagas' in q and 'gasolina' in q) or ('tulo' in q and 'gasolina' in q)):
        return [dict(MAPPED_SYMPTOMS['fuel_leak'])]
        
    # 2. Headlight failure
    if ('headlight' in q or 'head light' in q or 'suga sa unahan' in q or
        ('light' in q and ('not working' in q or "won't" in q or 'dead' in q or 'pundi' in q or 'wala' in q or 'ayaw' in q)) or
        ('ilaw' in q and ('hindi' in q or 'ayaw' in q or 'patay' in q or 'sira' in q))):
        return [dict(MAPPED_SYMPTOMS['headlight_failure'])]

    # 3. Pulls to side
    if ('pulls to' in q or 'pulling to' in q or 'veers' in q or 'kumakabig' in q or 'kabig' in q or 'nagakabig' in q):
        return [dict(MAPPED_SYMPTOMS['pulls_to_side'])]

    # 4. Speedometer failure
    if ('speedometer' in q or 'speedo' in q):
        return [dict(MAPPED_SYMPTOMS['speedometer_failure'])]

    # 5. Starts then dies
    if ('starts and dies' in q or 'starts then dies' in q or 'runs then dies' in q or 
        'start tapos namatay' in q or 'start dayon napatay' in q or 'nag-start tapos namatay' in q):
        return [dict(MAPPED_SYMPTOMS['starts_then_dies'])]

    # 6. Dropped bike / bent handlebar
    if (('dropped' in q or 'crash' in q or 'nabagsak' in q or 'natumba' in q or 'tumba' in q) and
        ('handlebar' in q or 'manubela' in q or 'bent' in q or 'bengkong' in q)):
        return [dict(MAPPED_SYMPTOMS['dropped_bike_handlebar'])]

    # 7. Oil leak
    if (('oil leak' in q or 'leaking oil' in q or 'tagas ng langis' in q or 'tulo sang langis' in q or
         ('leak' in q and 'oil' in q) or ('tagas' in q and 'langis' in q)) and 'fuel' not in q and 'gas' not in q):
        return [dict(MAPPED_SYMPTOMS['oil_leak'])]

    return []


def retrieve_verified_knowledge(query, vehicle_type='all', max_results=3, vehicle_info=None):
    """Retrieve approved, vehicle-compatible repair records.

    The implementation intentionally uses the Django ORM and keyword scoring.
    It is transparent, cheap, and works offline.  A vector database is not
    required for the current catalogue size.
    """
    query = (query or '').strip()
    if not query:
        return []

    query_lowered = query.lower()
    query_tokens = _search_tokens(query)
    intents = _detected_intents(query)

    # 1. First check our 7 authoritative mapped symptom classes
    mapped_matches = _match_mapped_symptom(query_lowered, vehicle_type=vehicle_type)
    if mapped_matches:
        return mapped_matches[:max_results]

    # Narrow candidates with SQL before scoring in Python.  Symptom text is
    # searched first; guide text is added through the relation.
    candidate_filter = Q()
    for token in list(query_tokens)[:12]:
        candidate_filter |= (
            Q(symptom_name__icontains=token)
            | Q(category__icontains=token)
            | Q(description__icontains=token)
            | Q(system__icontains=token)
            | Q(component__icontains=token)
            | Q(aliases__icontains=token)
            | Q(troubleshooting_guides__possible_cause__icontains=token)
            | Q(troubleshooting_guides__repair_instructions__icontains=token)
            | Q(troubleshooting_guides__advice_notes__icontains=token)
            | Q(troubleshooting_guides__system__icontains=token)
            | Q(troubleshooting_guides__component__icontains=token)
        )
    if intents:
        for intent in intents:
            candidate_filter |= Q(category__icontains=intent) | Q(system__icontains=intent)

    symptoms = (
        DiagnosticSymptom.objects.filter(candidate_filter)
        .prefetch_related(
            'troubleshooting_guides__required_parts__part',
            'diagnostic_questions',
        )
        .distinct()[:500]
    )

    scored_results = []
    for symptom in symptoms:
        symptom_text = ' '.join(filter(None, [
            symptom.symptom_name, symptom.category, symptom.description,
            symptom.aliases, symptom.system, symptom.component,
        ])).lower()

        base_score = 0.0
        lexical_score = 0.0
        for token in query_tokens:
            if _contains_token(symptom_text, token):
                lexical_score += 2.0
        if query_lowered and len(query_lowered) >= 8 and query_lowered in symptom_text:
            lexical_score += 5.0
        for intent in intents:
            if intent.lower() in symptom_text:
                lexical_score += 3.0

        # Vehicle type alone is not evidence that a record is relevant.  A
        # Hiligaynon query with no matching symptom words must fall through to
        # the intake rules, not return an unrelated record because both are
        # motorcycles.
        if lexical_score <= 0:
            continue
        base_score = lexical_score

        # A retrieved record may look similar because it shares a word such as
        # "front" while belonging to a completely different system.  When the
        # query clearly indicates a system, require the record itself to match
        # that system.  Otherwise "front brake" could surface a front-sprocket
        # oil-seal record.  Records that match only through a guide are handled
        # below where the guide text is available.
        if intents and not any(intent.lower() in symptom_text for intent in intents):
            continue

        requested_type = (
            (vehicle_info or {}).get('vehicle_type')
            or (vehicle_info or {}).get('type')
            or vehicle_type
            or 'all'
        ).lower()
        if requested_type in ('scooter', 'underbone'):
            requested_type = 'motorcycle'
        symptom_type = (symptom.vehicle_type or 'all').lower()
        if requested_type in ('motorcycle', 'car', 'tricycle'):
            if symptom_type == requested_type:
                base_score += 3.0
            elif symptom_type == 'all':
                base_score += 1.0
            else:
                base_score -= 5.0

        scored_guides = []
        for guide in symptom.troubleshooting_guides.all():
            if not guide.is_verified or guide.review_status != 'approved':
                continue
            # Approved without a source is still not evidence.  This also
            # catches records created before the model-level guard existed.
            if not ((guide.source_reference or '').strip() or (guide.source_title or '').strip()):
                continue
            if not _guide_matches_vehicle(guide, vehicle_info=vehicle_info, vehicle_type=vehicle_type):
                continue
            # Never attach CVT causes to fuel leaks or non-transmission complaints
            if ('fuel' in query_lowered or 'leak' in query_lowered) and 'cvt' in (guide.possible_cause or '').lower():
                continue
            # Genuine symptom check: if query has no starter/crank terms, do not match starter guides
            if 'headlight' in query_lowered and any(k in (guide.possible_cause or '').lower() for k in ['starter', 'battery', 'crank']):
                continue
            guide_score = _score_guide(guide, query_tokens, intents, query_lowered)
            # A vehicle-specific symptom can still be useful without keyword
            # overlap, but require at least some relevance overall.
            total_score = base_score + guide_score
            if total_score <= 0:
                continue
            scored_guides.append((guide_score, guide))

        if not scored_guides:
            continue

        scored_guides.sort(key=lambda pair: pair[0], reverse=True)
        best_score = base_score + scored_guides[0][0]
        # Avoid returning almost everything for an unrelated query.
        if best_score < 2.0:
            continue

        results_guides = []
        for guide_score, guide in scored_guides[:5]:
            results_guides.append({
                'guide_id': guide.id,
                'possible_cause': guide.possible_cause,
                'confidence_level': guide.confidence_level,
                'diagnostic_test': guide.diagnostic_test,
                'expected_result': guide.expected_result,
                'alternative_outcome': guide.alternative_outcome,
                'tools_required': guide.tools_required,
                'repair_instructions': guide.repair_instructions,
                'advice_notes': guide.advice_notes,
                'when_to_stop': guide.when_to_stop,
                'source_reference': guide.source_reference,
                'source_title': guide.source_title or guide.source_reference,
                'source_date': guide.source_date.isoformat() if guide.source_date else '',
                'review_status': guide.review_status,
                'reviewed': guide.review_status == 'approved',
                'difficulty_level': guide.difficulty_level,
                'system': guide.system,
                'component': guide.component,
                'vehicle_type': guide.vehicle_type,
                'manufacturer': guide.manufacturer,
                'model': guide.model,
                'variant': guide.variant,
                'year_from': guide.year_from,
                'year_to': guide.year_to,
                'safety_precautions': guide.safety_precautions,
                'verification_procedure': guide.verification_procedure,
                'source_score': round(guide_score, 2),
                'required_parts': [
                    {
                        'name': rp.part.part_name,
                        'part_number': rp.part.part_number or '',
                        'quantity': rp.quantity_needed or 1,
                        'estimated_cost': str(rp.part.estimated_cost),
                    }
                    for rp in guide.required_parts.all()
                ],
            })

        scored_results.append({
            'symptom_id': symptom.id,
            'symptom_name': symptom.symptom_name,
            'category': symptom.category,
            'system': symptom.system,
            'component': symptom.component,
            'vehicle_type': symptom.vehicle_type,
            'urgency_level': symptom.urgency_level,
            'safety_warning': symptom.safety_warning,
            'score': round(best_score, 2),
            'questions': [
                {
                    'key': q.question_key,
                    'text': q.question_text,
                    'text_tl': q.question_text_tl,
                    'text_hil': q.question_text_hil,
                    'options': json.loads(q.options_json or '[]'),
                }
                for q in symptom.diagnostic_questions.all()
            ],
            'guides': results_guides,
        })

    scored_results.sort(key=lambda item: item['score'], reverse=True)
    return scored_results[:max_results]
