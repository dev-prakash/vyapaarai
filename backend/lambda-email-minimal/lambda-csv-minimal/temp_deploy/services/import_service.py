import aiohttp
import asyncio
import json
from typing import List, Dict, Optional
from datetime import datetime
import re

class ProductImportService:
    def __init__(self):
        self.open_food_facts_base = "https://world.openfoodfacts.org/api/v0"
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_indian_products_from_off(self, limit=100, category=None) -> List[Dict]:
        """Fetch Indian products from Open Food Facts"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            url = f"{self.open_food_facts_base}/search"
            params = {
                'countries': 'india',
                'fields': 'code,product_name,brands,categories,image_url,image_small_url,nutriments,ingredients_text',
                'page_size': limit,
                'json': 1
            }
            
            if category:
                params['categories'] = category
                
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    products = data.get('products', [])
                    
                    return self.transform_off_products(products)
                else:
                    print(f"Error fetching from Open Food Facts: {response.status}")
                    return []
                    
        except Exception as e:
            print(f"Error in fetch_indian_products_from_off: {e}")
            return []
    
    def transform_off_products(self, off_products: List[Dict]) -> List[Dict]:
        """Transform Open Food Facts products to our format"""
        transformed = []
        
        for product in off_products:
            try:
                # Skip products without essential data
                if not product.get('product_name') or not product.get('code'):
                    continue
                    
                # Clean and validate barcode
                barcode = self.clean_barcode(product.get('code', ''))
                if not barcode:
                    continue
                
                # Extract brand
                brands = product.get('brands', '').split(',')
                brand = brands[0].strip() if brands and brands[0].strip() else 'Unknown Brand'
                
                # Extract and map category
                category = self.map_category(product.get('categories', ''))
                
                # Build image URLs
                image_urls = {}
                if product.get('image_url'):
                    image_urls['original'] = product['image_url']
                if product.get('image_small_url'):
                    image_urls['thumbnail'] = product['image_small_url']
                
                # Build attributes
                attributes = {
                    'source': 'open_food_facts',
                    'original_categories': product.get('categories', ''),
                    'ingredients': product.get('ingredients_text', ''),
                    'imported_at': datetime.utcnow().isoformat()
                }
                
                # Add nutritional info if available
                nutriments = product.get('nutriments', {})
                if nutriments:
                    attributes['nutrition'] = {
                        'energy': nutriments.get('energy'),
                        'fat': nutriments.get('fat'),
                        'carbohydrates': nutriments.get('carbohydrates'),
                        'proteins': nutriments.get('proteins'),
                        'salt': nutriments.get('salt')
                    }
                
                transformed_product = {
                    'name': product['product_name'].strip(),
                    'brand': brand,
                    'category': category,
                    'barcode': barcode,
                    'canonical_image_urls': image_urls,
                    'attributes': attributes,
                    'verification_status': 'admin_created',
                    'regional_names': self.generate_regional_names(product['product_name'], category)
                }
                
                transformed.append(transformed_product)
                
            except Exception as e:
                print(f"Error transforming product {product.get('product_name', 'Unknown')}: {e}")
                continue
        
        return transformed
    
    def clean_barcode(self, barcode: str) -> Optional[str]:
        """Clean and validate barcode"""
        if not barcode:
            return None
            
        # Remove any non-digit characters
        clean = re.sub(r'\D', '', str(barcode))
        
        # Validate length (common barcode lengths)
        if len(clean) in [8, 12, 13, 14]:
            return clean
        
        return None
    
    def map_category(self, categories_string: str) -> str:
        """Map Open Food Facts categories to our category system"""
        if not categories_string:
            return "Unknown"
        
        categories_lower = categories_string.lower()
        
        # Category mapping rules
        category_mapping = {
            'rice': 'Rice & Grains',
            'wheat': 'Rice & Grains',
            'flour': 'Rice & Grains',
            'dal': 'Rice & Grains',
            'lentil': 'Rice & Grains',
            'spice': 'Spices & Condiments',
            'masala': 'Spices & Condiments',
            'salt': 'Spices & Condiments',
            'oil': 'Cooking Oil',
            'ghee': 'Cooking Oil',
            'milk': 'Dairy',
            'curd': 'Dairy',
            'cheese': 'Dairy',
            'tea': 'Beverages',
            'coffee': 'Beverages',
            'juice': 'Beverages',
            'biscuit': 'Snacks',
            'namkeen': 'Snacks',
            'pickle': 'Spices & Condiments',
            'sauce': 'Spices & Condiments',
            'vegetable': 'Vegetables',
            'fruit': 'Fruits'
        }
        
        for keyword, mapped_category in category_mapping.items():
            if keyword in categories_lower:
                return mapped_category
        
        # Extract first meaningful category if no mapping found
        categories = [cat.strip() for cat in categories_string.split(',')]
        return categories[0] if categories else "Unknown"
    
    def generate_regional_names(self, product_name: str, category: str) -> Dict:
        """Generate basic regional names for common products"""
        regional_names = {}
        name_lower = product_name.lower()
        
        # Common product translations
        translations = {
            'rice': {
                'IN-MH': ['चावल', 'भात'],
                'IN-TN': ['அரிசி'],
                'IN-KA': ['ಅಕ್ಕಿ'],
                'IN-UP': ['चावल']
            },
            'oil': {
                'IN-MH': ['तेल'],
                'IN-TN': ['எண்ணெய்'],
                'IN-KA': ['ಎಣ್ಣೆ'],
                'IN-GJ': ['તેલ']
            },
            'salt': {
                'IN-MH': ['मीठ'],
                'IN-TN': ['உப்பு'],
                'IN-KA': ['ಉಪ್ಪು'],
                'IN-GJ': ['મીઠું']
            },
            'milk': {
                'IN-MH': ['दूध'],
                'IN-TN': ['பால்'],
                'IN-KA': ['ಹಾಲು'],
                'IN-GJ': ['દૂધ']
            }
        }
        
        # Check if product name contains translatable terms
        for term, regions in translations.items():
            if term in name_lower:
                for region, names in regions.items():
                    # Replace the English term with regional name
                    regional_names[region] = [
                        product_name.replace(term.title(), names[0])
                    ]
                break
        
        return regional_names

# Common Indian products seed data
COMMON_INDIAN_PRODUCTS = [
    {
        'name': 'Basmati Rice 1kg',
        'brand': 'India Gate',
        'category': 'Rice & Grains',
        'barcode': '8901030875391',
        'attributes': {
            'weight': '1kg',
            'type': 'basmati',
            'grain_length': 'long'
        },
        'regional_names': {
            'IN-MH': ['बासमती चावल 1kg', 'बासमती भात 1kg'],
            'IN-TN': ['பாஸ்மதி அரிசி 1kg'],
            'IN-KA': ['ಬಾಸ್ಮತಿ ಅಕ್ಕಿ 1kg'],
            'IN-UP': ['बासमती चावल 1kg']
        }
    },
    {
        'name': 'Tata Salt 1kg',
        'brand': 'Tata',
        'category': 'Spices & Condiments',
        'barcode': '8901030800009',
        'attributes': {
            'weight': '1kg',
            'type': 'iodized',
            'purity': 'refined'
        },
        'regional_names': {
            'IN-MH': ['टाटा मीठ 1kg'],
            'IN-TN': ['டாடா உப்பு 1kg'],
            'IN-KA': ['ಟಾಟಾ ಉಪ್ಪು 1kg'],
            'IN-GJ': ['ટાટા મીઠું 1kg']
        }
    },
    {
        'name': 'Amul Milk 500ml',
        'brand': 'Amul',
        'category': 'Dairy',
        'barcode': '8901020200005',
        'attributes': {
            'volume': '500ml',
            'fat_content': '3.5%',
            'type': 'full_cream'
        },
        'regional_names': {
            'IN-MH': ['अमूल दूध 500ml'],
            'IN-TN': ['அமுல் பால் 500ml'],
            'IN-KA': ['ಅಮೂಲ್ ಹಾಲು 500ml'],
            'IN-GJ': ['અમૂલ દૂધ 500ml']
        }
    },
    {
        'name': 'Fortune Sunflower Oil 1L',
        'brand': 'Fortune',
        'category': 'Cooking Oil',
        'barcode': '8901030867200',
        'attributes': {
            'volume': '1L',
            'type': 'refined',
            'oil_source': 'sunflower'
        },
        'regional_names': {
            'IN-MH': ['फॉर्च्यून सूर्यफूल तेल 1L'],
            'IN-TN': ['பார்ச்சூன் சூரியகாந்தி எண்ணெய் 1L'],
            'IN-KA': ['ಫಾರ್ಚೂನ್ ಸೂರ್ಯಕಾಂತಿ ಎಣ್ಣೆ 1L']
        }
    },
    {
        'name': 'MDH Turmeric Powder 100g',
        'brand': 'MDH',
        'category': 'Spices & Condiments',
        'barcode': '8901020201234',
        'attributes': {
            'weight': '100g',
            'spice_type': 'turmeric',
            'form': 'powder'
        },
        'regional_names': {
            'IN-MH': ['MDH हळद पावडर 100g'],
            'IN-TN': ['MDH மஞ்சள் பொடி 100g'],
            'IN-KA': ['MDH ಅರಿಶಿನ ಪುಡಿ 100g'],
            'IN-UP': ['MDH हल्दी पाउडर 100g']
        }
    },
    {
        'name': 'Maggi 2-Minute Noodles 70g',
        'brand': 'Maggi',
        'category': 'Snacks',
        'barcode': '8901030875123',
        'attributes': {
            'weight': '70g',
            'type': 'instant_noodles',
            'flavor': 'masala'
        },
        'regional_names': {
            'IN-MH': ['मॅगी 2-मिनिट नूडल्स 70g'],
            'IN-TN': ['மேகி 2-நிமிட நூடுல்ஸ் 70g'],
            'IN-KA': ['ಮ್ಯಾಗಿ 2-ನಿಮಿಷ ನೂಡಲ್ಸ್ 70g']
        }
    },
    {
        'name': 'Britannia Good Day Biscuits 100g',
        'brand': 'Britannia',
        'category': 'Snacks',
        'barcode': '8901030867456',
        'attributes': {
            'weight': '100g',
            'type': 'cookies',
            'flavor': 'butter'
        },
        'regional_names': {
            'IN-MH': ['ब्रिटानिया गुड डे बिस्कीट 100g'],
            'IN-TN': ['பிரிட்டானியா குட் டே பிஸ்கட் 100g'],
            'IN-KA': ['ಬ್ರಿಟಾನಿಯಾ ಗುಡ್ ಡೇ ಬಿಸ್ಕತ್ತು 100g']
        }
    }
]

