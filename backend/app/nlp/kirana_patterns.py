"""
Kirana Patterns - Extracted from kirana-voice-enterprise project
Clean Python data structures for VyaparAI NLP processing
"""

from typing import Dict, List, Set, Tuple

# =============================================================================
# INTENT PATTERNS (22 Categories)
# =============================================================================

INTENT_PATTERNS: Dict[str, List[str]] = {
    "greeting": [
        # English
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening", "good night",
        "how are you", "how do you do", "nice to meet you", "pleasure to meet you",
        "greetings", "welcome", "sup", "what's up", "yo",
        
        # Hindi
        "namaste", "namaskar", "satsriakal", "suprabhat", "shubh prabhat", "shubh sandhya", 
        "shubh ratri", "kaise ho", "kya haal hai", "kaisa hai", "aap kaise hain", 
        "tum kaise ho", "sab badhiya", "sab theek", "pranam", "jai mata di",
        
        # Hinglish
        "hello ji", "hi ji", "namaste ji", "kaise ho ji", "kya haal hai ji"
    ],
    
    "weather": [
        # English
        "weather", "temperature", "hot", "cold", "rain", "sunny", "cloudy", "humidity",
        "weather forecast", "weather today", "weather tomorrow", "is it raining",
        "is it sunny", "what's the weather", "weather condition", "weather report",
        
        # Hindi
        "mausam", "barish", "garmi", "sardi", "nami", "aaj ka mausam", "weather kaisa hai",
        "barish aa rahi hai", "garmi bahut hai", "sardi lag rahi hai", "humidity kitni hai",
        "monsoon", "sawan", "basant", "grishm", "varsha", "hemant", "mausam ka haal",
        "aaj barish hogi", "temperature kitna hai", "garmi kitni hai", "sardi kitni hai",
        
        # Hinglish
        "weather kaisa hai", "temperature kitna hai", "barish aa rahi hai"
    ],
    
    "cricket": [
        # English
        "cricket", "match", "team", "player", "batting", "bowling", "wicket", "run",
        "cricket match", "india vs", "pakistan vs", "ipl", "world cup", "test match",
        "odi", "t20", "captain", "batsman", "bowler", "all rounder",
        
        # Hindi
        "khel", "match", "team", "player", "batting", "bowling", "wicket", "run",
        "india pakistan", "ipl match", "world cup", "test match", "odi match",
        "t20 match", "captain", "batsman", "bowler", "all rounder", "khel raha hai",
        
        # Hinglish
        "cricket match", "india vs pakistan", "ipl match", "world cup match"
    ],
    
    "jokes": [
        # English
        "joke", "funny", "humor", "comedy", "laugh", "entertain me", "entertainment",
        "fun", "enjoy", "amuse", "sarcasm", "wit", "humorous", "hilarious", "amusing",
        "tell me a joke", "do you know any jokes", "can you tell jokes", "any jokes",
        "tell jokes", "share jokes", "jokes please", "funny jokes", "good jokes",
        
        # Hindi
        "hansi", "mazak", "joke sunao", "funny story", "mazak sunao", "entertainment",
        "fun", "enjoy", "amuse", "sarcasm", "wit", "humorous", "hilarious", "amusing",
        "joke sunao", "funny story", "mazak sunao", "entertain me", "entertainment",
        
        # Hinglish
        "joke sunao", "funny story", "mazak sunao", "entertain me"
    ],
    
    "politics": [
        # English
        "politics", "political", "government", "election", "vote", "democracy",
        "politician", "party", "policy", "minister", "prime minister", "president",
        "parliament", "congress", "bjp", "aap", "trinamool", "dmk", "aiadmk",
        
        # Hindi
        "rajneeti", "sarkar", "chunav", "vote", "loktantra", "netaji", "party",
        "policy", "mantri", "pradhan mantri", "rashtrapati", "sansad", "congress",
        "bjp", "aap", "trinamool", "dmk", "aiadmk", "rajneeti kya hai",
        
        # Hinglish
        "politics kya hai", "government kya hai", "election kab hai"
    ],
    
    "movies": [
        # English
        "movie", "film", "cinema", "actor", "actress", "director", "producer",
        "bollywood", "hollywood", "tollywood", "kollywood", "marathi", "bengali",
        "tamil", "telugu", "malayalam", "kannada", "punjabi", "gujarati",
        
        # Hindi
        "film", "cinema", "actor", "actress", "director", "producer", "bollywood",
        "hollywood", "tollywood", "kollywood", "marathi", "bengali", "tamil",
        "telugu", "malayalam", "kannada", "punjabi", "gujarati", "film dekha",
        
        # Hinglish
        "movie dekha", "film dekha", "cinema dekha"
    ],
    
    "food": [
        # English
        "food", "eat", "hungry", "thirsty", "restaurant", "cafe", "dhaba", "hotel",
        "breakfast", "lunch", "dinner", "snack", "meal", "cuisine", "recipe",
        "cooking", "chef", "kitchen", "delicious", "tasty", "spicy", "sweet",
        
        # Hindi
        "khana", "khana khana", "bhook", "pyaas", "restaurant", "cafe", "dhaba",
        "hotel", "nashta", "dopahar ka khana", "raat ka khana", "snack", "meal",
        "cuisine", "recipe", "cooking", "chef", "kitchen", "swadisht", "tasty",
        "spicy", "meetha", "khana kahan khana hai", "restaurant kahan hai",
        
        # Hinglish
        "food kahan khana hai", "restaurant kahan hai", "khana khana hai"
    ],
    
    "health": [
        # English
        "health", "healthy", "sick", "ill", "doctor", "hospital", "medicine",
        "fitness", "exercise", "gym", "yoga", "diet", "nutrition", "vitamin",
        "protein", "carbohydrate", "fat", "calorie", "weight", "height",
        
        # Hindi
        "swasthya", "swasth", "bimar", "doctor", "hospital", "dawai", "medicine",
        "fitness", "exercise", "gym", "yoga", "diet", "nutrition", "vitamin",
        "protein", "carbohydrate", "fat", "calorie", "weight", "height",
        "swasthya kya hai", "doctor kahan hai", "hospital kahan hai",
        
        # Hinglish
        "health kya hai", "doctor kahan hai", "hospital kahan hai"
    ],
    
    "education": [
        # English
        "education", "study", "learn", "school", "college", "university", "student",
        "teacher", "professor", "course", "degree", "diploma", "certificate",
        "exam", "test", "assignment", "homework", "project", "research",
        
        # Hindi
        "shiksha", "padhai", "seekhna", "school", "college", "university",
        "student", "teacher", "professor", "course", "degree", "diploma",
        "certificate", "exam", "test", "assignment", "homework", "project",
        "research", "shiksha kya hai", "school kahan hai", "college kahan hai",
        
        # Hinglish
        "education kya hai", "school kahan hai", "college kahan hai"
    ],
    
    "jobs": [
        # English
        "job", "work", "employment", "career", "profession", "salary", "wage",
        "interview", "resume", "cv", "application", "hire", "fire", "promotion",
        "office", "company", "business", "industry", "sector", "field",
        
        # Hindi
        "naukri", "kaam", "rozgar", "career", "profession", "salary", "wage",
        "interview", "resume", "cv", "application", "hire", "fire", "promotion",
        "office", "company", "business", "industry", "sector", "field",
        "naukri kahan hai", "kaam kahan hai", "job kahan hai",
        
        # Hinglish
        "job kahan hai", "naukri kahan hai", "kaam kahan hai"
    ],
    
    "family": [
        # English
        "family", "father", "mother", "son", "daughter", "brother", "sister",
        "grandfather", "grandmother", "uncle", "aunt", "cousin", "nephew",
        "niece", "husband", "wife", "spouse", "parent", "child", "kid",
        
        # Hindi
        "parivar", "pita", "mata", "beta", "beti", "bhai", "behen", "dada",
        "dadi", "chacha", "chachi", "mama", "mami", "bhanja", "bhanji",
        "pati", "patni", "shadi", "vivah", "parivar kya hai",
        
        # Hinglish
        "family kya hai", "parivar kya hai", "family kahan hai"
    ],
    
    "religion": [
        # English
        "religion", "god", "temple", "mosque", "church", "gurudwara", "mandir",
        "puja", "prayer", "worship", "faith", "belief", "spiritual", "holy",
        "sacred", "divine", "heaven", "hell", "karma", "dharma",
        
        # Hindi
        "dharm", "bhagwan", "mandir", "masjid", "church", "gurudwara", "puja",
        "prarthana", "upasana", "shraddha", "vishwas", "adhyatmik", "pavitra",
        "punya", "paap", "swarg", "narak", "karma", "dharma", "dharm kya hai",
        
        # Hinglish
        "religion kya hai", "dharm kya hai", "mandir kahan hai"
    ],
    
    "technology": [
        # English
        "technology", "tech", "computer", "mobile", "phone", "laptop", "tablet",
        "internet", "wifi", "app", "software", "hardware", "programming",
        "coding", "developer", "engineer", "startup", "innovation", "digital",
        
        # Hindi
        "technology", "tech", "computer", "mobile", "phone", "laptop", "tablet",
        "internet", "wifi", "app", "software", "hardware", "programming",
        "coding", "developer", "engineer", "startup", "innovation", "digital",
        "technology kya hai", "computer kya hai", "mobile kya hai",
        
        # Hinglish
        "technology kya hai", "computer kya hai", "mobile kya hai"
    ],
    
    "sports": [
        # English
        "sports", "game", "play", "football", "hockey", "tennis", "badminton",
        "volleyball", "basketball", "swimming", "running", "cycling", "gym",
        "fitness", "exercise", "tournament", "championship", "league", "team",
        
        # Hindi
        "khel", "game", "football", "hockey", "tennis", "badminton", "volleyball",
        "basketball", "swimming", "running", "cycling", "gym", "fitness",
        "exercise", "tournament", "championship", "league", "team", "khel kya hai",
        
        # Hinglish
        "sports kya hai", "khel kya hai", "game kya hai"
    ],
    
    "travel": [
        # English
        "travel", "trip", "journey", "tour", "vacation", "holiday", "destination",
        "hotel", "resort", "flight", "train", "bus", "car", "taxi", "booking",
        "ticket", "passport", "visa", "tourist", "guide",
        
        # Hindi
        "yatra", "safar", "tour", "vacation", "holiday", "destination", "hotel",
        "resort", "flight", "train", "bus", "car", "taxi", "booking", "ticket",
        "passport", "visa", "tourist", "guide", "yatra kahan jana hai",
        
        # Hinglish
        "travel kahan jana hai", "yatra kahan jana hai", "tour kahan jana hai"
    ],
    
    "shopping": [
        # English
        "shopping", "buy", "purchase", "shop", "store", "mall", "market",
        "price", "cost", "discount", "offer", "sale", "deal", "bargain",
        "brand", "product", "item", "goods", "merchandise", "retail",
        
        # Hindi
        "shopping", "khareedna", "purchase", "shop", "store", "mall", "market",
        "price", "cost", "discount", "offer", "sale", "deal", "bargain",
        "brand", "product", "item", "goods", "merchandise", "retail",
        "shopping kahan karna hai", "khareedna kya hai",
        
        # Hinglish
        "shopping kahan karna hai", "khareedna kya hai", "buy kya hai"
    ],
    
    "finance": [
        # English
        "finance", "money", "bank", "account", "loan", "credit", "debit",
        "investment", "savings", "insurance", "tax", "budget", "expense",
        "income", "salary", "profit", "loss", "business", "economy",
        
        # Hindi
        "finance", "paisa", "bank", "account", "loan", "credit", "debit",
        "investment", "savings", "insurance", "tax", "budget", "expense",
        "income", "salary", "profit", "loss", "business", "economy",
        "finance kya hai", "paisa kya hai", "bank kahan hai",
        
        # Hinglish
        "finance kya hai", "paisa kya hai", "bank kahan hai"
    ],
    
    "general_conversation": [
        # English
        "talk", "chat", "conversation", "discuss", "share", "tell", "say",
        "think", "feel", "believe", "know", "understand", "agree", "disagree",
        "opinion", "view", "perspective", "experience", "story", "life",
        
        # Hindi
        "baat", "chat", "conversation", "discuss", "share", "tell", "say",
        "think", "feel", "believe", "know", "understand", "agree", "disagree",
        "opinion", "view", "perspective", "experience", "story", "life",
        "baat kya hai", "chat kya hai", "conversation kya hai",
        
        # Hinglish
        "baat kya hai", "chat kya hai", "conversation kya hai"
    ],
    
    "help": [
        # English
        "help", "support", "assist", "guide", "advice", "suggestion", "recommend",
        "problem", "issue", "trouble", "difficulty", "confusion", "doubt",
        "question", "query", "inquiry", "information", "details", "explain",
        
        # Hindi
        "madad", "support", "assist", "guide", "advice", "suggestion", "recommend",
        "problem", "issue", "trouble", "difficulty", "confusion", "doubt",
        "question", "query", "inquiry", "information", "details", "explain",
        "madad chahiye", "help chahiye", "support chahiye",
        
        # Hinglish
        "help chahiye", "madad chahiye", "support chahiye"
    ],
    
    "registration": [
        # English
        "register", "registration", "sign up", "signup", "enroll", "enrollment",
        "join", "apply", "application", "form", "document", "paperwork",
        "store", "shop", "business", "company", "enterprise", "startup",
        "merchant", "vendor", "seller", "trader", "dealer",
        
        # Hindi
        "register", "registration", "sign up", "signup", "enroll", "enrollment",
        "join", "apply", "application", "form", "document", "paperwork",
        "store", "shop", "business", "company", "enterprise", "startup",
        "merchant", "vendor", "seller", "trader", "dealer", "dukan", "kirana",
        "vyapar", "business", "company", "enterprise", "startup", "merchant",
        "vendor", "seller", "trader", "dealer", "dukan register karna hai",
        "kirana register karna hai", "vyapar register karna hai",
        
        # Hinglish
        "store register karna hai", "shop register karna hai", "business register karna hai"
    ],
    
    "information_request": [
        # English
        "information", "info", "details", "data", "facts", "knowledge", "learn",
        "know", "understand", "explain", "describe", "tell me", "what is",
        "how to", "where is", "when is", "why is", "who is", "which is",
        
        # Hindi
        "information", "info", "details", "data", "facts", "knowledge", "learn",
        "know", "understand", "explain", "describe", "tell me", "what is",
        "how to", "where is", "when is", "why is", "who is", "which is",
        "information chahiye", "details chahiye", "data chahiye",
        
        # Hinglish
        "information chahiye", "details chahiye", "data chahiye"
    ],
    
    "complaints": [
        # English
        "complaint", "problem", "issue", "trouble", "difficulty", "wrong",
        "error", "mistake", "fault", "defect", "damage", "broken", "not working",
        "bad", "poor", "terrible", "awful", "horrible", "disappointed",
        
        # Hindi
        "shikayat", "problem", "issue", "trouble", "difficulty", "wrong",
        "error", "mistake", "fault", "defect", "damage", "broken", "not working",
        "bad", "poor", "terrible", "awful", "horrible", "disappointed",
        "shikayat hai", "problem hai", "issue hai",
        
        # Hinglish
        "complaint hai", "problem hai", "issue hai"
    ]
}

# =============================================================================
# INDIAN PRODUCT NAMES AND VARIATIONS
# =============================================================================

INDIAN_PRODUCTS: Dict[str, List[str]] = {
    "grains": [
        "rice", "chawal", "wheat", "gehun", "atta", "maida", "besan", "dal",
        "lentils", "masoor", "moong", "urad", "chana", "rajma", "kidney beans",
        "black gram", "green gram", "red gram", "pigeon pea", "chickpea",
        "basmati", "sona masoori", "jeera rice", "brown rice", "white rice"
    ],
    
    "vegetables": [
        "potato", "aloo", "onion", "pyaz", "tomato", "tamatar", "carrot", "gajar",
        "cabbage", "patta gobhi", "cauliflower", "phool gobhi", "brinjal", "baingan",
        "lady finger", "bhindi", "cucumber", "kheera", "radish", "mooli",
        "spinach", "palak", "fenugreek", "methi", "coriander", "dhania",
        "mint", "pudina", "curry leaves", "kadi patta", "ginger", "adrak",
        "garlic", "lehsun", "green chili", "hari mirch", "red chili", "lal mirch"
    ],
    
    "fruits": [
        "apple", "seb", "banana", "kela", "orange", "santra", "mango", "aam",
        "grapes", "angur", "watermelon", "tarbuj", "muskmelon", "kharbuja",
        "papaya", "papita", "guava", "amrood", "pomegranate", "anaar",
        "coconut", "nariyal", "pineapple", "ananas", "strawberry", "strawberry"
    ],
    
    "dairy": [
        "milk", "doodh", "curd", "dahi", "butter", "makhan", "ghee", "ghee",
        "cheese", "paneer", "cream", "malai", "buttermilk", "chaas",
        "yogurt", "dahi", "cottage cheese", "paneer", "cream cheese"
    ],
    
    "spices": [
        "salt", "namak", "sugar", "chini", "black pepper", "kali mirch",
        "red chili powder", "lal mirch powder", "turmeric", "haldi",
        "cumin", "jeera", "coriander powder", "dhania powder", "garam masala",
        "cardamom", "elaichi", "cinnamon", "dalchini", "cloves", "laung",
        "bay leaves", "tej patta", "asafoetida", "hing", "mustard", "rai",
        "fenugreek seeds", "methi dana", "fennel", "saunf"
    ],
    
    "oils": [
        "cooking oil", "tel", "mustard oil", "sarson ka tel", "groundnut oil",
        "peanut oil", "mungfali ka tel", "sesame oil", "til ka tel",
        "coconut oil", "nariyal ka tel", "sunflower oil", "suraj mukhi ka tel",
        "olive oil", "jaitun ka tel", "vegetable oil", "sabzi ka tel"
    ],
    
    "beverages": [
        "tea", "chai", "coffee", "coffee", "milk", "doodh", "water", "paani",
        "juice", "ras", "lemonade", "nimbu pani", "lassi", "lassi",
        "buttermilk", "chaas", "coconut water", "nariyal paani"
    ],
    
    "snacks": [
        "biscuits", "biscuit", "cookies", "cookie", "chips", "chips",
        "namkeen", "namkeen", "mixture", "mixture", "chivda", "chivda",
        "peanuts", "mungfali", "cashews", "kaju", "almonds", "badam",
        "raisins", "kishmish", "dates", "khajur", "dry fruits", "dry fruits"
    ],
    
    "household": [
        "soap", "sabun", "shampoo", "shampoo", "toothpaste", "toothpaste",
        "brush", "brush", "detergent", "detergent", "washing powder", "washing powder",
        "cleaning", "safai", "broom", "jhadoo", "bucket", "bucket",
        "mug", "mug", "towel", "towel", "tissue", "tissue"
    ]
}

# =============================================================================
# UNITS AND MEASUREMENTS
# =============================================================================

UNITS_AND_MEASUREMENTS: Dict[str, List[str]] = {
    "weight": [
        # Metric
        "kg", "kilo", "kilogram", "gram", "g", "gm", "ton", "tonne",
        # Indian
        "ser", "seer", "pound", "lb", "lbs", "ounce", "oz",
        # Hindi
        "kilo", "gram", "ton", "ser", "pound", "ounce"
    ],
    
    "volume": [
        # Metric
        "liter", "l", "ml", "milliliter", "cc", "cubic centimeter",
        # Indian
        "gallon", "quart", "pint", "cup", "glass", "bottle",
        # Hindi
        "liter", "glass", "bottle", "cup", "gallon"
    ],
    
    "count": [
        # English
        "piece", "pieces", "pc", "pcs", "pack", "packs", "packet", "packets",
        "dozen", "dozens", "hundred", "thousand", "million", "billion",
        # Hindi
        "piece", "pack", "packet", "dozen", "hundred", "thousand"
    ],
    
    "length": [
        # Metric
        "meter", "m", "cm", "centimeter", "mm", "millimeter", "km", "kilometer",
        # Indian
        "foot", "feet", "ft", "inch", "inches", "yard", "yards",
        # Hindi
        "meter", "foot", "inch", "yard"
    ],
    
    "area": [
        # Metric
        "square meter", "sq m", "sqm", "square feet", "sq ft", "sqft",
        "acre", "hectare", "ha",
        # Hindi
        "square meter", "square feet", "acre", "hectare"
    ]
}

# =============================================================================
# NUMBER WORDS IN MULTIPLE LANGUAGES
# =============================================================================

NUMBER_WORDS: Dict[str, Dict[str, str]] = {
    "english": {
        "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
        "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
        "10": "ten", "11": "eleven", "12": "twelve", "13": "thirteen",
        "14": "fourteen", "15": "fifteen", "16": "sixteen", "17": "seventeen",
        "18": "eighteen", "19": "nineteen", "20": "twenty", "30": "thirty",
        "40": "forty", "50": "fifty", "60": "sixty", "70": "seventy",
        "80": "eighty", "90": "ninety", "100": "hundred", "1000": "thousand"
    },
    
    "hindi": {
        "0": "shunya", "1": "ek", "2": "do", "3": "teen", "4": "char",
        "5": "paanch", "6": "cheh", "7": "saat", "8": "aath", "9": "nau",
        "10": "das", "11": "gyarah", "12": "barah", "13": "terah",
        "14": "chaudah", "15": "pandrah", "16": "solah", "17": "satrah",
        "18": "atharah", "19": "unnees", "20": "bees", "30": "tees",
        "40": "chaalis", "50": "pachaas", "60": "saath", "70": "sattar",
        "80": "assi", "90": "nabbe", "100": "sau", "1000": "hazaar"
    },
    
    "urdu": {
        "0": "sifar", "1": "ek", "2": "do", "3": "teen", "4": "char",
        "5": "paanch", "6": "cheh", "7": "saat", "8": "aath", "9": "nau",
        "10": "das", "11": "gyarah", "12": "barah", "13": "terah",
        "14": "chaudah", "15": "pandrah", "16": "solah", "17": "satrah",
        "18": "atharah", "19": "unnees", "20": "bees", "30": "tees",
        "40": "chaalis", "50": "pachaas", "60": "saath", "70": "sattar",
        "80": "assi", "90": "nabbe", "100": "sau", "1000": "hazaar"
    }
}

# =============================================================================
# BRAND NAMES AND VARIATIONS
# =============================================================================

BRAND_NAMES: Dict[str, List[str]] = {
    "beverages": [
        "coca cola", "coke", "pepsi", "sprite", "fanta", "thumbs up",
        "limca", "7up", "mirinda", "mountain dew", "red bull", "monster",
        "sting", "gatorade", "powerade", "tropicana", "real", "dabur",
        "parle", "britannia", "nestle", "amul", "mother dairy"
    ],
    
    "snacks": [
        "lays", "kurkure", "cheetos", "doritos", "pringles", "bingo",
        "haldirams", "bikaji", "balaji", "prince", "yellow diamond",
        "uncle chips", "wheels", "ringos", "cornitos", "act ii"
    ],
    
    "biscuits": [
        "parle g", "parle", "britannia", "good day", "marie", "hide and seek",
        "oreo", "bourbon", "tiger", "50 50", "monaco", "krackjack",
        "sunfeast", "dark fantasy", "milk bikis", "nutri choice"
    ],
    
    "dairy": [
        "amul", "mother dairy", "nandini", "verka", "milma", "aavin",
        "heritage", "kwality", "dodla", "creamline", "dynamix", "parag"
    ],
    
    "personal_care": [
        "dabur", "himalaya", "patanjali", "colgate", "close up", "pepsodent",
        "sunsilk", "head and shoulders", "dove", "lux", "lifebuoy", "santoor",
        "fair and lovely", "ponds", "lakme", "maybelline", "garnier"
    ],
    
    "household": [
        "surf excel", "ariel", "tide", "rin", "wheel", "ghari", "nirma",
        "harpic", "lizol", "domex", "good knight", "hit", "all out",
        "odonil", "godrej", "asian paints", "berger", "dulux"
    ],
    
    "electronics": [
        "samsung", "lg", "sony", "panasonic", "philips", "bajaj", "usha",
        "orient", "havells", "anchor", "polycab", "finolex", "v guard"
    ],
    
    "automotive": [
        "maruti", "hyundai", "honda", "tata", "mahindra", "toyota", "ford",
        "volkswagen", "skoda", "bmw", "mercedes", "audi", "volvo"
    ]
}

# =============================================================================
# COMMON INDIAN NAMES
# =============================================================================

INDIAN_NAMES: Dict[str, List[str]] = {
    "male": [
        "raj", "rahul", "amit", "suresh", "ramesh", "mohan", "sohan",
        "rohan", "arjun", "karan", "vivek", "vikas", "sanjay", "ajay",
        "vijay", "sunil", "anil", "manoj", "rajesh", "mahesh", "dinesh",
        "prakash", "dev", "kumar", "singh", "verma", "sharma", "gupta",
        "patel", "yadav", "kumar", "reddy", "naidu", "iyer", "iyengar"
    ],
    
    "female": [
        "priya", "neha", "puja", "ritu", "kavita", "sunita", "anita",
        "meena", "reena", "seema", "deepa", "reema", "kiran", "kavya",
        "aditi", "ananya", "diya", "isha", "kiara", "mira", "nisha",
        "pooja", "radha", "sita", "tara", "uma", "vandana", "yashoda"
    ]
}

# =============================================================================
# INDIAN CITIES AND STATES
# =============================================================================

INDIAN_LOCATIONS: Dict[str, List[str]] = {
    "major_cities": [
        "mumbai", "delhi", "bangalore", "hyderabad", "chennai", "kolkata",
        "pune", "ahmedabad", "surat", "jaipur", "lucknow", "kanpur",
        "nagpur", "indore", "thane", "bhopal", "visakhapatnam", "patna",
        "vadodara", "ghaziabad", "ludhiana", "agra", "nashik", "faridabad",
        "meerut", "rajkot", "kalyan", "vasai", "vashi", "navi mumbai"
    ],
    
    "states": [
        "maharashtra", "delhi", "karnataka", "telangana", "tamil nadu",
        "west bengal", "gujarat", "rajasthan", "uttar pradesh", "bihar",
        "madhya pradesh", "andhra pradesh", "punjab", "haryana", "kerala",
        "odisha", "jharkhand", "assam", "chhattisgarh", "himachal pradesh",
        "uttarakhand", "goa", "manipur", "meghalaya", "mizoram", "nagaland",
        "sikkim", "tripura", "arunachal pradesh"
    ]
}

# =============================================================================
# COMMON PHRASES AND EXPRESSIONS
# =============================================================================

COMMON_PHRASES: Dict[str, List[str]] = {
    "greetings": [
        "namaste", "namaskar", "satsriakal", "hello", "hi", "hey",
        "kaise ho", "kya haal hai", "how are you", "good morning",
        "good afternoon", "good evening", "good night"
    ],
    
    "agreements": [
        "haan", "yes", "bilkul", "exactly", "sahi hai", "correct",
        "theek hai", "okay", "ok", "accha", "good", "bahut achha",
        "very good", "perfect", "perfect"
    ],
    
    "disagreements": [
        "nahi", "no", "nahi hai", "not", "galat", "wrong", "nahi sahi",
        "not correct", "nahi theek", "not okay", "buri baat", "bad thing"
    ],
    
    "thanks": [
        "dhanyavad", "thank you", "thanks", "shukriya", "thank you",
        "bahut dhanyavad", "thank you very much", "thanks a lot"
    ],
    
    "goodbye": [
        "alvida", "goodbye", "bye", "see you", "phir milenge", "see you later",
        "take care", "khayal rakhna", "good night", "shubh ratri"
    ]
}

# =============================================================================
# CONFIDENCE THRESHOLDS
# =============================================================================

CONFIDENCE_THRESHOLDS = {
    "high_confidence": 0.8,
    "medium_confidence": 0.6,
    "low_confidence": 0.4,
    "minimum_confidence": 0.3
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
