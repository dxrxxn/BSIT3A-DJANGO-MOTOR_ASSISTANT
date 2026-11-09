"""Offline motorcycle technical answers and templates for MotorAssistant / J.A.R.V.I.S.

Provides accurate, safe, concise offline guidance for:
- Valve clearances (Honda TMX 125 and generic 4T)
- Spark plug gaps (Honda Beat and generic)
- Coolant specifications (PCX 160 and generic liquid-cooled)
- CVT belt and roller intervals (Honda Click 150i and generic scooters)
- Battery charging voltages (normal resting and charging ranges)
- Clutch cable adjustments (Raider 150 and manual motorcycles)
- Model comparisons (Yamaha Aerox vs NMAX, etc.)
- Model overviews (Honda Click 125i, etc.)
- Beginner motorcycle recommendations
- Riding gear and helmets (ECE/DOT standards, ATGATT)
- Wet weather / rain riding safety
- Oil types and oil filter replacement
- Tire pressures (Yamaha NMAX, etc.)
- Traffic overheating troubleshooting
"""
from __future__ import annotations

import re


def get_valve_clearance_answer(query: str, make: str = '', model: str = '', language: str = 'english') -> str:
    q = (query + ' ' + model).lower()
    is_tmx = 'tmx' in q
    if language == 'tagalog':
        if is_tmx:
            return (
                "Para sa **Honda TMX 125 Alpha**, ang karaniwang valve clearance (dapat sukatin habang ganap na **MALAMIG** ang makina):\n\n"
                "- **Intake (pasukan):** **0.06 – 0.08 mm** (0.002 – 0.003 in)\n"
                "- **Exhaust (labasan):** **0.08 – 0.10 mm** (0.003 – 0.004 in)\n\n"
                "**Mahalagang Paalala:** I-adjust lamang ito kapag malamig ang makina (room temperature). "
                "Gumamit ng feeler gauge na may bahagyang drag o hagod. Kumpirmahin din ang eksaktong sukat sa opisyal na Honda owner's manual.\n\n"
                "[chips: Paano mag-adjust ng valve? | Spark plug check | Change oil interval | Maintenance schedule]"
            )
        return (
            "Para sa karamihang 4-stroke single-cylinder na motor, ang karaniwang valve clearance (sukatin habang **MALAMIG** ang makina):\n\n"
            "- **Intake:** Karaniwang **0.05 – 0.08 mm**\n"
            "- **Exhaust:** Karaniwang **0.08 – 0.10 mm**\n\n"
            "Dahil nag-iiba-iba ang eksaktong clearance bawat modelo at manufacturer, laging kumpirmahin ang tumpak na numero sa iyong owner's manual bago mag-adjust.\n\n"
            "[chips: Paano mag-adjust ng valve? | Spark plug gap | Engine tune-up | Maintenance schedule]"
        )

    # English
    if is_tmx:
        return (
            "For the **Honda TMX 125 Alpha**, the factory valve clearance specifications (measured with the engine completely **COLD**):\n\n"
            "- **Intake:** **0.06 – 0.08 mm** (0.002 – 0.003 in)\n"
            "- **Exhaust:** **0.08 – 0.10 mm** (0.003 – 0.004 in)\n\n"
            "**Key note:** Always adjust valve clearance when the engine is stone cold. "
            "Use a clean feeler gauge with slight dragging resistance. Confirm the exact specification in your official Honda owner's manual.\n\n"
            "[chips: How to adjust valve clearance | Spark plug gap | Oil change interval | Full maintenance schedule]"
        )
    return (
        "Typical cold valve clearance specifications for small-displacement 4-stroke motorcycles:\n\n"
        "- **Intake:** Typically **0.05 – 0.08 mm** (0.002 – 0.003 in)\n"
        "- **Exhaust:** Typically **0.08 – 0.10 mm** (0.003 – 0.004 in)\n\n"
        "Clearances must be measured when the engine is completely cold. "
        "Exact clearances vary by engine architecture; confirm your model's exact numbers in your owner's manual before adjusting.\n\n"
        "[chips: How to check valve clearance | Spark plug gap | Engine tune-up | Full maintenance schedule]"
    )


def get_spark_plug_gap_answer(query: str, make: str = '', model: str = '', language: str = 'english') -> str:
    q = (query + ' ' + model).lower()
    is_beat = 'beat' in q
    if language == 'tagalog':
        if is_beat:
            return (
                "Para sa **Honda Beat 110 (FI)**, ang tamang spark plug gap ay **0.8 – 0.9 mm**.\n\n"
                "- **Inirerekomendang spark plug:** NGK CPR9EA-9 o Denso U27EPR9.\n"
                "- Sukatin gamit ang wire feeler gauge. Huwag pilitin ang pagbabaon upang hindi mabasag ang electrode. Kumpirmahin din sa owner's manual.\n\n"
                "[chips: Paano linisin ang spark plug | Tamang tire pressure | Change oil interval | Maintenance schedule]"
            )
        return (
            "Ang karaniwang spark plug gap para sa mga motor:\n\n"
            "- Karaniwang standard plugs: **0.6 – 0.7 mm**\n"
            "- Modernong FI / extended-reach plugs (hal. CPR9EA-9): **0.8 – 0.9 mm**\n\n"
            "Laging gamitin ang wire feeler gauge at kumpirmahin ang eksaktong gap sa iyong owner's manual.\n\n"
            "[chips: Spark plug check | Engine tune-up | Change oil | Maintenance schedule]"
        )

    if is_beat:
        return (
            "For the **Honda Beat (FI)**, the recommended spark plug gap is **0.8 – 0.9 mm** (0.031 – 0.035 in).\n\n"
            "- **Standard plug:** NGK CPR9EA-9 (or CPR8EA-9 depending on year) / Denso U27EPR9.\n"
            "- Check gap with a wire-type feeler gauge. Never pry against the center electrode ceramic. Confirm in your owner's manual.\n\n"
            "[chips: How to clean spark plug | Beat tire pressure | Oil change interval | Maintenance schedule]"
        )
    return (
        "Typical motorcycle spark plug gaps:\n\n"
        "- Standard small motorcycles / underbones: **0.6 – 0.7 mm** (0.024 – 0.028 in)\n"
        "- Modern fuel-injected scooters / extended-reach plugs: **0.8 – 0.9 mm** (0.031 – 0.035 in)\n\n"
        "Check with a wire feeler gauge and confirm your model's exact gap in the owner's manual.\n\n"
        "[chips: Spark plug cleaning | Valve clearance | Oil change interval | Maintenance schedule]"
    )


def get_coolant_spec_answer(query: str, make: str = '', model: str = '', language: str = 'english') -> str:
    q = (query + ' ' + model).lower()
    is_pcx = 'pcx' in q
    if language == 'tagalog':
        return (
            f"Para sa {'Honda PCX 160' if is_pcx else 'liquid-cooled na motor'}, gumamit ng **pre-mixed 50/50 silicate-free at phosphate-free ethylene glycol motorcycle coolant** na ligtas para sa aluminum engine at radiator.\n\n"
            "- **Huwag gumamit:** Karaniwang tubig mula sa gripo (nagdudulot ng kalawang at bara) o automotive coolant na may silicates (nakakasira ng mechanical water pump seal).\n"
            "- Palitan tuwing 2 taon o 24,000 km, at i-check ang reservoir level buwan-buwan habang malamig ang makina. Kumpirmahin ang capacity sa owner's manual.\n\n"
            "[chips: Paano mag-flush ng coolant | Radiator fan check | Engine overheating | Maintenance schedule]"
        )
    return (
        f"For the {'Honda PCX 160' if is_pcx else 'liquid-cooled motorcycles'}, use **pre-mixed 50/50 silicate-free, phosphate-free ethylene glycol coolant** formulated for aluminum motorcycle engines.\n\n"
        "- **What to avoid:** Never use tap water (causes scale buildup and corrosion) or heavy automotive coolants containing silicates (abrasive silicates prematurely wear out the water pump mechanical seal).\n"
        "- Replace every 2 years or 24,000 km, and check cold reservoir level monthly. Confirm capacity in your owner's manual.\n\n"
        "[chips: How to flush coolant | Radiator check | Overheating guide | Maintenance schedule]"
    )


def get_cvt_belt_roller_answer(query: str, make: str = '', model: str = '', language: str = 'english') -> str:
    q = (query + ' ' + model).lower()
    is_click = 'click' in q
    if language == 'tagalog':
        return (
            f"Para sa {'Honda Click 150i' if is_click else 'mga automatic scooter'}:\n\n"
            "- **Inspeksyon ng Belt at Rollers:** Bawat **8,000 km** — linisin ang alikabok sa CVT case at suriin kung may bitak o flat spots ang roller weights.\n"
            "- **Pagpapalit ng Belt:** Karaniwang bawat **16,000 – 24,000 km** (o agad kung may basag, fraying, o manipis na sa service limit).\n"
            "- **Roller Weights:** Palitan kapag hindi na bilog o may flat spots upang hindi maging maalog o tamad ang arangkada.\n\n"
            "Kumpirmahin ang eksaktong sukat at interval sa iyong owner's manual.\n\n"
            "[chips: CVT cleaning guide | Slider piece check | Engine oil change | Full PMS schedule]"
        )
    return (
        f"For the {'Honda Click 150i' if is_click else 'automatic CVT scooters'}:\n\n"
        "- **Inspection interval:** Inspect drive belt and roller weights every **8,000 km** (clean belt dust and inspect for cracking or flat spots).\n"
        "- **Belt replacement:** Typically every **16,000 – 24,000 km** (or earlier if cracks, fraying, or width wear exceeds the service limit).\n"
        "- **Roller weights:** Replace when flat spots appear to prevent sluggish acceleration and clutch shudder.\n\n"
        "Confirm the exact belt width wear limit in your owner's manual.\n\n"
        "[chips: How to clean CVT | Roller weight signs | Oil change schedule | Full maintenance schedule]"
    )


def get_battery_voltage_answer(query: str, language: str = 'english') -> str:
    if language == 'tagalog':
        return (
            "Ang tamang boltahe (voltage) ng 12V motorcycle battery:\n\n"
            "- **Nakatayong makina (key OFF):** **12.6V – 12.8V DC** (100% full charge). Kung 12.0V pababa, kailangan nang i-charge.\n"
            "- **Habang nag-i-start (cranking):** Hindi dapat bumaba sa **10.0V DC** (kung bababa sa 9.5V, mahina na ang baterya).\n"
            "- **Umaandar ang makina (charging at ~3,000–5,000 RPM):** **13.5V – 14.5V DC**.\n"
            "- Kapag lampas 15.0V, overcharging (sira ang regulator/rectifier); kapag mababa sa 13.0V habang umaandar, hindi nagkakarga ang charging system.\n\n"
            "[chips: Battery dead troubleshooting | Stator check | Main fuse check | Maintenance schedule]"
        )
    return (
        "Standard motorcycle 12V battery voltage specifications:\n\n"
        "- **Resting voltage (key OFF):** **12.6V – 12.8V DC** (fully charged). Below 12.0V indicates deep discharge.\n"
        "- **Cranking voltage (starter pressed):** Must remain above **10.0V DC** (drops below 9.5V indicate weakened or sulfated plates).\n"
        "- **Charging voltage (engine at ~3,000–5,000 RPM):** **13.5V – 14.5V DC**.\n"
        "- Over 15.0V indicates overcharging (faulty regulator/rectifier, risks battery boiling); under 13.0V indicates undercharging (stator or rectifier fault).\n\n"
        "[chips: Battery test guide | Stator check | Starter relay check | Full maintenance schedule]"
    )


def get_clutch_cable_answer(query: str, make: str = '', model: str = '', language: str = 'english') -> str:
    q = (query + ' ' + model).lower()
    is_raider = 'raider' in q
    if language == 'tagalog':
        return (
            f"Para sa {'Suzuki Raider 150' if is_raider else 'manual clutch na motor'}:\n\n"
            "- **Tamang Free Play:** **10 – 15 mm** (o 10–20 mm) sa dulo ng clutch lever bago magsimulang humila ang clutch.\n"
            "- **Minor Adjustment:** Gamitin ang barrel adjuster at locknut sa tabi ng clutch lever perch sa handlebar.\n"
            "- **Major Adjustment:** Kung sagad na sa taas, i-adjust ang dalawang nuts sa clutch cable bracket sa kanang bahagi ng makina (crankcase).\n"
            "- Siguraduhing madulas ang hila ng kable at walang napapatid na hibla ng wire. Kumpirmahin sa owner's manual.\n\n"
            "[chips: Clutch slip symptoms | Chain slack adjustment | Engine oil change | Full PMS schedule]"
        )
    return (
        f"Clutch cable free play adjustment {'for Suzuki Raider 150' if is_raider else 'for manual motorcycles'}:\n\n"
        "- **Correct free play:** **10 – 15 mm** (or 10–20 mm) of slack measured at the tip of the clutch lever before engagement begins.\n"
        "- **Minor adjustment:** Turn the knurled barrel adjuster and locknut at the handlebar clutch lever perch.\n"
        "- **Major adjustment:** If the lever adjuster is maxed out, adjust the locking nuts at the clutch cable bracket on the engine crankcase.\n"
        "- Lubricate the inner cable periodically and inspect for frayed wire strands near both cable ends. Confirm specs in your owner's manual.\n\n"
        "[chips: Clutch slipping check | Chain slack check | Oil change interval | Maintenance schedule]"
    )


def get_comparison_answer(query: str, language: str = 'english') -> str:
    q = query.lower()
    if 'aerox' in q and 'nmax' in q:
        if language == 'tagalog':
            return (
                "**Yamaha Aerox 155 vs. Yamaha NMAX 155 — Paghahambing:**\n\n"
                "Parehong gumagamit ng 155cc liquid-cooled 4-valve Blue Core VVA engine (~15.1 hp) at V-belt automatic transmission.\n\n"
                "**Yamaha Aerox 155:**\n"
                "- **Estilo at Porma:** Sporty at aggressive; mas matigas ang rear dual-shock suspension para sa mabilis na cornering.\n"
                "- **Gulong:** Mas malapad (110/80 harap, 140/70 likod).\n"
                "- **Gasolina:** Nasa ilalim ng upuan ang tangke (kailangang buksan ang upuan sa gasolinahan).\n\n"
                "**Yamaha NMAX 155:**\n"
                "- **Kaginhawaan:** Maxi-scooter ergonomics; relaxed ang tapakan at komportable sa malayuang biyahe (touring).\n"
                "- **Features:** Front fuel-filler flap (hindi kailangang buksan ang upuan); Dual-channel ABS at traction control sa higher variants.\n\n"
                "**Alin ang mas maganda?** Piliin ang **NMAX** kung prayoridad mo ang touring, komportableng upo, at daily practicality; piliin ang **Aerox** kung nais mo ang sporty look, agile handling, at aggressive riding.\n\n"
                "[chips: NMAX maintenance schedule | Aerox tire pressure | CVT belt interval | Full maintenance schedule]"
            )
        return (
            "**Yamaha Aerox 155 vs. Yamaha NMAX 155 — Side-by-Side Comparison:**\n\n"
            "Both scooters share Yamaha's proven 155cc 4-valve liquid-cooled Blue Core engine with Variable Valve Actuation (VVA), producing ~15.1 hp.\n\n"
            "**Yamaha Aerox 155:**\n"
            "- **Design & Handling:** Aggressive sport-bike styling, firmer dual rear shocks tuned for agile city cornering, wider tires (110/80 front, 140/70 rear).\n"
            "- **Fuel Tank:** Located under the seat (requires lifting seat to refuel).\n"
            "- **Best For:** Solo riders, sporty commuters, and riders who prefer aggressive aesthetics and sharp handling.\n\n"
            "**Yamaha NMAX 155:**\n"
            "- **Ergonomics & Comfort:** Maxi-scooter upright seating, extended footboards, plush passenger seat, dual-channel ABS and Traction Control on top variants.\n"
            "- **Fuel Tank:** Front-access fuel flap on the center tunnel (no need to lift seat at gas stations).\n"
            "- **Best For:** Daily commuters, two-up riding, and long-distance touring.\n\n"
            "**Verdict:** Choose the **NMAX** for touring comfort, passenger ease, and convenience; choose the **Aerox** for sporty styling, sharper cornering, and athletic road presence.\n\n"
            "[chips: NMAX maintenance interval | Aerox tire pressure | CVT belt replacement | Full schedule]"
        )
    return (
        "When comparing motorcycles, the best choice depends on your riding style, budget, and daily commute:\n\n"
        "1. **Engine & Transmission:** Automatic CVT scooters offer easy city riding; manual underbones/backbones offer higher fuel efficiency and precise gear control.\n"
        "2. **Ergonomics:** Upright seating and step-through frames are best for traffic; firm suspensions suit aggressive cornering.\n"
        "3. **Practicality:** Check under-seat storage, fuel tank capacity, and local parts availability.\n\n"
        "Tell me which two models you want to compare and I'll break down specs and pros/cons!\n\n"
        "[chips: Aerox vs NMAX | Click 125i vs Beat | Beginner bike guide | Maintenance schedule]"
    )


def get_model_info_answer(query: str, language: str = 'english') -> str:
    q = query.lower()
    if 'click' in q:
        if language == 'tagalog':
            return (
                "**Honda Click 125i — Impormasyon at Buod:**\n\n"
                "- **Makina:** 124.8cc liquid-cooled, 4-stroke SOHC eSP (enhanced Smart Power) PGM-FI engine (~11.1 hp, 10.8 Nm torque).\n"
                "- **Transmission:** V-Matic automatic CVT (belt drive).\n"
                "- **Pangunahing Features:** Full digital meter panel, all-LED lighting, Combi-Brake System (CBS), 18-litrong under-seat utility box, tubeless tires.\n"
                "- **Tipid sa Gasolina:** Karaniwang **50 – 53 km/L** sa normal na pagmamaneho sa lungsod.\n"
                "- **Maintenance:** Engine oil palitan bawat 2,000–3,000 km, CVT inspection bawat 8,000 km, coolant check buwan-buwan.\n"
                "- **Para kanino ito:** Tamang-tama para sa araw-araw na city commuter, madaling imaneho, at napakatipid panatilihin.\n\n"
                "[chips: Click 125i oil change | CVT belt interval | Spark plug check | Full PMS schedule]"
            )
        return (
            "**Honda Click 125i — Overview and Key Details:**\n\n"
            "- **Engine & Powertrain:** 124.8cc liquid-cooled 4-stroke SOHC eSP (enhanced Smart Power) PGM-FI engine producing ~11.1 hp and 10.8 Nm of torque, paired with a V-Matic automatic CVT.\n"
            "- **Key Features:** Full digital instrument cluster, all-LED headlight and tail light, Combi-Brake System (CBS), 18-liter under-seat utility compartment, tubeless tires, and idling stop system (on select variants).\n"
            "- **Fuel Economy:** Averages **50 – 53 km/L** under typical mixed city commuting conditions.\n"
            "- **Maintenance Baselines:** Oil change every 2,000–3,000 km (JASO MB), CVT inspection and cleaning every 8,000 km, and cold coolant checks monthly.\n"
            "- **Target Rider:** One of the most popular and reliable daily commuters in Southeast Asia, known for low operating costs and accessible handling.\n\n"
            "[chips: Click 125i oil interval | CVT belt interval | Spark plug gap | Full maintenance schedule]"
        )
    return (
        "I can provide technical overviews, engine specifications, maintenance intervals, and pros/cons for any motorcycle model. "
        "Which specific model would you like to know about? (e.g. Honda Click 125i, Yamaha NMAX 155, Honda Beat, Suzuki Raider 150).\n\n"
        "[chips: Tell me about Click 125i | Tell me about NMAX | Tell me about Beat | Raider 150 specs]"
    )


def get_beginner_bike_answer(language: str = 'english') -> str:
    if language == 'tagalog':
        return (
            "**Mga Inirerekomendang Motor para sa Baguhan (Beginners):**\n\n"
            "1. **Honda Beat 110 (Automatic Scooter):**\n"
            "   - Sobrang magaan (~90 kg) at mababa ang upuan (seat height) kaya madaling itukod ang dalawang paa.\n"
            "   - Matipid sa gas (~58 km/L) at mura ang piyesa.\n\n"
            "2. **Honda Click 125i (Automatic Scooter):**\n"
            "   - Napakagandang balanse ng lakas, liquid-cooled engine, at 18L storage. Maaasahang pang-araw-araw na motor.\n\n"
            "3. **Yamaha Mio Gear / Sporty:**\n"
            "   - Compact, maliksi sa trapiko, at madaling maniobrahin.\n\n"
            "4. **Honda Wave 110 o TMX 125 (Kung gustong matuto ng de-kambyo):**\n"
            "   - Subok na tibay, madaling ayusin, at matipid sa maintenance.\n\n"
            "**Mahahalagang Pamantayan:** Piliin ang magaan, abot ng paa ang lupa, mura ang pyesa, at madaling kontrolin ang arangkada.\n\n"
            "[chips: Anong helmet ang bibilhin? | Tamang tire pressure | Change oil schedule | Paano mag-break-in?]"
        )
    return (
        "**Best Motorcycles for Beginners:**\n\n"
        "1. **Honda Beat 110 (Automatic Scooter):**\n"
        "   - Ultra-lightweight (~90 kg) with an accessible low seat height allowing both feet flat on the ground.\n"
        "   - Outstanding fuel economy (~58 km/L) and very affordable replacement parts.\n\n"
        "2. **Honda Click 125i (Automatic Scooter):**\n"
        "   - Excellent balance of 125cc power, liquid-cooled reliability, and 18-liter under-seat storage.\n\n"
        "3. **Yamaha Mio Gear (Automatic Scooter):**\n"
        "   - Compact, rugged chassis, and nimble handling in tight traffic.\n\n"
        "4. **Honda Wave 110 or TMX 125 (For Manual / Semi-Automatic Learning):**\n"
        "   - Bulletproof durability, forgiving clutch, and ubiquitous parts availability.\n\n"
        "**Key buying advice:** Prioritize lightweight curb weight, approachable seat height, accessible parts, and progressive throttle response.\n\n"
        "[chips: What helmet should I buy? | How to ride in rain | Oil change interval | Maintenance schedule]"
    )


def get_riding_gear_answer(language: str = 'english') -> str:
    if language == 'tagalog':
        return (
            "**Gabay sa Riding Gear at Helmet para sa Kaligtasan:**\n\n"
            "1. **Helmet (Pinakamahalaga):**\n"
            "   - Pumili ng **Full-face** o **Modular** helmet na may lehitimong safety certification: **ECE 22.06** (pinakabagong pamantayan ng Europa), **DOT**, o **Snell** (at may ICC/BPS sticker sa Pilipinas).\n"
            "   - Siguraduhing sakto (snug fit) sa pisngi at noo; hindi dapat umiikot ang helmet kapag ginalaw ang ulo.\n\n"
            "2. **Riding Jacket:** Jacket na may CE-rated armor sa siko, balikat, at likod para sa proteksyon sa impact at gasgas.\n"
            "3. **Gloves:** Full-finger gloves na may palm slider at knuckle protection.\n"
            "4. **Sapatos / Bota:** Saradong sapatos na lampas sa bukong-bukong (ankle protection); huwag magtsinelas o sapatos na madulas.\n"
            "5. **Prinsipyong ATGATT:** *All The Gear, All The Time* — magsuot ng kumpletong proteksyon kahit sa maikling biyahe.\n\n"
            "[chips: Paano sumakay sa ulan? | Tamang tire pressure | Brake check guide | Maintenance schedule]"
        )
    return (
        "**Riding Gear & Helmet Safety Guide:**\n\n"
        "1. **Helmet (Most Critical):**\n"
        "   - Choose a **Full-face** or **Modular** helmet certified to **ECE 22.06** (latest and strictest standard), **DOT**, or **Snell** (with legitimate ICC/BPS validation in the Philippines).\n"
        "   - Fit: Must be snug without painful pressure points; your cheeks should be lightly pressed and the helmet should not twist on your head.\n\n"
        "2. **Riding Jacket:** Abrasion-resistant jacket equipped with CE-rated impact armor at the elbows, shoulders, and back.\n"
        "3. **Gloves:** Dedicated motorcycle gloves with abrasion-resistant palm sliders and knuckle guards.\n"
        "4. **Footwear:** Over-the-ankle sturdy riding shoes or boots with reinforced soles and heel cups. Never ride in slippers or canvas sneakers.\n"
        "5. **Follow ATGATT:** *All The Gear, All The Time* — road hazards and falls can happen at any speed or distance.\n\n"
        "[chips: How to ride in the rain | Beginner motorcycle guide | Brake safety check | Full maintenance schedule]"
    )


def get_rain_riding_answer(language: str = 'english') -> str:
    if language == 'tagalog':
        return (
            "**Gabay sa Ligtas na Pagmamaneho sa Ulan (Rain Riding):**\n\n"
            "1. **Makinis at Mabagal na Kontrol:** Iwasan ang biglaang pagpiga ng silinyador o madiing pagpreno. Magpreno nang maaga at dahan-dahan gamit ang harap at likod na preno nang sabay.\n"
            "2. **Iwasan ang Madudulas na Lugar:**\n"
            "   - Pintura sa kalsada (pedestrian lanes, linya)\n"
            "   - Bakal na manhole covers at drainage grates\n"
            "   - Makukulay na oil slicks sa gitna ng lane kapag bagong buhos ang ulan.\n"
            "3. **Doblehin ang Distansya:** Panatilihin ang 4–6 segundong agwat sa sinusundang sasakyan upang may sapat na distansya sa paghinto.\n"
            "4. **Kondisyon ng Gulong:** Tiyaking may sapat na tread depth (hindi pudpod, higit sa 2.0 mm) at tamang presyon ng hangin upang maiwasan ang hydroplaning.\n"
            "5. **Proteksyon at Visor:** Magsuot ng high-visibility rain suit at panatilihing malinaw ang helmet visor gamit ang anti-fog treatment o Pinlock lens.\n\n"
            "[chips: Tamang tire pressure | Brake check guide | Chain maintenance | Full PMS schedule]"
        )
    return (
        "**Safe Motorcycle Riding in Wet & Rainy Conditions:**\n\n"
        "1. **Smooth, Progressive Inputs:** Avoid sudden throttle twists or abrupt braking. Brake earlier and progressively using both front and rear brakes smoothly.\n"
        "2. **Watch Slippery Road Hazards:**\n"
        "   - Painted road markings (crosswalks and lane lines)\n"
        "   - Metal manhole covers and bridge expansion joints\n"
        "   - Rainbow sheen oil slicks that rise to the surface during the first 15 minutes of rain.\n"
        "3. **Double Following Distance:** Increase following distance to 4–6 seconds to account for increased stopping distance on wet pavement.\n"
        "4. **Tire Tread & Pressure:** Verify tires have at least 2.0 mm of tread depth and are set to recommended cold tire pressure to channel water away and avoid hydroplaning.\n"
        "5. **Visibility:** Wear high-visibility waterproof rain gear and use an anti-fog Pinlock visor to prevent breath fogging inside the helmet.\n\n"
        "[chips: Tire pressure check | Brake check guide | Chain care after rain | Full maintenance schedule]"
    )


def get_oil_type_answer(make: str = '', model: str = '', language: str = 'english') -> str:
    if language == 'tagalog':
        return (
            "**Inirerekomendang Uri ng Langis ng Makina (Engine Oil Type):**\n\n"
            "- **Para sa De-kambyo / Manual na Motor (Wet Clutch, hal. TMX, Raider, Wave, Barako):**\n"
            "  - Gumamit ng **JASO MA** o **JASO MA2** 4T motorcycle oil. Ang MA rating ay tinitiyak na hindi magpapadulas sa wet clutch plates.\n"
            "- **Para sa Automatic Scooters (Dry CVT Clutch, hal. Click, NMAX, Aerox, Beat):**\n"
            "  - Gumamit ng **JASO MB** (o JASO MA2) 4T oil. Ang MB rating ay may friction modifiers para sa mas magandang fuel economy dahil hiwalay ang clutch sa CVT.\n"
            "- **Viscosity:** Karaniwang **10W-40** para sa klima sa Pilipinas (o 10W-30 kung nakasaad sa manual).\n"
            "- Huwag gumamit ng automotive car oil na may label na 'Energy Conserving' dahil magdudulot ito ng clutch slip.\n\n"
            "[chips: Kailan magpapalit ng oil filter? | Oil change interval | Paano magpalit ng langis? | Full PMS schedule]"
        )
    return (
        "**Recommended Engine Oil Specifications:**\n\n"
        "- **For Manual / Underbone motorcycles (Wet Clutch, e.g. TMX, Raider, Wave):**\n"
        "  - Use **JASO MA** or **JASO MA2** 4T motorcycle oil. The MA rating guarantees friction characteristics that prevent wet clutch slippage.\n"
        "- **For Automatic Scooters (Dry CVT Clutch, e.g. Click, NMAX, Aerox, Beat):**\n"
        "  - Use **JASO MB** (or JASO MA2) 4T oil. JASO MB contains friction modifiers designed to maximize fuel efficiency since the clutch runs dry inside the CVT.\n"
        "- **Viscosity Grade:** **10W-40** is the standard multi-grade specification for tropical climates (or 10W-30 per manufacturer spec).\n"
        "- Never use 'Energy Conserving' automotive car oils in a wet-clutch manual motorcycle.\n\n"
        "[chips: What about the filter? | Oil change interval | How to change oil | Full maintenance schedule]"
    )


def get_oil_filter_answer(make: str = '', model: str = '', language: str = 'english') -> str:
    if language == 'tagalog':
        return (
            "**Gabay sa Oil Filter ng Motor:**\n\n"
            "- **Kailan pinapalitan:** Palitan ang oil filter sa bawat change oil, o kahit bawat pangalawang change oil (tuwing **4,000 – 8,000 km**).\n"
            "- **Uri:** Karamihan ay paper cartridge element sa ilalim ng side engine cover na may 2 o 3 bolts, o spin-on canister.\n"
            "- **Mahalagang Hakbang:** Palaging palitan ang rubber O-ring sa takip ng filter at pahiran ng kaunting sariwang langis bago ikabit.\n"
            "- Higpitan nang katamtaman (karaniwang 8–12 Nm) upang hindi maputol ang thread sa aluminum crankcase. Kumpirmahin sa manual.\n\n"
            "[chips: Anong oil type ang gagamitin? | Oil change interval | Paano magpalit ng langis? | Full PMS schedule]"
        )
    return (
        "**Motorcycle Oil Filter Guide:**\n\n"
        "- **Replacement interval:** Replace the oil filter every engine oil change, or at least every second oil change (every **4,000 – 8,000 km**).\n"
        "- **Filter types:** Most modern bikes use an internal paper cartridge filter housed behind an engine side cover secured by 2–3 bolts, while some larger bikes use external spin-on canisters.\n"
        "- **Installation best practices:** Always inspect and replace the rubber O-ring gasket on the filter cover, coat the O-ring with clean fresh oil, and insert the pleated filter in the correct direction (open grommet toward engine inlet).\n"
        "- Torque cover bolts gently (typically 8–12 Nm) to avoid stripping the aluminum crankcase threads.\n\n"
        "[chips: What oil type should I use? | How often to change oil | How to change oil | Full maintenance schedule]"
    )


def get_tire_pressure_answer(query: str, make: str = '', model: str = '', language: str = 'english') -> str:
    q = (query + ' ' + model).lower()
    is_nmax = 'nmax' in q
    if language == 'tagalog':
        if is_nmax:
            return (
                "Para sa **Yamaha NMAX 155**, ang inirerekomendang malamig na tire pressure (cold tire pressure):\n\n"
                "- **Harap (Front):** **22 psi** (solo) hanggang **29 psi**\n"
                "- **Likod (Rear):** **33 psi** (solo) o **36 psi** (may angkas o kargada)\n\n"
                "Sukatin tuwing malamig ang gulong (bago bumiyahe) gamit ang tumpak na tire pressure gauge. Tingnan din ang tire label sticker sa rear fender ng iyong NMAX.\n\n"
                "[chips: Gulong inspection guide | Brake check guide | Change oil schedule | Full PMS schedule]"
            )
        return (
            "Ang karaniwang malamig na tire pressure (cold tire pressure) para sa mga motor at scooter:\n\n"
            "- **Harap (Front):** **28 – 30 psi**\n"
            "- **Likod (Rear):** **32 – 34 psi** (solo) / **36 psi** (may angkas)\n\n"
            "Laging sukatin habang malamig ang gulong bago bumiyahe. Kumpirmahin ang eksaktong numero sa sticker sa swingarm o owner's manual.\n\n"
            "[chips: NMAX tire pressure | Gulong inspection | Brake check | Full maintenance schedule]"
        )
    if is_nmax:
        return (
            "Recommended cold tire pressure for the **Yamaha NMAX 155**:\n\n"
            "- **Front tire:** **22 psi** (standard solo) up to **29 psi**\n"
            "- **Rear tire:** **33 psi** (solo rider) / **36 psi** (with passenger or cargo)\n\n"
            "Always measure tire pressures when tires are completely cold. Confirm the exact tire specification on the swingarm or rear fender decal of your NMAX.\n\n"
            "[chips: Tire inspection guide | Brake pad check | Oil change interval | Full maintenance schedule]"
        )
    return (
        "Typical motorcycle cold tire pressures:\n\n"
        "- **Front tire:** **28 – 30 psi** (underbones/scooters)\n"
        "- **Rear tire:** **32 – 34 psi** (solo) / **36 psi** (with pillion passenger)\n\n"
        "Check weekly using a calibrated tire pressure gauge when the rubber is cold. Confirm on the swingarm decal or in your owner's manual.\n\n"
        "[chips: NMAX tire pressure | Tire wear check | Brake check | Full maintenance schedule]"
    )


def get_traffic_overheat_answer(query: str, make: str = '', model: str = '', language: str = 'english') -> str:
    if language == 'tagalog':
        return (
            "> [!CAUTION]\n"
            "> **BABALA SA KALIGTASAN:** Huwag na huwag buksan ang radiator cap habang mainit ang makina. Maaaring sumabog ang kumukulong coolant at magdulot ng malubhang paso.\n\n"
            "Kapag nag-o-overheat ang motor tuwing traffic o mabagal ang takbo, ito ang mga pangunahing dapat suriin:\n\n"
            "1. **Radiator Fan:** Umiikot ba ang radiator fan kapag mainit na ang makina? Kung hindi, suriin ang fan motor, fuse, at radiator thermo-switch.\n"
            "2. **Lebel ng Coolant:** Tiyaking nasa pagitan ng LOW at FULL ang coolant sa reservoir tank (suriin habang malamig ang makina).\n"
            "3. **Radiator Fins:** Baka barado ng tuyong putik o dumi ang mga fins ng radiator kaya walang hanging dumadaan habang nakatigil sa traffic.\n"
            "4. **Water Pump at Thermostat:** Siguraduhing umiikot ang coolant at bumubukas ang thermostat valve kapag mainit na ang makina.\n"
            "5. **Lebel ng Langis ng Makina:** Ang mababang lebel ng langis ay nagdudulot ng matinding friction at init sa makina.\n\n"
            "[chips: Paano mag-flush ng coolant | Radiator fan check | Engine oil check | Maintenance schedule]"
        )
    return (
        "> [!CAUTION]\n"
        "> **SAFETY ALERT:** Never open the radiator cap or coolant reservoir while the engine is hot. Boiling pressurized coolant will violently erupt causing severe scald burns.\n\n"
        "When a liquid-cooled motorcycle overheats specifically in heavy traffic or at idle, check these primary causes:\n\n"
        "1. **Radiator Cooling Fan:** Does the electric fan spin when the engine reaches operating temperature? If not, inspect the fan fuse, relay, fan motor, and thermo-switch.\n"
        "2. **Coolant Level:** Inspect the translucent expansion reservoir (cold engine only). Low coolant causes air pockets and rapid overheating.\n"
        "3. **Clogged Radiator Fins:** External mud, road grime, or bent cooling fins prevent airflow through the radiator core when the bike is not moving.\n"
        "4. **Water Pump & Thermostat:** A stuck-closed thermostat or worn water pump impeller restricts circulation through the cooling jackets.\n"
        "5. **Engine Oil Level:** Low engine oil removes internal lubrication and heat dissipation, worsening cooling load.\n\n"
        "[chips: How to check radiator fan | Coolant flush guide | Engine oil check | Full maintenance schedule]"
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_offline_answer(message, language='english'):
    """
    Return a rider-friendly offline answer for the given message, or None
    if no specific template matches (caller should fall back further).
    Language is 'english', 'tagalog', or 'hiligaynon'.
    """
    msg = (message or '').lower()
    lang = language if language in ('english', 'tagalog', 'hiligaynon') else 'english'

    # --- Tagalog/Hiligaynon common keyword normalisations ---
    tl_map = {
        'nag-ooverheat': 'overheat',
        'uminit ang': 'overheat',
        'sobrang init': 'overheat',
        'presyon ng gulong': 'tire pressure',
        'tamang presyon': 'tire pressure',
        'palitan ng langis': 'oil change',
        'palit ng langis': 'oil change',
        'palitan ng spark plug': 'spark plug',
        'clutch cable': 'clutch cable adjustment',
        'sukatin ang valve': 'valve clearance',
    }
    for tl, en in tl_map.items():
        if tl in msg:
            msg = msg.replace(tl, en)

    # 1. Comparison: "aerox vs nmax", "which is better"
    if re.search(r'\b(?:vs|versus|compare|comparison)\b', msg) or ('better' in msg and any(b in msg for b in ['aerox', 'nmax', 'click', 'beat', 'raider', 'sniper'])):
        return get_comparison_answer(msg, language=lang)

    # 2. Model info: "tell me about click 125i"
    if re.search(r'\b(?:tell me about|about the|overview of|ano ang|unsa ang)\b', msg) and any(m in msg for m in ['click', 'nmax', 'aerox', 'beat', 'raider', 'tmx', 'barako', 'pcx']):
        return get_model_info_answer(msg, language=lang)

    # 3. Buying / beginner
    if re.search(r'\b(?:beginner|starter bike|first bike|buy|recommend|best for|baguhan|simula)\b', msg) and not any(k in msg for k in ['helmet', 'gear']):
        return get_beginner_bike_answer(language=lang)

    # 4. Riding gear / helmet
    if re.search(r'\b(?:helmet|gear|gloves|jacket|boots|riding gear|safety gear|suot)\b', msg):
        return get_riding_gear_answer(language=lang)

    # 5. Rain riding
    if re.search(r'\b(?:rain|ulan|wet|slippery|basa)\b', msg):
        return get_rain_riding_answer(language=lang)

    # 6. Valve clearance
    if 'valve' in msg and ('clearance' in msg or 'gap' in msg or 'adjust' in msg):
        return get_valve_clearance_answer(msg, language=lang)

    # 7. Spark plug gap
    if 'plug' in msg and ('gap' in msg or 'spark' in msg):
        return get_spark_plug_gap_answer(msg, language=lang)

    # 8. Coolant / coolant spec
    if re.search(r'\b(?:coolant|antifreeze|anti-freeze|radiator fluid|cooling fluid)\b', msg):
        return get_coolant_spec_answer(msg, language=lang)

    # 9. CVT belt / roller
    if 'cvt' in msg or ('belt' in msg and any(k in msg for k in ['roller', 'replace', 'change', 'interval', 'click', 'scooter', 'nmax', 'aerox'])):
        return get_cvt_belt_roller_answer(msg, language=lang)

    # 10. Battery charging / voltage
    if 'battery' in msg and any(k in msg for k in ['voltage', 'charging', 'multimeter', 'volts', '12v', 'spec']):
        return get_battery_voltage_answer(msg, language=lang)

    # 11. Clutch cable adjustment
    if 'clutch' in msg and any(k in msg for k in ['cable', 'adjust', 'free play', 'freeplay']):
        return get_clutch_cable_answer(msg, language=lang)

    # 12. Tire pressure
    if re.search(r'\b(?:tire pressure|tyre pressure|presyon|hangin)\b', msg) or ('pressure' in msg and any(k in msg for k in ['tire', 'tyre', 'nmax', 'click', 'beat'])):
        return get_tire_pressure_answer(msg, language=lang)

    # 13. Traffic overheat
    if 'overheat' in msg and any(k in msg for k in ['traffic', 'idle', 'stop and go', 'nakahinto']):
        return get_traffic_overheat_answer(msg, language=lang)

    # 14. Oil filter
    if 'oil filter' in msg or ('filter' in msg and 'oil' in msg):
        return get_oil_filter_answer(language=lang)

    # 15. Oil type / oil grade
    if 'oil' in msg and any(k in msg for k in ['type', 'grade', 'viscosity', 'jaso', 'what oil', 'which oil', 'langis']):
        return get_oil_type_answer(language=lang)

    return None
