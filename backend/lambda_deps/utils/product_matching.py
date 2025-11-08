import difflib
import hashlib
import re
from typing import List, Dict, Any, Optional
from services.product_catalog_service import extract_region_from_store_data


def calculate_name_similarity(name1: str, name2: str) -> float:
    """Use difflib.SequenceMatcher to calculate similarity ratio"""
    if not name1 or not name2:
        return 0.0

    # Normalize names before comparison
    norm1 = normalize_product_name(name1)
    norm2 = normalize_product_name(name2)

    return difflib.SequenceMatcher(None, norm1, norm2).ratio()


def normalize_product_name(name: str) -> str:
    """Remove common variations and normalize for matching"""
    if not name:
        return ""

    # Convert to lowercase
    normalized = name.lower().strip()

    # Remove common weight variations
    normalized = re.sub(r"\b(kg|kgs|kilogram|kilograms)\b", "kg", normalized)
    normalized = re.sub(r"\b(gm|gms|gram|grams)\b", "g", normalized)
    normalized = re.sub(r"\b(ltr|ltrs|litre|litres|liter|liters)\b", "l", normalized)

    # Remove extra spaces and special characters
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def extract_barcodes_from_data(product_data: Dict[str, Any]) -> List[str]:
    """Handle both single barcode and list of barcodes"""
    barcodes: List[str] = []

    # Handle single barcode field
    if product_data.get("barcode"):
        barcodes.append(str(product_data["barcode"]))

    # Handle barcodes list
    if product_data.get("barcodes"):
        if isinstance(product_data["barcodes"], list):
            barcodes.extend([str(b) for b in product_data["barcodes"]])
        else:
            barcodes.append(str(product_data["barcodes"]))

    # Remove duplicates and validate
    valid_barcodes: List[str] = []
    for barcode in set(barcodes):
        if validate_barcode_format(barcode):
            valid_barcodes.append(barcode)

    return valid_barcodes


def validate_barcode_format(barcode: str) -> bool:
    """Validate barcode format (EAN-13, UPC, etc.)"""
    if not barcode:
        return False

    # Remove any non-numeric characters
    clean_barcode = re.sub(r"\D", "", str(barcode))

    # Check common barcode lengths
    valid_lengths = [8, 12, 13, 14]  # EAN-8, UPC-A, EAN-13, ITF-14

    return len(clean_barcode) in valid_lengths


def generate_image_hash(image_data: bytes) -> str | None:
    """Generate SHA-256 hash of image data"""
    if not image_data:
        return None

    return hashlib.sha256(image_data).hexdigest()


def fuzzy_match_products(
    candidate_product: Dict[str, Any],
    existing_products: List[Dict[str, Any]],
    threshold: float = 0.8,
) -> List[Dict[str, Any]]:
    """Compare candidate against list of existing products"""
    matches: List[Dict[str, Any]] = []

    candidate_name = candidate_product.get("name", "")
    candidate_brand = candidate_product.get("brand", "")
    candidate_category = candidate_product.get("category", "")

    for existing in existing_products:
        existing_name = existing.get("name", "")
        existing_brand = existing.get("brand", "")
        existing_category = existing.get("category", "")

        # Calculate name similarity
        name_similarity = calculate_name_similarity(candidate_name, existing_name)

        # Calculate brand similarity
        brand_similarity = (
            calculate_name_similarity(candidate_brand, existing_brand)
            if candidate_brand and existing_brand
            else 0
        )

        # Calculate category similarity
        category_similarity = (
            calculate_name_similarity(candidate_category, existing_category)
            if candidate_category and existing_category
            else 0
        )

        # Weighted overall similarity
        overall_similarity = (
            name_similarity * 0.6
            + brand_similarity * 0.3
            + category_similarity * 0.1
        )

        if overall_similarity >= threshold:
            matches.append(
                {
                    "product": existing,
                    "confidence": overall_similarity,
                    "match_reason": "fuzzy_name_brand_match",
                    "similarities": {
                        "name": name_similarity,
                        "brand": brand_similarity,
                        "category": category_similarity,
                    },
                }
            )

    # Sort by confidence descending
    return sorted(matches, key=lambda x: x["confidence"], reverse=True)


def find_exact_matches(
    candidate_product: Dict[str, Any],
    existing_products: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Find exact matches by barcode, name+brand, or image hash"""
    matches: List[Dict[str, Any]] = []

    candidate_barcodes = extract_barcodes_from_data(candidate_product)
    candidate_name = normalize_product_name(candidate_product.get("name", ""))
    candidate_brand = normalize_product_name(candidate_product.get("brand", ""))
    candidate_image_hash = candidate_product.get("image_hash")

    for existing in existing_products:
        existing_barcodes = extract_barcodes_from_data(existing)
        existing_name = normalize_product_name(existing.get("name", ""))
        existing_brand = normalize_product_name(existing.get("brand", ""))
        existing_image_hash = existing.get("image_hash")

        # Check barcode match
        for candidate_barcode in candidate_barcodes:
            if candidate_barcode in existing_barcodes:
                matches.append(
                    {
                        "product": existing,
                        "confidence": 1.0,
                        "match_reason": "exact_barcode_match",
                        "matched_barcode": candidate_barcode,
                    }
                )
                continue

        # Check exact name + brand match
        if (
            candidate_name
            and existing_name
            and candidate_name == existing_name
            and candidate_brand
            and existing_brand
            and candidate_brand == existing_brand
        ):
            matches.append(
                {
                    "product": existing,
                    "confidence": 0.95,
                    "match_reason": "exact_name_brand_match",
                }
            )
            continue

        # Check image hash match
        if (
            candidate_image_hash
            and existing_image_hash
            and candidate_image_hash == existing_image_hash
        ):
            matches.append(
                {
                    "product": existing,
                    "confidence": 0.9,
                    "match_reason": "exact_image_match",
                }
            )

    # Remove duplicates and sort by confidence
    seen = set()
    unique_matches: List[Dict[str, Any]] = []
    for match in matches:
        product_id = match["product"].get("product_id")
        if product_id not in seen:
            seen.add(product_id)
            unique_matches.append(match)

    return sorted(unique_matches, key=lambda x: x["confidence"], reverse=True)


def find_all_matches(
    candidate_product: Dict[str, Any],
    existing_products: List[Dict[str, Any]],
    fuzzy_threshold: float = 0.8,
) -> List[Dict[str, Any]]:
    """Find both exact and fuzzy matches, with exact matches prioritized"""

    # First find exact matches
    exact_matches = find_exact_matches(candidate_product, existing_products)

    # If we have high-confidence exact matches, return those
    if exact_matches and exact_matches[0]["confidence"] >= 0.9:
        return exact_matches[:3]  # Return top 3 exact matches

    # Otherwise, also look for fuzzy matches
    fuzzy_matches = fuzzy_match_products(candidate_product, existing_products, fuzzy_threshold)

    # Combine and deduplicate
    all_matches = exact_matches + fuzzy_matches
    seen = set()
    unique_matches: List[Dict[str, Any]] = []

    for match in all_matches:
        product_id = match["product"].get("product_id")
        if product_id not in seen:
            seen.add(product_id)
            unique_matches.append(match)

    return sorted(unique_matches, key=lambda x: x["confidence"], reverse=True)[:5]


def match_by_regional_name(candidate_name: str, existing_products: List[dict], region_code: str = None) -> List[dict]:
    """
    Match products by regional names
    Higher priority if region_code matches
    """
    matches = []
    
    if not candidate_name:
        return matches
    
    candidate_normalized = normalize_product_name(candidate_name)
    
    for product in existing_products:
        regional_names = product.get('regional_names', {})
        
        # Check all regional names
        for region, names in regional_names.items():
            for name in names:
                normalized_regional = normalize_product_name(name)
                similarity = calculate_name_similarity(candidate_normalized, normalized_regional)
                
                if similarity >= 0.8:  # Threshold for regional match
                    confidence = similarity
                    
                    # Boost confidence if region matches
                    if region_code and region == region_code:
                        confidence = min(1.0, confidence + 0.15)  # 15% boost for region match
                    
                    matches.append({
                        'product': product,
                        'confidence': confidence,
                        'match_reason': f'regional_name_match_{region}',
                        'matched_name': name,
                        'matched_region': region,
                        'similarities': {
                            'regional_name': similarity,
                            'region_boost': 0.15 if region_code and region == region_code else 0
                        }
                    })
    
    return sorted(matches, key=lambda x: x['confidence'], reverse=True)


def detect_language_from_text(text: str) -> str:
    """
    Detect language from text based on character sets
    """
    if not text:
        return 'en'
    
    # Check for different Indian language character ranges
    devanagari_range = range(0x0900, 0x097F)  # Hindi, Marathi, Sanskrit
    tamil_range = range(0x0B80, 0x0BFF)       # Tamil
    telugu_range = range(0x0C00, 0x0C7F)      # Telugu
    kannada_range = range(0x0C80, 0x0CFF)     # Kannada
    malayalam_range = range(0x0D00, 0x0D7F)   # Malayalam
    gujarati_range = range(0x0A80, 0x0AFF)    # Gujarati
    punjabi_range = range(0x0A00, 0x0A7F)     # Punjabi
    bengali_range = range(0x0980, 0x09FF)     # Bengali
    
    char_counts = {
        'hi': 0,  # Hindi/Devanagari
        'ta': 0,  # Tamil
        'te': 0,  # Telugu
        'kn': 0,  # Kannada
        'ml': 0,  # Malayalam
        'gu': 0,  # Gujarati
        'pa': 0,  # Punjabi
        'bn': 0,  # Bengali
        'en': 0   # English/Latin
    }
    
    for char in text:
        char_code = ord(char)
        
        if char_code in devanagari_range:
            char_counts['hi'] += 1
        elif char_code in tamil_range:
            char_counts['ta'] += 1
        elif char_code in telugu_range:
            char_counts['te'] += 1
        elif char_code in kannada_range:
            char_counts['kn'] += 1
        elif char_code in malayalam_range:
            char_counts['ml'] += 1
        elif char_code in gujarati_range:
            char_counts['gu'] += 1
        elif char_code in punjabi_range:
            char_counts['pa'] += 1
        elif char_code in bengali_range:
            char_counts['bn'] += 1
        elif char.isalpha():
            char_counts['en'] += 1
    
    # Return language with highest character count
    return max(char_counts, key=char_counts.get)


def get_regional_language_for_state(region_code: str) -> str:
    """
    Map Indian state codes to primary regional languages
    """
    language_mappings = {
        'IN-MH': 'mr',  # Maharashtra - Marathi
        'IN-TN': 'ta',  # Tamil Nadu - Tamil
        'IN-KA': 'kn',  # Karnataka - Kannada
        'IN-TG': 'te',  # Telangana - Telugu
        'IN-AP': 'te',  # Andhra Pradesh - Telugu
        'IN-KL': 'ml',  # Kerala - Malayalam
        'IN-GJ': 'gu',  # Gujarat - Gujarati
        'IN-PB': 'pa',  # Punjab - Punjabi
        'IN-WB': 'bn',  # West Bengal - Bengali
        'IN-UP': 'hi',  # Uttar Pradesh - Hindi
        'IN-MP': 'hi',  # Madhya Pradesh - Hindi
        'IN-RJ': 'hi',  # Rajasthan - Hindi
        'IN-BR': 'hi',  # Bihar - Hindi
        'IN-JH': 'hi',  # Jharkhand - Hindi
        'IN-HR': 'hi',  # Haryana - Hindi
        'IN-DL': 'hi',  # Delhi - Hindi
        'IN-CG': 'hi',  # Chhattisgarh - Hindi
        'IN-OR': 'or',  # Odisha - Odia
        'IN-AS': 'as',  # Assam - Assamese
    }
    
    return language_mappings.get(region_code, 'en')


def find_existing_product_with_regional(candidate_product: Dict[str, Any], existing_products: List[Dict[str, Any]], region_code: str = None) -> Optional[Dict[str, Any]]:
    """
    Enhanced product matching that includes regional name matching
    """
    
    # 1. Try exact barcode match first (highest priority)
    candidate_barcodes = extract_barcodes_from_data(candidate_product)
    for existing in existing_products:
        existing_barcodes = extract_barcodes_from_data(existing)
        for candidate_barcode in candidate_barcodes:
            if candidate_barcode in existing_barcodes:
                return {
                    'product': existing,
                    'confidence': 1.0,
                    'match_reason': 'exact_barcode_match'
                }
    
    # 2. Try regional name matching (high priority for regional context)
    if region_code:
        regional_matches = match_by_regional_name(
            candidate_product.get('name', ''), 
            existing_products, 
            region_code
        )
        if regional_matches and regional_matches[0]['confidence'] >= 0.9:
            return regional_matches[0]
    
    # 3. Try exact name + brand match
    exact_matches = find_exact_matches(candidate_product, existing_products)
    if exact_matches and exact_matches[0]['confidence'] >= 0.9:
        return exact_matches[0]
    
    # 4. Try fuzzy matching
    fuzzy_matches = fuzzy_match_products(candidate_product, existing_products, threshold=0.8)
    if fuzzy_matches and fuzzy_matches[0]['confidence'] >= 0.8:
        return fuzzy_matches[0]
    
    # 5. Try regional name matching with lower threshold
    if region_code:
        regional_matches = match_by_regional_name(
            candidate_product.get('name', ''), 
            existing_products, 
            region_code
        )
        if regional_matches and regional_matches[0]['confidence'] >= 0.75:
            return regional_matches[0]
    
    return None


def find_all_matches_with_regional(candidate_product: Dict[str, Any], existing_products: List[Dict[str, Any]], region_code: str = None, fuzzy_threshold: float = 0.7) -> List[Dict[str, Any]]:
    """
    Find both exact and fuzzy matches, including regional name matches
    """
    all_matches = []
    
    # 1. Exact matches (barcode, name+brand, image)
    exact_matches = find_exact_matches(candidate_product, existing_products)
    all_matches.extend(exact_matches)
    
    # 2. Regional name matches
    if region_code:
        regional_matches = match_by_regional_name(
            candidate_product.get('name', ''), 
            existing_products, 
            region_code
        )
        all_matches.extend(regional_matches)
    
    # 3. Fuzzy matches
    fuzzy_matches = fuzzy_match_products(candidate_product, existing_products, fuzzy_threshold)
    all_matches.extend(fuzzy_matches)
    
    # Remove duplicates and sort by confidence
    seen = set()
    unique_matches = []
    
    for match in all_matches:
        product_id = match['product'].get('product_id')
        if product_id not in seen:
            seen.add(product_id)
            unique_matches.append(match)
    
    return sorted(unique_matches, key=lambda x: x['confidence'], reverse=True)[:5]


