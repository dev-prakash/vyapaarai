"""
Test cases extracted from kirana-voice-enterprise project
Comprehensive validation of VyaparAI NER implementation against kirana examples
"""

import unittest
import sys
import os
from typing import Dict, List, Any

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from nlp.indian_ner import IndianNER, EntityType, Entity, NERResult
from nlp.kirana_patterns import INTENT_PATTERNS, INDIAN_PRODUCTS, BRAND_NAMES

class TestIndianNERAgainstKiranaExamples(unittest.TestCase):
    """Test Indian NER implementation against kirana examples"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.ner = IndianNER()
        
    def test_language_detection(self):
        """Test language detection with kirana examples"""
        test_cases = [
            # English examples
            ("Hello! How are you?", "en"),
            ("How is the weather today?", "en"),
            ("Did you watch the cricket match?", "en"),
            ("Tell me a joke", "en"),
            ("What do you think about politics?", "en"),
            
            # Hindi examples
            ("नमस्ते! कैसे हो?", "hi"),
            ("मौसम कैसा है?", "hi"),
            ("क्रिकेट मैच देखा?", "hi"),
            ("जोक सुनाओ", "hi"),
            ("राजनीति क्या है?", "hi"),
            
            # Hinglish examples
            ("Hello! कैसे हो?", "hinglish"),
            ("Weather कैसा है?", "hinglish"),
            ("Cricket match देखा?", "hinglish"),
            ("Joke sunao", "hinglish"),
            ("Politics kya hai?", "hinglish"),
        ]
        
        for text, expected_lang in test_cases:
            with self.subTest(text=text):
                detected_lang = self.ner.detect_language(text)
                self.assertEqual(detected_lang, expected_lang, 
                               f"Expected {expected_lang} for '{text}', got {detected_lang}")
    
    def test_intent_patterns_extraction(self):
        """Test extraction of intent patterns from kirana"""
        test_cases = [
            # Greeting intent
            ("Hello! How are you?", "greeting"),
            ("नमस्ते! कैसे हो?", "greeting"),
            ("Hi ji", "greeting"),
            
            # Weather intent
            ("How is the weather today?", "weather"),
            ("मौसम कैसा है?", "weather"),
            ("Weather kaisa hai?", "weather"),
            
            # Cricket intent
            ("Did you watch the cricket match?", "cricket"),
            ("क्रिकेट मैच देखा?", "cricket"),
            ("India vs Pakistan match kab hai?", "cricket"),
            
            # Jokes intent
            ("Tell me a joke", "jokes"),
            ("जोक सुनाओ", "jokes"),
            ("Joke sunao", "jokes"),
            
            # Registration intent
            ("I want to register my store", "registration"),
            ("मैं अपनी दुकान का रजिस्ट्रेशन करना चाहता हूं", "registration"),
            ("Store register karna hai", "registration"),
        ]
        
        for text, expected_intent in test_cases:
            with self.subTest(text=text):
                # Check if any pattern from the expected intent matches
                patterns = INTENT_PATTERNS.get(expected_intent, [])
                text_lower = text.lower()
                pattern_found = any(pattern in text_lower for pattern in patterns)
                self.assertTrue(pattern_found, 
                              f"No pattern found for intent '{expected_intent}' in text '{text}'")
    
    def test_product_extraction(self):
        """Test product name extraction from kirana patterns"""
        test_cases = [
            # Grains
            ("I need 2 kg rice", [("rice", "grains")]),
            ("चावल 5 किलो चाहिए", [("चावल", "grains")]),
            ("Wheat flour 1 kg", [("wheat", "grains")]),
            
            # Vegetables
            ("Potato 2 kg", [("potato", "vegetables")]),
            ("टमाटर 1 किलो", [("टमाटर", "vegetables")]),
            ("Onion 500 gram", [("onion", "vegetables")]),
            
            # Fruits
            ("Apple 6 pieces", [("apple", "fruits")]),
            ("केला 1 दर्जन", [("केला", "fruits")]),
            ("Mango 2 kg", [("mango", "fruits")]),
            
            # Dairy
            ("Milk 1 liter", [("milk", "dairy")]),
            ("दूध 2 लीटर", [("दूध", "dairy")]),
            ("Curd 500 gram", [("curd", "dairy")]),
            
            # Spices
            ("Salt 1 kg", [("salt", "spices")]),
            ("नमक 500 ग्राम", [("नमक", "spices")]),
            ("Turmeric powder", [("turmeric", "spices")]),
        ]
        
        for text, expected_products in test_cases:
            with self.subTest(text=text):
                result = self.ner.analyze(text)
                product_entities = [e for e in result.entities if e.entity_type == EntityType.PRODUCT]
                
                # Check if expected products are found
                for expected_product, expected_category in expected_products:
                    found = any(
                        e.text.lower() == expected_product.lower() and 
                        e.metadata.get('category') == expected_category
                        for e in product_entities
                    )
                    self.assertTrue(found, 
                                  f"Product '{expected_product}' (category: {expected_category}) not found in '{text}'")
    
    def test_brand_extraction(self):
        """Test brand name extraction from kirana patterns"""
        test_cases = [
            # Beverages
            ("Coca Cola 2 bottles", [("coca cola", "beverages")]),
            ("Pepsi 1 liter", [("pepsi", "beverages")]),
            ("Amul milk", [("amul", "dairy")]),
            
            # Snacks
            ("Lays chips 2 packs", [("lays", "snacks")]),
            ("Kurkure 1 packet", [("kurkure", "snacks")]),
            ("Haldirams namkeen", [("haldirams", "snacks")]),
            
            # Biscuits
            ("Parle G 1 pack", [("parle g", "biscuits")]),
            ("Britannia biscuits", [("britannia", "biscuits")]),
            ("Oreo cookies", [("oreo", "biscuits")]),
            
            # Personal care
            ("Colgate toothpaste", [("colgate", "personal_care")]),
            ("Dabur honey", [("dabur", "personal_care")]),
            ("Himalaya face wash", [("himalaya", "personal_care")]),
        ]
        
        for text, expected_brands in test_cases:
            with self.subTest(text=text):
                result = self.ner.analyze(text)
                brand_entities = [e for e in result.entities if e.entity_type == EntityType.BRAND]
                
                # Check if expected brands are found
                for expected_brand, expected_category in expected_brands:
                    found = any(
                        e.text.lower() == expected_brand.lower() and 
                        e.metadata.get('category') == expected_category
                        for e in brand_entities
                    )
                    self.assertTrue(found, 
                                  f"Brand '{expected_brand}' (category: {expected_category}) not found in '{text}'")
    
    def test_quantity_extraction(self):
        """Test quantity and unit extraction"""
        test_cases = [
            # Weight units
            ("2 kg rice", [("2", "kg")]),
            ("500 gram sugar", [("500", "gram")]),
            ("1 kilo atta", [("1", "kilo")]),
            ("5 ton wheat", [("5", "ton")]),
            
            # Volume units
            ("1 liter milk", [("1", "liter")]),
            ("500 ml oil", [("500", "ml")]),
            ("2 bottles water", [("2", "bottles")]),
            
            # Count units
            ("6 pieces apple", [("6", "pieces")]),
            ("1 dozen banana", [("1", "dozen")]),
            ("2 packs biscuits", [("2", "packs")]),
            ("5 packets chips", [("5", "packets")]),
        ]
        
        for text, expected_quantities in test_cases:
            with self.subTest(text=text):
                result = self.ner.analyze(text)
                quantity_entities = [e for e in result.entities if e.entity_type == EntityType.QUANTITY]
                
                # Check if expected quantities are found
                for expected_value, expected_unit in expected_quantities:
                    found = any(
                        e.metadata.get('value') == float(expected_value) and 
                        e.metadata.get('unit') == expected_unit.lower()
                        for e in quantity_entities
                    )
                    self.assertTrue(found, 
                                  f"Quantity '{expected_value} {expected_unit}' not found in '{text}'")
    
    def test_phone_number_extraction(self):
        """Test phone number extraction with Indian formats"""
        test_cases = [
            # Valid Indian numbers
            ("Call me at 9876543210", ["9876543210"]),
            ("My number is +91 9876543210", ["+91 9876543210"]),
            ("Contact: +91-987-654-3210", ["+91-987-654-3210"]),
            ("Phone: 987 654 3210", ["987 654 3210"]),
            
            # Invalid numbers (should not be extracted)
            ("Call me at 1234567890", []),  # Invalid starting digit
            ("My number is 987654321", []),  # Too short
            ("Contact: 98765432101", []),  # Too long
        ]
        
        for text, expected_numbers in test_cases:
            with self.subTest(text=text):
                result = self.ner.analyze(text)
                phone_entities = [e for e in result.entities if e.entity_type == EntityType.PHONE_NUMBER]
                
                extracted_numbers = [e.text for e in phone_entities]
                self.assertEqual(extracted_numbers, expected_numbers,
                               f"Expected {expected_numbers}, got {extracted_numbers} for '{text}'")
    
    def test_aadhaar_extraction(self):
        """Test Aadhaar number extraction"""
        test_cases = [
            # Valid Aadhaar formats
            ("My Aadhaar is 123456789012", ["123456789012"]),
            ("Aadhaar: 1234 5678 9012", ["1234 5678 9012"]),
            ("Number: 1234-5678-9012", ["1234-5678-9012"]),
            
            # Invalid Aadhaar (should not be extracted)
            ("My Aadhaar is 12345678901", []),  # Too short
            ("Aadhaar: 1234567890123", []),  # Too long
            ("Number: 12345678901A", []),  # Contains letters
        ]
        
        for text, expected_numbers in test_cases:
            with self.subTest(text=text):
                result = self.ner.analyze(text)
                aadhaar_entities = [e for e in result.entities if e.entity_type == EntityType.AADHAAR]
                
                extracted_numbers = [e.text for e in aadhaar_entities]
                self.assertEqual(extracted_numbers, expected_numbers,
                               f"Expected {expected_numbers}, got {extracted_numbers} for '{text}'")
    
    def test_pan_extraction(self):
        """Test PAN number extraction"""
        test_cases = [
            # Valid PAN formats
            ("My PAN is ABCDE1234F", ["ABCDE1234F"]),
            ("PAN: ABCDE 1234 F", ["ABCDE 1234 F"]),
            ("Number: ABCDE-1234-F", ["ABCDE-1234-F"]),
            
            # Invalid PAN (should not be extracted)
            ("My PAN is ABCDE1234", []),  # Too short
            ("PAN: ABCDE12345F", []),  # Too long
            ("Number: ABCDE1234G", []),  # Wrong format
        ]
        
        for text, expected_numbers in test_cases:
            with self.subTest(text=text):
                result = self.ner.analyze(text)
                pan_entities = [e for e in result.entities if e.entity_type == EntityType.PAN]
                
                extracted_numbers = [e.text for e in pan_entities]
                self.assertEqual(extracted_numbers, expected_numbers,
                               f"Expected {expected_numbers}, got {extracted_numbers} for '{text}'")
    
    def test_price_extraction(self):
        """Test price extraction with Indian currency formats"""
        test_cases = [
            # Valid price formats
            ("Price is ₹100", ["₹100"]),
            ("Cost: Rs. 1,234", ["Rs. 1,234"]),
            ("Amount: ₹1,234.56", ["₹1,234.56"]),
            ("Rupees 500", ["Rupees 500"]),
            ("Rs 2,000", ["Rs 2,000"]),
            
            # Invalid prices (should not be extracted)
            ("Price is $100", []),  # Wrong currency
            ("Cost: 100", []),  # No currency symbol
        ]
        
        for text, expected_prices in test_cases:
            with self.subTest(text=text):
                result = self.ner.analyze(text)
                price_entities = [e for e in result.entities if e.entity_type == EntityType.PRICE]
                
                extracted_prices = [e.text for e in price_entities]
                self.assertEqual(extracted_prices, expected_prices,
                               f"Expected {expected_prices}, got {extracted_prices} for '{text}'")
    
    def test_name_extraction(self):
        """Test Indian name extraction"""
        test_cases = [
            # Male names
            ("My name is Raj Kumar", [("raj", "male")]),
            ("I am Amit Singh", [("amit", "male")]),
            ("Call me Rahul", [("rahul", "male")]),
            
            # Female names
            ("My name is Priya", [("priya", "female")]),
            ("I am Neha", [("neha", "female")]),
            ("Call me Puja", [("puja", "female")]),
        ]
        
        for text, expected_names in test_cases:
            with self.subTest(text=text):
                result = self.ner.analyze(text)
                name_entities = [e for e in result.entities if e.entity_type == EntityType.PERSON_NAME]
                
                # Check if expected names are found
                for expected_name, expected_gender in expected_names:
                    found = any(
                        e.text.lower() == expected_name.lower() and 
                        e.metadata.get('gender') == expected_gender
                        for e in name_entities
                    )
                    self.assertTrue(found, 
                                  f"Name '{expected_name}' (gender: {expected_gender}) not found in '{text}'")
    
    def test_location_extraction(self):
        """Test location extraction"""
        test_cases = [
            # Major cities
            ("I live in Mumbai", [("mumbai", "major_cities")]),
            ("Store in Delhi", [("delhi", "major_cities")]),
            ("Office in Bangalore", [("bangalore", "major_cities")]),
            
            # States
            ("I am from Maharashtra", [("maharashtra", "states")]),
            ("Born in Karnataka", [("karnataka", "states")]),
            ("Living in Gujarat", [("gujarat", "states")]),
        ]
        
        for text, expected_locations in test_cases:
            with self.subTest(text=text):
                result = self.ner.analyze(text)
                location_entities = [e for e in result.entities if e.entity_type == EntityType.LOCATION]
                
                # Check if expected locations are found
                for expected_location, expected_type in expected_locations:
                    found = any(
                        e.text.lower() == expected_location.lower() and 
                        e.metadata.get('type') == expected_type
                        for e in location_entities
                    )
                    self.assertTrue(found, 
                                  f"Location '{expected_location}' (type: {expected_type}) not found in '{text}'")
    
    def test_complex_registration_scenarios(self):
        """Test complex registration scenarios from kirana examples"""
        test_cases = [
            # Complete registration in English
            {
                "text": "I am Raj Kumar, phone 9876543210, store name ABC Store, address 123 Main Street Mumbai Maharashtra 400001",
                "expected_entities": {
                    "person_name": ["raj", "kumar"],
                    "phone_number": ["9876543210"],
                    "location": ["mumbai", "maharashtra"],
                }
            },
            
            # Complete registration in Hindi
            {
                "text": "मेरा नाम राज कुमार है, फोन 9876543210, दुकान का नाम ABC स्टोर, पता 123 मेन स्ट्रीट मुंबई महाराष्ट्र 400001",
                "expected_entities": {
                    "person_name": ["raj", "kumar"],
                    "phone_number": ["9876543210"],
                    "location": ["mumbai", "maharashtra"],
                }
            },
            
            # Mixed language registration
            {
                "text": "I am Raj Kumar, मेरा फोन नंबर 9876543210 है, store name ABC Store, Aadhaar 123456789012, address Mumbai Maharashtra",
                "expected_entities": {
                    "person_name": ["raj", "kumar"],
                    "phone_number": ["9876543210"],
                    "aadhaar": ["123456789012"],
                    "location": ["mumbai", "maharashtra"],
                }
            },
        ]
        
        for test_case in test_cases:
            with self.subTest(text=test_case["text"]):
                result = self.ner.analyze(text=test_case["text"])
                
                # Check each expected entity type
                for entity_type, expected_values in test_case["expected_entities"].items():
                    if entity_type == "person_name":
                        entities = [e for e in result.entities if e.entity_type == EntityType.PERSON_NAME]
                        extracted_values = [e.text.lower() for e in entities]
                    elif entity_type == "phone_number":
                        entities = [e for e in result.entities if e.entity_type == EntityType.PHONE_NUMBER]
                        extracted_values = [e.text for e in entities]
                    elif entity_type == "aadhaar":
                        entities = [e for e in result.entities if e.entity_type == EntityType.AADHAAR]
                        extracted_values = [e.text for e in entities]
                    elif entity_type == "location":
                        entities = [e for e in result.entities if e.entity_type == EntityType.LOCATION]
                        extracted_values = [e.text.lower() for e in entities]
                    else:
                        continue
                    
                    # Check if all expected values are found
                    for expected_value in expected_values:
                        self.assertIn(expected_value, extracted_values,
                                    f"Expected {entity_type} '{expected_value}' not found in '{test_case['text']}'")
    
    def test_performance_benchmark(self):
        """Test performance against kirana examples"""
        test_texts = [
            "Hello! How are you?",
            "मौसम कैसा है?",
            "Cricket match देखा?",
            "I want to register my store",
            "मैं अपनी दुकान का रजिस्ट्रेशन करना चाहता हूं",
            "I am Raj Kumar, phone 9876543210, store name ABC Store, address 123 Main Street Mumbai Maharashtra 400001",
            "My Aadhaar is 123456789012, PAN is ABCDE1234F, GSTIN is 27ABCDE1234F1Z5",
        ]
        
        for text in test_texts:
            with self.subTest(text=text):
                result = self.ner.analyze(text)
                
                # Performance assertions
                self.assertLess(result.processing_time, 0.1,  # Should process in < 100ms
                               f"Processing time {result.processing_time}s exceeds 100ms for text: {text}")
                
                # Quality assertions
                self.assertGreater(result.confidence, 0.0,
                                 f"Confidence should be > 0 for text: {text}")
                
                # Language detection should work
                self.assertIn(result.language, ['en', 'hi', 'hinglish', 'unknown'],
                             f"Invalid language detected: {result.language} for text: {text}")
    
    def test_kirana_compatibility(self):
        """Test compatibility with kirana patterns and examples"""
        # Test all 22 intent patterns from kirana
        for intent_name, patterns in INTENT_PATTERNS.items():
            with self.subTest(intent=intent_name):
                # Test a few patterns from each intent
                test_patterns = patterns[:3]  # Test first 3 patterns
                for pattern in test_patterns:
                    result = self.ner.analyze(pattern)
                    
                    # Should detect language
                    self.assertIsNotNone(result.language)
                    
                    # Should have reasonable confidence
                    self.assertGreaterEqual(result.confidence, 0.0)
                    
                    # Should process quickly
                    self.assertLess(result.processing_time, 0.05)  # < 50ms for simple patterns

if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
