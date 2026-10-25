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

    def __init__(self, message, history, user=None, language=None, experience_level=None):
        self.message = message or ''
        self.history = history or []
        self.user = user

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

        # Retrieve relevant verified knowledge
        self.verified_knowledge = retrieve_verified_knowledge(
            self.message + " " + self.corpus[:200],
            vehicle_type=self.vehicle_type,
            max_results=2
        )

        # Safety evaluation
        self.safety_hazard = evaluate_safety_hazards(self.message, self.language)
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


class LocalTutorFormatter:
    """Formats verified database knowledge into the strict 9-point Step-by-Step Repair Tutor."""

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
    model = getattr(settings, 'AI_MODEL', 'gemini-3.8-flash')
    api_key = getattr(settings, 'AI_API_KEY', '') or getattr(settings, 'GEMINI_API_KEY', '')
    base_url = getattr(settings, 'AI_API_BASE_URL', '')

    combined_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt

    if provider == 'gemini':
        from .views import _get_gemini_client
        client = _get_gemini_client()
        if not client:
            raise RuntimeError("Gemini client unavailable (check GEMINI_API_KEY).")
        clean_model = model.replace('models/', '')
        try:
            response = client.models.generate_content(
                model=clean_model,
                contents=combined_prompt,
            )
        except Exception as api_err:
            if clean_model != 'gemini-3.1-flash-lite':
                logger.info(f"Model {clean_model} failed ({api_err}); trying fallback gemini-3.1-flash-lite.")
                response = client.models.generate_content(
                    model='gemini-3.1-flash-lite',
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
        except Exception as e:
            logger.debug(f"Usage record skipped: {e}")
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


def orchestrate_diagnostic_response(message, user, history=None, language=None, experience_level=None):
    """
    Main entry point for intelligent diagnostic workflow:
    1. Evaluates session state, vehicle info, and safety tripwires.
    2. Retrieves verified database knowledge (RAG).
    3. If diagnostic testing is needed, asks ONE targeted question.
    4. Formats prompt with strict anti-hallucination guardrails and 9-point tutor format.
    5. Calls configured AI provider with seamless fallback to verified local database knowledge.
    """
    session = DiagnosticSession(message, history, user=user, language=language, experience_level=experience_level)

    # 1. Immediate Critical Safety Notice
    safety_header = ""
    if session.safety_hazard and session.safety_hazard['urgency'] == 'critical_stop':
        safety_header = f"> [!CAUTION]\n> **SAFETY ALERT:** {session.safety_hazard['alert_text']}\n\n"

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
1. Always format answers using the 9-part Step-by-Step Repair Tutor:
   1. Short symptom summary.
   2. Immediate safety warning (if applicable).
   3. Most likely causes with explicit confidence ratings (High, Medium, Tentative).
   4. Tools and preparation required.
   5. Numbered diagnostic/repair steps with `- [ ] 1. Step` checklist.
   6. Expected result after each test.
   7. What to do if the result differs.
   8. When to stop and consult a qualified mechanic.
   9. Final question asking whether the problem was resolved.
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
        logger.warning(f"Configured AI provider call failed ({exc}); initiating verified local knowledge fallback.")

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
