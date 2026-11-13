"""Centralized Intent Classifier for MotorAssistant / J.A.R.V.I.S.

Routes rider queries reliably to the appropriate handler:
- off_topic (prompt injection, non-motorcycle topics, fictional parts)
- safety (critical safety tripwires)
- spec (valve clearances, plug gaps, tire pressures, torque, fluid specs)
- maintenance_howto (oil change interval, clutch adjustment, CVT belt, chain care)
- model_info (overview of a specific motorcycle model)
- comparison (model vs model)
- buying_advice (beginner recommendations, buying guide)
- riding_gear (helmets, jackets, protective equipment)
- riding_advice (rain riding, wet road safety, traffic riding)
- location (component placement on motorcycle)
- visual (requests to see a component image)
- follow_up (contextual follow-ups like "what should I check first?", "what about the filter?", "and what oil type?")
- resolution ("thanks, that worked", acknowledgment)
- greeting ("hello", "kamusta", greeting courteous entry)
- identity ("who are you", "introduce yourself")
- help ("what can you do", "capabilities", "help")
- diagnostic (motorcycle symptom troubleshooting)
"""
from __future__ import annotations

import re


INJECTION_PATTERNS = [
    r'ignore\s+(?:all\s+)?previous\s+instructions',
    r'disregard\s+(?:all\s+)?prior\s+instructions',
    r'ignore\s+(?:the\s+)?above\s+instructions',
    r'system\s+prompt',
    r'jailbreak',
    r'dan\s+mode',
    r'pretend\s+you\s+are\s+not',
    r'bypass\s+safety',
]

FICTIONAL_PARTS = [
    'blinker fluid', 'turn signal fluid', 'flux capacitor',
    'muffler bearing', 'muffler bearings', 'exhaust bearing',
]

OFF_TOPIC_DOMAINS = [
    # Geography / General Knowledge
    (r'\bcapital\s+of\b', 'geography'),
    (r'\bpopulation\s+of\b', 'geography'),
    (r'\bwhere\s+is\s+(?:france|spain|italy|germany|paris|madrid|tokyo|london|europe|asia|america)\b', 'geography'),
    (r'\bwho\s+(?:is|was)\s+(?:napoleon|einstein|shakespeare|george\s+washington|elon\s+musk)\b', 'history'),
    # Sports
    (r'\b(?:world\s+cup|fifa|olympics|nba|super\s+bowl|premier\s+league|uefa)\b', 'sports'),
    (r'\bwho\s+won\s+the\s+(?:\d{4}\s+)?(?:world\s+cup|championship|super\s+bowl)\b', 'sports'),
    (r'\b(?:messi|ronaldo|lebron|curry|mbappe)\b', 'sports'),
    # Home appliances / Refrigerators
    (r'\b(?:refrigerator|fridge|freezer|microwave|washing\s+machine|aircon|air\s+conditioner|dishwasher|vacuum|toaster)\b', 'home_appliance'),
    # Cooking / Food
    (r'\b(?:recipe|how\s+to\s+cook|how\s+to\s+bake|ingredients?\s+for|pancake|baking|cooking\s+oil|adobo\s+recipe)\b', 'cooking'),
    # Creative writing / Coding
    (r'\b(?:write\s+(?:me\s+)?(?:a\s+)?(?:poem|poetry|story|song|essay)|poem|tell\s+me\s+a\s+(?:joke|riddle)|joke)\b', 'creative'),
    (r'\b(?:write\s+(?:python|javascript|c\+\+|java|html)\s+code)\b', 'coding'),
    # Academics / Math
    (r'\b(?:math|calculus|algebra|homework|solve\s+\d+|2\s*\+\s*2)\b', 'academics'),
    # Science / Biology
    (r'\b(?:photosynthesis|cellular\s+respiration|quantum\s+physics|gravity\s+in\s+space|dna|mitochondria|solar\s+system|black\s+hole)\b', 'science'),
    # Pets / Animals
    (r'\b(?:train\s+(?:my\s+)?(?:dog|cat|pet|puppy)|dog\s+training|pet\s+care|dog\s+food|cat\s+food|puppy|kitten)\b', 'pets'),
    # Celebrities / Pop culture
    (r'\b(?:taylor\s+swift|billie\s+eilish|kpop|bts|beyonce|drake)\b', 'celebrities'),
    # Tech / Non-motorcycle electronics
    (r'\b(?:smartphone|iphone|android\s+phone|laptop|macbook|windows\s+11|playstation|xbox|nintendo)\b', 'tech'),
    # Weather
    (r'\b(?:weather\s+today|weather\s+forecast|temperature\s+outside)\b', 'weather'),
    # Car transmission (when explicitly about automobiles/cars)
    (r'\b(?:car\s+transmission|automatic\s+transmission\s+for\s+(?:civic|vios|corolla|toyota|honda\s+car)|torque\s+converter\s+in\s+a\s+car)\b', 'car_transmission'),
]

SPEC_PATTERNS = [
    r'valve\s+clearance',
    r'spark\s+plug\s+gap',
    r'plug\s+gap',
    r'tire\s+pressure',
    r'tyre\s+pressure',
    r'hangin\s+ng\s+gulong',
    r'presyon\s+ng\s+gulong',
    r'tamang\s+tire\s+pressure',
    r'coolant\s+(?:spec|specification|type)',
    r'what\s+coolant\b',
    r'coolant\s+should\b',
    r'charging\s+voltage',
    r'battery\s+voltage',
    r'torque\s+(?:spec|value)',
    r'oil\s+capacity',
    r'clearance\s+for\b',
    r'gap\s+should\b',
]

COMPARISON_PATTERNS = [
    r'\bvs\b|\bversus\b',
    r'\bwhich\s+is\s+better\b',
    r'\bcompare\b|\bcomparison\b',
    r'\bbeter\s+(?:than|or)\b',
    r'\balin\s+ang\s+mas\s+maganda\b',
    r'\bdiin\s+ang\s+mas\s+maayo\b',
]

BUYING_PATTERNS = [
    r'beginner\s+(?:bike|motorcycle|scooter)',
    r'best\s+(?:bike|motorcycle|scooter)\s+for\s+beginner',
    r'motorcycle\s+should\s+(?:a\s+)?beginner\s+buy',
    r'recommend\s+(?:a\s+)?(?:bike|motorcycle|scooter)',
    r'anong\s+magandang\s+motor\s+sa\s+beginner',
    r'ano\s+nga\s+motor\s+manami\s+sa\s+beginner',
]

COMPONENT_INQUIRY_PATTERNS = [
    # What controls / what regulates / what powers / what charges
    r'\bwhat\s+(?:controls|powers|regulates|charges|drives|connects|operates|triggers|cuts\s*off|cuts\s*outs?)\b',
    r'\bwhich\s+(?:controls|powers|regulates|charges|drives|connects|operates|triggers|cuts\s*off|cuts\s*outs?)\b',
    r'\bano\s+ang\s+(?:nagpapatakbo|kumokontrol|nagpapatay|nagkakarga|nag-aayos|nagkontrol)\b',
    r'\bano\s+ang\s+nagakontrol\b',
    # Component purpose / function / role / what is it for
    r'\b(?:what\s+is|what\'s)\s+(?:the\s+)?(?:purpose|function|role|job|use)\s+of\b',
    r'\bwhat\s+(?:is|are)\s+(?:a|an|the)?\s*([a-z0-9\s-]+)\s+(?:for|used\s+for)\b',
    r'\bpara\s+saan\s+(?:ang|yung|ang\s+mga)\b',
    r'\bano\s+ang\s+(?:gamit|silbi|tungkulin)\s+ng\b',
    r'\bano\s+ang\s+pulos\s+sang\b',
    # How a component or system works / operates
    r'\bhow\s+does\s+(?:the|a|an)\s+([a-z0-9\s-]+)\s+work\b',
    r'\bhow\s+do\s+([a-z0-9\s-]+)\s+work\b',
    r'\bpaano\s+gumagana\s+(?:ang|yung)\b',
    r'\bpaano\s+naga-andar\s+(?:ang)\b',
    # System inquiries & explanations
    r'\bexplain\s+(?:the\s+)?([a-z0-9\s-]+)\s+(?:system|circuit|wiring|operation|mechanism|function)\b',
    r'\bhow\s+(?:is|are)\s+([a-z0-9\s-]+)\s+(?:wired|connected|controlled|charged)\b',
    r'\bwhat\s+does\s+(?:the|a|an)?\s*([a-z0-9\s-]+)\s+do\b',
    r'\bwhat\s+parts?\s+(?:control|make\s+up|belong\s+to|are\s+in)\b',
    # Electrical and ignition inquiry patterns
    r'\bwhat\s+controls?\s+(?:the\s+)?engine\s+cut\s*outs?\b',
    r'\bignition\s+(?:and\s+electrical|system)\b.*\bwhat\s+controls\b',
    r'\bheadlight\s+and\s+battery\s+charging\b',
    r'\belectrical\s+and\s+ignition\b',
]

GEAR_PATTERNS = [
    r'\bhelmet\b',
    r'what\s+helmet\b',
    r'riding\s+gear\b',
    r'riding\s+jacket\b',
    r'protective\s+gear\b',
    r'anong\s+helmet\b',
    r'ano\s+nga\s+helmet\b',
]

RAIN_PATTERNS = [
    r'ride.*(?:\brain|wet\b|ulan\b)',
    r'rain\s+riding',
    r'riding\s+in\s+the\s+rain',
    r'pag\s+umuulan',
    r'kon\s+nagauran',
]

MODEL_INFO_PATTERNS = [
    r'tell\s+me\s+about\s+(?:the\s+)?([a-z0-9\s]+)',
    r'what\s+can\s+you\s+tell\s+me\s+about\s+(?:the\s+)?([a-z0-9\s]+)',
    r'overview\s+of\s+(?:the\s+)?([a-z0-9\s]+)',
    r'information\s+about\s+(?:the\s+)?([a-z0-9\s]+)',
    r'ano\s+ang\s+(?:specs|impormasyon)\s+ng\s+([a-z0-9\s]+)',
]

RESOLUTION_PATTERNS = [
    r'^(?:thanks|thank\s+you|ty|thx)[\s,\.!]*$',
    r'^(?:thanks|thank\s+you)[\s,]+that\s+worked[\s,\.!]*$',
    r'^(?:that|it)\s+worked[\s,\.!]*$',
    r'^(?:salamat|maraming\s+salamat|ayos\s+na|gumana\s+na)[\s,\.!]*$',
    r'^(?:salamat\s+nag-andar\s+na|salamat\s+ayos\s+na)[\s,\.!]*$',
]

FOLLOWUP_PATTERNS = [
    ('check_first', [
        r'what\s+should\s+i\s+check\s+first',
        r'what\s+(?:to|do\s+i)\s+check\s+first',
        r'where\s+do\s+i\s+start',
        r'ano\s+(?:ang\s+)?unahin\s+ko',
        r'diin\s+ko\s+mauna',
    ]),
    ('oil_filter', [
        r'what\s+about\s+the\s+filter',
        r'how\s+about\s+the\s+filter',
        r'paano\s+ang\s+filter',
        r'kumusta\s+ang\s+filter',
        r'yung\s+filter\b',
    ]),
    ('oil_type', [
        r'(?:and\s+)?what\s+oil\s+type',
        r'what\s+type\s+of\s+oil',
        r'what\s+oil\s+should\s+i\s+use',
        r'anong\s+(?:klase|uri)\s+ng\s+langis',
        r'ano\s+nga\s+klase\s+sang\s+langis',
    ]),
]

COURTESY_PATTERNS = [
    (r'^(?:hello|hi|hey|good\s+(?:morning|afternoon|evening)|kamusta|kumusta|maayong\s+(?:adlaw|aga|hapon|gab-i)|howdy)\b', 'greeting'),
    (r'\b(?:who\s+are\s+you|what\s+are\s+you|your\s+name|introduce\s+yourself|sin-o\s+ka|sino\s+ka)\b', 'identity'),
    (r'\b(?:what\s+can\s+you\s+do|capabilities|commands|help|bulig|tulong)\b', 'help'),
]

MOTORCYCLE_VOCABULARY = [
    # Vehicle types
    'motorcycle', 'motorbike', 'motor', 'motorsiklo', 'scooter', 'skuter',
    'underbone', 'moped', 'big bike', 'bigbike', 'dirt bike', 'pit bike',
    'dual-sport', 'cruiser', 'cafe racer', 'trike', 'tricycle', 'toda',
    'two-wheeler', '2-wheeler', 'bike',
    # Brands
    'honda', 'yamaha', 'suzuki', 'kawasaki', 'bajaj', 'tvs', 'kymco',
    'sym', 'ktm', 'bmw', 'ducati', 'royal enfield', 'benelli', 'bristol',
    'keeway', 'rusi', 'motorstar', 'euro motors', 'vespa', 'aprilia',
    'harley', 'triumph',
    # Models
    'click', 'nmax', 'aerox', 'beat', 'mio', 'pcx', 'adv', 'sniper',
    'raider', 'tmx', 'barako', 'ct 100', 'ct100', 'ct 125', 'ct125',
    'ct 150', 'ct150', 'rouser', 'wave', 'xrm', 'smash', 'burgman',
    'fazzio', 'gravis', 'sporty', 'soul', 'vega', 'ytx', 'dominar',
    'duke', 'gixxer', 'gsx', 'mt-09', 'mt09', 'mt 09', 'mt-09 sp', 'mt-07', 'mt-03', 'mt-15', 'mt15', 'cp3', 'r15', 'cbr', 'crf',
    'wr155', 'klx', 'w175', 'ninja', 'fz', 'sight', 'sz', 'boxer',
    'discover', 'pulsar', 'dink', 'like 125', 'like 150',
    # Parts & Systems
    'engine', 'makina', 'piston', 'cylinder', 'silindro', 'head gasket',
    'cylinder head', 'valve', 'valves', 'balbula', 'tappet', 'rocker arm',
    'camshaft', 'timing chain', 'cam chain', 'tensioner', 'crank', 'crankshaft',
    'crankcase', 'connecting rod', 'rod knock', 'spark plug', 'sparkplug',
    'busiya', 'plug gap', 'oil seal', 'drain bolt', 'drain plug', 'crush washer',
    'dipstick', 'oil filter', 'oil strainer', 'oil pump', 'radiator',
    'water pump', 'thermostat', 'coolant', 'cvt', 'drive belt', 'belt',
    'pulley', 'variator', 'flyball', 'flyballs', 'roller weights', 'rollers',
    'bola-bola', 'torque drive', 'clutch bell', 'campana', 'sliding piece',
    'clutch', 'clutch plates', 'clutch lining', 'clutch cable', 'clutch lever',
    'sprocket', 'sprockets', 'piñon', 'chain', 'drive chain', 'kadena',
    'chain slack', 'chain lube', 'gearbox', 'gear oil', 'shift pedal', 'kambyo',
    'carburetor', 'carb', 'carburador', 'karburador', 'main jet', 'pilot jet',
    'jetting', 'float', 'float bowl', 'needle valve', 'fuel pump', 'fuel filter',
    'fuel injector', 'injector', 'throttle body', 'tps', 'throttle',
    'silinyador', 'choke', 'air filter', 'air box', 'petcock', 'fuel tank',
    'gas tank', 'tangke', 'fuel line', 'gas line', 'fuel hose', 'fuel leak',
    'electrical', 'wiring', 'wiring harness', 'ground wire', 'fluid', 'brake fluid', 'clutch fluid', 'no sound', 'battery', 'baterya', 'stator', 'stator coil', 'magneto', 'flywheel',
    'rectifier', 'regulator', 'cdi', 'ecu', 'ecm', 'fuse', 'fuses',
    'fuse box', 'relay', 'starter relay', 'solenoid', 'starter motor',
    'starter', 'estarter', 'kickstarter', 'kickstart', 'ignition coil',
    'kill switch', 'sidestand switch', 'side stand switch', 'headlight',
    'headlamp', 'suga', 'ilaw', 'tail light', 'signal light', 'blinker',
    'turn signal', 'hazard', 'horn', 'busina', 'speedometer', 'speedo',
    'odometer', 'tachometer', 'gauge cluster', 'speed sensor', 'speedo cable',
    'brake', 'brakes', 'preno', 'front brake', 'rear brake', 'disc brake',
    'drum brake', 'caliper', 'kaliper', 'brake pads', 'brake shoes',
    'master cylinder', 'brake lever', 'brake pedal', 'brake fluid', 'dot 3',
    'dot 4', 'brake hose', 'brake line', 'rotor', 'brake disc', 'tambor',
    'fork', 'forks', 'front fork', 'fork oil', 'fork seal', 'suspension',
    'shock absorber', 'shock', 'rear shock', 'monoshock', 'handlebar',
    'handlebars', 'manibela', 'steering stem', 'head bearing', 'ball race',
    'swingarm', 'swing arm', 'wheel', 'wheels', 'gulong', 'rim', 'rims',
    'spokes', 'mag wheels', 'tire', 'tires', 'tyre', 'tyres', 'goma',
    'tire pressure', 'wheel bearing', 'axle', 'exhaust', 'muffler', 'pipe',
    'tambutso', 'silencer', 'header pipe', 'fairing', 'fairings',
    'side mirror', 'center stand', 'kickstand', 'footpeg', 'pillion', 'angkas',
    'helmet', 'helmets', 'riding gear', 'riding jacket', 'riding gloves',
    'part', 'parts', 'component', 'components', 'maintenance', 'maintenance schedule', 'schedule', 'pms',
    'knee pads',
    # Procedures and symptoms
    'oil change', 'change oil', 'palit langis', 'tune-up', 'tune up',
    'valve clearance', 'spark plug gap', 'chain slack', 'chain lube',
    'bleed brake', 'bleed brakes', 'coolant flush', 'clutch adjustment',
    'won\'t start', 'wont start', 'ayaw mag-start', 'ayaw umandar',
    'indi mag-andar', 'indi magstart', 'hard starting', 'hard to start',
    'mahirap i-start', 'crank', 'cranks', 'cranking', 'no crank', 'clicking',
    'stall', 'stalls', 'stalling', 'namamatay', 'namatayan', 'starts then dies',
    'dies immediately', 'bogging', 'hesitation', 'hesitating', 'misfire',
    'backfire', 'backfiring', 'loss of power', 'walang hatak', 'mahina ang hatak',
    'overheat', 'overheating', 'nag-ooverheat', 'temperature light', 'temp light',
    'smoke', 'usok', 'aso', 'white smoke', 'black smoke', 'blue smoke',
    'knocking', 'ticking', 'rattling', 'squeaking', 'squeal', 'grinding',
    'leak', 'leaks', 'leaking', 'tagas', 'tulo', 'oil leak', 'oil leaks', 'fuel leak', 'fuel leaks', 'gas leak', 'gas leaks',
    'dropped bike', 'fell over', 'nabagsak', 'natumba', 'bent handlebar',
    'speedometer stopped', 'speedometer not working', 'headlight not working',
    'pulls to one side', 'kumakabig', 'wobble', 'wobbling', 'spongy', 'soft lever',
    'rain riding', 'riding in the rain', 'wet road', 'pag umuulan',
]


def is_motorcycle_related(norm: str, history=None, vehicle_profile=None) -> bool:
    """Check whether the message has genuine motorcycle relevance or context."""
    # 1. Any fictional part or injection is never motorcycle-related
    for fictional in FICTIONAL_PARTS:
        if fictional in norm:
            return False
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, norm):
            return False

    # 2. Check off-topic domains
    for pattern, domain in OFF_TOPIC_DOMAINS:
        if re.search(pattern, norm):
            has_mc = any(kw in norm for kw in [
                'motorcycle', 'motorbike', 'scooter', 'underbone', 'moped',
                'click', 'nmax', 'aerox', 'beat', 'raider', 'tmx', 'barako',
                'mt-09', 'mt09', 'mt 09', 'mt',
            ])
            if not has_mc or domain in ('geography', 'sports', 'home_appliance', 'cooking', 'academics', 'science', 'pets', 'creative', 'celebrities', 'tech', 'weather'):
                return False

    # 3. Direct vocabulary match
    has_vocab = any(re.search(r'\b' + re.escape(kw) + r'\b', norm) for kw in MOTORCYCLE_VOCABULARY)
    if has_vocab:
        return True

    # 4. With vehicle_profile or active history:
    # Diagnostic symptoms, status checks, observations, follow-ups
    has_veh = bool(vehicle_profile and (vehicle_profile.get('make') or vehicle_profile.get('model')))
    has_hist = bool(history and len(history) > 0)
    if has_veh or has_hist:
        _PURE_OFFTOPIC = re.compile(
            r'\b(?:poem|joke|weather|president|capital|country|sport|game|cook|recipe|'
            r'bake|dog|cat|animal|plant|school|math|science|history|politics|music|'
            r'movie|actor|singer|celebrity|stock|crypto|bitcoin|election|refrigerator|dishwasher)\b',
            re.IGNORECASE,
        )
        if _PURE_OFFTOPIC.search(norm):
            return False

        # Diagnostic symptoms or check observations
        _DIAGNOSTIC_TERMS = re.compile(
            r'\b(?:start|crank|sound|noise|spongy|lever|pedal|fluid|min|max|level|'
            r'leak|smoke|vibrat|idle|stalls?|die|dies|power|dead|light|lights|'
            r'spark|fire|check|inspect|test|tested|fixed|work|working|broken|'
            r'problem|issue|trouble|hindi|ayaw|wala|grabe|init|amoy|usok|tunog|'
            r'ingay|preno|makina|langis|kuryente|clutch|preno)\b',
            re.IGNORECASE,
        )
        if _DIAGNOSTIC_TERMS.search(norm):
            return True

        # Short in-session answers (under 6 words) that aren\'t open-ended general knowledge questions
        if len(norm.split()) <= 5 and not norm.startswith(('who ', 'where is ', 'what is ', 'how do i cook', 'tell me ')):
            return True

    return False


class IntentResult(str):
    """An intent classification string that also provides dictionary-like access
    and rich metadata for backwards and forwards compatibility."""
    def __new__(cls, intent, sub_intent="", entity=None, is_off_topic=False, details=None):
        val = str(intent)
        inst = super().__new__(cls, val)
        inst.intent = val
        inst.sub_intent = sub_intent
        inst.entity = entity
        inst.is_off_topic = is_off_topic
        inst.details = details or {}
        return inst

    def __getitem__(self, key):
        if key == 'intent':
            return str(self)
        if key == 'sub_intent':
            return self.sub_intent
        if key == 'entity':
            return self.entity
        if key == 'is_off_topic':
            return self.is_off_topic
        if key == 'details':
            return self.details
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        return key in ('intent', 'sub_intent', 'entity', 'is_off_topic', 'details')

    def items(self):
        return [
            ('intent', str(self)),
            ('sub_intent', self.sub_intent),
            ('entity', self.entity),
            ('is_off_topic', self.is_off_topic),
            ('details', self.details),
        ]


def _make_intent(intent, sub_intent="", entity=None, is_off_topic=False, details=None):
    return IntentResult(intent, sub_intent=sub_intent, entity=entity,
                        is_off_topic=is_off_topic, details=details)


def classify_intent(message: str, history=None, vehicle_profile=None) -> IntentResult:
    """Classify the user's intent.

    Returns an IntentResult (subclasses str) with:
      - 'intent': str
      - 'sub_intent': str
      - 'entity': str or None
      - 'is_off_topic': bool
      - 'details': dict
    """
    text = (message or '').strip()
    norm = text.lower()

    # 1. Prompt injections
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, norm):
            return _make_intent('off_topic', sub_intent='prompt_injection', entity=None, is_off_topic=True, details={'reason': 'Prompt injection attempt detected'})

    # 2. Fictional / joke parts
    for fictional in FICTIONAL_PARTS:
        if fictional in norm:
            return _make_intent('off_topic', sub_intent='fictional_part', entity=fictional, is_off_topic=True, details={'fictional_part': fictional})

    # 3. Off-topic domains
    for pattern, domain in OFF_TOPIC_DOMAINS:
        if re.search(pattern, norm):
            has_motorcycle = any(kw in norm for kw in [
                'motorcycle', 'motorbike', 'scooter', 'underbone', 'moped',
                'click', 'nmax', 'aerox', 'beat', 'raider', 'tmx', 'barako',
                'mt-09', 'mt09', 'mt 09', 'mt',
            ])
            if not has_motorcycle or domain in ('geography', 'sports', 'home_appliance', 'cooking', 'academics', 'science', 'pets', 'creative', 'celebrities', 'tech', 'weather'):
                return _make_intent('off_topic', sub_intent=domain, entity=None, is_off_topic=True, details={'domain': domain})

    # 4. Standalone numbers without vehicle context
    if re.fullmatch(r'\d{4}', norm):
        has_context = bool(vehicle_profile and (vehicle_profile.get('make') or vehicle_profile.get('model')))
        if not has_context and history:
            hist_str = ' '.join(t.get('text', '') if isinstance(t, dict) else str(t) for t in history).lower()
            if any(m in hist_str for m in ['click', 'nmax', 'aerox', 'beat', 'raider', 'tmx', 'barako', 'honda', 'yamaha', 'suzuki', 'kawasaki', 'motor', 'year', 'model']):
                has_context = True
        if not has_context:
            return _make_intent('off_topic', sub_intent='standalone_number', entity=norm, is_off_topic=True, details={'number': norm})

    # 5. Acknowledgment / resolution
    for pattern in RESOLUTION_PATTERNS:
        if re.search(pattern, norm):
            return _make_intent('resolution', sub_intent='resolved', entity=None, is_off_topic=False, details={})

    # 6. Follow-up intents
    for follow_key, patterns in FOLLOWUP_PATTERNS:
        for p in patterns:
            if re.search(p, norm):
                return _make_intent('follow_up', sub_intent=follow_key, entity=None, is_off_topic=False, details={'follow_key': follow_key})

    # 7. Comparison
    for pattern in COMPARISON_PATTERNS:
        if re.search(pattern, norm):
            if is_motorcycle_related(norm, history, vehicle_profile):
                return _make_intent('comparison', sub_intent='model_comparison', entity=None, is_off_topic=False, details={})
            return _make_intent('off_topic', sub_intent='non_motorcycle', entity=None, is_off_topic=True, details={'reason': 'Non-motorcycle comparison'})

    # 8. Model Information
    for pattern in MODEL_INFO_PATTERNS:
        m = re.search(pattern, norm)
        if m:
            entity = m.group(1).strip() if m.groups() else None
            if is_motorcycle_related(norm, history, vehicle_profile):
                return _make_intent('model_info', sub_intent='overview', entity=entity, is_off_topic=False, details={'model': entity})
            return _make_intent('off_topic', sub_intent='non_motorcycle', entity=entity, is_off_topic=True, details={'reason': 'Non-motorcycle entity'})

    # 9. Buying advice
    for pattern in BUYING_PATTERNS:
        if re.search(pattern, norm):
            return _make_intent('buying_advice', sub_intent='recommendation', entity=None, is_off_topic=False, details={})

    # 10. Riding gear / helmet
    for pattern in GEAR_PATTERNS:
        if re.search(pattern, norm):
            return _make_intent('riding_gear', sub_intent='gear', entity='helmet' if 'helmet' in norm else 'gear', is_off_topic=False, details={})

    # 11. Rain / wet weather riding
    for pattern in RAIN_PATTERNS:
        if re.search(pattern, norm):
            return _make_intent('riding_advice', sub_intent='rain_riding', entity='rain', is_off_topic=False, details={})

    # 12. Specifications
    for pattern in SPEC_PATTERNS:
        if re.search(pattern, norm):
            return _make_intent('spec', sub_intent=pattern, entity=None, is_off_topic=False, details={})

    # 13. Component location
    if re.search(r'\b(?:where\s+(?:is|to\s+locate|can\s+i\s+find|are|do\s+i\s+find)|nasaan\s+ang|diin\s+ang|saan\s+matatagpuan)\b', norm) and not re.search(r'\b(?:noise|tunog|usok|smoke)\b', norm):
        # Explicit part word mentioned (e.g. "where to locate that part", "where is that component")
        if re.search(r'\b(?:parts?|components?)\b', norm):
            return _make_intent('location', sub_intent='part_location', entity=None, is_off_topic=False, details={})
        # Pure pronoun reference (e.g. "where is it located")
        if re.search(r'\b(?:it|that|diyan|dito|ini|ina)\b', norm) and not any(kw in norm for kw in MOTORCYCLE_VOCABULARY if kw not in ('part', 'parts', 'component', 'components')):
            from apps.core.guided_diagnostic import _history_mentions_part
            if _history_mentions_part(history):
                return _make_intent('location', sub_intent='part_location', entity=None, is_off_topic=False, details={})
            if history and len(history) > 0:
                return _make_intent('diagnostic', sub_intent='symptom_location', entity=None, is_off_topic=False, details={})
            return _make_intent('off_topic', sub_intent='non_motorcycle', entity=None, is_off_topic=True, details={'reason': 'Non-motorcycle location'})
        if is_motorcycle_related(norm, history, vehicle_profile):
            return _make_intent('location', sub_intent='part_location', entity=None, is_off_topic=False, details={})
        return _make_intent('off_topic', sub_intent='non_motorcycle', entity=None, is_off_topic=True, details={'reason': 'Non-motorcycle location'})

    # 14. Visual query
    if re.search(r'\b(?:picture|photo|image|larawan|litrato|show\s+me|what\s+does\s+a\s+.*look\s+like)\b', norm):
        if is_motorcycle_related(norm, history, vehicle_profile):
            return _make_intent('visual', sub_intent='part_image', entity=None, is_off_topic=False, details={})
        return _make_intent('off_topic', sub_intent='non_motorcycle', entity=None, is_off_topic=True, details={'reason': 'Non-motorcycle visual'})

    # 15. Maintenance / how-to
    if re.search(r'\b(?:how\s+often|how\s+to|how\s+do\s+i\s+(?:change|replace|adjust|clean|check|flush|bleed|lube|service|tune|fix)|change\s+oil|oil\s+change|adjust\s+(?:the\s+)?clutch|replace\s+(?:cvt\s+)?belt|chain\s+lube|bleed\s+brakes?|maintenance\s+schedule|service\s+schedule|routine\s+maintenance|how\s+to\s+check\s+for)\b', norm):
        if is_motorcycle_related(norm, history, vehicle_profile):
            return _make_intent('maintenance_howto', sub_intent='maintenance', entity=None, is_off_topic=False, details={})
        return _make_intent('off_topic', sub_intent='non_motorcycle', entity=None, is_off_topic=True, details={'reason': 'Non-motorcycle how-to'})

    # 16. Component / System Educational Inquiry
    # Distinguish user wanting to learn how a motorcycle component/system functions
    # vs reporting an active motorcycle breakdown
    for pattern in COMPONENT_INQUIRY_PATTERNS:
        if re.search(pattern, norm):
            if is_motorcycle_related(norm, history, vehicle_profile):
                return _make_intent('component_inquiry', sub_intent='concept_explanation', entity=None, is_off_topic=False, details={'pattern': pattern})

    # 17. Courtesy / greeting / identity / help
    for pattern, kind in COURTESY_PATTERNS:
        if re.search(pattern, norm):
            return _make_intent(kind, sub_intent=kind, entity=None, is_off_topic=False, details={})

    # 17. Motorcycle relevance gate before diagnostic fallback
    if is_motorcycle_related(norm, history, vehicle_profile):
        return _make_intent('diagnostic', sub_intent='symptom', entity=None, is_off_topic=False, details={})

    # 18. Non-motorcycle query fallback
    return _make_intent('off_topic', sub_intent='non_motorcycle', entity=None, is_off_topic=True, details={'reason': 'No motorcycle relation detected'})
