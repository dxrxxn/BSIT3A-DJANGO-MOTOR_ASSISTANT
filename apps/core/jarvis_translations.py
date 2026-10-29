"""
Localized J.A.R.V.I.S. offline fallback texts (Tagalog/Taglish + Hiligaynon).

The offline rule-based engine in apps.core.views returns English narratives by
default. For every key in BRANCH_TEXTS, a Tagalog (tl) and Hiligaynon (hil)
variant is offered. Technical checklist steps stay in English — that is natural
Taglish/Ilonggo mechanic style — while narrative lines, safety warnings and
action chips are localized.

Placeholders: {sir} (user's first name or 'sir'), {veh} (vehicle label),
{count} (stats queries only).
"""

BRANCH_TEXTS = {
    # ───────────────────────── Brakes (vehicle known) ─────────────────────────
    'brake_bleed': {
        'tl': (
            "Kumpirmadong pagsusuri para sa **{veh}** mo, {sir}:\n\n"
            "**Pinaka-malamang na sanhi:** Naipit na hangin sa hydraulic brake line o mayam-ang na ang brake fluid (Confidence: High).\n"
            "**Bakit nangyayari ito:** Naipit ang hangin, kaya naibibigay ng lever ang presyon sa hangin imbes na sa brake fluid — kaya malambot o spongy ang preno.\n\n"
            "**Mga kailangang gamit at materyales:**\n"
            "- 8mm o 10mm box wrench\n"
            "- Panibagong DOT 4 brake fluid (hindi pa nabubuksan)\n"
            "- Malinaw na 1/4-inch vinyl tubing at malinis na sisidlan\n"
            "- JIS / Phillips screwdriver at lint-free shop towels\n\n"
            "**Hakbang-hakbang na pag-bleed ng preno:**\n"
            "- [ ] 1. Park vehicle on level ground and turn handlebars until master cylinder reservoir is perfectly horizontal.\n"
            "- [ ] 2. Wipe reservoir cap clean; remove 2 screws, cover, and rubber diaphragm.\n"
            "- [ ] 3. Inspect fluid level and color (dark amber or cloudy indicates moisture contamination).\n"
            "- [ ] 4. Slip 8mm box wrench over caliper bleeder nipple, then attach clear vinyl tubing routed into catch bottle.\n"
            "- [ ] 5. Top up reservoir to UPPER line with fresh DOT 4 fluid.\n"
            "- [ ] 6. Slowly pump brake lever 3 to 4 times, then hold squeezed firmly against handlebar grip.\n"
            "- [ ] 7. Crack bleeder nipple open 1/4 turn for 1 second; observe fluid and air bubbles in tubing, then snug nipple shut BEFORE releasing lever.\n"
            "- [ ] 8. Repeat pump-hold-bleed cycle until only clear fluid emerges with zero air bubbles.\n"
            "- [ ] 9. Verify lever resistance is firm and solid, top reservoir to upper level, and replace diaphragm/cap.\n\n"
            "**PAALALA SA KALIGTASAN:** Siguraduhing matigas ang lever sa loob ng 60 segundo habang nakahinto ang sasakyan. Kapag unti-unting lumulubog, suriin ang master cylinder piston cup seals o caliper piston seals.\n\n"
            "[chips: Anong brake fluid ang gagamitin? | Paano suriin ang brake pads | Matigas na ang lever ko | Suriin ang brake disc rotor]"
        ),
        'hil': (
            "Kumpirmasyon sang pagsusuri para sa **{veh}** mo, {sir}:\n\n"
            "**Pinakamaluluparan nga kasulundan:** Ngaipit nga hangin sa hydraulic brake line ukon mayamo na ang brake fluid (Confidence: High).\n"
            "**Ngaa:** Ang hangin nga ngaipit nagakuha sing presyon halin sa lever, indi ang brake fluid — sining nga rason kon ngaa humok ang preno.\n\n"
            "**Mga kinahanglan nga higug ug materyales:**\n"
            "- 8mm ukon 10mm box wrench\n"
            "- Bag-o nga DOT 4 brake fluid (wala pa ginabuksan)\n"
            "- Malimsag nga 1/4-inch vinyl tubing kag malinis nga sisidlan\n"
            "- JIS / Phillips screwdriver kag lint-free shop towels\n\n"
            "**Sunod-sunod nga pag-bleed sang preno:**\n"
            "- [ ] 1. Park vehicle on level ground and turn handlebars until master cylinder reservoir is perfectly horizontal.\n"
            "- [ ] 2. Wipe reservoir cap clean; remove 2 screws, cover, and rubber diaphragm.\n"
            "- [ ] 3. Inspect fluid level and color (dark amber or cloudy indicates moisture contamination).\n"
            "- [ ] 4. Slip 8mm box wrench over caliper bleeder nipple, then attach clear vinyl tubing routed into catch bottle.\n"
            "- [ ] 5. Top up reservoir to UPPER line with fresh DOT 4 fluid.\n"
            "- [ ] 6. Slowly pump brake lever 3 to 4 times, then hold squeezed firmly against handlebar grip.\n"
            "- [ ] 7. Crack bleeder nipple open 1/4 turn for 1 second; observe fluid and air bubbles in tubing, then snug nipple shut BEFORE releasing lever.\n"
            "- [ ] 8. Repeat pump-hold-bleed cycle until only clear fluid emerges with zero air bubbles.\n"
            "- [ ] 9. Verify lever resistance is firm and solid, top reservoir to upper level, and replace diaphragm/cap.\n\n"
            "**PAHILIG-AN SA KALIGTASAN:** Siguruha nga matig-a ang lever sa sulod sing 60 segundo samtang napatdong ang salakyan. Kon nagaubod-ubod, usisa-on ang master cylinder piston cup seals ukon caliper piston seals.\n\n"
            "[chips: Ano nga brake fluid ang gamiton? | Paano usisahon ang brake pads | Matig-a na ang lever ko | Usisahon ang brake disc rotor]"
        ),
    },
    'brake_squeal': {
        'tl': (
            "Pagsusuri sa ingay ng preno para sa **{veh}** mo, {sir}.\n\n"
            "**Pinaka-malamang na sanhi:** Glazed brake pads o makikintab na road dust na naipit sa pagitan ng pads at rotor (Confidence: High).\n\n"
            "**Hakbang-hakbang na pagsusuri:**\n"
            "- [ ] 1. Remove caliper mounting bolts and slide caliper off brake rotor disc.\n"
            "- [ ] 2. Measure brake pad friction material thickness (replace if under 2.0 mm).\n"
            "- [ ] 3. Thoroughly spray rotor disc and caliper body with dedicated residue-free brake cleaner.\n"
            "- [ ] 4. Place 240-grit sandpaper on a flat surface; lightly scuff glazed shiny surface of brake pads in a figure-8 pattern.\n"
            "- [ ] 5. Apply a tiny smear of high-temp copper anti-seize paste to pad backing plate contact points (never on friction side).\n"
            "- [ ] 6. Reinstall caliper and torque mounting bolts to factory specification (25–30 Nm).\n\n"
            "[chips: Malambot o spongy ang preno | May metal na kagat-kagat | Listahan ng lahat ng pyesa]"
        ),
        'hil': (
            "Pagsusuri sang huni sang preno para sa **{veh}** mo, {sir}.\n\n"
            "**Pinakamaluluparan nga kasulundan:** Glazed brake pads ukon lapta nga road dust sa tunga sang pads kag rotor (Confidence: High).\n\n"
            "**Sunod-sunod nga pagsusuri:**\n"
            "- [ ] 1. Remove caliper mounting bolts and slide caliper off brake rotor disc.\n"
            "- [ ] 2. Measure brake pad friction material thickness (replace if under 2.0 mm).\n"
            "- [ ] 3. Thoroughly spray rotor disc and caliper body with dedicated residue-free brake cleaner.\n"
            "- [ ] 4. Place 240-grit sandpaper on a flat surface; lightly scuff glazed shiny surface of brake pads in a figure-8 pattern.\n"
            "- [ ] 5. Apply a tiny smear of high-temp copper anti-seize paste to pad backing plate contact points (never on friction side).\n"
            "- [ ] 6. Reinstall caliper and torque mounting bolts to factory specification (25–30 Nm).\n\n"
            "[chips: Humok ukon spongy ang preno | May metal nga kagat-kagat | Listahan sang tanan nga pyesa]"
        ),
    },
    'brake_grinding': {
        'tl': (
            "**MAHIGPIT NA BABALA SA KALIGTASAN, {sir}.** Lubos nang gasgas ang friction material sa **{veh}** mo.\n\n"
            "Ang steel backing plate ay kumakaskas nang diretso sa brake rotor disc. Huwag nang ituloy ang paggamit.\n\n"
            "**Mga hakbang na agad-agad:**\n"
            "- [ ] 1. Stop riding immediately — continued operation will score and destroy the rotor disc.\n"
            "- [ ] 2. Remove caliper retaining pins and extract worn brake pads.\n"
            "- [ ] 3. Inspect rotor surface for deep grooving or blue heat discoloration (replace rotor if thickness < 3.0mm).\n"
            "- [ ] 4. Clean caliper piston walls and gently push pistons back into caliper housing.\n"
            "- [ ] 5. Install fresh sintered or semi-metallic brake pads and secure retaining clips.\n\n"
            "[chips: Suriin ang buong brake system | Listahan ng lahat ng pyesa | Anong mga gamit ang kailangan?]"
        ),
        'hil': (
            "**KUSOG NGA PAHILING SA KALIGTASAN, {sir}.** Ubos na ang friction material sa **{veh}** mo.\n\n"
            "Ang steel backing plate nagaiskrak na diretso sa brake rotor disc. Indi na it pagpadayon nga gamiton.\n\n"
            "**Mga lakat dayon-dayon:**\n"
            "- [ ] 1. Stop riding immediately — continued operation will score and destroy the rotor disc.\n"
            "- [ ] 2. Remove caliper retaining pins and extract worn brake pads.\n"
            "- [ ] 3. Inspect rotor surface for deep grooving or blue heat discoloration (replace rotor if thickness < 3.0mm).\n"
            "- [ ] 4. Clean caliper piston walls and gently push pistons back into caliper housing.\n"
            "- [ ] 5. Install fresh sintered or semi-metallic brake pads and secure retaining clips.\n\n"
            "[chips: Usisahon ang buo nga preno | Listahan sang tanan nga pyesa | Ano nga mga higug ang kinahanglan?]"
        ),
    },
    'brake_generic_known': {
        'tl': (
            "Handa na ang pagsusuri ng preno para sa **{veh}** mo, {sir}. Anong partikular na sintomas nararamdaman mo?\n\n"
            "[chips: Malambot o spongy ang lever | Mayumid o mataas na ingay | May metal na kagat-kagat | Lumulubog ang lever hanggang dulo]"
        ),
        'hil': (
            "Andam na ang pagsusuri sang preno para sa **{veh}** mo, {sir}. Ano nga pigtak nga sintomas ang imo naagyan?\n\n"
            "[chips: Humok ukon spongy ang lever | May nagapiti-piti | May metal nga kagat-kagat | Nagadul-ong ang lever tubtob sa duluhan]"
        ),
    },

    # ───────────────────────── Starting (vehicle known) ───────────────────────
    'start_known': {
        'tl': (
            "Naka-engrande na ang diagnostic protocol para sa **{veh}** mo, {sir}.\n\n"
            "Para agad matukoy ang sira — **ano ang nangyayari kapag pinipindot mo ang starter?**\n\n"
            '[vehicle-form: {"category": "start"}]\n'
            "[chips: Mabilisang nitik | Umiikot normal pero hindi masindihan | Mahinang pag-crank | Patay lahat - walang ilaw]"
        ),
        'hil': (
            "Nakahanda na ang diagnostic protocol para sa **{veh}** mo, {sir}.\n\n"
            "Agud madasig mabisto ang sira — **ano ang nagakahinabo kon pinduton mo ang starter?**\n\n"
            '[vehicle-form: {"category": "start"}]\n'
            "[chips: Madasig nga lagatik | Normal mag-tiog pero indi maglunsar | Mahinay mag-tiog | Patay tanan - wala sing suga]"
        ),
    },
    'start_clicking': {
        'tl': (
            "Pagsusuri sa pagsisimula, {sir}. **Starter Solenoid Relay Chatter** ang naririnig natin.\n\n"
            "**Sanhi:** May sapat na boltahe ang baterya para isara ang relay, ngunit kapag humingi na ng 50–80 Amps ang starter motor, bumabagsak ang boltahe sa ibaba ng 10.5V. Naire-release ang coil, bumabalik ang boltahe, at paulit-ulit itong nitik nang mabilis.\n\n"
            "**Hakbang-hakbang na pagsusuri:**\n"
            "- [ ] 1. Switch ignition OFF and inspect 10mm battery terminal bolts for loose fitment or white sulfate corrosion.\n"
            "- [ ] 2. Measure resting voltage with a multimeter (Healthy: 12.6V+; Discharged: < 12.0V).\n"
            "- [ ] 3. Measure battery terminal voltage while holding starter button (if it plunges below 9.6V, battery cells are degraded).\n"
            "- [ ] 4. Check negative ground cable bolted to engine casing for loose bolt or paint/corrosion.\n"
            "- [ ] 5. Connect a 12V motorcycle smart charger or test-jump with a healthy 12V battery.\n\n"
            "[chips: Paano mag-test ng baterya gamit ang multimeter | Mahinang pag-crank pero hindi mag-start | Umiikot normal pero hindi masindihan]"
        ),
        'hil': (
            "Pagsusuri sa pagtiyog sang makina, {sir}. **Starter Solenoid Relay Chatter** ang nadungan naton.\n\n"
            "**Kasulundan:** May igo nga boltahe ang baterya agud sirihan ang relay, pero kon mangayo na sing 50–80 Amps ang starter motor, nagahulog ang boltahe sa idalom sang 10.5V. Nagarelease ang coil, nagabalik ang boltahe, kag nagapirit sini sing madasig.\n\n"
            "**Sunod-sunod nga pagsusuri:**\n"
            "- [ ] 1. Switch ignition OFF and inspect 10mm battery terminal bolts for loose fitment or white sulfate corrosion.\n"
            "- [ ] 2. Measure resting voltage with a multimeter (Healthy: 12.6V+; Discharged: < 12.0V).\n"
            "- [ ] 3. Measure battery terminal voltage while holding starter button (if it plunges below 9.6V, battery cells are degraded).\n"
            "- [ ] 4. Check negative ground cable bolted to engine casing for loose bolt or paint/corrosion.\n"
            "- [ ] 5. Connect a 12V motorcycle smart charger or test-jump with a healthy 12V battery.\n\n"
            "[chips: Paano mag-test sang baterya sing multimeter | Mahinay mag-tiog pero indi mag-andar | Normal mag-tiog pero indi maglunsar]"
        ),
    },
    'start_slow_crank': {
        'tl': (
            "Pagsusuri sa pagsisimula, {sir}. **Mabigat na elektrikal na karga o huyang na baterya**.\n\n"
            "**Sanhi:** Kulang ang amperage na dumarating sa starter motor, o may mabigat na mekanikal na tungkulin nito.\n\n"
            "**Hakbang-hakbang na pagsusuri:**\n"
            "- [ ] 1. Check engine oil level and viscosity — cold or overfilled oil creates heavy drag.\n"
            "- [ ] 2. Inspect negative ground lead bolted to engine case for loose fastener or oxidation.\n"
            "- [ ] 3. Perform a voltage drop test across starter relay terminals during cranking (should be < 0.5V).\n"
            "- [ ] 4. Inspect starter motor carbon brushes for wear or oil penetration through the starter armature seal.\n\n"
            "[chips: Mabilisang nitik | Pagsusuri sa baterya | Tingnan ang langis ng makina]"
        ),
        'hil': (
            "Pagsusuri sa pagtiyog, {sir}. **Mabug-at nga elektrikal nga karga ukon huyop na ang baterya**.\n\n"
            "**Kasulundan:** Kulang ang amperage nga makaabot sa starter motor, ukon may mabug-at nga mekanikal nga ginatubod sini.\n\n"
            "**Sunod-sunod nga pagsusuri:**\n"
            "- [ ] 1. Check engine oil level and viscosity — cold or overfilled oil creates heavy drag.\n"
            "- [ ] 2. Inspect negative ground lead bolted to engine case for loose fastener or oxidation.\n"
            "- [ ] 3. Perform a voltage drop test across starter relay terminals during cranking (should be < 0.5V).\n"
            "- [ ] 4. Inspect starter motor carbon brushes for wear or oil penetration through the starter armature seal.\n\n"
            "[chips: Madasig nga lagatik | Pagsusuri sang baterya | Usisahon ang langa sang makina]"
        ),
    },
    'start_no_combustion': {
        'tl': (
            "Pagsusuri sa pagsisimula, {sir}. **Naantala ang Combustion Triangle**.\n\n"
            "Makinis na umiikot ang starter — malinis na ang baterya at starter motor. Kulang ang makina sa alinman sa **Spark**, **Gasolina**, o **Compression**.\n\n"
            "**Hakbang-hakbang na pagsusuri:**\n"
            "- [ ] 1. Confirm handlebar kill switch is in 'RUN' position and side-stand is fully raised (safety interlock check).\n"
            "- [ ] 2. Remove spark plug; rest grounded metal threads against cylinder head and crank to inspect for crisp blue spark.\n"
            "- [ ] 3. Inspect spark plug tip: if wet and smelling of gas, engine is flooded; if bone dry, fuel delivery has stalled.\n"
            "- [ ] 4. For EFI models: turn key on and listen for high-pitch 2-second fuel pump priming buzz beneath fuel tank.\n"
            "- [ ] 5. For carburetor models: loosen float bowl drain screw to confirm clean fuel flows freely.\n\n"
            "[chips: Paano suriin ang spark plug | Linisin ang carburetor jets | Nabaha ang makina protocol]"
        ),
        'hil': (
            "Pagsusuri sa pagtiyog, {sir}. **Naaantala ang Combustion Triangle**.\n\n"
            "Hamon na nagatiog ang starter — wala sing problema ang baterya kag starter motor. Kulang ang makina sa **Spark**, **Gasolina**, ukon **Compression**.\n\n"
            "**Sunod-sunod nga pagsusuri:**\n"
            "- [ ] 1. Confirm handlebar kill switch is in 'RUN' position and side-stand is fully raised (safety interlock check).\n"
            "- [ ] 2. Remove spark plug; rest grounded metal threads against cylinder head and crank to inspect for crisp blue spark.\n"
            "- [ ] 3. Inspect spark plug tip: if wet and smelling of gas, engine is flooded; if bone dry, fuel delivery has stalled.\n"
            "- [ ] 4. For EFI models: turn key on and listen for high-pitch 2-second fuel pump priming buzz beneath fuel tank.\n"
            "- [ ] 5. For carburetor models: loosen float bowl drain screw to confirm clean fuel flows freely.\n\n"
            "[chips: Paano usisahon ang spark plug | Linisin ang carburetor jets | Nahunug ang makina protocol]"
        ),
    },
    'start_dead': {
        'tl': (
            "Pagsusuri sa pagsisimula, {sir}. **Kumpletong pagkaputol ng daloy ng kuryente**.\n\n"
            "**Sanhi:** May pumipigil sa main electrical power na makarating sa ignition switch at main fuse bus.\n\n"
            "**Hakbang-hakbang na pagsusuri:**\n"
            "- [ ] 1. Check the Main 30A Fuse (housed inside or adjacent to the starter magnetic solenoid switch).\n"
            "- [ ] 2. Inspect battery terminal connections — clean lead posts and tighten 10mm terminal bolts.\n"
            "- [ ] 3. Inspect key ignition switch harness connector under the steering stem / fuel tank.\n"
            "- [ ] 4. Test battery terminal resting voltage with a multimeter — verify not reverse-connected or 0V.\n\n"
            "[chips: Nasaan ang main fuse? | Mabilisang nitik | Tingnan ang boltahe ng baterya]"
        ),
        'hil': (
            "Pagsusuri sa pagtiyog, {sir}. **Tinan-aw nga pagkauntod sang daloy sang kuryente**.\n\n"
            "**Kasulundan:** May nagapugong sa main electrical power nga makaabot sa ignition switch kag main fuse bus.\n\n"
            "**Sunod-sunod nga pagsusuri:**\n"
            "- [ ] 1. Check the Main 30A Fuse (housed inside or adjacent to the starter magnetic solenoid switch).\n"
            "- [ ] 2. Inspect battery terminal connections — clean lead posts and tighten 10mm terminal bolts.\n"
            "- [ ] 3. Inspect key ignition switch harness connector under the steering stem / fuel tank.\n"
            "- [ ] 4. Test battery terminal resting voltage with a multimeter — verify not reverse-connected or 0V.\n\n"
            "[chips: Diin ang main fuse? | Madasig nga lagatik | Usisahon ang boltahe sang baterya]"
        ),
    },
    'start_dies': {
        'tl': (
            "Pagsusuri sa pagsisimula, {sir}. **Nasasablay sa pagpapatuloy ng pag-andar (umaga-umaga tapos namamatay)**.\n\n"
            "**Sanhi:** Umaabot sa inisyal na pag-aapoy ang makina pero hindi kayang panatilihing buhay dahil sa kulang na gasolina, hangin leak, o bumabagsak na ignition.\n\n"
            "**Hakbang-hakbang na pagsusuri:**\n"
            "- [ ] 1. For EFI: Check fuel pump priming pressure and inspect fuel filter / injector spray pattern.\n"
            "- [ ] 2. For Carburetor: Clean pilot (idle) jet and adjust fuel/air mixture screw (typically 1.5 to 2 turns out).\n"
            "- [ ] 3. Inspect rubber intake manifold boot between throttle body/carburetor and cylinder head for vacuum cracks or loose clamps.\n"
            "- [ ] 4. Check Idle Air Control Valve (IACV) or manual idle stop screw setting.\n"
            "- [ ] 5. Test fuel quality — drain float bowl / tank sample to inspect for water contamination or stale fuel.\n\n"
            "[chips: Linisin ang carburetor jets | Tingnan ang presyon ng fuel pump | I-test kung may vacuum leak]"
        ),
        'hil': (
            "Pagsusuri sa pagtiyog, {sir}. **Nagapalpak sa pagpadayon sang pag-andar (nagalunsar dayon tapos namatay)**.\n\n"
            "**Kasulundan:** Nakab-ot ang inisyal nga pagkalayo pero indi makapanindot sang buhi tungod sa kulang nga gasolina, hangin leak, ukon nagahulog nga ignition.\n\n"
            "**Sunod-sunod nga pagsusuri:**\n"
            "- [ ] 1. For EFI: Check fuel pump priming pressure and inspect fuel filter / injector spray pattern.\n"
            "- [ ] 2. For Carburetor: Clean pilot (idle) jet and adjust fuel/air mixture screw (typically 1.5 to 2 turns out).\n"
            "- [ ] 3. Inspect rubber intake manifold boot between throttle body/carburetor and cylinder head for vacuum cracks or loose clamps.\n"
            "- [ ] 4. Check Idle Air Control Valve (IACV) or manual idle stop screw setting.\n"
            "- [ ] 5. Test fuel quality — drain float bowl / tank sample to inspect for water contamination or stale fuel.\n\n"
            "[chips: Linisin ang carburetor jets | Usisahon ang presyon sang fuel pump | I-test kon may vacuum leak]"
        ),
    },
    'start_silent': {
        'tl': (
            "Pagsusuri sa pagsisimula, {sir}. **Bukas na circuit sa starter control interlock**.\n\n"
            "**Sanhi:** May kuryente ang dashboard, ngunit bukas ang circuit ng starter relay control coil dahil sa isang safety switch o naputol na control line.\n\n"
            "**Hakbang-hakbang na pagsusuri:**\n"
            "- [ ] 1. Squeeze both brake levers firmly (scooters) or pull clutch lever (motorcycles) to ensure brake/clutch safety switch clicks.\n"
            "- [ ] 2. Inspect side-stand safety kill switch — clean road grime from the plunger spring mechanism.\n"
            "- [ ] 3. Disconnect handlebar starter button switch housing; spray contacts with electrical contact cleaner to remove oxidation.\n"
            "- [ ] 4. Locate starter solenoid relay and test for 12V signal on trigger wire when button is pressed.\n"
            "- [ ] 5. Tap starter motor casing lightly with a plastic mallet while pressing starter button (if it turns, starter carbon brushes are worn).\n\n"
            "[chips: Pag-test ng side stand switch | Paglilinis ng starter button | Mabilisang nitik]"
        ),
        'hil': (
            "Pagsusuri sa pagtiyog, {sir}. **Bukad nga circuit sa starter control interlock**.\n\n"
            "**Kasulundan:** May kuryente ang dashboard, pero bukad ang circuit sang starter relay control coil tungod sa isa ka safety switch ukon bakas nga control line.\n\n"
            "**Sunod-sunod nga pagsusuri:**\n"
            "- [ ] 1. Squeeze both brake levers firmly (scooters) or pull clutch lever (motorcycles) to ensure brake/clutch safety switch clicks.\n"
            "- [ ] 2. Inspect side-stand safety kill switch — clean road grime from the plunger spring mechanism.\n"
            "- [ ] 3. Disconnect handlebar starter button switch housing; spray contacts with electrical contact cleaner to remove oxidation.\n"
            "- [ ] 4. Locate starter solenoid relay and test for 12V signal on trigger wire when button is pressed.\n"
            "- [ ] 5. Tap starter motor casing lightly with a plastic mallet while pressing starter button (if it turns, starter carbon brushes are worn).\n\n"
            "[chips: Pag-test sang side stand switch | Pagpamutas sang starter button | Madasig nga lagatik]"
        ),
    },

    # ───────────────────────── Overheating (vehicle known) ────────────────────
    'overheat_known': {
        'tl': (
            "Cooling System Diagnostic Protocol para sa **{veh}** mo, {sir}:\n\n"
            "**MAHIGPIT NA BABALA SA KALIGTASAN:** Huwag nang huwag bubuksan ang takip ng radiator habang mainit pa! Hintaying lumamig nang lubusan (30–45 minuto) bago hawakan.\n\n"
            "**Hakbang-hakbang na pagsusuri ng cooling system:**\n"
            "- [ ] 1. Allow engine to sit turned off for 45 minutes until radiator neck is cool to bare hands.\n"
            "- [ ] 2. Inspect coolant expansion reservoir level between MIN and MAX indicators.\n"
            "- [ ] 3. Remove radiator cap: check for milky oil residue (head gasket leak) or rust contamination.\n"
            "- [ ] 4. Inspect radiator aluminum cooling fins for road mud, crushed fins, or debris blockage.\n"
            "- [ ] 5. Start engine, allow temperature to reach 95°C–100°C: verify radiator electric fan turns on automatically.\n"
            "- [ ] 6. If fan does not spin: inspect fan relay, thermo-switch sensor, and cooling fan fuse.\n\n"
            "[chips: Puting mabangong usok | Tingnan ang langis ng makina | Suriin ang pagsisimula ng makina]"
        ),
        'hil': (
            "Cooling System Diagnostic Protocol para sa **{veh}** mo, {sir}:\n\n"
            "**KUSOG NGA PAHILING SA KALIGTASAN:** Indi gid pagbuksan ang takop sang radiator samtang mainit pa! Hulata nga magbugnaw gid (30-45 minuto) antes haptanon.\n\n"
            "**Sunod-sunod nga pagsusuri sang cooling system:**\n"
            "- [ ] 1. Allow engine to sit turned off for 45 minutes until radiator neck is cool to bare hands.\n"
            "- [ ] 2. Inspect coolant expansion reservoir level between MIN and MAX indicators.\n"
            "- [ ] 3. Remove radiator cap: check for milky oil residue (head gasket leak) or rust contamination.\n"
            "- [ ] 4. Inspect radiator aluminum cooling fins for road mud, crushed fins, or debris blockage.\n"
            "- [ ] 5. Start engine, allow temperature to reach 95°C–100°C: verify radiator electric fan turns on automatically.\n"
            "- [ ] 6. If fan does not spin: inspect fan relay, thermo-switch sensor, and cooling fan fuse.\n\n"
            "[chips: Puti nga mabahu nga aso | Usisahon ang langa sang makina | Suri-on ang pagtiyog sang makina]"
        ),
    },

    # ───────────────────────── Acceleration (vehicle known) ───────────────────
    'accel_slip': {
        'tl': (
            "Pagsusuri sa drivetrain ng **{veh}** mo, {sir}. **Nagdudulas ang transmisyon o clutch**.\n\n"
            "**Pinaka-malamang na sanhi:** Gasgas na ang friction plates, mali ang clutch cable free play, o (sa scooter) makintab na ang CVT belt at pudpod na ang variator rollers.\n\n"
            "**Hakbang-hakbang na pagsusuri:**\n"
            "- [ ] 1. Check clutch handlebar cable free play (ensure 2–3 mm free movement at perch).\n"
            "- [ ] 2. For scooters/CVT: remove crankcase belt cover; measure drive belt width with vernier caliper.\n"
            "- [ ] 3. Inspect variator rollers (flyballs) for flat spots or oval wear.\n"
            "- [ ] 4. For manual clutch: drain oil and inspect clutch friction disc thickness and pressure plate springs.\n"
            "- [ ] 5. Verify motorcycle oil used complies with JASO-MA2 standards (car oil with friction modifiers induces clutch slip).\n\n"
            "[chips: Tingnan ang langis ng makina | Suriin ang spark plug | Listahan ng lahat ng pyesa]"
        ),
        'hil': (
            "Pagsusuri sang drivetrain sang **{veh}** mo, {sir}. **Nagaduflas ang transmisyon ukon clutch**.\n\n"
            "**Pinakamaluluparan nga kasulundan:** Gasgas na ang friction plates, sala ang clutch cable free play, ukon (sa scooter) makintab na ang CVT belt kag pudpod na ang variator rollers.\n\n"
            "**Sunod-sunod nga pagsusuri:**\n"
            "- [ ] 1. Check clutch handlebar cable free play (ensure 2–3 mm free movement at perch).\n"
            "- [ ] 2. For scooters/CVT: remove crankcase belt cover; measure drive belt width with vernier caliper.\n"
            "- [ ] 3. Inspect variator rollers (flyballs) for flat spots or oval wear.\n"
            "- [ ] 4. For manual clutch: drain oil and inspect clutch friction disc thickness and pressure plate springs.\n"
            "- [ ] 5. Verify motorcycle oil used complies with JASO-MA2 standards (car oil with friction modifiers induces clutch slip).\n\n"
            "[chips: Usisahon ang langa sang makina | Suri-on ang spark plug | Listahan sang tanan nga pyesa]"
        ),
    },
    'accel_fuel': {
        'tl': (
            "Pagsusuri sa combustion at fuel ng **{veh}** mo, {sir}. **Kulang sa gasolina o pumapalya ang ignition**.\n\n"
            "**Hakbang-hakbang na pagsusuri:**\n"
            "- [ ] 1. Remove and inspect air filter element for oil or dirt choking airflow.\n"
            "- [ ] 2. Inspect spark plug tip: clean electrode or replace if fouled or gap exceeds 0.8 mm.\n"
            "- [ ] 3. For EFI: clean fuel injector nozzle and inspect fuel pump delivery pressure.\n"
            "- [ ] 4. For carburetor: spray main jet and pilot jet with carb cleaner to clear varnish.\n\n"
            "[chips: Linisin ang carburetor jets | Suriin ang spark plug | Palitan ang air filter]"
        ),
        'hil': (
            "Pagsusuri sang combustion kag gasolina sang **{veh}** mo, {sir}. **Kulang sa gasolina ukon nagapalpalyar ang ignition**.\n\n"
            "**Sunod-sunod nga pagsusuri:**\n"
            "- [ ] 1. Remove and inspect air filter element for oil or dirt choking airflow.\n"
            "- [ ] 2. Inspect spark plug tip: clean electrode or replace if fouled or gap exceeds 0.8 mm.\n"
            "- [ ] 3. For EFI: clean fuel injector nozzle and inspect fuel pump delivery pressure.\n"
            "- [ ] 4. For carburetor: spray main jet and pilot jet with carb cleaner to clear varnish.\n\n"
            "[chips: Linisin ang carburetor jets | Suri-on ang spark plug | Ilisan ang air filter]"
        ),
    },

    # ───────────────────────── Engine noise ───────────────────────────────────
    'noise_valve': {
        'tl': (
            "Pagsusuri sa tunog, {sir}. **Sobrang lapad ng valve tappet clearance** sa cylinder head.\n\n"
            "**Hakbang-hakbang na pag-adjust ng valve:**\n"
            "- [ ] 1. Allow engine to cool completely (inspection must be performed at ambient room temp).\n"
            "- [ ] 2. Remove cylinder head valve inspection caps and alternator timing inspection plug.\n"
            "- [ ] 3. Rotate crankshaft with 14mm socket to Top Dead Center (TDC) on compression stroke (T mark aligned).\n"
            "- [ ] 4. Insert feeler gauge between rocker arm adjuster screw and valve stem tip.\n"
            "- [ ] 5. Loosen 9mm locknut, adjust screw until slight drag is felt on gauge, retighten locknut.\n\n"
            "[chips: Suriin ang cam chain tensioner | Tingnan ang oil pressure | Kakaibang ingay sa makina]"
        ),
        'hil': (
            "Pagsusuri sang tingog, {sir}. **Sobra nga lapad ang valve tappet clearance** sa cylinder head.\n\n"
            "**Sunod-sunod nga pag-adjust sang valve:**\n"
            "- [ ] 1. Allow engine to cool completely (inspection must be performed at ambient room temp).\n"
            "- [ ] 2. Remove cylinder head valve inspection caps and alternator timing inspection plug.\n"
            "- [ ] 3. Rotate crankshaft with 14mm socket to Top Dead Center (TDC) on compression stroke (T mark aligned).\n"
            "- [ ] 4. Insert feeler gauge between rocker arm adjuster screw and valve stem tip.\n"
            "- [ ] 5. Loosen 9mm locknut, adjust screw until slight drag is felt on gauge, retighten locknut.\n\n"
            "[chips: Usisahon ang cam chain tensioner | Usisahon ang oil pressure | Kakaiba nga tingog sang makina]"
        ),
    },
    'noise_knock': {
        'tl': (
            "**AGARANG BABALA, {sir}.** **Pudpod na ang Bottom-End Bearing (Connecting Rod / Crank Journal)**.\n\n"
            "Mabigat na metal na tunog na sumasabay sa RPM ng makina at lumalakas kapag binibirit — senyales ng bearing play.\n\n"
            "**Hakbang-hakbang na pagsusuri:**\n"
            "- [ ] 1. Shut off engine immediately to avoid catastrophic connecting rod ejection through engine crankcase.\n"
            "- [ ] 2. Drain engine oil into a clean pan; inspect for copper, brass, or silver metallic flakes.\n"
            "- [ ] 3. Inspect oil filter element for trapped metal shavings.\n"
            "- [ ] 4. Perform oil pressure test using a mechanical gauge attached to the main oil gallery port.\n\n"
            "[chips: Tingnan ang langis ng makina | Metal na tingog sa itaas | Listahan ng lahat ng pyesa]"
        ),
        'hil': (
            "**AGARON NGA PAHILING, {sir}.** **Pudpod na ang Bottom-End Bearing (Connecting Rod / Crank Journal)**.\n\n"
            "Mabug-at nga metal nga tingog nga nasingraw sa RPM sang makina kag nagakusog kon magbirit — tima-an sang bearing play.\n\n"
            "**Sunod-sunod nga pagsusuri:**\n"
            "- [ ] 1. Shut off engine immediately to avoid catastrophic connecting rod ejection through engine crankcase.\n"
            "- [ ] 2. Drain engine oil into a clean pan; inspect for copper, brass, or silver metallic flakes.\n"
            "- [ ] 3. Inspect oil filter element for trapped metal shavings.\n"
            "- [ ] 4. Perform oil pressure test using a mechanical gauge attached to the main oil gallery port.\n\n"
            "[chips: Usisahon ang langa sang makina | Metal nga tingog sa ibabaw | Listahan sang tanan nga pyesa]"
        ),
    },
    'noise_camchain': {
        'tl': (
            "Pagsusuri sa tunog, {sir}. **Luwag na cam timing chain o naiipit na tensioner**.\n\n"
            "**Hakbang-hakbang na pagsusuri ng cam chain:**\n"
            "- [ ] 1. Locate the automatic cam chain tensioner on the rear of the cylinder barrel.\n"
            "- [ ] 2. Remove center sealing bolt and spring to verify internal ratchet mechanism has not jammed.\n"
            "- [ ] 3. Manually turn tensioner screw clockwise to retract plunger, re-install, and release to reset tension.\n"
            "- [ ] 4. If noise persists, cam chain guide slippers or chain links are stretched beyond service limits.\n\n"
            "[chips: Metal na tingog sa itaas | Tingnan ang oil pressure | Kakaibang ingay sa makina]"
        ),
        'hil': (
            "Pagsusuri sang tingog, {sir}. **Luwag nga cam timing chain ukon nangaipit nga tensioner**.\n\n"
            "**Sunod-sunod nga pagsusuri sang cam chain:**\n"
            "- [ ] 1. Locate the automatic cam chain tensioner on the rear of the cylinder barrel.\n"
            "- [ ] 2. Remove center sealing bolt and spring to verify internal ratchet mechanism has not jammed.\n"
            "- [ ] 3. Manually turn tensioner screw clockwise to retract plunger, re-install, and release to reset tension.\n"
            "- [ ] 4. If noise persists, cam chain guide slippers or chain links are stretched beyond service limits.\n\n"
            "[chips: Metal nga tingog sa ibabaw | Usisahon ang oil pressure | Kakaiba nga tingog sang makina]"
        ),
    },
    'noise_generic': {
        'tl': (
            "Bukas na ang acoustic scanner, {sir}. Saang bahagi ng makina naririnig ang ingay?\n\n"
            "[chips: Metal na tilian sa itaas | Mabigat na katok sa ibaba | Kalat-kalat sa gilid ng makina | Mataas na ingay sa takbo]"
        ),
        'hil': (
            "Bukad na ang acoustic scanner, {sir}. Sa diin nga bahin sang makina madungan ang tingog?\n\n"
            "[chips: Metal nga tilian sa ibabaw | Mabug-at nga katok sa idalom | Kalat-kalat sa kilid sang makina | Mataas nga tingog sa takbo]"
        ),
    },

    # ───────────────────────── Smoke ──────────────────────────────────────────
    'smoke_generic': {
        'tl': (
            "Pagsusuri sa thermal at combustion, {sir}. Anong kulay o pinagmulan ng usok ang nakikita mo?\n\n"
            "[chips: Asul na usok sa tambutso | Itim na usok sa tambutso | Puting mabangong usok | Usok malapit sa makina at sprocket]"
        ),
        'hil': (
            "Pagsusuri sang thermal kag combustion, {sir}. Ano nga kolor ukon diin nga bahin nga aso ang imo nakikita?\n\n"
            "[chips: Asul nga aso sa tambutso | Itum nga aso sa tambutso | Puti nga mabahu nga aso | Aso malapit sa makina kag sprocket]"
        ),
    },
    'smoke_blue': {
        'tl': (
            "Pagsusuri sa combustion, {sir}. **Pumasok ang langis sa combustion chamber**.\n\n"
            "**Sanhi:** Pudpod na ang piston compression/oil scraper rings o tigang na ang valve stem seals.\n\n"
            "**Hakbang-hakbang na pagsusuri ng compression:**\n"
            "- [ ] 1. Warm engine to operating temperature, then remove spark plug.\n"
            "- [ ] 2. Thread mechanical compression gauge into spark plug socket and hold throttle wide open.\n"
            "- [ ] 3. Crank engine 4-5 revolutions (Healthy: 140–180 PSI; Worn: < 110 PSI).\n"
            "- [ ] 4. Wet test: squirt 1 teaspoon of engine oil into spark hole; if PSI rises dramatically, piston rings are worn.\n"
            "- [ ] 5. If PSI remains unchanged, valve stem seals or guides are leaking oil down intake valves.\n\n"
            "[chips: Tingnan ang langis ng makina | Suriin ang spark plug | Itim na usok sa tambutso]"
        ),
        'hil': (
            "Pagsusuri sang combustion, {sir}. **Nagsulod nga langa sa combustion chamber**.\n\n"
            "**Kasulundan:** Pudpod na ang piston compression/oil scraper rings ukon tig-a na ang valve stem seals.\n\n"
            "**Sunod-sunod nga pagsusuri sang compression:**\n"
            "- [ ] 1. Warm engine to operating temperature, then remove spark plug.\n"
            "- [ ] 2. Thread mechanical compression gauge into spark plug socket and hold throttle wide open.\n"
            "- [ ] 3. Crank engine 4-5 revolutions (Healthy: 140–180 PSI; Worn: < 110 PSI).\n"
            "- [ ] 4. Wet test: squirt 1 teaspoon of engine oil into spark hole; if PSI rises dramatically, piston rings are worn.\n"
            "- [ ] 5. If PSI remains unchanged, valve stem seals or guides are leaking oil down intake valves.\n\n"
            "[chips: Usisahon ang langa sang makina | Suri-on ang spark plug | Itum nga aso sa tambutso]"
        ),
    },
    'smoke_black': {
        'tl': (
            "Pagsusuri sa combustion, {sir}. **Sobrang siksik na air-fuel mixture (labis na gasolina)**.\n\n"
            "**Hakbang-hakbang na pagsusuri ng carburetor at fuel:**\n"
            "- [ ] 1. Inspect engine air filter — a clogged, oily air filter chokes airflow, causing severe rich mixture.\n"
            "- [ ] 2. Verify choke / enricher lever or plunger is retracting completely when warm.\n"
            "- [ ] 3. Remove spark plug: inspect for heavy dry black carbon deposits.\n"
            "- [ ] 4. For carburetor models: check float height and clean main/pilot jets with carb cleaner spray.\n"
            "- [ ] 5. For EFI models: verify oxygen (O2) sensor and engine coolant temperature (ECT) sensor wiring.\n\n"
            "[chips: Linisin ang carburetor jets | Suriin ang spark plug | Puting mabangong usok]"
        ),
        'hil': (
            "Pagsusuri sang combustion, {sir}. **Sobra nga siksik nga air-fuel mixture (lapad nga gasolina)**.\n\n"
            "**Sunod-sunod nga pagsusuri sang carburetor kag gasolina:**\n"
            "- [ ] 1. Inspect engine air filter — a clogged, oily air filter chokes airflow, causing severe rich mixture.\n"
            "- [ ] 2. Verify choke / enricher lever or plunger is retracting completely when warm.\n"
            "- [ ] 3. Remove spark plug: inspect for heavy dry black carbon deposits.\n"
            "- [ ] 4. For carburetor models: check float height and clean main/pilot jets with carb cleaner spray.\n"
            "- [ ] 5. For EFI models: verify oxygen (O2) sensor and engine coolant temperature (ECT) sensor wiring.\n\n"
            "[chips: Linisin ang carburetor jets | Suri-on ang spark plug | Puti nga mabahu nga aso]"
        ),
    },
    'smoke_white': {
        'tl': (
            "Babala sa thermal, {sir}. **Papasok ang coolant sa combustion chamber (posibleng putol na head gasket)**.\n\n"
            "**Hakbang-hakbang na pagsusuri ng cooling system:**\n"
            "- [ ] 1. Allow engine to cool completely before touching radiator cap.\n"
            "- [ ] 2. Check coolant level in recovery tank and radiator neck for milky residue or oil film.\n"
            "- [ ] 3. Inspect engine oil sight glass for milky white emulsion (water in oil).\n"
            "- [ ] 4. Perform a cooling system pressure test at 1.1 bar to verify head gasket seal integrity.\n\n"
            "[chips: Suriin ang coolant at radiator | Tingnan ang langis ng makina | Asul na usok sa tambutso]"
        ),
        'hil': (
            "Pahiling sa thermal, {sir}. **Nagapasulod nga coolant sa combustion chamber (posible nga bakas nga head gasket)**.\n\n"
            "**Sunod-sunod nga pagsusuri sang cooling system:**\n"
            "- [ ] 1. Allow engine to cool completely before touching radiator cap.\n"
            "- [ ] 2. Check coolant level in recovery tank and radiator neck for milky residue or oil film.\n"
            "- [ ] 3. Inspect engine oil sight glass for milky white emulsion (water in oil).\n"
            "- [ ] 4. Perform a cooling system pressure test at 1.1 bar to verify head gasket seal integrity.\n\n"
            "[chips: Usisahon ang coolant kag radiator | Usisahon ang langa sang makina | Asul nga aso sa tambutso]"
        ),
    },

    # ───────────────────────── Maintenance protocols ──────────────────────────
    'proto_tools': {
        'tl': (
            "Karaniwang workshop tool checklist, {sir}:\n\n"
            "- [ ] 1. Metric socket set (8mm, 10mm, 12mm, 14mm, 17mm, 19mm)\n"
            "- [ ] 2. Combination open-end wrenches\n"
            "- [ ] 3. JIS / Phillips and flathead screwdrivers\n"
            "- [ ] 4. Digital Multimeter (for electrical, battery, and sensor testing)\n"
            "- [ ] 5. Spark plug socket wrench with rubber insert\n"
            "- [ ] 6. Clean oil catch pan and lint-free shop towels\n"
            "- [ ] 7. Nitrile work gloves & eye protection\n\n"
            "[chips: Suriin ang pagsisimula ng makina | Sira ang preno | Acoustic noise scan]"
        ),
        'hil': (
            "Kasarangan nga workshop tool checklist, {sir}:\n\n"
            "- [ ] 1. Metric socket set (8mm, 10mm, 12mm, 14mm, 17mm, 19mm)\n"
            "- [ ] 2. Combination open-end wrenches\n"
            "- [ ] 3. JIS / Phillips and flathead screwdrivers\n"
            "- [ ] 4. Digital Multimeter (for electrical, battery, and sensor testing)\n"
            "- [ ] 5. Spark plug socket wrench with rubber insert\n"
            "- [ ] 6. Clean oil catch pan and lint-free shop towels\n"
            "- [ ] 7. Nitrile work gloves & eye protection\n\n"
            "[chips: Suri-on ang pagtiyog sang makina | Guba ang preno | Acoustic noise scan]"
        ),
    },
    'proto_oil': {
        'tl': (
            "Protocol sa pagpapalit ng langis ng makina, {sir}:\n\n"
            "- [ ] 1. Warm engine 3 minutes, then shut off and keep vehicle upright on level ground.\n"
            "- [ ] 2. Inspect sight glass or clean dipstick: oil should sit between MIN and MAX marks.\n"
            "- [ ] 3. Place drain pan below crankcase; remove drain bolt (replace crush washer upon reassembly).\n"
            "- [ ] 4. Replace spin-on or cartridge oil filter and torque to manufacturer specification.\n"
            "- [ ] 5. Refill with recommended JASO-MA2 motorcycle 4T oil (do not use passenger car oil with friction modifiers).\n\n"
            "[chips: Usok malapit sa makina at sprocket | Ilan ang pyesa | Suriin ang pagsisimula ng makina]"
        ),
        'hil': (
            "Protocol sa pag-ilis nga langa sang makina, {sir}:\n\n"
            "- [ ] 1. Warm engine 3 minutes, then shut off and keep vehicle upright on level ground.\n"
            "- [ ] 2. Inspect sight glass or clean dipstick: oil should sit between MIN and MAX marks.\n"
            "- [ ] 3. Place drain pan below crankcase; remove drain bolt (replace crush washer upon reassembly).\n"
            "- [ ] 4. Replace spin-on or cartridge oil filter and torque to manufacturer specification.\n"
            "- [ ] 5. Refill with recommended JASO-MA2 motorcycle 4T oil (do not use passenger car oil with friction modifiers).\n\n"
            "[chips: Aso malapit sa makina kag sprocket | Pila ang pyesa | Suri-on ang pagtiyog sang makina]"
        ),
    },
    'proto_battery': {
        'tl': (
            "Pagsusuri sa baterya, {sir}:\n\n"
            "• **12.6V+** ang malusog na baterya kapag nakapahinga\n"
            "• Sa **12.0V o mas mababa**, 75% nang discharge ang baterya\n"
            "• Hindi dapat lumagpas sa ibaba ng **9.6V** ang boltahe habang nagki-crank\n"
            "• Karaniwang haba ng buhay ng motorcycle AGM/Lithium baterya: 3–5 taon\n\n"
            "[chips: Mabilisang nitik | Mahinang pag-crank pero hindi mag-start | Nasaan ang main fuse?]"
        ),
        'hil': (
            "Pagsusuri sang baterya, {sir}:\n\n"
            "• **12.6V+** ang malandum nga baterya kon nagapahuway\n"
            "• Sa **12.0V ukon mas ubos**, 75% na ang discharge sang baterya\n"
            "• Indi dapat lumapas sa idalom sang **9.6V** ang boltahe samtang nagatiog\n"
            "• Kasadyahan nga kabuhi sang motorcycle AGM/Lithium baterya: 3–5 katuig\n\n"
            "[chips: Madasig nga lagatik | Mahinay mag-tiog pero indi mag-andar | Diin ang main fuse?]"
        ),
    },
    'proto_tyre': {
        'tl': (
            "Protocol sa kaligtasan ng gulong, {sir}:\n\n"
            "- [ ] 1. Check cold tyre pressure weekly (typically 29–33 PSI front, 33–36 PSI rear).\n"
            "- [ ] 2. Inspect tread depth indicators — replace if tread is under 1.6 mm.\n"
            "- [ ] 3. Check for cracks, dry rot on sidewalls, or embedded nails/screws.\n"
            "- [ ] 4. Inspect wheel valve stem rubber for weathering or leakage.\n\n"
            "[chips: Sira ang preno sa harap | Suriin ang pagsisimula ng makina | Tulong at kakayahan]"
        ),
        'hil': (
            "Protocol sa kaligtasan sang gulong, {sir}:\n\n"
            "- [ ] 1. Check cold tyre pressure weekly (typically 29–33 PSI front, 33–36 PSI rear).\n"
            "- [ ] 2. Inspect tread depth indicators — replace if tread is under 1.6 mm.\n"
            "- [ ] 3. Check for cracks, dry rot on sidewalls, or embedded nails/screws.\n"
            "- [ ] 4. Inspect wheel valve stem rubber for weathering or leakage.\n\n"
            "[chips: Guba ang preno sa atubangan | Suri-on ang pagtiyog sang makina | Bulig kag serbisyo]"
        ),
    },
    'proto_sparkplug': {
        'tl': (
            "Protocol sa ignition, {sir}:\n\n"
            "- [ ] 1. Remove spark plug using dedicated rubber-lined plug socket.\n"
            "- [ ] 2. Inspect electrode color: light tan/grey is optimal; black soot indicates rich mixture; blistered white indicates lean.\n"
            "- [ ] 3. Measure electrode gap using wire feeler gauge (typically 0.7–0.8 mm).\n"
            "- [ ] 4. Clean electrode with brass wire brush or replace with fresh spark plug.\n\n"
            "[chips: Umiikot normal pero hindi masindihan | Itim na usok sa tambutso | Suriin ang pagsisimula ng makina]"
        ),
        'hil': (
            "Protocol sang ignition, {sir}:\n\n"
            "- [ ] 1. Remove spark plug using dedicated rubber-lined plug socket.\n"
            "- [ ] 2. Inspect electrode color: light tan/grey is optimal; black soot indicates rich mixture; blistered white indicates lean.\n"
            "- [ ] 3. Measure electrode gap using wire feeler gauge (typically 0.7–0.8 mm).\n"
            "- [ ] 4. Clean electrode with brass wire brush or replace with fresh spark plug.\n\n"
            "[chips: Normal mag-tiog pero indi maglunsar | Itum nga aso sa tambutso | Suri-on ang pagtiyog sang makina]"
        ),
    },

    # ─────────────────── General motorcycle Q&A (direct answers) ───────────────
    'general_oil': {
        'tl': (
            "**Pagpapalit ng langis ng makina, {sir}:**\n\n"
            "**Kailan:** Karaniwan tuwing **2,000–4,000 km** o **3–6 buwan** para sa araw-araw na scooter/underbone. "
            "Kung traffic, maikling biyahe, o maalikabok, mas malapit sa 2,000 km; kung highway, puwedeng umabot sa 4,000 km. "
            "Ang owner's manual ang pinakahuling batayan para sa exact na modelo mo.\n\n"
            "**Langis:** JASO MA/MA2 4T motorcycle oil, tamang viscosity ayon sa manual. "
            "Huwag gumamit ng car oil na may friction modifiers sa wet-clutch na motor.\n\n"
            "**Mga kailangan:** drain pan, tamang wrench/socket, bagong crush washer, oil filter, funnel, gloves, "
            "at sealed container para sa used oil. Patayuin ang motor sa level ground.\n\n"
            "**Hakbang:**\n"
            "- [ ] 1. Warm engine 2–3 minutes, patayin, hintayin 2–3 minutes.\n"
            "- [ ] 2. Patayuin ang motor sa level ground; ilagay ang drain pan sa ilalim ng drain bolt.\n"
            "- [ ] 3. Tanggalin ang drain bolt (at filter); hayaang maubos ang lumang langis.\n"
            "- [ ] 4. Palitan ang crush washer; ibalik ang drain bolt nang snug — huwag sobrang higpitan; gamitin ang manual torque kung may wrench.\n"
            "- [ ] 5. Palitan ang oil filter ayon sa manual; lagyan ng fresh oil ang filter seal.\n"
            "- [ ] 6. I-refill ang tamang dami, check ang sight glass/dipstick, at patakbuhin sandali ang engine.\n"
            "- [ ] 7. Patayin, hintayin, i-check muli ang level, at tingnan kung may tagas.\n\n"
            "**Kaligtasan at disposal:** Nakakalason ang used oil — ilagay sa sealed container at dalhin sa recycling center; huwag itapon sa imburnal. "
            "Kung rounded/seized ang drain bolt o may metal flakes sa langis, huminto at ipa-check sa mekaniko.\n\n"
            "[chips: Kailan dapat mag-change oil? | Anong oil type ang gagamitin? | Ano ang titingnan bago magpalit ng gulong? | Buong maintenance schedule]"
        ),
        'hil': (
            "**Pag-ilis sang langis sang makina, {sir}:**\n\n"
            "**San-o:** Kasadyahan every **2,000–4,000 km** ukon **3–6 ka bulan** para sa adlaw-adlaw nga scooter/underbone. "
            "Kon traffic, malip-ot nga biyahe, ukon madamo sang abog, mas malapit sa 2,000 km; kon highway, puwede makaabot 4,000 km. "
            "Ang owner's manual ang pinakaulahing basihan para sa exact nga modelo mo.\n\n"
            "**Lana:** JASO MA/MA2 4T motorcycle oil, husto nga viscosity suno sa manual. "
            "Indi maggamit car oil nga may friction modifiers sa wet-clutch nga motor.\n\n"
            "**Mga kinahanglan:** drain pan, husto nga wrench/socket, bag-o nga crush washer, oil filter, funnel, gloves, "
            "kag sealed container para sa used oil. Patindoga ang motor sa level ground.\n\n"
            "**Mga tikang:**\n"
            "- [ ] 1. Warm engine 2–3 minutes, patya, hintayi 2–3 minutes.\n"
            "- [ ] 2. Patindoga ang motor sa level ground; ibutang ang drain pan sa idalom sang drain bolt.\n"
            "- [ ] 3. Tangtanga ang drain bolt (kag filter); pabay-i nga maubos ang daan nga lana.\n"
            "- [ ] 4. Ilisan ang crush washer; ibalik ang drain bolt nga snug — indi sobra higot; gamita ang manual torque kon may wrench.\n"
            "- [ ] 5. Ilisan ang oil filter suno sa manual; butangi sang fresh oil ang filter seal.\n"
            "- [ ] 6. I-refill ang husto nga kadamu, check ang sight glass/dipstick, kag patakbuhon sing makadali ang engine.\n"
            "- [ ] 7. Patya, hintayi, i-check liwat ang level, kag tan-awa kon may tagas.\n\n"
            "**Kaligtasan kag disposal:** Makahilo ang used oil — ibutang sa sealed container kag dal-on sa recycling center; indi itapon sa imburnal. "
            "Kon rounded/seized ang drain bolt ukon may metal flakes sa lana, hunong kag ipa-check sa mekaniko.\n\n"
            "[chips: San-o dapat mag-ilis sang langis? | Ano nga oil type ang gamiton? | Ano ang usisahon antes mag-ilis sang gulong? | Bug-os nga maintenance schedule]"
        ),
    },
    'general_tire': {
        'tl': (
            "**Bago magpalit ng gulong, ito ang mga dapat i-check, {sir}:**\n\n"
            "1. **Size at rating:** Basahin ang sidewall (hal. 90/80-14) at siguraduhing pareho ang replacement. "
            "Check ang load/speed rating, at kung tube-type o tubeless ang rim mo.\n"
            "2. **Kondisyon:** Tread depth na hindi bababa sa **1.6 mm**, walang cracks, bulges, o naka-embed na nails/screws. "
            "Tingnan ang rim kung may bingkong, crack, o kalawang.\n"
            "3. **Tools:** Tyre levers, rim protectors, bead breaker (o shop), torque wrench, bagong valve stem kung kailangan, "
            "pump with gauge, at soapy water para sa leak check.\n"
            "4. **Brake at chain clearance:** Siguraduhing hindi baluktot ang disc rotor, hindi contaminated ang pads, at may clearance ang chain/sprocket. "
            "Sa drum brake, tandaan ang shoe at spring orientation bago tanggalin.\n"
            "5. **Wheel bearings at spokes:** I-rock ang wheel para sa play at check kung tight ang spokes. "
            "Itabi nang maayos ang axle nut, spacers, at adjusters.\n"
            "6. **Safety:** Secure ang motor sa center stand o paddock stand, chock ang kabilang wheel, "
            "at ilayo ang kamay sa umiikot na wheel. Gumamit ng torque wrench sa axle — huwag mag-estimate.\n"
            "7. **Pagkatapos:** I-seat ang bead, inflate sa pressure na nakasulat sa tyre/owner's manual, check leaks gamit ang soapy water, "
            "i-spin ang wheel, at dahan-dahang i-test ang brakes sa safe area bago mag-normal ride.\n\n"
            "**Tip:** Palitan ang gulong nang pares kung uneven ang wear, at i-check muli ang pressure cold sa susunod na umaga. "
            "Kung cracked ang rim o damaged ang axle threads, huminto at ipa-shop na.\n\n"
            "[chips: Anong tyre pressure ang dapat gamitin? | Kailan dapat mag-change oil? | Brake maintenance checklist | Buong maintenance schedule]"
        ),
        'hil': (
            "**Antes mag-ilis sang gulong, ini ang mga dapat usisahon, {sir}:**\n\n"
            "1. **Size kag rating:** Basaha ang sidewall (hal. 90/80-14) kag siguraduha nga pareho ang replacement. "
            "Check ang load/speed rating, kag kon tube-type ukon tubeless ang rim mo.\n"
            "2. **Kondisyon:** Tread depth nga indi kubos sa **1.6 mm**, wala sang cracks, bulges, ukon naka-embed nga nails/screws. "
            "Usisahon ang rim kon may bingkong, crack, ukon kalawang.\n"
            "3. **Tools:** Tyre levers, rim protectors, bead breaker (ukon shop), torque wrench, bag-o nga valve stem kon kinahanglan, "
            "pump with gauge, kag soapy water para sa leak check.\n"
            "4. **Brake kag chain clearance:** Siguraduha nga indi baluktot ang disc rotor, indi contaminated ang pads, kag may clearance ang chain/sprocket. "
            "Sa drum brake, tandaan ang shoe kag spring orientation antes tanggalon.\n"
            "5. **Wheel bearings kag spokes:** I-rock ang wheel para sa play kag check kon tight ang spokes. "
            "Itago sing maayo ang axle nut, spacers, kag adjusters.\n"
            "6. **Safety:** Secure ang motor sa center stand ukon paddock stand, chock ang isa ka wheel, "
            "kag ilayo ang kamot sa nagatuyok nga wheel. Gamita ang torque wrench sa axle — indi mag-estimate.\n"
            "7. **Pagkatapos:** I-seat ang bead, inflate sa pressure nga nakasulat sa tyre/owner's manual, check leaks gamit soapy water, "
            "i-spin ang wheel, kag hinay-hinay i-test ang brakes sa safe area antes mag-normal ride.\n\n"
            "**Tip:** Ilisan ang gulong sing pares kon uneven ang wear, kag i-check liwat ang pressure cold sa sunod nga aga. "
            "Kon cracked ang rim ukon damaged ang axle threads, hunong kag ipa-shop na.\n\n"
            "[chips: Ano nga tyre pressure ang dapat gamiton? | San-o dapat mag-ilis sang langis? | Brake maintenance checklist | Bug-os nga maintenance schedule]"
        ),
    },
    'general_chain': {
        'tl': (
            "**Chain care, {sir}:**\n\n"
            "- **Linis at lube:** Every **500 km** o pagkatapos ng ulan. Gumamit ng chain cleaner at dedicated chain lube — "
            "ang WD-40 ay cleaner/water displacer, hindi kapalit ng chain lubricant.\n"
            "- **Slack:** Karaniwang **20–35 mm** sa midpoint (i-confirm sa manual). Adjust sa rear axle at panatilihing aligned ang wheel.\n"
            "- **Inspection:** Tight links, rust, missing O-rings, at hooked/sharp sprocket teeth. "
            "Kung worn na ang chain, palitan ang chain at sprockets nang sabay — mabilis masira ang bagong chain sa worn sprockets.\n"
            "- **Safety:** Engine off, neutral, ilayo ang kamay sa sprocket, at gumamit ng paddock stand. "
            "Huwag sobrang higpitan ang chain; makakasira ito ng countershaft bearing.\n\n"
            "**Quick check:** Sa stand, i-spin slowly ang rear wheel at panoorin ang chain. "
            "Ang dry o kinked chain ay may tight spots habang dumadaan sa sprocket.\n\n"
            "[chips: Kailan dapat mag-change oil? | Ano ang titingnan bago magpalit ng gulong? | Brake maintenance checklist | Buong maintenance schedule]"
        ),
        'hil': (
            "**Chain care, {sir}:**\n\n"
            "- **Linis kag lana:** Every **500 km** ukon pagkatapos sang ulan. Gamita ang chain cleaner kag dedicated chain lube — "
            "ang WD-40 cleaner/water displacer, indi kapareho sang chain lubricant.\n"
            "- **Slack:** Kasadyahan **20–35 mm** sa midpoint (i-confirm sa manual). Adjust sa rear axle kag panatiliha nga aligned ang wheel.\n"
            "- **Inspection:** Tight links, rust, missing O-rings, kag hooked/sharp sprocket teeth. "
            "Kon worn na ang chain, ilisan ang chain kag sprockets sing dungan — madasig maguba ang bag-o nga chain sa worn sprockets.\n"
            "- **Safety:** Engine off, neutral, ilayo ang kamot sa sprocket, kag gamita ang paddock stand. "
            "Indi sobra higot ang chain; makaguba ini sang countershaft bearing.\n\n"
            "**Quick check:** Sa stand, i-spin slowly ang rear wheel kag tan-awa ang chain. "
            "Ang dry ukon kinked chain may tight spots samtang nagalabay sa sprocket.\n\n"
            "[chips: San-o dapat mag-ilis sang langis? | Ano ang usisahon antes mag-ilis sang gulong? | Brake maintenance checklist | Bug-os nga maintenance schedule]"
        ),
    },
    'general_brakes': {
        'tl': (
            "**Brake maintenance checklist, {sir}:**\n\n"
            "- **Pads/shoes:** Check every **2,000–4,000 km** o monthly. Palitan ang disc pads kapag mga **2 mm** na lang ang lining; "
            "palitan ang drum shoes kapag manipis o contaminated ang friction material.\n"
            "- **Fluid:** Check ang reservoir level at kulay. Bleed every **1–2 taon**, o mas maaga kapag spongy ang lever. "
            "Gamitin ang DOT 3/DOT 4 na nakasulat sa cap — huwag paghalo.\n"
            "- **Disc/drum:** Tingnan kung may deep grooves, blue heat spots, o warped rotor. Dapat firm ang lever/pedal at hold ang pressure.\n"
            "- **Leaks:** Check ang master cylinder, hose, caliper, at banjo bolts para sa wet spots o crusty residue.\n"
            "- **Safety:** Huwag i-ride kung lumulubog ang lever, may leak, o may metal grinding. "
            "Nakakalason ang brake dust — gumamit ng gloves at mask, at magtrabaho sa maaliwalas na lugar.\n\n"
            "**When to stop:** Kung cracked ang brake line, seized ang caliper piston, o below minimum thickness ang rotor, "
            "palitan ang affected parts imbes na i-adjust pa.\n\n"
            "[chips: Kailan dapat mag-change oil? | Ano ang titingnan bago magpalit ng gulong? | Paano linisin at lagyan ng langis ang chain? | Buong maintenance schedule]"
        ),
        'hil': (
            "**Brake maintenance checklist, {sir}:**\n\n"
            "- **Pads/shoes:** Check every **2,000–4,000 km** ukon monthly. Ilisan ang disc pads kon mga **2 mm** na lang ang lining; "
            "ilisan ang drum shoes kon manipis ukon contaminated ang friction material.\n"
            "- **Fluid:** Check ang reservoir level kag kolor. Bleed every **1–2 ka tuig**, ukon mas temprano kon spongy ang lever. "
            "Gamita ang DOT 3/DOT 4 nga nakasulat sa cap — indi paghalo.\n"
            "- **Disc/drum:** Tan-awa kon may deep grooves, blue heat spots, ukon warped rotor. Dapat matig-a ang lever/pedal kag hold ang pressure.\n"
            "- **Leaks:** Check ang master cylinder, hose, caliper, kag banjo bolts para sa wet spots ukon crusty residue.\n"
            "- **Safety:** Indi mag-ride kon nagalubog ang lever, may leak, ukon may metal grinding. "
            "Makahilo ang brake dust — gamita ang gloves kag mask, kag magtrabaho sa maayo ang hangin nga lugar.\n\n"
            "**When to stop:** Kon cracked ang brake line, seized ang caliper piston, ukon below minimum thickness ang rotor, "
            "ilisan ang affected parts imbes nga i-adjust pa.\n\n"
            "[chips: San-o dapat mag-ilis sang langis? | Ano ang usisahon antes mag-ilis sang gulong? | Paano limpyohan kag butangan sang lana ang chain? | Bug-os nga maintenance schedule]"
        ),
    },
    'general_schedule': {
        'tl': (
            "**Routine motorcycle maintenance schedule, {sir}:**\n\n"
            "- **Bago bawat ride:** Tyres, brakes, lights, chain, at quick look para sa leaks.\n"
            "- **Weekly:** Cold tyre pressure, chain lubrication, engine oil level, brake fluid level, at coolant level (kung liquid-cooled).\n"
            "- **Every 2,000–4,000 km:** Engine oil at filter, air-filter check, chain adjustment, brake inspection.\n"
            "- **Every 4,000–6,000 km:** Spark plug, valve-clearance check (kung applicable), CVT inspection sa scooter.\n"
            "- **Every 8,000–12,000 km:** CVT belt at rollers, brake fluid, fork oil, wheel bearings, at suspension check.\n"
            "- **Yearly o ayon sa manual:** Coolant replacement, brake fluid flush, battery check, at full fastener/torque check.\n\n"
            "**Importante:** Typical intervals ito para sa araw-araw na paggamit. Traffic, alikabok, ulan, at hard riding ay nagpapashorten nito; "
            "ang owner's manual at kondisyon ng parts ang final authority. "
            "Kung heavy traffic o maalikabok ang ruta, gawin ang oil at air-filter service sa mas maikling interval.\n\n"
            "[chips: Kailan dapat mag-change oil? | Ano ang titingnan bago magpalit ng gulong? | Paano linisin at lagyan ng langis ang chain? | Brake maintenance checklist]"
        ),
        'hil': (
            "**Routine motorcycle maintenance schedule, {sir}:**\n\n"
            "- **Antes sang kada ride:** Tyres, brakes, lights, chain, kag quick look para sa leaks.\n"
            "- **Weekly:** Cold tyre pressure, chain lubrication, engine oil level, brake fluid level, kag coolant level (kon liquid-cooled).\n"
            "- **Every 2,000–4,000 km:** Engine oil kag filter, air-filter check, chain adjustment, brake inspection.\n"
            "- **Every 4,000–6,000 km:** Spark plug, valve-clearance check (kon applicable), CVT inspection sa scooter.\n"
            "- **Every 8,000–12,000 km:** CVT belt kag rollers, brake fluid, fork oil, wheel bearings, kag suspension check.\n"
            "- **Tuig-tuig ukon suno sa manual:** Coolant replacement, brake fluid flush, battery check, kag full fastener/torque check.\n\n"
            "**Importante:** Typical intervals ini para sa adlaw-adlaw nga paggamit. Traffic, abog, ulan, kag hard riding nagapamubo sini; "
            "ang owner's manual kag kondisyon sang parts ang final authority. "
            "Kon heavy traffic ukon madamo abog ang ruta, himuoa ang oil kag air-filter service sa mas malip-ot nga interval.\n\n"
            "[chips: San-o dapat mag-ilis sang langis? | Ano ang usisahon antes mag-ilis sang gulong? | Paano limpyohan kag butangan sang lana ang chain? | Brake maintenance checklist]"
        ),
    },
    'general_help': {
        'tl': (
            "Matutulungan kita sa kahit anong tanong tungkol sa motor, {sir} — hindi lang kapag may sira. "
            "Ito ang mga quick baseline na pwede mong gamitin agad:\n\n"
            "- **Oil/filter:** 2,000–4,000 km o 3–6 buwan; JASO MA/MA2 4T oil; filter ayon sa manual.\n"
            "- **Tyres:** Check cold pressure weekly (karaniwang 29–33 psi front / 33–36 psi rear), tread at least 1.6 mm, "
            "walang cracks, bulges, o nails.\n"
            "- **Chain:** Linis at lube every 500 km; 20–35 mm slack; palitan ang chain at sprockets nang sabay kapag worn.\n"
            "- **Brakes:** Pads at least 2 mm, fluid clear at level, firm lever; bleed every 1–2 taon o kapag spongy.\n"
            "- **Battery:** 12.6 V+ at rest, 13.5–14.5 V while charging; typical life 3–5 taon.\n"
            "- **CVT:** Inspect belt at rollers around 8,000–12,000 km; palitan ayon sa wear at manual.\n"
            "- **Coolant:** Check cold monthly; palitan every 2 taon o ayon sa manual.\n\n"
            "Sabihin lang ang model ng motor mo (optional) at kung ano ang gusto mong gawin — oil change, tyre change, chain care, brake check, "
            "o full service — at ibibigay ko ang interval, tools, steps, at safety notes. "
            "Ang owner's manual ang laging final authority sa exact specs.\n\n"
            "[chips: Kailan dapat mag-change oil? | Ano ang titingnan bago magpalit ng gulong? | Paano linisin at lagyan ng langis ang chain? | Brake maintenance checklist | Buong maintenance schedule]"
        ),
        'hil': (
            "Mabuligan ko ikaw sa bisan ano nga pamangkot parte sa motor, {sir} — indi lang kon may guba. "
            "Ini ang mga quick baseline nga pwede mo gamiton dayon:\n\n"
            "- **Oil/filter:** 2,000–4,000 km ukon 3–6 ka bulan; JASO MA/MA2 4T oil; filter suno sa manual.\n"
            "- **Tyres:** Check cold pressure weekly (kasadyahan 29–33 psi front / 33–36 psi rear), tread at least 1.6 mm, "
            "wala sang cracks, bulges, ukon nails.\n"
            "- **Chain:** Linis kag lube every 500 km; 20–35 mm slack; ilisan ang chain kag sprockets sing dungan kon worn.\n"
            "- **Brakes:** Pads at least 2 mm, fluid clear kag level, matig-a lever; bleed every 1–2 ka tuig ukon kon spongy.\n"
            "- **Battery:** 12.6 V+ at rest, 13.5–14.5 V while charging; kasadyahan nga kabuhi 3–5 ka tuig.\n"
            "- **CVT:** Inspect belt kag rollers around 8,000–12,000 km; ilisan suno sa wear kag manual.\n"
            "- **Coolant:** Check cold monthly; ilisan every 2 ka tuig ukon suno sa manual.\n\n"
            "Sugiri lang ang model sang motor mo (optional) kag ano ang gusto mo himuon — oil change, tyre change, chain care, brake check, "
            "ukon full service — kag ihatag ko ang interval, tools, steps, kag safety notes. "
            "Ang owner's manual ang permi final authority sa exact specs.\n\n"
            "[chips: San-o dapat mag-ilis sang langis? | Ano ang usisahon antes mag-ilis sang gulong? | Paano limpyohan kag butangan sang lana ang chain? | Brake maintenance checklist | Bug-os nga maintenance schedule]"
        ),
    },

    # ───────────────────────── Stats ──────────────────────────────────────────
    'stats_symptoms': {
        'tl': (
            "Nakatala sa diagnostic archive na **{count}** kilalang sintomas ng sasakyan, {sir}.\n\n"
            "[chips: Listahan ng mga sintomas | Ilan ang gabay | Ilan ang pyesa]"
        ),
        'hil': (
            "Natala sa diagnostic archive nga **{count}** kilala nga sintomas sang salakyan, {sir}.\n\n"
            "[chips: Listahan sang mga sintomas | Pila ang gabay | Pila ang pyesa]"
        ),
    },
    'stats_parts': {
        'tl': (
            "May **{count}** pyesa sa workshop inventory, {sir}.\n\n"
            "[chips: Listahan ng lahat ng pyesa | Magtanong ng diagnostic | Suriin ang pagsisimula ng makina]"
        ),
        'hil': (
            "May **{count}** ka pyesa sa workshop inventory, {sir}.\n\n"
            "[chips: Listahan sang tanan nga pyesa | Pamangkot diagnostic | Suri-on ang pagtiyog sang makina]"
        ),
    },
    'stats_guides': {
        'tl': (
            "May **{count}** troubleshooting protocol akong handa sa workshop archive, {sir}.\n\n"
            "[chips: Listahan ng mga sintomas | Listahan ng mga pyesa | Ayaw mag-start ang makina]"
        ),
        'hil': (
            "May **{count}** ka troubleshooting protocol ako nga handa sa workshop archive, {sir}.\n\n"
            "[chips: Listahan sang mga sintomas | Listahan sang mga pyesa | Indi mag-andar ang makina]"
        ),
    },

    # ───────────────────────── Misc ───────────────────────────────────────────
    'thanks': {
        'tl': (
            "Anumang oras, {sir}. Nakahanda si J.A.R.V.I.S. sa standby. "
            "Mag-ingat sa pagmamaneho, at huwag mag-atubiling magpa-diagnose muli kapag kailangan.\n\n"
            "[chips: Suriin ang pagsisimula ng makina | Sira ang preno | Acoustic noise scan]"
        ),
        'hil': (
            "Bisang anumang oras, {sir}. Nakahanda si J.A.R.V.I.S. sa standby. "
            "Mag-amlig sa pagmaneho, kag indi magpanumang pag-usisa liwat kon kinahanglan.\n\n"
            "[chips: Suri-on ang pagtiyog sang makina | Guba ang preno | Acoustic noise scan]"
        ),
    },
    'fallback': {
        'tl': (
            "Pasensya na, hindi ko nakuha iyon, {sir}. Ito ang matutulungan ko sa iyo:\n\n"
            "• **Diagnostics** — Ayaw mag-start ng makina, sira ng preno, umainit ang makina, problema sa takbo\n"
            "• **Paliwanag sa pyesa** — Itanong mo sa akin *\"Ano ang caliper?\"* o *\"Ano ang sprocket?\"* at ipapakita ko ang litrato\n"
            "• **Repair protocols** — Hakbang-hakbang na interactive checklist para sa mga karaniwang ayos\n"
            "• **Parts inventory** — Presyo, part number, at mga gabay mula sa workshop database\n\n"
            "Pumili sa mga opsyon sa ibaba, o ilarawan ang sintomas ng sasakyan mo nang detalyado:\n\n"
            "[chips: Ayaw mag-start ng makina | Sira ang preno | Ano ang caliper? | Ano ang sprocket? | Palit ng langis | Patay na baterya]"
        ),
        'hil': (
            "Pasensya na, wala ko na sabtan ina, {sir}. Ini ang mabuligan ko sa imo:\n\n"
            "• **Diagnostics** — Indi mag-andar ang makina, guba nga preno, naga-init ang makina, problema sa kadasigon\n"
            "• **Paliwanag sang pyesa** — Pamangkuta ako *\"Ano ang caliper?\"* ukon *\"Ano ang sprocket?\"* kag ipakita ko ang hulagway\n"
            "• **Repair protocols** — Sunod-sunod nga interactive checklist para sa mga komon nga ayuhon\n"
            "• **Parts inventory** — Presyo, part number, kag mga gabay halin sa workshop database\n\n"
            "Pilia ang mga opsyon sa idalom, ukon isaysay ang sintomas sang salakyan mo:\n\n"
            "[chips: Indi mag-andar ang makina | Guba ang preno | Ano ang caliper? | Ano ang sprocket? | Ilis nga langa | Patay nga baterya]"
        ),
    },
}
