"""
Indian Multilingual Order Service
Supports all major Indian languages with Google Translate integration
Handles Hinglish, regional languages, and Indian context preservation
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from functools import lru_cache
import asyncio

# Google Cloud Translation imports
try:
    from google.cloud import translate_v2 as translate
    from google.cloud import translate
    GOOGLE_TRANSLATE_AVAILABLE = True
except ImportError:
    GOOGLE_TRANSLATE_AVAILABLE = False
    logging.warning("Google Cloud Translation not available. Install with: pip install google-cloud-translate")

# Local imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from nlp.indian_commerce_ner import indian_commerce_ner
from nlp.intent_classifier import indian_intent_classifier

@dataclass
class MultilingualResult:
    """Result from multilingual order processing"""
    original_text: str
    detected_language: str
    translated_text: Optional[str]
    intent: str
    confidence: float
    entities: List[Dict[str, Any]]
    response: str
    response_language: str
    processing_time: float

class IndianMultilingualService:
    """
    Indian Multilingual Order Service
    Supports all major Indian languages with intelligent translation and context preservation
    """
    
    def __init__(self, google_api_key: Optional[str] = None):
        """Initialize the multilingual service"""
        self.google_api_key = google_api_key
        self.translate_client = None
        self._initialize_translation_client()
        self._build_indian_languages()
        self._build_hinglish_patterns()
        self._build_indian_context_patterns()
        self._build_translation_cache()
        
    def _initialize_translation_client(self):
        """Initialize Google Cloud Translation client"""
        if not GOOGLE_TRANSLATE_AVAILABLE:
            logging.error("Google Cloud Translation not available")
            return
            
        try:
            if self.google_api_key:
                # Use API key authentication
                self.translate_client = translate.Client(api_key=self.google_api_key)
            else:
                # Use default credentials (service account)
                self.translate_client = translate.Client()
            logging.info("Google Cloud Translation client initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize Google Cloud Translation: {e}")
            self.translate_client = None
    
    def _build_indian_languages(self):
        """Build comprehensive Indian language mappings"""
        self.INDIAN_LANGUAGES = {
            # Direct support (no translation needed)
            "en": {"name": "English", "script": "Latin", "needs_translation": False},
            "hi": {"name": "Hindi", "script": "Devanagari", "needs_translation": False},
            "mixed": {"name": "Hinglish", "script": "Mixed", "needs_translation": False},
            
            # Major Indian languages
            "bn": {"name": "Bengali", "script": "Bengali", "needs_translation": True},
            "ta": {"name": "Tamil", "script": "Tamil", "needs_translation": True},
            "te": {"name": "Telugu", "script": "Telugu", "needs_translation": True},
            "mr": {"name": "Marathi", "script": "Devanagari", "needs_translation": True},
            "gu": {"name": "Gujarati", "script": "Gujarati", "needs_translation": True},
            "kn": {"name": "Kannada", "script": "Kannada", "needs_translation": True},
            "ml": {"name": "Malayalam", "script": "Malayalam", "needs_translation": True},
            "pa": {"name": "Punjabi", "script": "Gurmukhi", "needs_translation": True},
            
            # Regional Indian languages
            "or": {"name": "Odia", "script": "Odia", "needs_translation": True},
            "as": {"name": "Assamese", "script": "Bengali", "needs_translation": True},
            "ur": {"name": "Urdu", "script": "Perso-Arabic", "needs_translation": True},
            "kok": {"name": "Konkani", "script": "Devanagari", "needs_translation": True},
            "sd": {"name": "Sindhi", "script": "Perso-Arabic", "needs_translation": True},
            "ne": {"name": "Nepali", "script": "Devanagari", "needs_translation": True},
            "ks": {"name": "Kashmiri", "script": "Perso-Arabic", "needs_translation": True}
        }
        
        # Language detection patterns
        self.language_scripts = {
            "Devanagari": r"[\u0900-\u097F]",  # Hindi, Marathi, Konkani, Nepali
            "Bengali": r"[\u0980-\u09FF]",     # Bengali, Assamese
            "Tamil": r"[\u0B80-\u0BFF]",       # Tamil
            "Telugu": r"[\u0C00-\u0C7F]",      # Telugu
            "Gujarati": r"[\u0A80-\u0AFF]",    # Gujarati
            "Kannada": r"[\u0C80-\u0CFF]",     # Kannada
            "Malayalam": r"[\u0D00-\u0D7F]",   # Malayalam
            "Gurmukhi": r"[\u0A00-\u0A7F]",    # Punjabi
            "Odia": r"[\u0B00-\u0B7F]",        # Odia
            "Perso-Arabic": r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]",  # Urdu, Sindhi, Kashmiri
        }
    
    def _build_hinglish_patterns(self):
        """Build patterns for Hinglish detection"""
        self.hinglish_indicators = {
            "hindi_words": [
                "chahiye", "hai", "hain", "karna", "karo", "do", "dena", "lana", "bhejo",
                "mangana", "order", "cancel", "status", "kahan", "kab", "kaise", "kya",
                "mujhe", "main", "aap", "tum", "yeh", "woh", "aur", "par", "se", "ko"
            ],
            "english_words": [
                "order", "want", "need", "buy", "get", "send", "bring", "cancel", "status",
                "where", "when", "how", "what", "please", "thank", "hello", "hi", "ok"
            ],
            "mixed_patterns": [
                r"\b[a-zA-Z]+\s+[a-zA-Z\u0900-\u097F]+\b",  # English + Hindi
                r"\b[a-zA-Z\u0900-\u097F]+\s+[a-zA-Z]+\b",  # Hindi + English
                r"\b[a-zA-Z]+[a-zA-Z\u0900-\u097F]+\b",     # Mixed word
            ]
        }
    
    def _build_indian_context_patterns(self):
        """Build patterns for Indian context preservation"""
        self.indian_context = {
            "units": {
                "ser": ["ser", "सेर", "সের", "சேர்", "సేర్", "सेर", "સેર", "ಸೇರ್", "സേർ", "ਸੇਰ", "ସେର", "সেৰ", "سیر", "सेर", "سير", "सेर", "سیر"],
                "pau": ["pau", "पाव", "পাউ", "பவ்", "పవ్", "पाव", "પાવ", "ಪಾವ್", "പാവ്", "ਪਾਵ", "ପାଵ", "পাও", "پاؤ", "पाव", "پاو", "पाव", "پاؤ"],
                "kg": ["kg", "kilo", "kilogram", "किलो", "केजी", "কিলো", "கிலோ", "కిలో", "किलो", "કિલો", "ಕಿಲೋ", "കിലോ", "ਕਿਲੋ", "କିଲୋ", "কিলো", "کلو", "किलो", "کلو", "किलो", "کلو"],
                "l": ["l", "litre", "liter", "लीटर", "লিটার", "லிட்டர்", "లీటర్", "लीटर", "લિટર", "ಲೀಟರ್", "ലിറ്റർ", "ਲੀਟਰ", "ଲିଟର", "লিটাৰ", "لیٹر", "लीटर", "لیتر", "लीटर", "لیتر"]
            },
            "numbers": {
                "lakh": ["lakh", "लाख", "লাখ", "லட்சம்", "లక్షం", "लाख", "લાખ", "ಲಕ್ಷ", "ലക്ഷം", "ਲੱਖ", "ଲକ୍ଷ", "লক্ষ", "لاکھ", "लाख", "لکھ", "लाख", "لکھ"],
                "crore": ["crore", "करोड़", "কোটি", "கோடி", "కోటి", "करोड़", "કરોડ", "ಕೋಟಿ", "കോടി", "ਕਰੋੜ", "କୋଟି", "কোটি", "کروڑ", "करोड़", "کروڑ", "करोड़", "کروڑ"]
            },
            "products": {
                "rice": ["rice", "chawal", "चावल", "চাল", "அரிசி", "బియ్యం", "चावल", "ચોખા", "ಅಕ್ಕಿ", "അരി", "ਚਾਵਲ", "ଚାଉଳ", "চাউল", "چاول", "चावल", "چاول", "चावल", "چاول"],
                "flour": ["flour", "atta", "आटा", "আটা", "மாவு", "పిండి", "आटा", "આટો", "ಹಿಟ್ಟು", "മാവ്", "ਆਟਾ", "ଆଟା", "আটা", "آٹا", "आटा", "آٹا", "आटा", "آٹا"]
            },
            "brands": {
                "maggi": ["maggi", "मैगी", "ম্যাগি", "மாகி", "మాగీ", "मैगी", "મેગી", "ಮ್ಯಾಗಿ", "മാഗി", "ਮੈਗੀ", "ମାଗି", "মেগি", "میگی", "मैगी", "میگی", "मैगी", "میگی"],
                "amul": ["amul", "अमूल", "আমুল", "அமுல்", "అముల్", "अमूल", "અમૂલ", "ಅಮೂಲ್", "അമൂൽ", "ਅਮੂਲ", "ଆମୁଲ", "আমুল", "امول", "अमूल", "امول", "अमूल", "امول"]
            }
        }
    
    def _build_translation_cache(self):
        """Build translation cache for common phrases"""
        self.translation_cache = {
            # Common order phrases
            "order_phrases": {
                "en": ["I want", "I need", "Please send", "Order", "Buy"],
                "hi": ["मुझे चाहिए", "मुझे जरूरत है", "कृपया भेजें", "ऑर्डर", "खरीदें"],
                "bn": ["আমার দরকার", "আমার প্রয়োজন", "অনুগ্রহ করে পাঠান", "অর্ডার", "কিনুন"],
                "ta": ["எனக்கு வேண்டும்", "எனக்கு தேவை", "தயவுசெய்து அனுப்புங்கள்", "ஆர்டர்", "வாங்குங்கள்"],
                "te": ["నాకు కావాలి", "నాకు అవసరం", "దయచేసి పంపండి", "ఆర్డర్", "కొనండి"],
                "mr": ["मला हवे आहे", "मला गरज आहे", "कृपया पाठवा", "ऑर्डर", "विकत घ्या"],
                "gu": ["મને જોઈએ છે", "મને જરૂર છે", "કૃપા કરી મોકલો", "ઓર્ડર", "ખરીદો"],
                "kn": ["ನನಗೆ ಬೇಕು", "ನನಗೆ ಅಗತ್ಯವಿದೆ", "ದಯವಿಟ್ಟು ಕಳುಹಿಸಿ", "ಆರ್ಡರ್", "ಖರೀದಿಸಿ"],
                "ml": ["എനിക്ക് വേണം", "എനിക്ക് ആവശ്യമാണ്", "ദയവായി അയയ്ക്കുക", "ഓർഡർ", "വാങ്ങുക"],
                "pa": ["ਮੈਨੂੰ ਚਾਹੀਦਾ ਹੈ", "ਮੈਨੂੰ ਲੋੜ ਹੈ", "ਕਿਰਪਾ ਕਰਕੇ ਭੇਜੋ", "ਆਰਡਰ", "ਖਰੀਦੋ"]
            },
            # Common responses
            "response_phrases": {
                "en": ["Order confirmed", "Order received", "Thank you", "Processing"],
                "hi": ["ऑर्डर कन्फर्म", "ऑर्डर प्राप्त", "धन्यवाद", "प्रोसेसिंग"],
                "bn": ["অর্ডার নিশ্চিত", "অর্ডার প্রাপ্ত", "ধন্যবাদ", "প্রক্রিয়াকরণ"],
                "ta": ["ஆர்டர் உறுதி", "ஆர்டர் பெறப்பட்டது", "நன்றி", "செயலாக்கம்"],
                "te": ["ఆర్డర్ నిర్ధారించబడింది", "ఆర్డర్ స్వీకరించబడింది", "ధన్యవాదాలు", "ప్రాసెసింగ్"],
                "mr": ["ऑर्डर कन्फर्म", "ऑर्डर प्राप्त", "धन्यवाद", "प्रोसेसिंग"],
                "gu": ["ઓર્ડર કન્ફર્મ", "ઓર્ડર પ્રાપ્ત", "ધન્યવાદ", "પ્રોસેસિંગ"],
                "kn": ["ಆರ್ಡರ್ ದೃಢೀಕರಿಸಲಾಗಿದೆ", "ಆರ್ಡರ್ ಸ್ವೀಕರಿಸಲಾಗಿದೆ", "ಧನ್ಯವಾದಗಳು", "ಪ್ರಕ್ರಿಯೆ"],
                "ml": ["ഓർഡർ സ്ഥിരീകരിച്ചു", "ഓർഡർ ലഭിച്ചു", "നന്ദി", "പ്രോസസിംഗ്"],
                "pa": ["ਆਰਡਰ ਦੀ ਪੁਸ਼ਟੀ", "ਆਰਡਰ ਪ੍ਰਾਪਤ", "ਧੰਨਵਾਦ", "ਪ੍ਰਕਿਰਿਆ"]
            }
        }
    
    async def process_indian_order(self, message: str, session_id: str) -> MultilingualResult:
        """
        Main method to process Indian order in any supported language
        
        Args:
            message: Input message in any Indian language
            session_id: Session identifier for caching
            
        Returns:
            MultilingualResult with processed order details
        """
        import time
        start_time = time.time()
        
        try:
            # Step 1: Detect language
            detected_lang = self.detect_indian_language(message)
            
            # Step 2: Handle translation if needed
            translated_text = None
            if detected_lang != "en" and detected_lang != "hi" and detected_lang != "mixed":
                translated_text = await self.translate_for_processing(message, detected_lang)
                if not translated_text:
                    # Fallback to English processing
                    translated_text = message
                    detected_lang = "en"
            
            # Step 3: Process with NLP components
            processing_text = translated_text if translated_text else message
            
            # Intent classification
            intent_result = indian_intent_classifier.classify(processing_text)
            
            # Entity extraction
            entities = indian_commerce_ner.extract_entities(processing_text)
            
            # Step 4: Generate response
            response = self._generate_response(intent_result, entities, detected_lang)
            
            # Step 5: Translate response if needed
            response_lang = detected_lang
            if detected_lang not in ["en", "hi", "mixed"]:
                translated_response = await self.translate_response(response, detected_lang)
                if translated_response:
                    response = translated_response
                    response_lang = detected_lang
            
            processing_time = time.time() - start_time
            
            return MultilingualResult(
                original_text=message,
                detected_language=detected_lang,
                translated_text=translated_text,
                intent=intent_result.get("intent", "general_query"),
                confidence=intent_result.get("confidence", 0.0),
                entities=entities,
                response=response,
                response_language=response_lang,
                processing_time=processing_time
            )
            
        except Exception as e:
            logging.error(f"Error processing Indian order: {e}")
            # Return fallback result
            return MultilingualResult(
                original_text=message,
                detected_language="en",
                translated_text=None,
                intent="general_query",
                confidence=0.0,
                entities=[],
                response="Sorry, I couldn't process your request. Please try again.",
                response_language="en",
                processing_time=time.time() - start_time
            )
    
    def is_hinglish(self, text: str) -> bool:
        """
        Detect if text is Hinglish (mixed Hindi-English)
        
        Args:
            text: Input text to check
            
        Returns:
            True if text is Hinglish, False otherwise
        """
        if not text:
            return False
        
        text_lower = text.lower()
        words = text_lower.split()
        
        # Check for mixed script patterns
        has_hindi = bool(re.search(r'[\u0900-\u097F]', text))
        has_english = bool(re.search(r'[a-zA-Z]', text))
        
        if has_hindi and has_english:
            return True
        
        # Check for mixed word patterns
        hindi_count = 0
        english_count = 0
        
        for word in words:
            if word in self.hinglish_indicators["hindi_words"]:
                hindi_count += 1
            elif word in self.hinglish_indicators["english_words"]:
                english_count += 1
        
        # If both Hindi and English words present, likely Hinglish
        if hindi_count > 0 and english_count > 0:
            return True
        
        # Check for mixed patterns
        for pattern in self.hinglish_indicators["mixed_patterns"]:
            if re.search(pattern, text):
                return True
        
        return False
    
    def detect_indian_language(self, text: str) -> str:
        """
        Detect Indian language from text
        
        Args:
            text: Input text to detect language for
            
        Returns:
            Language code (en, hi, mixed, bn, ta, etc.)
        """
        if not text:
            return "en"
        
        # First check if Hinglish
        if self.is_hinglish(text):
            return "mixed"
        
        # Check for script-based detection
        for script_name, script_pattern in self.language_scripts.items():
            if re.search(script_pattern, text):
                # Map script to language codes
                script_to_lang = {
                    "Devanagari": "hi",
                    "Bengali": "bn", 
                    "Tamil": "ta",
                    "Telugu": "te",
                    "Gujarati": "gu",
                    "Kannada": "kn",
                    "Malayalam": "ml",
                    "Gurmukhi": "pa",
                    "Odia": "or",
                    "Perso-Arabic": "ur"
                }
                return script_to_lang.get(script_name, "en")
        
        # Use Google Translate for detection if available
        if self.translate_client:
            try:
                result = self.translate_client.detect_language(text)
                detected_lang = result['language']
                
                # Map to our supported languages
                if detected_lang in self.INDIAN_LANGUAGES:
                    return detected_lang
                else:
                    return "en"  # Fallback to English
                    
            except Exception as e:
                logging.warning(f"Google Translate detection failed: {e}")
                return "en"
        
        # Fallback: assume English if no other indicators
        return "en"
    
    async def translate_for_processing(self, text: str, source_lang: str) -> Optional[str]:
        """
        Translate text to English for processing
        
        Args:
            text: Text to translate
            source_lang: Source language code
            
        Returns:
            Translated English text or None if translation fails
        """
        if not self.translate_client or source_lang in ["en", "hi", "mixed"]:
            return None
        
        try:
            # Check cache first
            cache_key = f"{source_lang}:{text}"
            if hasattr(self, '_translation_cache') and cache_key in self._translation_cache:
                return self._translation_cache[cache_key]
            
            # Perform translation
            result = self.translate_client.translate(
                text,
                source_language=source_lang,
                target_language='en'
            )
            
            translated_text = result['translatedText']
            
            # Cache the result
            if not hasattr(self, '_translation_cache'):
                self._translation_cache = {}
            self._translation_cache[cache_key] = translated_text
            
            return translated_text
            
        except Exception as e:
            logging.error(f"Translation failed: {e}")
            return None
    
    async def translate_response(self, text: str, target_lang: str) -> Optional[str]:
        """
        Translate response back to target language
        
        Args:
            text: English text to translate
            target_lang: Target language code
            
        Returns:
            Translated text or None if translation fails
        """
        if not self.translate_client or target_lang in ["en", "hi", "mixed"]:
            return None
        
        try:
            # Check cache first
            cache_key = f"en:{text}:{target_lang}"
            if hasattr(self, '_response_cache') and cache_key in self._response_cache:
                return self._response_cache[cache_key]
            
            # Perform translation
            result = self.translate_client.translate(
                text,
                source_language='en',
                target_language=target_lang
            )
            
            translated_text = result['translatedText']
            
            # Cache the result
            if not hasattr(self, '_response_cache'):
                self._response_cache = {}
            self._response_cache[cache_key] = translated_text
            
            return translated_text
            
        except Exception as e:
            logging.error(f"Response translation failed: {e}")
            return None
    
    def get_language_name(self, code: str) -> str:
        """
        Get language name from code
        
        Args:
            code: Language code
            
        Returns:
            Language name
        """
        return self.INDIAN_LANGUAGES.get(code, {}).get("name", "Unknown")
    
    def _generate_response(self, intent_result: Dict[str, Any], entities: List[Dict[str, Any]], language: str) -> str:
        """
        Generate response based on intent and entities
        
        Args:
            intent_result: Intent classification result
            entities: Extracted entities
            language: Target language for response
            
        Returns:
            Generated response
        """
        intent = intent_result.get("intent", "general_query")
        confidence = intent_result.get("confidence", 0.0)
        
        if intent == "place_order" and entities:
            # Generate order confirmation
            items = []
            for entity in entities:
                product = entity.get("product", "item")
                quantity = entity.get("quantity", 0)
                unit = entity.get("unit", "")
                brand = entity.get("brand", "")
                
                item_desc = f"{quantity} {unit} {product}".strip()
                if brand:
                    item_desc = f"{brand} {item_desc}"
                items.append(item_desc)
            
            if len(items) == 1:
                return f"Order confirmed: {items[0]}"
            else:
                return f"Order confirmed: {', '.join(items[:-1])} and {items[-1]}"
        
        elif intent == "check_status":
            return "Your order status is being checked. Please provide your order number."
        
        elif intent == "cancel_order":
            return "Your order has been cancelled successfully."
        
        elif intent == "greeting":
            return "Hello! How can I help you with your order today?"
        
        elif intent == "modify_order":
            return "I'll help you modify your order. Please provide the changes you'd like to make."
        
        else:
            return "I understand you're looking for something. Could you please provide more details about your order?"
    
    def get_supported_languages(self) -> Dict[str, str]:
        """
        Get list of supported languages
        
        Returns:
            Dictionary of language codes to names
        """
        return {code: info["name"] for code, info in self.INDIAN_LANGUAGES.items()}
    
    def is_language_supported(self, language_code: str) -> bool:
        """
        Check if language is supported
        
        Args:
            language_code: Language code to check
            
        Returns:
            True if supported, False otherwise
        """
        return language_code in self.INDIAN_LANGUAGES
    
    @lru_cache(maxsize=1000)
    def get_cached_translation(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """
        Get cached translation if available
        
        Args:
            text: Text to translate
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            Cached translation or None
        """
        cache_key = f"{source_lang}:{text}:{target_lang}"
        return getattr(self, '_translation_cache', {}).get(cache_key)
    
    def clear_cache(self):
        """Clear translation cache"""
        if hasattr(self, '_translation_cache'):
            self._translation_cache.clear()
        if hasattr(self, '_response_cache'):
            self._response_cache.clear()
        self.get_cached_translation.cache_clear()

# Global instance for easy access
indian_multilingual_service = IndianMultilingualService()
