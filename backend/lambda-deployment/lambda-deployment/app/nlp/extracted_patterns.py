"""
Patterns and data extracted from kirana-voice-enterprise
This is pure data, no code logic
"""

# =============================================================================
# INTENT PATTERNS (22 Categories from Kirana)
# =============================================================================

INTENT_PATTERNS = {
    "place_order": {
        "keywords_en": ["order", "want", "need", "buy", "get", "deliver", "send", "bring"],
        "keywords_hi": ["chahiye", "mangana", "bhejo", "dena", "lana", "dila do", "bhej do"],
        "keywords_mixed": ["chahiye", "order karna", "manga do", "want hai"],
        "phrases": ["i want", "mujhe chahiye", "please send", "bhej do", "order karna hai", "mujhe samaan mangana hai", "order karna hai"],
        "confidence_threshold": 0.7,
        "priority": "high"
    },
    
    "modify_order": {
        "keywords_en": ["change", "modify", "update", "replace", "instead", "wrong", "mistake"],
        "keywords_hi": ["badlo", "change karo", "dusra", "jagah", "galat", "sahi karo"],
        "keywords_mixed": ["change karo", "badal do", "wrong hai"],
        "phrases": ["make it", "uski jagah", "no not that", "galat hai", "sahi karo"],
        "confidence_threshold": 0.6,
        "priority": "medium"
    },
    
    "check_status": {
        "keywords_en": ["status", "where", "when", "delivered", "track", "kahan", "kab"],
        "keywords_hi": ["kahan", "kab", "pahunch", "aaya", "status", "track"],
        "keywords_mixed": ["kahan hai", "kab aayega", "delivered hua"],
        "phrases": ["where is my order", "kab aayega", "delivered", "track karo", "what's my order status", "order status"],
        "confidence_threshold": 0.8,
        "priority": "high"
    },
    
    "cancel_order": {
        "keywords_en": ["cancel", "stop", "don't want", "remove", "nahi chahiye"],
        "keywords_hi": ["cancel", "rok do", "nahi chahiye", "mat bhejo", "cancel karo"],
        "keywords_mixed": ["cancel karo", "nahi chahiye", "stop karo"],
        "phrases": ["cancel my order", "order cancel kar do", "nahi chahiye"],
        "confidence_threshold": 0.9,
        "priority": "high"
    },
    
    "greeting": {
        "keywords_en": ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"],
        "keywords_hi": ["namaste", "namaskar", "satsriakal", "suprabhat", "shubh prabhat"],
        "keywords_mixed": ["hello ji", "hi ji", "namaste ji"],
        "phrases": ["how are you", "kaise ho", "kya haal hai", "hello bhaiya"],
        "confidence_threshold": 0.8,
        "priority": "low"
    },
    
    "weather": {
        "keywords_en": ["weather", "temperature", "hot", "cold", "rain", "sunny"],
        "keywords_hi": ["mausam", "barish", "garmi", "sardi", "nami"],
        "keywords_mixed": ["weather kaisa hai", "mausam kya hai"],
        "phrases": ["how is weather", "aaj ka mausam", "barish aa rahi hai"],
        "confidence_threshold": 0.7,
        "priority": "low"
    },
    
    "cricket": {
        "keywords_en": ["cricket", "match", "team", "player", "batting", "bowling"],
        "keywords_hi": ["khel", "match", "team", "player", "batting", "bowling"],
        "keywords_mixed": ["cricket match", "india vs pakistan"],
        "phrases": ["cricket match", "india pakistan", "ipl match"],
        "confidence_threshold": 0.8,
        "priority": "low"
    },
    
    "jokes": {
        "keywords_en": ["joke", "funny", "humor", "comedy", "laugh", "entertain"],
        "keywords_hi": ["hansi", "mazak", "joke", "funny", "entertainment"],
        "keywords_mixed": ["joke sunao", "funny story", "mazak sunao"],
        "phrases": ["tell me a joke", "joke sunao", "funny story"],
        "confidence_threshold": 0.7,
        "priority": "low"
    },
    
    "registration": {
        "keywords_en": ["register", "registration", "sign up", "enroll", "join", "store"],
        "keywords_hi": ["register", "registration", "dukan", "kirana", "vyapar"],
        "keywords_mixed": ["store register karna hai", "dukan register karna hai"],
        "phrases": ["i want to register", "dukan register karna hai", "store registration"],
        "confidence_threshold": 0.9,
        "priority": "high"
    },
    
    "help": {
        "keywords_en": ["help", "support", "assist", "guide", "problem", "issue"],
        "keywords_hi": ["madad", "support", "help", "problem", "issue"],
        "keywords_mixed": ["help chahiye", "madad chahiye", "problem hai"],
        "phrases": ["i need help", "madad chahiye", "problem hai"],
        "confidence_threshold": 0.8,
        "priority": "medium"
    }
}

# =============================================================================
# INDIAN GROCERY PRODUCT DATABASE
# =============================================================================

PRODUCT_DATABASE = {
    "flour": {
        "variations": ["atta", "aata", "आटा", "flour", "wheat flour", "gehun", "gehun ka atta"],
        "default_unit": "kg",
        "common_quantities": [0.5, 1, 2, 5, 10],
        "category": "staples",
        "price_range": {"min": 30, "max": 60, "per": "kg"},
        "brands": ["aashirvaad", "ashirwad", "आशीर्वाद", "pillsbury", "fortune", "rajdhani"]
    },
    
    "rice": {
        "variations": ["chawal", "चावल", "rice", "chaval", "basmati", "sona masoori"],
        "default_unit": "kg",
        "common_quantities": [1, 2, 5, 10, 25],
        "category": "staples",
        "price_range": {"min": 40, "max": 200, "per": "kg"},
        "brands": ["india gate", "daawat", "kohinoor", "fortune", "tilda"]
    },
    
    "lentils": {
        "variations": ["dal", "daal", "दाल", "lentils", "dhal"],
        "types": ["arhar", "moong", "masoor", "chana", "urad", "toor"],
        "default_unit": "kg",
        "common_quantities": [0.5, 1, 2],
        "category": "staples",
        "price_range": {"min": 80, "max": 150, "per": "kg"},
        "brands": ["tata", "fortune", "rajdhani", "organic india"]
    },
    
    "oil": {
        "variations": ["tel", "तेल", "oil", "cooking oil"],
        "types": ["mustard", "sarso", "sunflower", "refined", "groundnut", "sesame"],
        "default_unit": "l",
        "common_quantities": [0.5, 1, 2, 5],
        "category": "cooking",
        "price_range": {"min": 100, "max": 300, "per": "l"},
        "brands": ["fortune", "saffola", "sundrop", "dhara", "gemini"]
    },
    
    "sugar": {
        "variations": ["chini", "चीनी", "sugar", "shakkar"],
        "default_unit": "kg",
        "common_quantities": [0.5, 1, 2, 5],
        "category": "staples",
        "price_range": {"min": 40, "max": 60, "per": "kg"},
        "brands": ["dabur", "tata", "dhampur", "bajaj"]
    },
    
    "salt": {
        "variations": ["namak", "नमक", "salt"],
        "default_unit": "kg",
        "common_quantities": [0.5, 1, 2],
        "category": "staples",
        "price_range": {"min": 15, "max": 25, "per": "kg"},
        "brands": ["tata", "sambhar", "annapurna"]
    },
    
    "milk": {
        "variations": ["doodh", "दूध", "milk"],
        "default_unit": "l",
        "common_quantities": [0.5, 1, 2],
        "category": "dairy",
        "price_range": {"min": 50, "max": 80, "per": "l"},
        "brands": ["amul", "mother dairy", "nandini", "sudha"]
    },
    
    "bread": {
        "variations": ["bread", "ब्रेड", "double roti"],
        "default_unit": "packet",
        "common_quantities": [1, 2, 3],
        "category": "bakery",
        "price_range": {"min": 20, "max": 40, "per": "packet"},
        "brands": ["britannia", "modern", "harvest gold", "english oven"]
    },
    
    "noodles": {
        "variations": ["noodles", "नूडल्स", "maggi", "मैगी"],
        "default_unit": "packet",
        "common_quantities": [1, 2, 3, 5, 10],
        "category": "instant_food",
        "price_range": {"min": 10, "max": 20, "per": "packet"},
        "brands": ["maggi", "मैगी", "yippee", "top ramen", "wai wai"]
    },
    
    "biscuits": {
        "variations": ["biscuit", "बिस्कुट", "cookies"],
        "default_unit": "packet",
        "common_quantities": [1, 2, 3],
        "category": "snacks",
        "price_range": {"min": 10, "max": 50, "per": "packet"},
        "brands": ["parle g", "parle", "britannia", "good day", "oreo"]
    },
    
    "tea": {
        "variations": ["chai", "चाय", "tea", "tea leaves"],
        "default_unit": "packet",
        "common_quantities": [1, 2, 3],
        "category": "beverages",
        "price_range": {"min": 20, "max": 100, "per": "packet"},
        "brands": ["taj mahal", "red label", "brooke bond", "lipton"]
    },
    
    "coffee": {
        "variations": ["coffee", "कॉफी", "kaffee"],
        "default_unit": "packet",
        "common_quantities": [1, 2, 3],
        "category": "beverages",
        "price_range": {"min": 50, "max": 200, "per": "packet"},
        "brands": ["nescafe", "bru", "continental", "davidoff"]
    },
    
    "potato": {
        "variations": ["aloo", "आलू", "potato", "batata"],
        "default_unit": "kg",
        "common_quantities": [0.5, 1, 2, 5],
        "category": "vegetables",
        "price_range": {"min": 20, "max": 40, "per": "kg"},
        "brands": []
    },
    
    "onion": {
        "variations": ["pyaz", "प्याज", "onion", "kanda"],
        "default_unit": "kg",
        "common_quantities": [0.5, 1, 2, 5],
        "category": "vegetables",
        "price_range": {"min": 20, "max": 60, "per": "kg"},
        "brands": []
    },
    
    "tomato": {
        "variations": ["tamatar", "टमाटर", "tomato"],
        "default_unit": "kg",
        "common_quantities": [0.5, 1, 2],
        "category": "vegetables",
        "price_range": {"min": 20, "max": 80, "per": "kg"},
        "brands": []
    }
}

# =============================================================================
# UNITS AND MEASUREMENTS MAPPING
# =============================================================================

UNITS_MAPPING = {
    "weight": {
        "kg": ["kg", "kilo", "kilogram", "किलो", "केजी", "k.g.", "kgs"],
        "g": ["g", "gram", "grams", "ग्राम", "gm", "grams"],
        "mg": ["mg", "milligram", "मिलीग्राम"],
        "ton": ["ton", "tonne", "टन"],
        "ser": ["ser", "seer", "सेर"],
        "pound": ["pound", "lb", "lbs", "पाउंड"]
    },
    
    "volume": {
        "l": ["l", "litre", "liter", "लीटर", "लिटर", "lit", "liters"],
        "ml": ["ml", "millilitre", "milliliter", "मिली", "मिलीलीटर", "mls"],
        "gallon": ["gallon", "गैलन"],
        "quart": ["quart", "क्वार्ट"],
        "pint": ["pint", "पिंट"]
    },
    
    "quantity": {
        "packet": ["packet", "pack", "पैकेट", "पैक", "pouch", "packets"],
        "piece": ["piece", "pc", "pcs", "नग", "पीस", "nos", "pieces"],
        "dozen": ["dozen", "doz", "दर्जन", "darjan", "dozens"],
        "box": ["box", "डिब्बा", "बॉक्स", "dabba", "boxes"],
        "bottle": ["bottle", "बोतल", "bottal", "bottles"],
        "can": ["can", "tin", "कैन", "टिन", "cans"],
        "glass": ["glass", "ग्लास", "glasses"],
        "cup": ["cup", "कप", "cups"]
    },
    
    "area": {
        "sqft": ["sqft", "square feet", "sq ft", "वर्ग फुट"],
        "sqm": ["sqm", "square meter", "sq m", "वर्ग मीटर"],
        "acre": ["acre", "एकड़", "acres"],
        "hectare": ["hectare", "हेक्टेयर", "ha"]
    },
    
    "length": {
        "m": ["m", "meter", "मीटर", "meters"],
        "cm": ["cm", "centimeter", "सेंटीमीटर", "cms"],
        "mm": ["mm", "millimeter", "मिलीमीटर"],
        "km": ["km", "kilometer", "किलोमीटर", "kms"],
        "ft": ["ft", "foot", "feet", "फुट"],
        "inch": ["inch", "inches", "इंच"]
    }
}

# =============================================================================
# NUMBER WORDS IN MULTIPLE LANGUAGES
# =============================================================================

NUMBER_WORDS = {
    "hindi": {
        "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5,
        "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
        "ग्यारह": 11, "बारह": 12, "तेरह": 13, "चौदह": 14, "पंद्रह": 15,
        "सोलह": 16, "सत्रह": 17, "अठारह": 18, "उन्नीस": 19, "बीस": 20,
        "तीस": 30, "चालीस": 40, "पचास": 50, "साठ": 60, "सत्तर": 70,
        "अस्सी": 80, "नब्बे": 90, "सौ": 100, "हज़ार": 1000,
        "आधा": 0.5, "डेढ़": 1.5, "ढाई": 2.5, "साढ़े": "+0.5"
    },
    
    "roman": {
        "ek": 1, "do": 2, "teen": 3, "char": 4, "panch": 5,
        "cheh": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
        "gyarah": 11, "barah": 12, "terah": 13, "chaudah": 14, "pandrah": 15,
        "solah": 16, "satrah": 17, "atharah": 18, "unnees": 19, "bees": 20,
        "tees": 30, "chaalis": 40, "pachaas": 50, "saath": 60, "sattar": 70,
        "assi": 80, "nabbe": 90, "sau": 100, "hazaar": 1000,
        "adha": 0.5, "dedh": 1.5, "dhai": 2.5, "saade": "+0.5"
    },
    
    "english": {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
        "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
        "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
        "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
        "half": 0.5, "quarter": 0.25, "dozen": 12
    }
}

# =============================================================================
# INDIAN BRAND NAMES DATABASE
# =============================================================================

BRAND_DATABASE = {
    "flour": ["aashirvaad", "ashirwad", "आशीर्वाद", "pillsbury", "fortune", "rajdhani", "annapurna"],
    "oil": ["fortune", "saffola", "sundrop", "dhara", "gemini", "kohinoor", "palmolein"],
    "noodles": ["maggi", "मैगी", "yippee", "top ramen", "wai wai", "knorr", "chings"],
    "milk": ["amul", "mother dairy", "nandini", "sudha", "verka", "milma", "aavin"],
    "bread": ["britannia", "modern", "harvest gold", "english oven", "wonder", "brown bread"],
    "biscuits": ["parle g", "parle", "britannia", "good day", "marie", "hide and seek", "oreo"],
    "tea": ["taj mahal", "red label", "brooke bond", "lipton", "tata tea", "wagh bakri"],
    "coffee": ["nescafe", "bru", "continental", "davidoff", "starbucks", "cafe coffee day"],
    "rice": ["india gate", "daawat", "kohinoor", "fortune", "tilda", "basmati", "sona masoori"],
    "lentils": ["tata", "fortune", "rajdhani", "organic india", "24 mantra", "organic"],
    "sugar": ["dabur", "tata", "dhampur", "bajaj", "shree renuka", "balrampur"],
    "salt": ["tata", "sambhar", "annapurna", "tata salt", "iodized salt"],
    "beverages": ["coca cola", "coke", "pepsi", "sprite", "fanta", "thumbs up", "limca"],
    "snacks": ["lays", "kurkure", "cheetos", "doritos", "pringles", "bingo", "haldirams"],
    "personal_care": ["dabur", "himalaya", "patanjali", "colgate", "close up", "pepsodent"],
    "household": ["surf excel", "ariel", "tide", "rin", "wheel", "ghari", "nirma"]
}

# =============================================================================
# CONVERSATION STATE MACHINE
# =============================================================================

CONVERSATION_STATES = {
    "greeting": {
        "next_states": ["intent_detection", "registration"],
        "timeout": 30,
        "prompts": ["Namaste! How can I help you?", "नमस्ते! आप क्या मंगाना चाहेंगे?"],
        "fallback": "intent_detection"
    },
    
    "intent_detection": {
        "next_states": ["order_taking", "status_check", "support", "registration"],
        "timeout": 20,
        "prompts": ["What would you like to order?", "क्या चाहिए आपको?", "How can I help?"],
        "fallback": "clarification"
    },
    
    "order_taking": {
        "next_states": ["confirm_order", "modify_order", "add_more"],
        "timeout": 60,
        "prompts": ["Please tell me your items", "अपना सामान बताइए", "What items do you need?"],
        "fallback": "clarification"
    },
    
    "confirm_order": {
        "next_states": ["order_confirmed", "modify_order", "cancel_order"],
        "timeout": 45,
        "prompts": ["Please confirm your order", "अपना order confirm करें", "Is this correct?"],
        "fallback": "order_taking"
    },
    
    "order_confirmed": {
        "next_states": ["payment", "delivery_setup"],
        "timeout": 30,
        "prompts": ["Order confirmed! Payment details?", "Order confirm हो गया! Payment?"],
        "fallback": "payment"
    },
    
    "status_check": {
        "next_states": ["order_found", "order_not_found"],
        "timeout": 30,
        "prompts": ["Please provide order number", "Order number बताइए"],
        "fallback": "intent_detection"
    },
    
    "registration": {
        "next_states": ["collect_store_name", "collect_address", "collect_phone"],
        "timeout": 120,
        "prompts": ["Let's register your store", "अपनी दुकान register करें"],
        "fallback": "intent_detection"
    },
    
    "clarification": {
        "next_states": ["intent_detection", "order_taking"],
        "timeout": 20,
        "prompts": ["Could you please clarify?", "कृपया स्पष्ट करें?"],
        "fallback": "greeting"
    }
}

# =============================================================================
# VALIDATION RULES
# =============================================================================

VALIDATION_RULES = {
    "quantity_limits": {
        "min": 0.1,
        "max": 100,
        "common_mistakes": {
            "5kg rice 2": "5kg rice, 2 packets",  # Missing unit
            "atta do": "2 kg atta",  # Quantity after product
            "ek kilo": "1 kg",  # Number word
            "aadha kilo": "0.5 kg",  # Fraction
        }
    },
    
    "price_ranges": {
        "rice": {"min": 30, "max": 200, "per": "kg"},
        "oil": {"min": 100, "max": 300, "per": "l"},
        "flour": {"min": 30, "max": 60, "per": "kg"},
        "milk": {"min": 50, "max": 80, "per": "l"},
        "bread": {"min": 20, "max": 40, "per": "packet"},
        "noodles": {"min": 10, "max": 20, "per": "packet"},
        "biscuits": {"min": 10, "max": 50, "per": "packet"},
        "tea": {"min": 20, "max": 100, "per": "packet"},
        "coffee": {"min": 50, "max": 200, "per": "packet"}
    },
    
    "phone_validation": {
        "pattern": r"^(\+91[\s-]?)?[789]\d{9}$",
        "min_length": 10,
        "max_length": 13,
        "country_code": "+91"
    },
    
    "aadhaar_validation": {
        "pattern": r"^\d{4}[\s-]?\d{4}[\s-]?\d{4}$",
        "length": 12,
        "format": "XXXX XXXX XXXX"
    },
    
    "pan_validation": {
        "pattern": r"^[A-Z]{5}\d{4}[A-Z]{1}$",
        "length": 10,
        "format": "ABCDE1234F"
    },
    
    "gstin_validation": {
        "pattern": r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d{1}[Z]{1}[A-Z\d]{1}$",
        "length": 15,
        "format": "27ABCDE1234F1Z5"
    }
}

# =============================================================================
# TEST EXAMPLES FROM KIRANA
# =============================================================================

TEST_EXAMPLES = {
    "simple_orders": [
        ("1 kg atta", [{"product": "flour", "quantity": 1, "unit": "kg"}]),
        ("do packet maggi", [{"product": "noodles", "quantity": 2, "unit": "packet", "brand": "maggi"}]),
        ("5 litre oil", [{"product": "oil", "quantity": 5, "unit": "l"}]),
        ("ek kilo chawal", [{"product": "rice", "quantity": 1, "unit": "kg"}]),
        ("aadha litre doodh", [{"product": "milk", "quantity": 0.5, "unit": "l"}]),
    ],
    
    "complex_orders": [
        ("1 kg atta, 2 litre milk, aur teen packet maggi", [
            {"product": "flour", "quantity": 1, "unit": "kg"},
            {"product": "milk", "quantity": 2, "unit": "l"},
            {"product": "noodles", "quantity": 3, "unit": "packet", "brand": "maggi"}
        ]),
        ("do kilo chawal, ek litre tel, panch packet biscuit", [
            {"product": "rice", "quantity": 2, "unit": "kg"},
            {"product": "oil", "quantity": 1, "unit": "l"},
            {"product": "biscuits", "quantity": 5, "unit": "packet"}
        ]),
    ],
    
    "voice_style": [
        ("uh... mujhe chahiye wo... atta... ek kilo", [{"product": "flour", "quantity": 1, "unit": "kg"}]),
        ("arey bhaiya do kilo chawal aur aadha litre tel", [
            {"product": "rice", "quantity": 2, "unit": "kg"},
            {"product": "oil", "quantity": 0.5, "unit": "l"}
        ]),
        ("hmm... let me think... ek packet maggi and... do bread", [
            {"product": "noodles", "quantity": 1, "unit": "packet", "brand": "maggi"},
            {"product": "bread", "quantity": 2, "unit": "packet"}
        ]),
    ],
    
    "registration_examples": [
        ("मेरा नाम राज कुमार है, फोन 9876543210, दुकान का नाम ABC स्टोर", {
            "person_name": ["raj", "kumar"],
            "phone_number": ["9876543210"],
            "store_name": ["ABC Store"]
        }),
        ("I am Raj Kumar, phone 9876543210, store name ABC Store", {
            "person_name": ["raj", "kumar"],
            "phone_number": ["9876543210"],
            "store_name": ["ABC Store"]
        }),
    ],
    
    "intent_examples": [
        ("order karna hai", "place_order"),
        ("status check karna hai", "check_status"),
        ("cancel kar do", "cancel_order"),
        ("namaste", "greeting"),
        ("weather kaisa hai", "weather"),
        ("cricket match kab hai", "cricket"),
        ("joke sunao", "jokes"),
        ("dukan register karna hai", "registration"),
        ("help chahiye", "help"),
    ]
}

# =============================================================================
# LANGUAGE DETECTION PATTERNS
# =============================================================================

LANGUAGE_PATTERNS = {
    "hindi_indicators": [
        "ka", "ki", "ke", "hai", "hain", "ho", "hoon", "main", "aap", "tum",
        "yeh", "woh", "kya", "kaise", "kahan", "kab", "kyun", "kaun", "konsa",
        "mein", "par", "se", "ko", "ka", "ki", "ke", "ne", "pe", "me"
    ],
    
    "english_indicators": [
        "the", "a", "an", "is", "are", "was", "were", "have", "has", "had",
        "will", "would", "can", "could", "should", "may", "might", "do",
        "does", "did", "am", "be", "been", "being", "this", "that", "these", "those"
    ],
    
    "hinglish_indicators": [
        "ok", "okay", "yes", "no", "good", "bad", "nice", "fine", "okay",
        "problem", "issue", "help", "support", "service", "customer", "business"
    ]
}

# =============================================================================
# CONFIDENCE THRESHOLDS
# =============================================================================

CONFIDENCE_THRESHOLDS = {
    "high_confidence": 0.8,
    "medium_confidence": 0.6,
    "low_confidence": 0.4,
    "minimum_confidence": 0.3,
    "intent_detection": 0.7,
    "entity_extraction": 0.8,
    "language_detection": 0.6
}

# =============================================================================
# CONTEXT PATTERNS
# =============================================================================

CONTEXT_PATTERNS = {
    "business_related": [
        "store", "shop", "business", "sell", "buy", "trade", "market",
        "customer", "client", "service", "product", "price", "cost",
        "profit", "loss", "income", "revenue", "sales", "marketing"
    ],
    
    "personal_related": [
        "family", "home", "personal", "private", "life", "health",
        "education", "job", "career", "relationship", "friend", "love"
    ],
    
    "technical_related": [
        "computer", "mobile", "phone", "internet", "software", "hardware",
        "technology", "digital", "online", "website", "app", "system"
    ]
}
