"""
Indian NER (Named Entity Recognition) Implementation
Clean Python implementation extracted from kirana-voice-enterprise patterns
Optimized for performance with pure Python regex and rules
"""

import re
import json
from typing import Dict, List, Set, Tuple, Optional, Any, NamedTuple
from dataclasses import dataclass
from enum import Enum
import logging

from .kirana_patterns import (
    INDIAN_PRODUCTS, UNITS_AND_MEASUREMENTS, NUMBER_WORDS,
    BRAND_NAMES, INDIAN_NAMES, INDIAN_LOCATIONS, COMMON_PHRASES
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EntityType(Enum):
    """Entity types for NER classification"""
    PRODUCT = "product"
    QUANTITY = "quantity"
    UNIT = "unit"
    BRAND = "brand"
    PERSON_NAME = "person_name"
    LOCATION = "location"
    PHONE_NUMBER = "phone_number"
    AADHAAR = "aadhaar"
    PAN = "pan"
    GSTIN = "gstin"
    PRICE = "price"
    CURRENCY = "currency"
    DATE = "date"
    TIME = "time"
    EMAIL = "email"
    WEBSITE = "website"
    ADDRESS = "address"

@dataclass
class Entity:
    """Named entity with metadata"""
    text: str
    entity_type: EntityType
    start: int
    end: int
    confidence: float
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class NERResult:
    """Complete NER analysis result"""
    entities: List[Entity]
    text: str
    language: str
    confidence: float
    processing_time: float

class IndianNER:
    """
    Indian NER implementation with multilingual support
    Extracted patterns from kirana-voice-enterprise project
    """
    
    def __init__(self):
        """Initialize NER with compiled patterns"""
        self._compile_patterns()
        self._build_product_index()
        self._build_brand_index()
        self._build_name_index()
        self._build_location_index()
        
    def _compile_patterns(self):
        """Compile regex patterns for performance"""
        # Phone number patterns (Indian)
        self.phone_patterns = [
            re.compile(r'(\+91[\s-]?)?[789]\d{9}', re.IGNORECASE),  # +91 9876543210
            re.compile(r'(\+91[\s-]?)?[789]\d{2}[\s-]?\d{3}[\s-]?\d{4}', re.IGNORECASE),  # +91 987 654 3210
            re.compile(r'[789]\d{9}', re.IGNORECASE),  # 9876543210
        ]
        
        # Aadhaar patterns
        self.aadhaar_patterns = [
            re.compile(r'\d{4}[\s-]?\d{4}[\s-]?\d{4}', re.IGNORECASE),  # 1234 5678 9012
            re.compile(r'\d{12}', re.IGNORECASE),  # 123456789012
        ]
        
        # PAN patterns
        self.pan_patterns = [
            re.compile(r'[A-Z]{5}\d{4}[A-Z]{1}', re.IGNORECASE),  # ABCDE1234F
            re.compile(r'[A-Z]{5}[\s-]?\d{4}[\s-]?[A-Z]{1}', re.IGNORECASE),  # ABCDE 1234 F
        ]
        
        # GSTIN patterns
        self.gstin_patterns = [
            re.compile(r'\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d{1}[Z]{1}[A-Z\d]{1}', re.IGNORECASE),
            re.compile(r'\d{2}[\s-]?[A-Z]{5}[\s-]?\d{4}[\s-]?[A-Z]{1}[\s-]?\d{1}[\s-]?[Z]{1}[\s-]?[A-Z\d]{1}', re.IGNORECASE),
        ]
        
        # Price patterns
        self.price_patterns = [
            re.compile(r'₹[\s]?\d+([.,]\d{3})*([.,]\d{2})?', re.IGNORECASE),  # ₹1,234.56
            re.compile(r'rs\.?[\s]?\d+([.,]\d{3})*([.,]\d{2})?', re.IGNORECASE),  # Rs. 1,234.56
            re.compile(r'rupees?[\s]?\d+([.,]\d{3})*([.,]\d{2})?', re.IGNORECASE),  # Rupees 1,234.56
            re.compile(r'₹[\s]?\d+', re.IGNORECASE),  # ₹1234
            re.compile(r'rs\.?[\s]?\d+', re.IGNORECASE),  # Rs. 1234
        ]
        
        # Quantity patterns
        self.quantity_patterns = [
            re.compile(r'(\d+(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(kg|kilo|gram|g|gm|ton|liter|l|ml|piece|pc|pcs|pack|packet|dozen|hundred|thousand)', re.IGNORECASE),
            re.compile(r'(\d+(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(kilo|gram|ton|liter|piece|pack|dozen)', re.IGNORECASE),
        ]
        
        # Number word patterns
        self.number_word_patterns = [
            re.compile(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)\b', re.IGNORECASE),
            re.compile(r'\b(ek|do|teen|char|paanch|cheh|saat|aath|nau|das|gyarah|barah|terah|chaudah|pandrah|solah|satrah|atharah|unnees|bees|tees|chaalis|pachaas|saath|sattar|assi|nabbe|sau|hazaar)\b', re.IGNORECASE),
        ]
        
        # Email patterns
        self.email_patterns = [
            re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE),
        ]
        
        # Website patterns
        self.website_patterns = [
            re.compile(r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?', re.IGNORECASE),
            re.compile(r'www\.(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?', re.IGNORECASE),
        ]
        
        # Date patterns
        self.date_patterns = [
            re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', re.IGNORECASE),  # DD/MM/YYYY
            re.compile(r'\d{4}[/-]\d{1,2}[/-]\d{1,2}', re.IGNORECASE),  # YYYY/MM/DD
            re.compile(r'\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{2,4}', re.IGNORECASE),
            re.compile(r'\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{2,4}', re.IGNORECASE),
        ]
        
        # Time patterns
        self.time_patterns = [
            re.compile(r'\d{1,2}:\d{2}(?::\d{2})?\s*(am|pm)?', re.IGNORECASE),  # HH:MM:SS AM/PM
            re.compile(r'\d{1,2}\s*(am|pm)', re.IGNORECASE),  # HH AM/PM
        ]
        
        # Address patterns
        self.address_patterns = [
            re.compile(r'\d+\s+[A-Za-z\s]+(?:street|road|avenue|lane|colony|nagar|vihar|puram|nagar|society)', re.IGNORECASE),
            re.compile(r'(?:near|opposite|behind|in front of)\s+[A-Za-z\s]+', re.IGNORECASE),
        ]
        
    def _build_product_index(self):
        """Build product name index for fast lookup"""
        self.product_index = {}
        for category, products in INDIAN_PRODUCTS.items():
            for product in products:
                self.product_index[product.lower()] = {
                    'name': product,
                    'category': category,
                    'confidence': 0.9
                }
                
    def _build_brand_index(self):
        """Build brand name index for fast lookup"""
        self.brand_index = {}
        for category, brands in BRAND_NAMES.items():
            for brand in brands:
                self.brand_index[brand.lower()] = {
                    'name': brand,
                    'category': category,
                    'confidence': 0.85
                }
                
    def _build_name_index(self):
        """Build name index for fast lookup"""
        self.name_index = {}
        for gender, names in INDIAN_NAMES.items():
            for name in names:
                self.name_index[name.lower()] = {
                    'name': name,
                    'gender': gender,
                    'confidence': 0.7
                }
                
    def _build_location_index(self):
        """Build location index for fast lookup"""
        self.location_index = {}
        for location_type, locations in INDIAN_LOCATIONS.items():
            for location in locations:
                self.location_index[location.lower()] = {
                    'name': location,
                    'type': location_type,
                    'confidence': 0.8
                }
    
    def detect_language(self, text: str) -> str:
        """
        Detect language of input text
        Returns: 'en', 'hi', 'hinglish', or 'unknown'
        """
        text_lower = text.lower()
        words = text_lower.split()
        
        hindi_count = 0
        english_count = 0
        hinglish_count = 0
        
        for word in words:
            # Check Hindi indicators
            if any(indicator in word for indicator in LANGUAGE_PATTERNS["hindi_indicators"]):
                hindi_count += 1
            # Check English indicators
            elif any(indicator in word for indicator in LANGUAGE_PATTERNS["english_indicators"]):
                english_count += 1
            # Check Hinglish indicators
            elif any(indicator in word for indicator in LANGUAGE_PATTERNS["hinglish_indicators"]):
                hinglish_count += 1
        
        total_words = len(words)
        if total_words == 0:
            return 'unknown'
            
        hindi_ratio = hindi_count / total_words
        english_ratio = english_count / total_words
        hinglish_ratio = hinglish_count / total_words
        
        if hindi_ratio > 0.6:
            return 'hi'
        elif english_ratio > 0.6:
            return 'en'
        elif hinglish_ratio > 0.3 or (hindi_ratio > 0.3 and english_ratio > 0.3):
            return 'hinglish'
        else:
            return 'unknown'
    
    def extract_phone_numbers(self, text: str) -> List[Entity]:
        """Extract phone numbers from text"""
        entities = []
        for pattern in self.phone_patterns:
            for match in pattern.finditer(text):
                phone = match.group(0)
                # Validate phone number
                if self._validate_phone_number(phone):
                    entities.append(Entity(
                        text=phone,
                        entity_type=EntityType.PHONE_NUMBER,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.95
                    ))
        return entities
    
    def extract_aadhaar(self, text: str) -> List[Entity]:
        """Extract Aadhaar numbers from text"""
        entities = []
        for pattern in self.aadhaar_patterns:
            for match in pattern.finditer(text):
                aadhaar = match.group(0)
                # Validate Aadhaar (basic check)
                if self._validate_aadhaar(aadhaar):
                    entities.append(Entity(
                        text=aadhaar,
                        entity_type=EntityType.AADHAAR,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.9
                    ))
        return entities
    
    def extract_pan(self, text: str) -> List[Entity]:
        """Extract PAN numbers from text"""
        entities = []
        for pattern in self.pan_patterns:
            for match in pattern.finditer(text):
                pan = match.group(0)
                if self._validate_pan(pan):
                    entities.append(Entity(
                        text=pan,
                        entity_type=EntityType.PAN,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.9
                    ))
        return entities
    
    def extract_gstin(self, text: str) -> List[Entity]:
        """Extract GSTIN from text"""
        entities = []
        for pattern in self.gstin_patterns:
            for match in pattern.finditer(text):
                gstin = match.group(0)
                if self._validate_gstin(gstin):
                    entities.append(Entity(
                        text=gstin,
                        entity_type=EntityType.GSTIN,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.9
                    ))
        return entities
    
    def extract_prices(self, text: str) -> List[Entity]:
        """Extract prices from text"""
        entities = []
        for pattern in self.price_patterns:
            for match in pattern.finditer(text):
                price = match.group(0)
                entities.append(Entity(
                    text=price,
                    entity_type=EntityType.PRICE,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                    metadata={'currency': 'INR'}
                ))
        return entities
    
    def extract_quantities(self, text: str) -> List[Entity]:
        """Extract quantities with units from text"""
        entities = []
        for pattern in self.quantity_patterns:
            for match in pattern.finditer(text):
                quantity = match.group(1)
                unit = match.group(2)
                
                # Extract quantity value
                quantity_value = self._parse_quantity(quantity)
                
                entities.append(Entity(
                    text=f"{quantity} {unit}",
                    entity_type=EntityType.QUANTITY,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9,
                    metadata={
                        'value': quantity_value,
                        'unit': unit.lower(),
                        'raw_quantity': quantity
                    }
                ))
        return entities
    
    def extract_products(self, text: str) -> List[Entity]:
        """Extract product names from text"""
        entities = []
        text_lower = text.lower()
        words = text_lower.split()
        
        # Check for exact product matches
        for i, word in enumerate(words):
            if word in self.product_index:
                product_info = self.product_index[word]
                # Find the actual text position
                start_pos = text_lower.find(word)
                if start_pos != -1:
                    entities.append(Entity(
                        text=text[start_pos:start_pos + len(word)],
                        entity_type=EntityType.PRODUCT,
                        start=start_pos,
                        end=start_pos + len(word),
                        confidence=product_info['confidence'],
                        metadata={
                            'category': product_info['category'],
                            'original_name': product_info['name']
                        }
                    ))
        
        # Check for multi-word products
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if bigram in self.product_index:
                product_info = self.product_index[bigram]
                start_pos = text_lower.find(bigram)
                if start_pos != -1:
                    entities.append(Entity(
                        text=text[start_pos:start_pos + len(bigram)],
                        entity_type=EntityType.PRODUCT,
                        start=start_pos,
                        end=start_pos + len(bigram),
                        confidence=product_info['confidence'],
                        metadata={
                            'category': product_info['category'],
                            'original_name': product_info['name']
                        }
                    ))
        
        return entities
    
    def extract_brands(self, text: str) -> List[Entity]:
        """Extract brand names from text"""
        entities = []
        text_lower = text.lower()
        words = text_lower.split()
        
        # Check for exact brand matches
        for word in words:
            if word in self.brand_index:
                brand_info = self.brand_index[word]
                start_pos = text_lower.find(word)
                if start_pos != -1:
                    entities.append(Entity(
                        text=text[start_pos:start_pos + len(word)],
                        entity_type=EntityType.BRAND,
                        start=start_pos,
                        end=start_pos + len(word),
                        confidence=brand_info['confidence'],
                        metadata={
                            'category': brand_info['category'],
                            'original_name': brand_info['name']
                        }
                    ))
        
        # Check for multi-word brands
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if bigram in self.brand_index:
                brand_info = self.brand_index[bigram]
                start_pos = text_lower.find(bigram)
                if start_pos != -1:
                    entities.append(Entity(
                        text=text[start_pos:start_pos + len(bigram)],
                        entity_type=EntityType.BRAND,
                        start=start_pos,
                        end=start_pos + len(bigram),
                        confidence=brand_info['confidence'],
                        metadata={
                            'category': brand_info['category'],
                            'original_name': brand_info['name']
                        }
                    ))
        
        return entities
    
    def extract_names(self, text: str) -> List[Entity]:
        """Extract person names from text"""
        entities = []
        text_lower = text.lower()
        words = text_lower.split()
        
        # Check for name patterns
        for word in words:
            if word in self.name_index:
                name_info = self.name_index[word]
                start_pos = text_lower.find(word)
                if start_pos != -1:
                    entities.append(Entity(
                        text=text[start_pos:start_pos + len(word)],
                        entity_type=EntityType.PERSON_NAME,
                        start=start_pos,
                        end=start_pos + len(word),
                        confidence=name_info['confidence'],
                        metadata={
                            'gender': name_info['gender'],
                            'original_name': name_info['name']
                        }
                    ))
        
        return entities
    
    def extract_locations(self, text: str) -> List[Entity]:
        """Extract location names from text"""
        entities = []
        text_lower = text.lower()
        words = text_lower.split()
        
        # Check for location patterns
        for word in words:
            if word in self.location_index:
                location_info = self.location_index[word]
                start_pos = text_lower.find(word)
                if start_pos != -1:
                    entities.append(Entity(
                        text=text[start_pos:start_pos + len(word)],
                        entity_type=EntityType.LOCATION,
                        start=start_pos,
                        end=start_pos + len(word),
                        confidence=location_info['confidence'],
                        metadata={
                            'type': location_info['type'],
                            'original_name': location_info['name']
                        }
                    ))
        
        return entities
    
    def extract_emails(self, text: str) -> List[Entity]:
        """Extract email addresses from text"""
        entities = []
        for pattern in self.email_patterns:
            for match in pattern.finditer(text):
                email = match.group(0)
                entities.append(Entity(
                    text=email,
                    entity_type=EntityType.EMAIL,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95
                ))
        return entities
    
    def extract_websites(self, text: str) -> List[Entity]:
        """Extract website URLs from text"""
        entities = []
        for pattern in self.website_patterns:
            for match in pattern.finditer(text):
                website = match.group(0)
                entities.append(Entity(
                    text=website,
                    entity_type=EntityType.WEBSITE,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9
                ))
        return entities
    
    def extract_dates(self, text: str) -> List[Entity]:
        """Extract dates from text"""
        entities = []
        for pattern in self.date_patterns:
            for match in pattern.finditer(text):
                date = match.group(0)
                entities.append(Entity(
                    text=date,
                    entity_type=EntityType.DATE,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.85
                ))
        return entities
    
    def extract_times(self, text: str) -> List[Entity]:
        """Extract times from text"""
        entities = []
        for pattern in self.time_patterns:
            for match in pattern.finditer(text):
                time = match.group(0)
                entities.append(Entity(
                    text=time,
                    entity_type=EntityType.TIME,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.85
                ))
        return entities
    
    def extract_addresses(self, text: str) -> List[Entity]:
        """Extract addresses from text"""
        entities = []
        for pattern in self.address_patterns:
            for match in pattern.finditer(text):
                address = match.group(0)
                entities.append(Entity(
                    text=address,
                    entity_type=EntityType.ADDRESS,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.7
                ))
        return entities
    
    def analyze(self, text: str) -> NERResult:
        """
        Perform complete NER analysis on text
        Returns: NERResult with all extracted entities
        """
        import time
        start_time = time.time()
        
        # Detect language
        language = self.detect_language(text)
        
        # Extract all entity types
        all_entities = []
        
        # Extract structured entities
        all_entities.extend(self.extract_phone_numbers(text))
        all_entities.extend(self.extract_aadhaar(text))
        all_entities.extend(self.extract_pan(text))
        all_entities.extend(self.extract_gstin(text))
        all_entities.extend(self.extract_prices(text))
        all_entities.extend(self.extract_quantities(text))
        all_entities.extend(self.extract_emails(text))
        all_entities.extend(self.extract_websites(text))
        all_entities.extend(self.extract_dates(text))
        all_entities.extend(self.extract_times(text))
        all_entities.extend(self.extract_addresses(text))
        
        # Extract named entities
        all_entities.extend(self.extract_products(text))
        all_entities.extend(self.extract_brands(text))
        all_entities.extend(self.extract_names(text))
        all_entities.extend(self.extract_locations(text))
        
        # Remove overlapping entities (keep highest confidence)
        all_entities = self._remove_overlapping_entities(all_entities)
        
        # Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(all_entities)
        
        processing_time = time.time() - start_time
        
        return NERResult(
            entities=all_entities,
            text=text,
            language=language,
            confidence=overall_confidence,
            processing_time=processing_time
        )
    
    def _validate_phone_number(self, phone: str) -> bool:
        """Validate Indian phone number"""
        # Remove spaces, dashes, and +91
        clean_phone = re.sub(r'[\s\-+]', '', phone)
        if clean_phone.startswith('91'):
            clean_phone = clean_phone[2:]
        
        # Check if it's a valid Indian mobile number
        if len(clean_phone) == 10 and clean_phone[0] in ['6', '7', '8', '9']:
            return True
        return False
    
    def _validate_aadhaar(self, aadhaar: str) -> bool:
        """Basic Aadhaar validation"""
        clean_aadhaar = re.sub(r'[\s\-]', '', aadhaar)
        return len(clean_aadhaar) == 12 and clean_aadhaar.isdigit()
    
    def _validate_pan(self, pan: str) -> bool:
        """Basic PAN validation"""
        clean_pan = re.sub(r'[\s\-]', '', pan.upper())
        if len(clean_pan) != 10:
            return False
        # Check format: 5 letters + 4 digits + 1 letter
        return bool(re.match(r'^[A-Z]{5}\d{4}[A-Z]$', clean_pan))
    
    def _validate_gstin(self, gstin: str) -> bool:
        """Basic GSTIN validation"""
        clean_gstin = re.sub(r'[\s\-]', '', gstin.upper())
        if len(clean_gstin) != 15:
            return False
        # Check format: 2 digits + 10 characters + 1 digit + 1 Z + 1 character
        return bool(re.match(r'^\d{2}[A-Z0-9]{10}\d[Z][A-Z0-9]$', clean_gstin))
    
    def _parse_quantity(self, quantity_str: str) -> float:
        """Parse quantity string to float"""
        try:
            # Remove commas and convert to float
            clean_quantity = re.sub(r'[,]', '', quantity_str)
            return float(clean_quantity)
        except ValueError:
            return 0.0
    
    def _remove_overlapping_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove overlapping entities, keeping highest confidence ones"""
        if not entities:
            return entities
        
        # Sort by confidence (highest first)
        sorted_entities = sorted(entities, key=lambda x: x.confidence, reverse=True)
        
        filtered_entities = []
        for entity in sorted_entities:
            # Check if this entity overlaps with any already accepted entity
            overlaps = False
            for accepted_entity in filtered_entities:
                if self._entities_overlap(entity, accepted_entity):
                    overlaps = True
                    break
            
            if not overlaps:
                filtered_entities.append(entity)
        
        return filtered_entities
    
    def _entities_overlap(self, entity1: Entity, entity2: Entity) -> bool:
        """Check if two entities overlap"""
        return not (entity1.end <= entity2.start or entity2.end <= entity1.start)
    
    def _calculate_overall_confidence(self, entities: List[Entity]) -> float:
        """Calculate overall confidence score"""
        if not entities:
            return 0.0
        
        total_confidence = sum(entity.confidence for entity in entities)
        return total_confidence / len(entities)
    
    def to_dict(self, result: NERResult) -> Dict[str, Any]:
        """Convert NER result to dictionary"""
        return {
            'text': result.text,
            'language': result.language,
            'confidence': result.confidence,
            'processing_time': result.processing_time,
            'entities': [
                {
                    'text': entity.text,
                    'type': entity.entity_type.value,
                    'start': entity.start,
                    'end': entity.end,
                    'confidence': entity.confidence,
                    'metadata': entity.metadata
                }
                for entity in result.entities
            ]
        }
    
    def to_json(self, result: NERResult) -> str:
        """Convert NER result to JSON string"""
        return json.dumps(self.to_dict(result), indent=2, ensure_ascii=False)

# Global instance for easy access
indian_ner = IndianNER()
