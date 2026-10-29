#!/usr/bin/env python
"""
Patch guided_diagnostic.py and assistant.py to make J.A.R.V.I.S.
answer general informational questions about motorcycles:
  - Comparison queries  (aerox vs nmax, what is better X or Y)
  - "Tell me about" / info queries  (tell me about honda click 125)
  - Riding gear / safety equipment questions  (what gear should i wear)
  - Buying / recommendation queries  (best motorcycle for beginners)
"""
import re

# ---------------------------------------------------------------------------
# 1. guided_diagnostic.py
# ---------------------------------------------------------------------------
GD = 'apps/core/guided_diagnostic.py'
with open(GD, encoding='utf-8') as f:
    src = f.read()

original = src  # keep for diff

# 1a. Expand GENERAL_DOMAIN_RE to include helmet/gear/buying/comparison words
src = src.replace(
    '        ride|riding|long\\s+ride|trips?\n    )\\b\n    """,\n    re.I | re.X,\n)\n\n# A question word only counts at the START',
    '        ride|riding|long\\s+ride|trips?|\n'
    '        helmet|helmets?|visor|gear|gears?|jacket|gloves?|boots?|protector|\n'
    '        riding\\s+gear|safety\\s+gear|apparel|atgatt|\n'
    '        buy(?:ing)?|purchas(?:e|ing)|beginner|starter|commut(?:e|er|ing)|\n'
    '        review|comparison|compare|versus|recommend(?:ation)?s?|\n'
    '        abs|efi|displacement|horsepower\n'
    '    )\\b\n    """,\n    re.I | re.X,\n)\n\n# A question word only counts at the START',
)

# 1b. Expand GENERAL_ACTION_RE to include comparison/recommendation/info words
src = src.replace(
    '        viscosity|weight|length|price|cost|difference|vs|versus|fitment|compatible\n    )\\b\n    """,\n    re.I | re.X,\n)\n\n# Maintenance/how-to words plus system nouns',
    '        viscosity|weight|length|price|cost|difference|vs|versus|fitment|compatible|\n'
    '        compar(?:e|ing|ison)|recommend(?:ation)?s?|review|better|best\\s+for|\n'
    '        beginner|starter|commuter|buying|purchase|tell\\s+me\\s+about|info(?:rmation)?\\s+about|\n'
    '        feature|pros?\\s+and\\s+cons?|advantage|disadvantage\n'
    '    )\\b\n    """,\n    re.I | re.X,\n)\n\n# Maintenance/how-to words plus system nouns',
)

# 1c. Add a new regex to detect comparison/info queries about bikes
COMPARISON_INFO_RE_BLOCK = '''
# Comparison, review, buying advice, and "tell me about" queries are
# informational and must be answered directly — not forced into the
# guided diagnostic intake, even when a bike name is mentioned.
COMPARISON_INFO_RE = re.compile(
    r\"\"\"
    \\b(?:
        better\\s+(?:than|or)|
        compare(?:d)?|comparison|versus|vs\\b|
        (?:tell|talk|ask)\\s+(?:me|us)\\s+about|
        (?:what|who)\\s+is\\s+(?:the\\s+)?(?:best|better|difference|diff)\\b|
        (?:which\\s+(?:is|one|would))|
        (?:should\\s+i\\s+(?:buy|get|choose|pick))|
        (?:between\\s+.{2,30}\\s+(?:and|or)\\s+.{2,30})|
        (?:pros?\\s+(?:and|or)\\s+cons?)|
        (?:review|overview|feature|spec\\s+comparison|buying\\s+guide)
    )\\b
    \"\"\",
    re.I | re.X,
)

'''

# Insert the new regex right before is_general_motorcycle_query definition
src = src.replace(
    'def is_general_motorcycle_query(message, history=None):\n',
    COMPARISON_INFO_RE_BLOCK + 'def is_general_motorcycle_query(message, history=None):\n',
)

# 1d. Inside is_general_motorcycle_query, add an early True return for comparison/info queries
#     Right after the _looks_like_part_location_query True return but before _has_active_fault check
src = src.replace(
    '    if _looks_like_part_location_query(msg, history):\n        return True\n    if _has_active_fault(msg):\n        return False',
    '    if _looks_like_part_location_query(msg, history):\n        return True\n    # Comparison, buying-advice, and "tell me about" queries should always\n    # get a direct informational answer even when a bike name is mentioned.\n    if COMPARISON_INFO_RE.search(msg):\n        return True\n    if _has_active_fault(msg):\n        return False',
)

# 1e. Also make is_guided_intent return False for comparison/info queries
#     (they must not be re-captured by the guided flow even when a bike name appears)
src = src.replace(
    '    if is_general_motorcycle_query(message, history):\n        if state and state.get(\'stage\') in (\'area\', \'checks\', \'narrow\', \'verdict\'):\n            if GUIDED_MAINTENANCE_RE.search(msg):\n                # \"Oil change / maintenance\" and similar chips are general\n                # questions; answer them instead of restarting the intake.\n                return False\n            if _is_guided_chip_answer(msg) or _is_guided_area_choice(msg):\n                return True\n        return False',
    '    if is_general_motorcycle_query(message, history):\n        if state and state.get(\'stage\') in (\'area\', \'checks\', \'narrow\', \'verdict\'):\n            # Comparison/info queries always escape the guided flow.\n            if COMPARISON_INFO_RE.search(msg):\n                return False\n            if GUIDED_MAINTENANCE_RE.search(msg):\n                # \"Oil change / maintenance\" and similar chips are general\n                # questions; answer them instead of restarting the intake.\n                return False\n            if _is_guided_chip_answer(msg) or _is_guided_area_choice(msg):\n                return True\n        return False',
)

if src == original:
    print('WARNING: no changes were applied to guided_diagnostic.py')
else:
    with open(GD, 'w', encoding='utf-8') as f:
        f.write(src)
    print('guided_diagnostic.py patched OK')

# ---------------------------------------------------------------------------
# 2. assistant.py — Expand GENERAL_SYSTEM_INSTRUCTION to cover Q&A/comparisons
# ---------------------------------------------------------------------------
AS = 'apps/core/services/assistant.py'
with open(AS, encoding='utf-8') as f:
    src_a = f.read()

original_a = src_a

OLD_GENERAL_SYSTEM = '''GENERAL_SYSTEM_INSTRUCTION = """You are J.A.R.V.I.S., a friendly and knowledgeable motorcycle assistant.
Answer any motorcycle question — maintenance, how-to, specifications, parts,
locations, or riding advice — directly and accurately.

Rules:
1. Answer directly in the first 1–3 sentences. Never ask for the make, model,
   or year before giving the answer.
2. Match the depth to the question. A simple interval, spec, or location
   question gets a concise answer; a full how-to may include tools, a short
   checklist, and safety notes.
3. For "where is X located?" questions, give the typical location first, then
   say it varies by model and tell the user to confirm in the owner's manual.
4. Use the conversation history. If the user says "that part" or "it", use the
   part from the previous turn. If it is genuinely unclear, ask which part they
   mean and offer 3–5 example chips — never repeat a generic capabilities answer.
5. Never invent torque values, clearances, fluid capacities, part numbers, or
   service intervals. If you are unsure, say so and give a safe general range.
6. Include safety warnings when relevant. Do not encourage riding with a
   dangerous fault.
7. Match the user's language: English, Tagalog/Taglish, or Hiligaynon.
8. End with 3–5 chips in the exact format
   `[chips: Option 1 | Option 2 | Option 3]`.
9. Be conversational and vary your wording; never repeat a previous answer
   verbatim.
10. Return plain text with short Markdown. Do not output JSON.'''

NEW_GENERAL_SYSTEM = '''GENERAL_SYSTEM_INSTRUCTION = """You are J.A.R.V.I.S., a friendly and knowledgeable motorcycle assistant.
Answer any motorcycle question — maintenance, how-to, specifications, parts,
locations, riding advice, comparisons, buying guidance, or general information
about motorcycles and riding gear — directly and accurately.

Rules:
1. Answer directly in the first 1–3 sentences. Never ask for the make, model,
   or year before giving the answer.
2. Match the depth to the question. A simple interval, spec, or location
   question gets a concise answer; a full how-to may include tools, a short
   checklist, and safety notes.
3. For "where is X located?" questions, give the typical location first, then
   say it varies by model and tell the user to confirm in the owner's manual.
4. For COMPARISON questions (e.g. "Aerox vs NMAX", "which is better"):
   - Give an objective side-by-side comparison of key differences (engine,
     features, riding style, price range, target user).
   - State which is generally better FOR WHAT USE CASE — commuting, sporty
     riding, long trips — rather than picking an absolute winner.
   - Keep it concise and balanced.
5. For "tell me about [bike]" / info questions:
   - Give a brief overview: type, displacement, fuel system, key features,
     typical use case, and notable pros/cons.
   - You may mention common maintenance points for that model if helpful.
6. For BUYING / RECOMMENDATION questions (e.g. "best motorcycle for beginners"):
   - Give 2–3 concrete recommendations with a one-sentence reason each.
   - Mention key factors (budget, use case, skill level, availability of parts).
7. For RIDING GEAR / SAFETY EQUIPMENT questions:
   - Recommend gear appropriate to the use case (commuting, sport, touring).
   - Always mention safety (helmet standards: DOT/ECE/SNELL, ATGATT principle).
8. Use the conversation history. If the user says "that part" or "it", use the
   part from the previous turn. If it is genuinely unclear, ask which part they
   mean and offer 3–5 example chips — never repeat a generic capabilities answer.
9. Never invent torque values, clearances, fluid capacities, part numbers, or
   service intervals. If you are unsure, say so and give a safe general range.
10. Include safety warnings when relevant. Do not encourage riding with a
    dangerous fault.
11. Match the user's language: English, Tagalog/Taglish, or Hiligaynon.
12. End with 3–5 chips in the exact format
    `[chips: Option 1 | Option 2 | Option 3]`.
13. Be conversational and vary your wording; never repeat a previous answer
    verbatim.
14. Return plain text with short Markdown. Do not output JSON.'''

if OLD_GENERAL_SYSTEM in src_a:
    src_a = src_a.replace(OLD_GENERAL_SYSTEM, NEW_GENERAL_SYSTEM)
    print('assistant.py GENERAL_SYSTEM_INSTRUCTION patched OK')
else:
    print('WARNING: GENERAL_SYSTEM_INSTRUCTION old text not found in assistant.py')

if src_a != original_a:
    with open(AS, 'w', encoding='utf-8') as f:
        f.write(src_a)
    print('assistant.py written OK')
else:
    print('WARNING: no changes written to assistant.py')

# ---------------------------------------------------------------------------
# 3. views.py — Expand _jarvis_gemini_general system prompt similarly
# ---------------------------------------------------------------------------
VW = 'apps/core/views.py'
with open(VW, encoding='utf-8') as f:
    src_v = f.read()

original_v = src_v

# Expand the general Gemini prompt to explicitly cover comparisons/buying/gear
OLD_GENERAL_RULES = '    The user is asking a GENERAL motorcycle question — maintenance, how-to, service intervals, pre-ride/pre-repair checks, tools, parts, riding technique, or buying advice. They are not necessarily reporting a breakdown.'
NEW_GENERAL_RULES = '    The user is asking a GENERAL motorcycle question — maintenance, how-to, service intervals, pre-ride/pre-repair checks, tools, parts, riding technique, buying advice, comparisons between models, riding gear, or general information about a motorcycle model. They are not necessarily reporting a breakdown.'

src_v = src_v.replace(OLD_GENERAL_RULES, NEW_GENERAL_RULES)

# Add expanded rules after the existing rule 4 (pre-check lists)
OLD_RULE_5 = '    5. Never refuse a motorcycle-related question. If you do not know an exact figure, say so and give safe general guidance. Never invent torque values, clearances, fluid capacities, or part numbers.'
NEW_RULE_5 = '''    4b. For COMPARISON questions (e.g. \"Aerox vs NMAX\", \"which is better X or Y\"):
   - Give an objective side-by-side comparison: engine, features, target user, riding style, price range.
   - State which is better FOR WHAT USE CASE rather than an absolute winner.
    4c. For \"tell me about [bike]\" / model info questions:
   - Give a brief overview: type, displacement, fuel system, key features, target user, and notable pros/cons.
    4d. For BUYING / RECOMMENDATION questions (\"best motorcycle for beginners\", \"what should I buy\"):
   - Give 2–3 concrete recommendations with a brief reason each and key factors (budget, skill, use case).
    4e. For RIDING GEAR / SAFETY EQUIPMENT questions (\"what helmet\", \"what gear to wear\"):
   - Recommend gear appropriate to the use case; always mention helmet safety standards (DOT/ECE/SNELL) and ATGATT.
    5. Never refuse a motorcycle-related question. If you do not know an exact figure, say so and give safe general guidance. Never invent torque values, clearances, fluid capacities, or part numbers.'''

src_v = src_v.replace(OLD_RULE_5, NEW_RULE_5)

if src_v != original_v:
    with open(VW, 'w', encoding='utf-8') as f:
        f.write(src_v)
    print('views.py patched OK')
else:
    print('WARNING: no changes applied to views.py')

print('All patches complete.')
