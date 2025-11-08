"""
Indian Commerce NER (Named Entity Recognition) Implementation
High-performance entity extraction for Indian grocery orders
Uses patterns from extracted_patterns.py for product, quantity, unit, and brand detection
"""

import re
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict

from .extracted_patterns import (
    PRODUCT_DATABASE, UNITS_MAPPING, NUMBER_WORDS, 
    BRAND_DATABASE, VALIDATION_RULES
)

@dataclass
class Entity:
    """Named entity with metadata for Indian commerce"""
    product: str
    quantity: float
    unit: str
    brand: Optional[str] = None
    confidence: float = 0.0
    original_text: str = ""
    start_pos: int = 0
    end_pos: int = 0

class IndianCommerceNER:
    """
    High-performance NER for Indian grocery orders
    Handles Hindi/English/Hinglish text with product, quantity, unit, and brand extraction
    """
    
    def __init__(self):
        """Initialize NER with pre-compiled patterns and lookup tables"""
        self._build_lookup_tables()
        self._compile_regex_patterns()
        self._build_product_variations()
        self._build_brand_variations()
        
    def _build_lookup_tables(self):
        """Build fast lookup tables for O(1) access"""
        # Product lookup by variation
        self.product_lookup = {}
        for product_name, product_data in PRODUCT_DATABASE.items():
            for variation in product_data.get("variations", []):
                self.product_lookup[variation.lower()] = {
                    "name": product_name,
                    "data": product_data
                }
        
        # Brand lookup by variation
        self.brand_lookup = {}
        for product_category, brands in BRAND_DATABASE.items():
            for brand in brands:
                self.brand_lookup[brand.lower()] = {
                    "name": brand,
                    "category": product_category
                }
        
        # Unit lookup by variation
        self.unit_lookup = {}
        for unit_type, units in UNITS_MAPPING.items():
            for unit_name, variations in units.items():
                for variation in variations:
                    self.unit_lookup[variation.lower()] = {
                        "standard": unit_name,
                        "type": unit_type
                    }
        
        # Number word lookup
        self.number_lookup = {}
        for language, numbers in NUMBER_WORDS.items():
            for word, value in numbers.items():
                self.number_lookup[word.lower()] = value
        
        # Delimiters for text segmentation
        self.delimiters = {
            "comma": [",", "،", "،"],
            "connectors": ["aur", "and", "और", "तथा", "एवं"],
            "separators": ["aur", "and", "और", ",", "।", "|", ";"]
        }
    
    def _compile_regex_patterns(self):
        """Pre-compile regex patterns for performance"""
        # Number patterns (digits, decimals, fractions)
        self.number_patterns = [
            re.compile(r'\b(\d+(?:\.\d+)?)\b'),  # 1, 1.5, 10.25
            re.compile(r'\b(\d+)/(\d+)\b'),  # 1/2, 3/4
        ]
        
        # Quantity patterns with units
        self.quantity_patterns = [
            re.compile(r'\b(\d+(?:\.\d+)?)\s*([a-zA-Z\u0900-\u097F]+)\b'),  # 2 kg, 1.5 litre
            re.compile(r'\b([a-zA-Z\u0900-\u097F]+)\s+(\d+(?:\.\d+)?)\b'),  # kg 2, litre 1.5
        ]
        
        # Product patterns
        self.product_patterns = [
            re.compile(r'\b([a-zA-Z\u0900-\u097F]+(?:\s+[a-zA-Z\u0900-\u097F]+)*)\b'),
        ]
        
        # Brand patterns
        self.brand_patterns = [
            re.compile(r'\b([A-Z][a-zA-Z\u0900-\u097F]+(?:\s+[A-Z][a-zA-Z\u0900-\u097F]+)*)\b'),
        ]
        
        # Common Indian grocery patterns
        self.indian_patterns = [
            re.compile(r'\b(ek|do|teen|char|paanch|cheh|saat|aath|nau|das)\b', re.IGNORECASE),
            re.compile(r'\b(एक|दो|तीन|चार|पांच|छह|सात|आठ|नौ|दस)\b'),
            re.compile(r'\b(adha|aadha|dedh|dhai|saade)\b', re.IGNORECASE),
            re.compile(r'\b(आधा|डेढ़|ढाई|साढ़े)\b'),
        ]
    
    def _build_product_variations(self):
        """Build comprehensive product variation mappings"""
        self.product_variations = {}
        for product_name, product_data in PRODUCT_DATABASE.items():
            variations = set()
            # Add main variations
            variations.update(product_data.get("variations", []))
            # Add types if available
            variations.update(product_data.get("types", []))
            # Add category as variation
            variations.add(product_data.get("category", ""))
            
            for variation in variations:
                if variation:
                    self.product_variations[variation.lower()] = product_name
    
    def _build_brand_variations(self):
        """Build comprehensive brand variation mappings"""
        self.brand_variations = {}
        for product_category, brands in BRAND_DATABASE.items():
            for brand in brands:
                # Add brand name
                self.brand_variations[brand.lower()] = {
                    "brand": brand,
                    "category": product_category
                }
                # Add brand without spaces
                self.brand_variations[brand.lower().replace(" ", "")] = {
                    "brand": brand,
                    "category": product_category
                }
    
    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract entities from Indian grocery order text
        
        Args:
            text: Input text in Hindi/English/Hinglish
            
        Returns:
            List of dictionaries with keys: product, quantity, unit, brand, confidence
        """
        if not text or not text.strip():
            return []
        
        # Normalize text
        normalized_text = self._normalize_text(text)
        
        # Segment text by delimiters
        segments = self._segment_text(normalized_text)
        
        entities = []
        for segment in segments:
            segment_entities = self._extract_entities_from_segment(segment)
            entities.extend(segment_entities)
        
        # Remove duplicates and merge similar entities
        entities = self._deduplicate_entities(entities)
        
        # Convert to dictionary format
        return [self._entity_to_dict(entity) for entity in entities]
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for better processing"""
        # Convert to lowercase
        text = text.lower()
        
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove extra punctuation
        text = re.sub(r'[^\w\s\u0900-\u097F,।|;]', ' ', text)
        
        return text.strip()
    
    def _segment_text(self, text: str) -> List[str]:
        """Segment text by common delimiters"""
        # Split by connectors first
        for connector in self.delimiters["connectors"]:
            if connector in text:
                segments = text.split(connector)
                return [seg.strip() for seg in segments if seg.strip()]
        
        # Split by comma
        if "," in text:
            segments = text.split(",")
            return [seg.strip() for seg in segments if seg.strip()]
        
        # Return as single segment
        return [text] if text else []
    
    def _extract_entities_from_segment(self, segment: str) -> List[Entity]:
        """Extract entities from a single text segment"""
        entities = []
        
        # Extract quantity and unit patterns
        quantity_entities = self._extract_quantity_entities(segment)
        entities.extend(quantity_entities)
        
        # Extract product entities
        product_entities = self._extract_product_entities(segment)
        entities.extend(product_entities)
        
        # Extract brand entities
        brand_entities = self._extract_brand_entities(segment)
        entities.extend(brand_entities)
        
        # Merge related entities
        merged_entities = self._merge_related_entities(entities, segment)
        
        return merged_entities
    
    def _extract_quantity_entities(self, segment: str) -> List[Entity]:
        """Extract quantity and unit entities"""
        entities = []
        
        # Pattern 1: "2 kg", "1.5 litre"
        for match in self.quantity_patterns[0].finditer(segment):
            quantity_str = match.group(1)
            unit_str = match.group(2)
            
            quantity = self._parse_quantity(quantity_str)
            unit = self._normalize_unit(unit_str)
            
            if quantity > 0 and unit:
                entities.append(Entity(
                    product="",
                    quantity=quantity,
                    unit=unit,
                    confidence=0.9,
                    original_text=match.group(0),
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
        
        # Pattern 2: "kg 2", "litre 1.5"
        for match in self.quantity_patterns[1].finditer(segment):
            unit_str = match.group(1)
            quantity_str = match.group(2)
            
            quantity = self._parse_quantity(quantity_str)
            unit = self._normalize_unit(unit_str)
            
            if quantity > 0 and unit:
                entities.append(Entity(
                    product="",
                    quantity=quantity,
                    unit=unit,
                    confidence=0.8,
                    original_text=match.group(0),
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
        
        # Pattern 3: Number words
        for match in self.indian_patterns[0].finditer(segment):
            word = match.group(1).lower()
            if word in self.number_lookup:
                quantity = self.number_lookup[word]
                entities.append(Entity(
                    product="",
                    quantity=quantity,
                    unit="",
                    confidence=0.7,
                    original_text=match.group(0),
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
        
        # Pattern 4: Hindi number words
        for match in self.indian_patterns[1].finditer(segment):
            word = match.group(1)
            if word in self.number_lookup:
                quantity = self.number_lookup[word]
                entities.append(Entity(
                    product="",
                    quantity=quantity,
                    unit="",
                    confidence=0.7,
                    original_text=match.group(0),
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
        
        # Pattern 5: Fractions
        for match in self.indian_patterns[2].finditer(segment):
            word = match.group(1).lower()
            if word in self.number_lookup:
                quantity = self.number_lookup[word]
                entities.append(Entity(
                    product="",
                    quantity=quantity,
                    unit="",
                    confidence=0.8,
                    original_text=match.group(0),
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
        
        return entities
    
    def _extract_product_entities(self, segment: str) -> List[Entity]:
        """Extract product entities"""
        entities = []
        words = segment.split()
        
        # Check single words
        for i, word in enumerate(words):
            if word in self.product_variations:
                product_name = self.product_variations[word]
                product_data = PRODUCT_DATABASE[product_name]
                
                entities.append(Entity(
                    product=product_name,
                    quantity=0,
                    unit=product_data.get("default_unit", ""),
                    confidence=0.9,
                    original_text=word,
                    start_pos=segment.find(word),
                    end_pos=segment.find(word) + len(word)
                ))
        
        # Check bigrams
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if bigram in self.product_variations:
                product_name = self.product_variations[bigram]
                product_data = PRODUCT_DATABASE[product_name]
                
                entities.append(Entity(
                    product=product_name,
                    quantity=0,
                    unit=product_data.get("default_unit", ""),
                    confidence=0.95,
                    original_text=bigram,
                    start_pos=segment.find(bigram),
                    end_pos=segment.find(bigram) + len(bigram)
                ))
        
        # Check trigrams
        for i in range(len(words) - 2):
            trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
            if trigram in self.product_variations:
                product_name = self.product_variations[trigram]
                product_data = PRODUCT_DATABASE[product_name]
                
                entities.append(Entity(
                    product=product_name,
                    quantity=0,
                    unit=product_data.get("default_unit", ""),
                    confidence=0.98,
                    original_text=trigram,
                    start_pos=segment.find(trigram),
                    end_pos=segment.find(trigram) + len(trigram)
                ))
        
        return entities
    
    def _extract_brand_entities(self, segment: str) -> List[Entity]:
        """Extract brand entities"""
        entities = []
        words = segment.split()
        
        # Check single words
        for word in words:
            if word in self.brand_variations:
                brand_info = self.brand_variations[word]
                
                entities.append(Entity(
                    product="",
                    quantity=0,
                    unit="",
                    brand=brand_info["brand"],
                    confidence=0.8,
                    original_text=word,
                    start_pos=segment.find(word),
                    end_pos=segment.find(word) + len(word)
                ))
        
        # Check bigrams
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if bigram in self.brand_variations:
                brand_info = self.brand_variations[bigram]
                
                entities.append(Entity(
                    product="",
                    quantity=0,
                    unit="",
                    brand=brand_info["brand"],
                    confidence=0.9,
                    original_text=bigram,
                    start_pos=segment.find(bigram),
                    end_pos=segment.find(bigram) + len(bigram)
                ))
        
        return entities
    
    def _merge_related_entities(self, entities: List[Entity], segment: str) -> List[Entity]:
        """Merge related entities into complete product entries"""
        merged_entities = []
        
        # Group entities by position
        quantity_entities = [e for e in entities if e.quantity > 0]
        product_entities = [e for e in entities if e.product]
        brand_entities = [e for e in entities if e.brand]
        
        # Try to match products with quantities
        for product_entity in product_entities:
            best_quantity = None
            best_brand = None
            max_confidence = product_entity.confidence
            
            # Find closest quantity
            for quantity_entity in quantity_entities:
                if self._entities_are_related(product_entity, quantity_entity, segment):
                    if best_quantity is None or quantity_entity.confidence > best_quantity.confidence:
                        best_quantity = quantity_entity
            
            # Find closest brand
            for brand_entity in brand_entities:
                if self._entities_are_related(product_entity, brand_entity, segment):
                    if best_brand is None or brand_entity.confidence > best_brand.confidence:
                        best_brand = brand_entity
            
            # Create merged entity
            merged_entity = Entity(
                product=product_entity.product,
                quantity=best_quantity.quantity if best_quantity else 0,
                unit=best_quantity.unit if best_quantity else product_entity.unit,
                brand=best_brand.brand if best_brand else None,
                confidence=max_confidence,
                original_text=product_entity.original_text,
                start_pos=product_entity.start_pos,
                end_pos=product_entity.end_pos
            )
            
            merged_entities.append(merged_entity)
        
        # Handle standalone quantities (no product found)
        for quantity_entity in quantity_entities:
            if not any(self._entities_are_related(quantity_entity, pe, segment) for pe in product_entities):
                merged_entities.append(quantity_entity)
        
        return merged_entities
    
    def _entities_are_related(self, entity1: Entity, entity2: Entity, segment: str) -> bool:
        """Check if two entities are related (close in text)"""
        # Simple proximity check
        distance = abs(entity1.start_pos - entity2.start_pos)
        return distance <= 20  # Within 20 characters
    
    def _parse_quantity(self, quantity_str: str) -> float:
        """Parse quantity string to float"""
        try:
            # Handle fractions like "1/2"
            if "/" in quantity_str:
                parts = quantity_str.split("/")
                if len(parts) == 2:
                    return float(parts[0]) / float(parts[1])
            
            # Handle decimals
            return float(quantity_str)
        except (ValueError, ZeroDivisionError):
            return 0.0
    
    def _normalize_unit(self, unit_str: str) -> str:
        """Normalize unit to standard form"""
        unit_lower = unit_str.lower()
        if unit_lower in self.unit_lookup:
            return self.unit_lookup[unit_lower]["standard"]
        return unit_str
    
    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove duplicate entities, keeping highest confidence ones"""
        if not entities:
            return entities
        
        # Group by product
        grouped = defaultdict(list)
        for entity in entities:
            if entity.product:
                grouped[entity.product].append(entity)
            else:
                grouped["unknown"].append(entity)
        
        # Keep highest confidence entity from each group
        deduplicated = []
        for group_entities in grouped.values():
            if group_entities:
                best_entity = max(group_entities, key=lambda e: e.confidence)
                deduplicated.append(best_entity)
        
        return deduplicated
    
    def _entity_to_dict(self, entity: Entity) -> Dict[str, Any]:
        """Convert Entity to dictionary format"""
        return {
            "product": entity.product,
            "quantity": entity.quantity,
            "unit": entity.unit,
            "brand": entity.brand,
            "confidence": entity.confidence,
            "original_text": entity.original_text
        }

# Global instance for easy access
indian_commerce_ner = IndianCommerceNER()
