"""
Indian Intent Classifier Implementation
High-performance intent classification for Indian commerce conversations
Uses patterns from extracted_patterns.py for multi-language intent detection
"""

import re
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict

from .extracted_patterns import INTENT_PATTERNS, CONFIDENCE_THRESHOLDS

@dataclass
class IntentResult:
    """Intent classification result with metadata"""
    intent: str
    confidence: float
    matched_keywords: List[str]
    matched_phrases: List[str]
    language: str = "unknown"

class IndianIntentClassifier:
    """
    High-performance intent classifier for Indian commerce conversations
    Handles Hindi/English/Hinglish text with multi-signal scoring
    """
    
    def __init__(self):
        """Initialize classifier with pre-processed patterns"""
        self._build_intent_patterns()
        self._compile_regex_patterns()
        self._build_language_indicators()
        
        # Intent categories from extracted patterns
        self.intent_categories = [
            "place_order", "modify_order", "check_status", "cancel_order",
            "greeting", "weather", "cricket", "jokes", "registration", "help"
        ]
        
        # Confidence thresholds
        self.confidence_threshold = CONFIDENCE_THRESHOLDS.get("intent_detection", 0.7)
        self.fallback_intent = "general_query"
        
    def _build_intent_patterns(self):
        """Build fast lookup tables for intent patterns"""
        self.intent_keywords = {}
        self.intent_phrases = {}
        self.keyword_to_intents = defaultdict(list)
        self.phrase_to_intents = defaultdict(list)
        
        for intent_name, intent_data in INTENT_PATTERNS.items():
            # Build keyword sets
            keywords = set()
            keywords.update(intent_data.get("keywords_en", []))
            keywords.update(intent_data.get("keywords_hi", []))
            keywords.update(intent_data.get("keywords_mixed", []))
            
            # Convert to lowercase for case-insensitive matching
            keywords = {kw.lower() for kw in keywords if kw}
            self.intent_keywords[intent_name] = keywords
            
            # Build phrase sets
            phrases = set(intent_data.get("phrases", []))
            phrases = {phrase.lower() for phrase in phrases if phrase}
            self.intent_phrases[intent_name] = phrases
            
            # Build reverse mappings for fast lookup
            for keyword in keywords:
                self.keyword_to_intents[keyword].append(intent_name)
            
            for phrase in phrases:
                self.phrase_to_intents[phrase].append(intent_name)
    
    def _compile_regex_patterns(self):
        """Pre-compile regex patterns for performance"""
        # Text normalization patterns
        self.normalization_patterns = [
            re.compile(r'\s+'),  # Multiple spaces
            re.compile(r'[^\w\s\u0900-\u097F]'),  # Remove punctuation except Hindi
        ]
        
        # Language detection patterns
        self.hindi_patterns = [
            re.compile(r'[\u0900-\u097F]'),  # Devanagari script
            re.compile(r'\b(ka|ki|ke|hai|hain|ho|hoon|main|aap|tum|yeh|woh|kya|kaise|kahan|kab|kyun|kaun|konsa|mein|par|se|ko|ne|pe|me)\b', re.IGNORECASE),
        ]
        
        self.english_patterns = [
            re.compile(r'\b(the|a|an|is|are|was|were|have|has|had|will|would|can|could|should|may|might|do|does|did|am|be|been|being|this|that|these|those)\b', re.IGNORECASE),
        ]
        
        self.hinglish_patterns = [
            re.compile(r'\b(ok|okay|yes|no|good|bad|nice|fine|problem|issue|help|support|service|customer|business)\b', re.IGNORECASE),
        ]
    
    def _build_language_indicators(self):
        """Build language detection indicators"""
        self.language_indicators = {
            "hindi": [
                "ka", "ki", "ke", "hai", "hain", "ho", "hoon", "main", "aap", "tum",
                "yeh", "woh", "kya", "kaise", "kahan", "kab", "kyun", "kaun", "konsa",
                "mein", "par", "se", "ko", "ne", "pe", "me"
            ],
            "english": [
                "the", "a", "an", "is", "are", "was", "were", "have", "has", "had",
                "will", "would", "can", "could", "should", "may", "might", "do",
                "does", "did", "am", "be", "been", "being", "this", "that", "these", "those"
            ],
            "hinglish": [
                "ok", "okay", "yes", "no", "good", "bad", "nice", "fine", "problem",
                "issue", "help", "support", "service", "customer", "business"
            ]
        }
    
    def classify(self, text: str) -> Dict[str, Any]:
        """
        Classify intent from input text
        
        Args:
            text: Input text in Hindi/English/Hinglish
            
        Returns:
            Dictionary with intent, confidence, and matched patterns
        """
        if not text or not text.strip():
            return self._create_fallback_result()
        
        # Normalize text
        normalized_text = self._normalize_text(text)
        
        # Detect language
        language = self._detect_language(normalized_text)
        
        # Get intent scores
        intent_scores = self._calculate_intent_scores(normalized_text)
        
        # Find best intent
        best_intent, best_score = self._find_best_intent(intent_scores)
        
        # Get matched patterns
        matched_keywords, matched_phrases = self._get_matched_patterns(normalized_text, best_intent)
        
        # Create result
        if best_score >= self.confidence_threshold:
            return {
                "intent": best_intent,
                "confidence": best_score,
                "matched_keywords": matched_keywords,
                "matched_phrases": matched_phrases,
                "language": language
            }
        else:
            return self._create_fallback_result(language)
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for better processing"""
        # Convert to lowercase
        text = text.lower()
        
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove punctuation except Hindi characters
        text = re.sub(r'[^\w\s\u0900-\u097F]', ' ', text)
        
        return text.strip()
    
    def _detect_language(self, text: str) -> str:
        """
        Detect language of input text
        Returns: 'hindi', 'english', 'hinglish', or 'unknown'
        """
        if not text:
            return "unknown"
        
        words = text.split()
        if not words:
            return "unknown"
        
        hindi_count = 0
        english_count = 0
        hinglish_count = 0
        
        # Check for Devanagari script
        if re.search(r'[\u0900-\u097F]', text):
            hindi_count += len(words) * 0.5  # Boost Hindi score
        
        # Count language indicators
        for word in words:
            if word in self.language_indicators["hindi"]:
                hindi_count += 1
            elif word in self.language_indicators["english"]:
                english_count += 1
            elif word in self.language_indicators["hinglish"]:
                hinglish_count += 1
        
        total_words = len(words)
        hindi_ratio = hindi_count / total_words
        english_ratio = english_count / total_words
        hinglish_ratio = hinglish_count / total_words
        
        # More lenient thresholds
        if hindi_ratio > 0.2:
            return "hindi"
        elif english_ratio > 0.3:
            return "english"
        elif hinglish_ratio > 0.1 or (hindi_ratio > 0.1 and english_ratio > 0.1):
            return "hinglish"
        else:
            return "unknown"
    
    def _calculate_intent_scores(self, text: str) -> Dict[str, float]:
        """Calculate intent scores using multi-signal approach"""
        intent_scores = defaultdict(float)
        words = set(text.split())
        
        # Calculate keyword scores
        keyword_scores = self._calculate_keyword_scores(words)
        
        # Calculate phrase scores
        phrase_scores = self._calculate_phrase_scores(text)
        
        # Combine scores with weights
        for intent in self.intent_categories:
            keyword_score = keyword_scores.get(intent, 0.0)
            phrase_score = phrase_scores.get(intent, 0.0)
            
            # Weighted combination: (keyword_score * 0.6) + (phrase_score * 0.4)
            combined_score = (keyword_score * 0.6) + (phrase_score * 0.4)
            intent_scores[intent] = combined_score
        
        return dict(intent_scores)
    
    def _calculate_keyword_scores(self, words: Set[str]) -> Dict[str, float]:
        """Calculate keyword-based scores for each intent"""
        keyword_scores = defaultdict(float)
        
        for word in words:
            if word in self.keyword_to_intents:
                # Word matches one or more intents
                matching_intents = self.keyword_to_intents[word]
                
                # Distribute score among matching intents
                score_per_intent = 1.0 / len(matching_intents)
                
                for intent in matching_intents:
                    keyword_scores[intent] += score_per_intent
        
        # Normalize scores
        max_score = max(keyword_scores.values()) if keyword_scores else 1.0
        if max_score > 0:
            for intent in keyword_scores:
                keyword_scores[intent] = min(keyword_scores[intent] / max_score, 1.0)
        
        return dict(keyword_scores)
    
    def _calculate_phrase_scores(self, text: str) -> Dict[str, float]:
        """Calculate phrase-based scores for each intent"""
        phrase_scores = defaultdict(float)
        
        for intent, phrases in self.intent_phrases.items():
            for phrase in phrases:
                if phrase in text:
                    # Phrase found in text
                    phrase_scores[intent] += 1.0
                else:
                    # Check for partial matches (for Hindi phrases)
                    words = text.split()
                    phrase_words = phrase.split()
                    if len(phrase_words) > 1:
                        # Check if most words in phrase are present
                        matches = sum(1 for pw in phrase_words if any(pw in w for w in words))
                        if matches >= len(phrase_words) * 0.7:  # 70% match threshold
                            phrase_scores[intent] += 0.5
        
        # Normalize scores
        max_score = max(phrase_scores.values()) if phrase_scores else 1.0
        if max_score > 0:
            for intent in phrase_scores:
                phrase_scores[intent] = min(phrase_scores[intent] / max_score, 1.0)
        
        return dict(phrase_scores)
    
    def _find_best_intent(self, intent_scores: Dict[str, float]) -> Tuple[str, float]:
        """Find the intent with highest score"""
        if not intent_scores:
            return self.fallback_intent, 0.0
        
        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        return best_intent
    
    def _get_matched_patterns(self, text: str, intent: str) -> Tuple[List[str], List[str]]:
        """Get matched keywords and phrases for the given intent"""
        matched_keywords = []
        matched_phrases = []
        
        if intent not in self.intent_keywords:
            return matched_keywords, matched_phrases
        
        # Find matched keywords
        words = set(text.split())
        intent_keywords = self.intent_keywords[intent]
        matched_keywords = [word for word in words if word in intent_keywords]
        
        # Find matched phrases
        intent_phrases = self.intent_phrases[intent]
        matched_phrases = [phrase for phrase in intent_phrases if phrase in text]
        
        return matched_keywords, matched_phrases
    
    def _create_fallback_result(self, language: str = "unknown") -> Dict[str, Any]:
        """Create fallback result when confidence is below threshold"""
        return {
            "intent": self.fallback_intent,
            "confidence": 0.0,
            "matched_keywords": [],
            "matched_phrases": [],
            "language": language
        }
    
    def get_intent_confidence_threshold(self, intent: str) -> float:
        """Get confidence threshold for specific intent"""
        if intent in INTENT_PATTERNS:
            return INTENT_PATTERNS[intent].get("confidence_threshold", self.confidence_threshold)
        return self.confidence_threshold
    
    def get_supported_intents(self) -> List[str]:
        """Get list of supported intent categories"""
        return self.intent_categories.copy()
    
    def get_intent_priority(self, intent: str) -> str:
        """Get priority level for specific intent"""
        if intent in INTENT_PATTERNS:
            return INTENT_PATTERNS[intent].get("priority", "medium")
        return "medium"
    
    def classify_with_metadata(self, text: str) -> IntentResult:
        """
        Classify intent and return detailed result object
        
        Args:
            text: Input text in Hindi/English/Hinglish
            
        Returns:
            IntentResult object with all classification metadata
        """
        result_dict = self.classify(text)
        
        return IntentResult(
            intent=result_dict["intent"],
            confidence=result_dict["confidence"],
            matched_keywords=result_dict["matched_keywords"],
            matched_phrases=result_dict["matched_phrases"],
            language=result_dict["language"]
        )

# Global instance for easy access
indian_intent_classifier = IndianIntentClassifier()
