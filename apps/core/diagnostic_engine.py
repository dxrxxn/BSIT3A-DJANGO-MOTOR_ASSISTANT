"""
Motor Assistant Intelligent Diagnostic Engine.

Implements Phases 2, 4, 5, 6, and 7:
- Multi-turn diagnostic session tracking (vehicle details, answered questions).
- Single most discriminative question selection (no question bombardment).
- Safety tripwires & mandatory warnings (brakes, overheating scald risk, fuel leaks, rod knock).
- Strict 9-point Step-by-Step Repair Tutor formatting.
- Configurable multi-provider AI gateway (Gemini, OpenAI-compatible).
- Grounded local knowledge retrieval fallback (explicitly labelled).
- Multilingual support (English, Tagalog, Hiligaynon).
"""
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from apps.motor.knowledge import retrieve_verified_knowledge

logger = logging.getLogger(__name__)


SAFETY_TRIPWIRES = {
    'brake_failure': {
        'triggers': ['spongy', 'soft', 'malambot', 'humok', 'walang preno', 'preno', 'brake failure', 'pedal to floor', 'no brakes', 'fluid leak', 'brake fluid'],
        'urgency': 'critical_stop',
        'en': 'CRITICAL SAFETY HAZARD: DO NOT RIDE OR DRIVE. Operating a vehicle with soft, spongy, or failing brakes can cause a fatal crash. Park the vehicle immediately on level ground.',
        'tl': 'MAHIGPIT NA BABALA SA KALIGTASAN: HUWAG MUNANG IMANEHO O ITULOY ANG PAG-ANDAR. Lubhang delikado ang malambot o walang preno. Iparada agad ang sasakyan sa ligtas na lugar.',
        'hil': 'MAHUGOD NGA PAHILIG-AN SA KALIGTASAN: INDII GID PAGPADALAGNA ANG SALAKYAN. Makatalagam ang humok ukon wala sing preno. Ipundo kag iparking gilayon ang salakyan sa hilway nga lugar.',
    },
    'overheating_scald': {
        'triggers': ['overheat', 'boiling', 'radiator', 'steam', 'singaw', 'kumukulo', 'nagabukal', 'temp light', 'high temperature'],
        'urgency': 'critical_stop',
        'en': 'SEVERE SCALD HAZARD: NEVER OPEN A HOT RADIATOR CAP. Boiling pressurized coolant will violently erupt causing catastrophic third-degree burns. Allow engine to cool for at least 45 minutes.',
        'tl': 'BABALA SA INIT AT PASO: HUWAG NA HUWAG BUBUKSAN ANG RADIATOR CAP HABANG MAINIT ANG MAKINA. Sasabog ang kumukulong coolant at magdudulot ng malubhang paso. Maghintay nang hindi bababa sa 45 minuto.',
        'hil': 'PAHILIG-AN SA PASO: INDII GID PAGBUKSI ANG RADIATOR CAP SAMTANG MAINIT ANG MAKINA. Magasabwag ang nagabukal nga coolant kag magatuga sing grabe nga paso. Palipasa anay ang 45 minutos tubtob magbugnaw.',
    },
    'fuel_leak': {
        'triggers': ['fuel leak', 'gas leak', 'amoy gasolina', 'tumutulo gasolina', 'nagasulod gas', 'dripping fuel', 'raw gas'],
        'urgency': 'critical_stop',
        'en': 'FIRE HAZARD: Active fuel leak detected. Switch off engine, do not smoke or use phone nearby, and disconnect battery negative terminal.',
        'tl': 'PANGANIB SA SUNOG: May tagas ng gasolina. Patayin agad ang makina, huwag manigarilyo, at tanggalin ang negative terminal ng baterya.',
        'hil': 'KATALAGMAN SA KALAYO: May tulo sang gasolina. Patya gilayon ang makina, indi magpanigarilyo, kag kuhaa ang negative terminal sang baterya.',
    },
    'rod_knock': {
        'triggers': ['rod knock', 'deep knock', 'katok sa makina', 'lagabog sa ilalim', 'crankshaft knock', 'tok tok tok sa loob'],
        'urgency': 'critical_stop',
        'en': 'CRITICAL ENGINE FAILURE: Deep bottom-end metallic knock detected. SHUT DOWN ENGINE IMMEDIATELY. Continued running will throw connecting rod through the crankcase, causing total engine destruction and wheel lockup.',
        'tl': 'MALUBHANG PAGKASIRA NG MAKINA: Malalim na katok mula sa ilalim ng makina. PATAYIN AGAD ANG MAKINA. Pwedeng mabali ang connecting rod at mawasak ang crankcase.',
        'hil': 'GRABE NGA GUGMA SANG MAKINA: Madalom nga lagabog sa dalom sang makina. PATYA GILAYON ANG MAKINA. Mahimo mabali ang connecting rod kag magisi ang crankcase.',
    },
}


def evaluate_safety_hazards(query, lang='english'):
    """Checks query against critical safety tripwires and returns alert if matched."""
    q_lower = query.lower()
    for hazard_key, data in SAFETY_TRIPWIRES.items():
        if any(trig in q_lower for trig in data['triggers']):
            alert_text = data.get(lang[:2], data['en'])
            return {
                'hazard_key': hazard_key,
                'urgency': data['urgency'],
                'alert_text': alert_text,
            }
    return None


class DiagnosticSession:
    """Tracks multi-turn vehicle details, symptom context, and answered questions."""

    def __init__(self, message, history, user=None, language=None, experience_level=None, guided_state=None):
        self.message = message or ''
        self.history = history or []
        self.user = user
        self.guided_state = guided_state or {}

        # Build full conversation text corpus
        corpus_parts = [self.message]
        if isinstance(self.history, list):
            for turn in self.history:
                corpus_parts.append(turn.get('text', ''))
        self.corpus = " ".join(corpus_parts).lower()

        # Vehicle extraction
        from .views import _extract_vehicle_info, _detect_language
        self.vehicle_info = _extract_vehicle_info(self.message, self.history)
        self.language = language or _detect_language(self.message, self.history)
        self.experience_level = experience_level or 'beginner'

        # Classify vehicle_type ('motorcycle', 'car', or 'all')
        v_type = self.vehicle_info.get('type') or ''
        if v_type in ('car', 'sedan', 'suv', 'truck', 'van'):
            self.vehicle_type = 'car'
        elif v_type in ('motorcycle', 'scooter', 'tricycle'):
            self.vehicle_type = 'motorcycle'
        else:
            self.vehicle_type = 'all'

        # Holistic session analysis (Bug 1 & Bug 2)
        self.is_issue_resolved = self._check_issue_resolved()
        self.is_reset = self._check_reset()
        self.is_procedure_continuation = self._check_procedure_continuation()
        self.is_unsuccessful_attempt = self._check_unsuccessful_attempt()

        # Check if an active symptom was mentioned in current message
        from .guided_diagnostic import detect_area, _has_active_fault
        symptom_form_match = re.search(r'symptom:\s*(.+)', self.message, re.I)
        has_form_symptom = bool(symptom_form_match and len(symptom_form_match.group(1).strip()) > 3)
        current_symptom = detect_area(self.message) or _has_active_fault(self.message) or (symptom_form_match.group(1).strip() if symptom_form_match else None)

        # Analyze session history if current message does not state a new symptom
        history_symptom = None
        if not current_symptom and not self.is_issue_resolved and not self.is_reset:
            history_symptom = self._extract_history_symptom()

        if not current_symptom and not history_symptom and not self.is_issue_resolved and not self.is_reset and self.guided_state:
            history_symptom = self.guided_state.get('area')
            if not self.vehicle_info.get('model') and self.guided_state.get('bike'):
                self.vehicle_info['model'] = self.guided_state.get('bike')

        self.active_symptom = current_symptom or history_symptom
        self.has_active_symptom = bool(self.active_symptom)

        # Retrieve relevant verified knowledge only when a symptom is being diagnosed
        if self.has_active_symptom:
            search_query = self.message if current_symptom else f"{self.active_symptom} {self.corpus[:200]}"
            self.verified_knowledge = retrieve_verified_knowledge(
                search_query,
                vehicle_type=self.vehicle_type,
                max_results=2
            )
        else:
            self.verified_knowledge = []

        # Safety evaluation
        self.safety_hazard = evaluate_safety_hazards(self.message, self.language)
        if not self.safety_hazard and self.active_symptom and not current_symptom:
            self.safety_hazard = evaluate_safety_hazards(str(self.active_symptom), self.language)
        if not self.safety_hazard and self.verified_knowledge:
            top_s = self.verified_knowledge[0]
            if top_s.get('urgency_level') == 'critical_stop' and top_s.get('safety_warning'):
                self.safety_hazard = {
                    'hazard_key': 'kb_critical',
                    'urgency': 'critical_stop',
                    'alert_text': top_s['safety_warning'],
                }

        # Analyze answered questions vs remaining questions
        self.answered_questions = self._extract_answered_questions()
        self.next_question = self._select_next_question()

    def _extract_answered_questions(self):
        answered = {}
        # Keyword mappings for common diagnostic answers
        answers_map = {
            'rapid_clicking': ['rapid clicking', 'clicking', 'nag-click', 'nagaklik', 'click click', 'tunog relay'],
            'slow_crank': ['slow crank', 'mabagal umikot', 'mabug-at magtuyok', 'weak crank'],
            'dead_silent': ['dead', 'tahimik', 'walang ilaw', 'patay', 'zero lights'],
            'cranks_no_start': ['cranks but won\'t start', 'umaandar starter pero ayaw mag-start', 'nagatuyok pero indi mag-andar'],
            'fluid_ok': ['fluid is full', 'above min', 'may langis pa preno', 'puno ang fluid', 'fluid ok'],
            'fluid_low': ['empty fluid', 'below min', 'walang fluid', 'ubos ang fluid'],
            'efi': ['efi', 'fuel injected', 'fi', 'pgm-fi'],
            'carb': ['carb', 'carburetor', 'karburador'],
            'better_with_choke': ['better with choke', 'gumaganda sa choke', 'nami sa choke'],
            'fan_dead': ['fan not working', 'fan not spinning', 'hindi umiikot ang fan', 'wala nagatuyok ang fan'],
            'fan_runs': ['fan is spinning', 'umiikot ang fan', 'nagatuyok ang fan'],
        }

        for ans_key, triggers in answers_map.items():
            if any(t in self.corpus for t in triggers):
                answered[ans_key] = True
        return answered

    def _select_next_question(self):
        """Picks the single most discriminative unanswered question."""
        if not self.verified_knowledge:
            return None

        primary = self.verified_knowledge[0]
        questions = primary.get('questions', [])
        for q in questions:
            # Check if any of its options are already answered
            is_answered = False
            for opt in q.get('options', []):
                val = opt.get('value', '')
                if val in self.answered_questions:
                    is_answered = True
                    break
            if not is_answered:
                return q
        return None

    def has_sufficient_diagnostic_data(self):
        """Returns True if vehicle intake is done and either no questions remain or a key question was answered."""
        has_vehicle = bool(self.vehicle_info.get('make') or self.vehicle_info.get('model') or self.vehicle_type != 'all')
        has_answers = bool(self.answered_questions) or (self.next_question is None)
        return has_vehicle and has_answers

    def _check_issue_resolved(self):
        msg = self.message.lower().strip()
        resolved_words = [
            'it worked', 'that worked', 'worked, thanks', 'problem solved',
            'fixed it', 'it is fixed', "it's fixed", 'feel better', 'feels better',
            'okay now', 'ok now', 'noise is gone', 'smoke is gone', 'nagana na',
            'naayos na', 'ok na', 'ayos na', 'all fixed', 'problem is fixed',
        ]
        return any(w in msg for w in resolved_words)

    def _check_reset(self):
        msg = self.message.lower().strip()
        reset_words = [
            'start over', 'start again', 'new problem', 'another problem', 'reset',
            'simula ulit', 'bagong problema', 'sugod liwat', 'clear chat',
        ]
        return any(w in msg for w in reset_words)

    def _check_procedure_continuation(self):
        msg = self.message.lower().strip()
        continue_words = [
            'proceed', 'start', 'commence', 'begin', 'continue', 'next', 'next step',
            'step 1', 'step one', 'first step', 'step 2', 'step two', 'step 3', 'step 4',
            "let's start", "lets start", "let's do it", "lets do it", 'ready', 'sige', 'umpisahan',
            'simulan', 'padayon', 'tuloy', 'read step 1', 'read step one', 'ok', 'okay',
            'sure', 'go ahead', 'yes', 'oo', 'sige proceed', 'do it', 'gawin natin',
            'ready to start', 'yes, ready', 'what is step 2', 'what is step 1', 'show step 2',
            'what next', "what's next", 'what do i do next', 'what to do next', 'ano susunod',
        ]
        is_cont = any(w in msg for w in continue_words) or bool(re.search(r'\b(?:step|hakbang|tikang)\s*\d+\b', msg))
        if not is_cont:
            return False

        if isinstance(self.history, list) and self.history:
            last_assistant_turns = [t for t in self.history if t.get('role') != 'user']
            if last_assistant_turns:
                last_txt = last_assistant_turns[-1].get('text', '').lower()
                if any(w in last_txt for w in ['step', 'procedure', 'commence', 'checklist', 'troubleshoot', 'inspect', '- [ ]', 'checks']):
                    return True

        return bool(self._extract_history_symptom() or self.guided_state.get('area'))

    def _extract_requested_step(self):
        msg = self.message.lower().strip()
        m = re.search(r'\b(?:step|hakbang|tikang)\s*(\d+)\b', msg)
        if m:
            return int(m.group(1))
        # Check history to see what was the last step given
        if isinstance(self.history, list):
            for turn in reversed(self.history):
                txt = turn.get('text', '')
                sm = re.search(r'\b(?:Step|Hakbang|Tikang)\s*(\d+)\b', txt)
                if sm:
                    return int(sm.group(1)) + 1
        return 1

    def _check_unsuccessful_attempt(self):
        msg = self.message.lower().strip()
        unsuccessful_words = [
            "didn't work", 'didnt work', 'still not fixed', 'still not working',
            'still broken', 'hindi pa', 'hindi gumana', 'ayaw pa rin', 'wala pa rin',
            'wala nagbago', 'indi gihapon', 'indi nag-andar', 'same problem', 'no difference',
            'abnormal', 'failed', 'wala epekto', 'hindi nagbago', 'still having problem',
            'did not work', 'does not work either', 'didnt fix it',
        ]
        if any(w in msg for w in unsuccessful_words):
            return True
        if ('not working' in msg or 'not work' in msg) and isinstance(self.history, list) and len(self.history) >= 2:
            return True
        return False

    def _extract_history_symptom(self):
        """Scans session history backwards to recover an active, unresolved symptom."""
        if not isinstance(self.history, list):
            return None
        from .guided_diagnostic import detect_area, _has_active_fault
        for turn in reversed(self.history):
            txt = (turn.get('text') or '').strip()
            area = detect_area(txt)
            if area:
                return area
            if _has_active_fault(txt):
                return txt[:80]
            match = re.search(r'symptom:\s*(.+)', txt, re.I)
            if match and len(match.group(1).strip()) > 3:
                return match.group(1).strip()
        return None


def extract_procedure_steps(text):
    if not text:
        return []
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    steps = []
    current_step = []
    for line in lines:
        if re.match(r'^(?:-\s*\[\s*\]\s*)?\d+[\.\)]', line):
            if current_step:
                steps.append("\n".join(current_step).strip())
                current_step = []
            cleaned = re.sub(r'^(?:-\s*\[\s*\]\s*)?\d+[\.\)]\s*', '', line).strip()
            current_step.append(cleaned)
        elif current_step:
            current_step.append(line)
    if current_step:
        steps.append("\n".join(current_step).strip())
    if not steps and text:
        steps = [text.strip()]
    return steps


class LocalTutorFormatter:
    """Formats verified database knowledge into the strict 9-point Step-by-Step Repair Tutor."""

    @staticmethod
    def format_step(session, step_num=1):
        lang = session.language
        v_info = session.vehicle_info
        veh_label = " ".join(filter(None, [v_info.get('year'), v_info.get('make'), v_info.get('model')])).strip()
        if not veh_label:
            veh_label = "Your Vehicle" if lang == 'english' else ("Sasakyan mo" if lang == 'tagalog' else "Salakyan mo")

        symptom_name = session.active_symptom or "Mechanical Fault"
        top_symptom = session.verified_knowledge[0] if session.verified_knowledge else None
        if top_symptom:
            symptom_name = top_symptom.get('symptom_name', symptom_name)
            guides = top_symptom.get('guides', [])
            primary_guide = guides[0] if guides else {}
            raw_instructions = primary_guide.get('repair_instructions', '').strip()
            steps = extract_procedure_steps(raw_instructions)
            tools = primary_guide.get('tools_required') or "Basic metric hand tools and clean shop towels."
            expected = primary_guide.get('expected_result') or "Operating parameter returns to normal factory specification."
            differs = primary_guide.get('alternative_outcome') or "If abnormal, proceed to subsequent component tests."
        else:
            from .guided_diagnostic import AREAS, pick_verdict
            area_info = AREAS.get(session.active_symptom, {})
            v = pick_verdict(session.active_symptom, {}) if session.active_symptom in AREAS else {}
            steps = v.get('free', []) or [c[1] for c in area_info.get('checks', [])]
            tools = "Basic metric hand tools, safety glasses, and clean shop towels."
            expected = "Component operates smoothly within manufacturer specification."
            differs = "If condition does not improve, proceed to secondary component tests."

        step_idx = max(0, step_num - 1)
        step_text = steps[step_idx] if steps and step_idx < len(steps) else (
            steps[-1] if steps else f"Inspect the {symptom_name} assembly for leaks, wear, or loose connections."
        )

        l_map = {
            'english': {
                'title': f"Step-by-Step Procedure for **{veh_label}** — {symptom_name}",
                'safety_label': "CRITICAL SAFETY DIRECTIVE",
                'step_label': f"Step {step_num}",
                'tools_label': "Required Tools & Preparation",
                'expected_label': "Expected Benchmark Reading",
                'differs_label': "What to do if the result differs",
                'ask': f"Perform this check, sir, and let me know what you find — did Step {step_num} pass or show an abnormal reading?",
                'chips': f"Step {step_num} passed (normal) | Step {step_num} failed (abnormal) | Next step | Show all steps | It worked",
            },
            'tagalog': {
                'title': f"Hakbang-Hakbang na Pagsusuri para sa **{veh_label}** — {symptom_name}",
                'safety_label': "MAHIGPIT NA DIREKTIBA SA KALIGTASAN",
                'step_label': f"Hakbang {step_num}",
                'tools_label': "Mga Kailangang Gamit at Paghahanda",
                'expected_label': "Inaasahang Normal na Sukat / Kundisyon",
                'differs_label': "Ano ang gagawin kapag iba ang lumabas na resulta",
                'ask': f"Gawin po ang hakbang na ito, sir, at sabihin kung ano ang inyong nakita sa Hakbang {step_num}.",
                'chips': f"Maayos ang Hakbang {step_num} | May depekto | Susunod na hakbang | Ipakita lahat | Nagana na",
            },
            'hiligaynon': {
                'title': f"Sunod-Sunod nga Pagsusuri para sa **{veh_label}** — {symptom_name}",
                'safety_label': "MAHUGOD NGA DIREKTIBA SA KALIGTASAN",
                'step_label': f"Tikang {step_num}",
                'tools_label': "Mga Kinahanglan nga Gamit kag Paghanda",
                'expected_label': "Ginalauman nga Normal nga Takus / Kahimtangan",
                'differs_label': "Ano ang himuon kon maglain ang resulta",
                'ask': f"Himua ini nga tikang, sir, kag sabta ako kon ano ang imo nakit-an sa Tikang {step_num}.",
                'chips': f"Maayo ang Tikang {step_num} | May diperensya | Sunod nga tikang | Ipakita tanan | Nagana na",
            },
        }

        L = l_map.get(lang, l_map['english'])
        out = []
        out.append(f"### {L['title']}\n")

        if session.safety_hazard:
            out.append(f"> [!CAUTION]\n> **{L['safety_label']}:** {session.safety_hazard['alert_text']}\n")
        elif top_symptom and top_symptom.get('safety_warning'):
            out.append(f"> [!WARNING]\n> **{L['safety_label']}:** {top_symptom['safety_warning']}\n")

        out.append(f"**{L['step_label']}:**\n{step_text}\n")
        out.append(f"**{L['tools_label']}:**\n{tools}\n")
        out.append(f"**{L['expected_label']}:**\n{expected}\n")
        out.append(f"**{L['differs_label']}:**\n{differs}\n")
        out.append(f"**{L['ask']}**")
        out.append(f"\n\n[chips: {L['chips']}]")
        return "\n".join(out)

    @staticmethod
    def format_step_one(session):
        return LocalTutorFormatter.format_step(session, step_num=1)

    @staticmethod
    def format_tutor(session, explanation_level='beginner'):
        lang = session.language
        v_info = session.vehicle_info
        veh_label = " ".join(filter(None, [v_info.get('year'), v_info.get('make'), v_info.get('model')])).strip()
        if not veh_label:
            veh_label = "Your Vehicle" if lang == 'english' else ("Sasakyan mo" if lang == 'tagalog' else "Salakyan mo")

        if not session.verified_knowledge:
            return None

        top_symptom = session.verified_knowledge[0]
        guides = top_symptom.get('guides', [])
        if not guides:
            return None

        primary_guide = guides[0]

        # Titles and labels localized
        l_map = {
            'english': {
                'summary': f"Diagnostic summary for **{veh_label}**: {top_symptom['symptom_name']}",
                'safety_label': "CRITICAL SAFETY DIRECTIVE",
                'causes_label': "Probable Cause Assessment",
                'tools_label': "Required Tools & Materials",
                'steps_label': "Step-by-Step Diagnostic & Repair Procedures",
                'expected_label': "Expected Benchmark Reading",
                'differs_label': "What to do if the result differs",
                'stop_label': "When to Stop & Consult a Qualified Mechanic",
                'resolved_q': "Did this test isolate and resolve the issue on your vehicle?",
                'source_label': "Verified Source Reference",
                'chips': "The test passed | Test showed abnormal reading | List of needed tools | Show next check",
            },
            'tagalog': {
                'summary': f"Buod ng pagsusuri para sa **{veh_label}**: {top_symptom['symptom_name']}",
                'safety_label': "MAHIGPIT NA DIREKTIBA SA KALIGTASAN",
                'causes_label': "Pagsusuri sa Malamang na Sanhi",
                'tools_label': "Mga Kailangang Gamit at Materyales",
                'steps_label': "Hakbang-Hakbang na Pagsusuri at Pag-aayos",
                'expected_label': "Inaasahang Normal na Sukat / Kundisyon",
                'differs_label': "Ano ang gagawin kapag iba ang lumabas na resulta",
                'stop_label': "Kailan Dapat Huminto at Kumonsulta sa Mekaniko",
                'resolved_q': "Naresolba ba o natukoy ang sira matapos isagawa ang hakbang na ito?",
                'source_label': "Pinagkunan / Verified Source",
                'chips': "Normal ang resulta | May depekto sa test | Listahan ng gamit | Susunod na hakbang",
            },
            'hiligaynon': {
                'summary': f"Kabilugan sang pagsusuri para sa **{veh_label}**: {top_symptom['symptom_name']}",
                'safety_label': "MAHUGOD NGA DIREKTIBA SA KALIGTASAN",
                'causes_label': "Pagsusuri sa Mahimo nga Kabangdanan",
                'tools_label': "Mga Kinahanglan nga Gamit kag Materyales",
                'steps_label': "Sunod-Sunod nga Pagsusuri kag Pagkay-o",
                'expected_label': "Ginalauman nga Normal nga Takus / Kahimtangan",
                'differs_label': "Ano ang himuon kon maglain ang resulta",
                'stop_label': "Kasan-o Dapat Magpundo kag Magpakig-angot sa Mekaniko",
                'resolved_q': "Nasolbar bala ukon nakit-an ang diperensya pagkatapos sini?",
                'source_label': "Ginsandigan nga Libro / Verified Source",
                'chips': "Normal ang resulta | May depekto sa test | Listahan sang gamit | Sunod nga tikang",
            },
        }

        L = l_map.get(lang, l_map['english'])

        out = []
        out.append(f"### {L['summary']}\n")

        # 2. Safety Warning
        if session.safety_hazard:
            out.append(f"> [!CAUTION]\n> **{L['safety_label']}:** {session.safety_hazard['alert_text']}\n")
        elif top_symptom.get('safety_warning'):
            out.append(f"> [!WARNING]\n> **{L['safety_label']}:** {top_symptom['safety_warning']}\n")

        # 3. Most likely causes with explicit uncertainty
        confidence = primary_guide.get('confidence_level', 'Medium')
        out.append(f"**{L['causes_label']}:**")
        out.append(f"- **Primary Hypothesis:** {primary_guide['possible_cause']} *(Confidence: {confidence})*")
        if len(guides) > 1:
            sec = guides[1]
            out.append(f"- **Secondary Possibility:** {sec['possible_cause']} *(Confidence: {sec.get('confidence_level', 'Tentative')})*")
        out.append("")

        # 4. Tools and Preparation
        tools = primary_guide.get('tools_required') or "Basic metric hand tools and clean shop towels."
        out.append(f"**{L['tools_label']}:**\n{tools}\n")

        # 5. Numbered diagnostic or repair steps
        instructions = primary_guide.get('repair_instructions', '').strip()
        out.append(f"**{L['steps_label']}:**\n{instructions}\n")

        # 6. Expected result after each important test
        if primary_guide.get('expected_result'):
            out.append(f"**{L['expected_label']}:**\n{primary_guide['expected_result']}\n")

        # 7. What to do if result differs
        if primary_guide.get('alternative_outcome'):
            out.append(f"**{L['differs_label']}:**\n{primary_guide['alternative_outcome']}\n")

        # 8. When to stop and consult a qualified mechanic
        when_stop = primary_guide.get('when_to_stop') or "Stop and consult a certified shop if mechanical disassembly requires specialized hydraulic press or pullers."
        out.append(f"**{L['stop_label']}:**\n{when_stop}\n")

        # Source reference
        if primary_guide.get('source_reference'):
            out.append(f"*{L['source_label']}: {primary_guide['source_reference']}*\n")

        # 9. Final question asking whether problem was resolved
        out.append(f"**{L['resolved_q']}**")
        out.append(f"\n\n[chips: {L['chips']}]")

        return "\n".join(out)


def call_configured_ai(prompt, system_instruction=None):
    """
    Dispatches prompt to the provider configured in settings / .env.
    Providers supported:
    - 'gemini' (Google GenAI SDK via GEMINI_API_KEY)
    - 'openai_compatible' (Any OpenAI-compatible REST endpoint)
    """
    provider = getattr(settings, 'AI_PROVIDER', 'gemini').lower()
    # Gemini and OpenAI-compatible providers use separate model settings.
    # Keep both env-driven; never embed a model name that may be unavailable
    # on the deployment's account.
    if provider == 'gemini':
        model = (
            getattr(settings, 'GEMINI_MODEL', '')
            or getattr(settings, 'AI_MODEL', '')
            or ''
        ).strip()
    else:
        model = (getattr(settings, 'AI_MODEL', '') or '').strip()
    api_key = getattr(settings, 'AI_API_KEY', '') or getattr(settings, 'GEMINI_API_KEY', '')
    base_url = getattr(settings, 'AI_API_BASE_URL', '')

    combined_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt

    if provider == 'gemini':
        from .views import _get_gemini_client
        client = _get_gemini_client()
        if not client:
            raise RuntimeError("Gemini client unavailable (check GEMINI_API_KEY).")
        if not model:
            raise RuntimeError('No Gemini model configured (set GEMINI_MODEL).')
        clean_model = model.replace('models/', '')
        from .services.ai import fallback_model_name
        try:
            response = client.models.generate_content(
                model=clean_model,
                contents=combined_prompt,
            )
        except Exception as api_err:
            fallback = fallback_model_name()
            if fallback and fallback != clean_model:
                # Log only the failure type.  Provider messages may contain
                # request details that should not be written to application logs.
                logger.info(
                    'Primary Gemini model failed (%s); trying the configured fallback.',
                    type(api_err).__name__,
                )
                response = client.models.generate_content(
                    model=fallback,
                    contents=combined_prompt,
                )
            else:
                raise
        # Record tokens
        try:
            from apps.core.models import GeminiUsageTracker
            meta = getattr(response, 'usage_metadata', None)
            p_tokens = getattr(meta, 'prompt_token_count', 0) or 0
            c_tokens = getattr(meta, 'candidates_token_count', 0) or 0
            GeminiUsageTracker.record_usage(prompt_tokens=p_tokens, candidates_tokens=c_tokens)
        except Exception as exc:
            logger.debug('Usage record skipped (%s).', type(exc).__name__)
        return response.text

    elif provider == 'openai_compatible':
        endpoint = base_url or 'http://localhost:8000/v1'
        url = endpoint.rstrip('/') + '/chat/completions'
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        messages = []
        if system_instruction:
            messages.append({'role': 'system', 'content': system_instruction})
        messages.append({'role': 'user', 'content': prompt})

        payload = json.dumps({
            'model': model,
            'messages': messages,
            'temperature': 0.3,
        }).encode('utf-8')

        req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data['choices'][0]['message']['content']

    else:
        raise ValueError(f"Unsupported AI_PROVIDER: {provider}")


def orchestrate_diagnostic_response(message, user, history=None, language=None, experience_level=None, guided_state=None):
    """
    Main entry point for intelligent diagnostic workflow:
    1. Evaluates session state, vehicle info, and safety tripwires.
    2. Retrieves verified database knowledge (RAG).
    3. If diagnostic testing is needed, asks ONE targeted question.
    4. Formats prompt with strict anti-hallucination guardrails and 9-point tutor format.
    5. Calls configured AI provider with seamless fallback to verified local database knowledge.
    """
    from .guided_diagnostic import _is_greeting
    if _is_greeting(message):
        return None
    session = DiagnosticSession(message, history, user=user, language=language, experience_level=experience_level, guided_state=guided_state)

    # 1. Immediate Critical Safety Notice
    safety_header = ""
    if session.safety_hazard and session.safety_hazard['urgency'] == 'critical_stop':
        safety_header = f"> [!CAUTION]\n> **SAFETY ALERT:** {session.safety_hazard['alert_text']}\n\n"

    # 1a. User confirmed to COMMENCE or CONTINUE step-by-step procedure: Deliver requested Step!
    if session.is_procedure_continuation and session.active_symptom:
        step_num = session._extract_requested_step()
        from .views import _jarvis_address
        sir = _jarvis_address(user)
        ai_step_system_prompt = f"""You are J.A.R.V.I.S., master automotive & motorcycle diagnostic assistant. Address user respectfully as '{sir}'.
The user requested Step {step_num} of the step-by-step diagnostic/repair procedure for active fault: {session.active_symptom}.
MANDATE:
1. Immediately present **Step {step_num}** of the diagnostic/repair procedure with complete detail:
   - Clear, step-by-step instructions.
   - Required tools & materials.
   - Expected benchmark reading / normal result.
   - What to do if the result differs / abnormal.
2. DO NOT ask what symptom they have or repeat intake questions.
3. Conclude with action chips: `[chips: Step {step_num} passed (normal) | Step {step_num} failed (abnormal) | Next step | Show all steps | It worked]`.
4. Language: Respond in {session.language.upper()}.
"""
        ai_step_prompt = f"User Request: '{message}'. Deliver Step {step_num} for vehicle: {session.vehicle_info}. Active Fault: {session.active_symptom}"
        try:
            ai_reply = call_configured_ai(ai_step_prompt, system_instruction=ai_step_system_prompt)
            if ai_reply and len(ai_reply.strip()) > 30:
                if session.safety_hazard and session.safety_hazard['alert_text'] not in ai_reply:
                    ai_reply = safety_header + ai_reply
                return ai_reply
        except Exception:
            pass

        local_step = LocalTutorFormatter.format_step(session, step_num=step_num)
        if local_step:
            return safety_header + local_step

    # 1b. If previous check/test was unsuccessful: Acknowledge & proceed to next check
    if session.is_unsuccessful_attempt and session.active_symptom:
        step_num = session._extract_requested_step()
        from .views import _jarvis_address
        sir = _jarvis_address(user)
        unsuccess_system_prompt = f"""You are J.A.R.V.I.S., master automotive & motorcycle diagnostic assistant. Address user respectfully as '{sir}'.
The user reports that the previous check/step was UNSUCCESSFUL ('{message}').
MANDATE:
1. Acknowledge that the previous check did not resolve the {session.active_symptom} problem.
2. Deliver the next diagnostic check (Step {step_num}) or secondary hypothesis.
3. DO NOT ask what symptom they have or start over from scratch!
4. Conclude with 3-5 action chips.
5. Language: Respond in {session.language.upper()}.
"""
        unsuccess_prompt = f"User Feedback: '{message}'. Issue: {session.active_symptom}. Vehicle: {session.vehicle_info}. Advance to Step {step_num}."
        try:
            ai_reply = call_configured_ai(unsuccess_prompt, system_instruction=unsuccess_system_prompt)
            if ai_reply and len(ai_reply.strip()) > 30:
                if session.safety_hazard and session.safety_hazard['alert_text'] not in ai_reply:
                    ai_reply = safety_header + ai_reply
                return ai_reply
        except Exception:
            pass

        local_step = LocalTutorFormatter.format_step(session, step_num=step_num)
        if local_step:
            return safety_header + local_step

    # If the user has NOT provided an active symptom or fault anywhere in the session, do NOT voluntarily assume one!
    if not session.has_active_symptom and not session.answered_questions:
        from .views import _jarvis_address
        sir = _jarvis_address(user)
        v_info = session.vehicle_info
        veh_name = " ".join(filter(None, [v_info.get('year'), v_info.get('make'), v_info.get('model')])).strip()
        if not veh_name:
            veh_name = "your vehicle"

        no_symptom_system_prompt = f"""You are J.A.R.V.I.S., the expert automotive & motorcycle diagnostic assistant. Address the user respectfully as '{sir}'.
Strict Rules:
1. RELEVANT & ACCURATE ANSWER: Answer the user's inquiry directly, concisely, and courteously.
2. ABSOLUTELY NO VOLUNTARY / ASSUMED SYMPTOMS: The user has NOT reported a breakdown or mechanical fault. NEVER assume, guess, or invent a symptom (such as 'No-Start', 'won't start', 'dead battery', or 'brake failure'). DO NOT draft a 9-step diagnostic repair protocol or checklist for an unstated condition!
3. VEHICLE FOCUS: If the user mentioned or switched to {veh_name}, acknowledge this machine courteously, give a brief 1-2 sentence note on its specifications if relevant (e.g. carburetor, commuter motorcycle, chain drive), and politely ask what specific issue, symptom, or service they need help with.
4. Language: Respond in {session.language.upper()}.
5. Conclude with 3-5 clickable action chips: `[chips: Engine will not start | Brakes weak or spongy | Overheating | Strange noise | Routine maintenance]`.
"""
        prompt = f"User Inquiry: {message}\nActive Vehicle: {session.vehicle_info}"
        try:
            ai_reply = call_configured_ai(prompt, system_instruction=no_symptom_system_prompt)
            if ai_reply and len(ai_reply.strip()) > 20:
                if session.safety_hazard and session.safety_hazard['alert_text'] not in ai_reply:
                    ai_reply = safety_header + ai_reply
                return ai_reply
        except Exception as exc:
            logger.warning('AI call for vehicle inquiry failed (%s); using local reply.', type(exc).__name__)

        lang = session.language
        if lang == 'tagalog':
            return (
                f"{safety_header}Naiintindihan ko, {sir}. Nakatutok na ang ating pagsusuri sa **{veh_name}**.\n\n"
                f"Ano po ang partikular na sintomas o problema na nararanasan ninyo sa inyong sasakyan?\n\n"
                f"[chips: Ayaw mag-start | Malambot ang preno | Nag-iinit / Overheat | Maingay na makina | Regular na maintenance]"
            )
        elif lang == 'hiligaynon':
            return (
                f"{safety_header}Naintindihan ko, {sir}. Nakatutok na ang aton sistema sa **{veh_name}**.\n\n"
                f"Ano bala ang partikular nga diperensya ukon sintomas sang imo salakyan?\n\n"
                f"[chips: Indi mag-start | Humok ang preno | Nagabukal / Overheat | Gahod sa makina | Regular nga maintenance]"
            )
        else:
            return (
                f"{safety_header}Understood, {sir}. Active diagnostic focus has been updated to the **{veh_name}**.\n\n"
                f"What specific symptom, mechanical issue, or maintenance procedure would you like assistance with on this vehicle?\n\n"
                f"[chips: Engine will not start | Brakes weak or spongy | Overheating | Strange noise | Routine maintenance]"
            )

    # 2. Check if we need to ask ONE targeted question before giving repair instructions
    # If a discriminative question is available and vehicle intake is not complete or no test answers yet
    if session.next_question and not session.has_sufficient_diagnostic_data():
        q = session.next_question
        lang = session.language
        q_text = q['text_tl'] if lang == 'tagalog' and q.get('text_tl') else (
            q['text_hil'] if lang == 'hiligaynon' and q.get('text_hil') else q['text']
        )
        opts = q.get('options', [])
        opt_lines = "\n".join(f"- {opt['label']}" for opt in opts)
        chips_str = " | ".join(opt['label'].split('. ')[-1] if '. ' in opt['label'] else opt['label'] for opt in opts)

        intake_note = ""
        v = session.vehicle_info
        if not (v.get('make') or v.get('model')):
            if lang == 'tagalog':
                intake_note = "Pakisabi rin ang brand, modelo, at taon ng sasakyan mo para sa tumpak na detalye.\n\n"
            elif lang == 'hiligaynon':
                intake_note = "Palihog hambal man sang brand, modelo, kag tuig sang imo salakyan para sa eksakto nga pagsusuri.\n\n"
            else:
                intake_note = "Please also confirm your vehicle make, model, and year for exact specifications.\n\n"

        response_body = f"{safety_header}{intake_note}**{q_text}**\n\n{opt_lines}\n\n[chips: {chips_str}]"
        return response_body

    # 3. Build RAG Context from verified knowledge
    rag_context_blocks = []
    for s in session.verified_knowledge:
        rag_context_blocks.append(f"### VERIFIED SYMPTOM: {s['symptom_name']} (Category: {s['category']}, Vehicle: {s['vehicle_type']})")
        if s.get('safety_warning'):
            rag_context_blocks.append(f"Safety Rule: {s['safety_warning']}")
        for g in s.get('guides', []):
            rag_context_blocks.append(f"Cause: {g['possible_cause']} (Confidence: {g['confidence_level']})")
            rag_context_blocks.append(f"Test: {g['diagnostic_test']}")
            rag_context_blocks.append(f"Expected: {g['expected_result']}")
            rag_context_blocks.append(f"If Differs: {g['alternative_outcome']}")
            rag_context_blocks.append(f"Tools: {g['tools_required']}")
            rag_context_blocks.append(f"Repair Steps:\n{g['repair_instructions']}")
            rag_context_blocks.append(f"When to Stop: {g['when_to_stop']}")
            rag_context_blocks.append(f"Source: {g['source_reference']}")

    knowledge_text = "\n".join(rag_context_blocks) if rag_context_blocks else "Use standard verified mechanical diagnostic procedures."

    exp_instruction = (
        "Explanation Level: EXPERIENCED MECHANIC (Concise, technical component values, electrical pinout tests, mechanical tolerances)."
        if session.experience_level == 'mechanic'
        else "Explanation Level: BEGINNER-FRIENDLY (Patient, explain unfamiliar parts, describe how components work, emphasize safety)."
    )

    # 4. Strict System Prompt
    system_prompt = f"""You are J.A.R.V.I.S., master automotive & motorcycle diagnostic tutor.
Strict Rules:
1. When diagnosing an active symptom or fault, format the response using the 9-part Step-by-Step Repair Tutor:
   1. Short symptom summary.
   2. Immediate safety warning (if applicable).
   3. Most likely causes with explicit confidence ratings (High, Medium, Tentative).
   4. Tools and preparation required.
   5. Numbered diagnostic/repair steps with `- [ ] 1. Step` checklist.
   6. Expected result after each test.
   7. What to do if the result differs.
   8. When to stop and consult a qualified mechanic.
   9. Final question asking whether the problem was resolved.
   CRITICAL: ONLY troubleshoot the exact symptom reported by the user. NEVER invent or assume unrelated symptoms.
2. Anti-Hallucination: NEVER invent torque values, electrical specs, or fluid types. Only use specifications in the verified workshop database below or state "check factory service manual stamp".
3. Language: Respond in {session.language.upper()}. Preserve technical part names (caliper, master cylinder, stator, carb, spark plug) while explaining them naturally.
4. {exp_instruction}
5. Conclude with 3-5 action chips: `[chips: Option 1 | Option 2 | Option 3]`.

## VERIFIED WORKSHOP KNOWLEDGE DATABASE:
{knowledge_text}
"""

    prompt = f"User Complaint: {message}\nVehicle Known: {session.vehicle_info}\nAnswered Details: {session.answered_questions}"

    # 5. Try calling configured AI Provider
    try:
        ai_reply = call_configured_ai(prompt, system_instruction=system_prompt)
        if ai_reply and len(ai_reply.strip()) > 30:
            if session.safety_hazard and session.safety_hazard['alert_text'] not in ai_reply:
                ai_reply = safety_header + ai_reply
            return ai_reply
    except Exception as exc:
        logger.warning(
            'Configured AI provider call failed (%s); using local knowledge.',
            type(exc).__name__,
        )

    # 6. Reliable Local Database Fallback (Explicitly Disclosed)
    local_reply = LocalTutorFormatter.format_tutor(
        session,
        explanation_level=getattr(settings, 'AI_EXPLANATION_LEVEL', 'beginner')
    )
    if local_reply:
        fallback_notice = (
            "> [!NOTE]\n"
            "> ⚙️ *Generated from Verified Workshop Knowledge Base (AI API Offline Mode)*\n\n"
        )
        return fallback_notice + local_reply

    # 7. Fallback to existing rule-based engine if database has no match
    from .views import _jarvis_rule_based_diagnostic
    return _jarvis_rule_based_diagnostic(message, user, history=history)
