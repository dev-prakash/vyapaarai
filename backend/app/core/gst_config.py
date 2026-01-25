"""
GST Configuration for VyapaarAI
India-specific GST rates, HSN codes, and category mappings for kirana stores

Author: DevPrakash
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional


class GSTRate(Enum):
    """Valid GST rates in India"""
    ZERO = Decimal("0")
    FIVE = Decimal("5")
    TWELVE = Decimal("12")
    EIGHTEEN = Decimal("18")
    TWENTY_EIGHT = Decimal("28")


@dataclass
class GSTCategory:
    """GST Category with HSN prefix and rate information"""
    code: str
    name: str
    hsn_prefix: str
    gst_rate: GSTRate
    cess_rate: Decimal = Decimal("0")
    description: str = ""


# ============================================================================
# GST CATEGORIES FOR KIRANA STORE ITEMS
# ============================================================================

GST_CATEGORIES: Dict[str, GSTCategory] = {
    # ------------------------------------------------------------------------
    # 0% GST - ESSENTIAL ITEMS (Exempt/Nil rated)
    # ------------------------------------------------------------------------
    "FRESH_VEGETABLES": GSTCategory(
        code="FRESH_VEG",
        name="Fresh Vegetables",
        hsn_prefix="0701-0714",
        gst_rate=GSTRate.ZERO,
        description="Potatoes, tomatoes, onions, all fresh vegetables"
    ),
    "FRESH_FRUITS": GSTCategory(
        code="FRESH_FRUITS",
        name="Fresh Fruits",
        hsn_prefix="0801-0810",
        gst_rate=GSTRate.ZERO,
        description="All fresh fruits - bananas, apples, mangoes, etc."
    ),
    "FRESH_MILK": GSTCategory(
        code="FRESH_MILK",
        name="Fresh Milk",
        hsn_prefix="0401",
        gst_rate=GSTRate.ZERO,
        description="Fresh milk (not UHT/tetra pack)"
    ),
    "RICE_WHEAT_GRAINS": GSTCategory(
        code="GRAINS",
        name="Rice, Wheat & Grains",
        hsn_prefix="1001-1008",
        gst_rate=GSTRate.ZERO,
        description="Unpackaged rice, wheat, cereals, pulses"
    ),
    "EGGS": GSTCategory(
        code="EGGS",
        name="Fresh Eggs",
        hsn_prefix="0407",
        gst_rate=GSTRate.ZERO,
        description="Fresh eggs in shell"
    ),
    "BREAD_PLAIN": GSTCategory(
        code="BREAD",
        name="Plain Bread",
        hsn_prefix="1905",
        gst_rate=GSTRate.ZERO,
        description="Plain bread without added sugar/flavoring"
    ),
    "UNBRANDED_ATTA": GSTCategory(
        code="UNBRANDED_ATTA",
        name="Unbranded Atta/Flour",
        hsn_prefix="1101",
        gst_rate=GSTRate.ZERO,
        description="Unbranded wheat flour, besan, maida"
    ),
    "FRESH_MEAT": GSTCategory(
        code="FRESH_MEAT",
        name="Fresh Meat",
        hsn_prefix="0201-0210",
        gst_rate=GSTRate.ZERO,
        description="Fresh meat (not frozen/processed)"
    ),
    "FRESH_FISH": GSTCategory(
        code="FRESH_FISH",
        name="Fresh Fish",
        hsn_prefix="0301-0307",
        gst_rate=GSTRate.ZERO,
        description="Fresh fish and seafood"
    ),
    "CURD_LASSI_BUTTERMILK": GSTCategory(
        code="CURD",
        name="Curd, Lassi, Buttermilk",
        hsn_prefix="0403",
        gst_rate=GSTRate.ZERO,
        description="Fresh curd, lassi, chaas (unbranded)"
    ),

    # ------------------------------------------------------------------------
    # 5% GST - BASIC PACKAGED GOODS
    # ------------------------------------------------------------------------
    "SUGAR": GSTCategory(
        code="SUGAR",
        name="Sugar & Jaggery",
        hsn_prefix="1701",
        gst_rate=GSTRate.FIVE,
        description="Sugar, gur, shakkar"
    ),
    "TEA_PACKAGED": GSTCategory(
        code="TEA",
        name="Tea (Packaged)",
        hsn_prefix="0902",
        gst_rate=GSTRate.FIVE,
        description="Packaged tea leaves, tea bags"
    ),
    "COFFEE_PACKAGED": GSTCategory(
        code="COFFEE",
        name="Coffee (Packaged)",
        hsn_prefix="0901",
        gst_rate=GSTRate.FIVE,
        description="Packaged coffee beans, ground coffee"
    ),
    "EDIBLE_OIL": GSTCategory(
        code="OIL",
        name="Edible Oils",
        hsn_prefix="1507-1518",
        gst_rate=GSTRate.FIVE,
        description="Mustard oil, sunflower oil, groundnut oil, etc."
    ),
    "SPICES_PACKAGED": GSTCategory(
        code="SPICES",
        name="Packaged Spices",
        hsn_prefix="0904-0910",
        gst_rate=GSTRate.FIVE,
        description="Turmeric, chilli, coriander, cumin, etc."
    ),
    "MILK_PACKAGED": GSTCategory(
        code="MILK_PKG",
        name="Packaged Milk",
        hsn_prefix="0402",
        gst_rate=GSTRate.FIVE,
        description="UHT milk, tetra pack milk, skimmed milk powder"
    ),
    "PANEER": GSTCategory(
        code="PANEER",
        name="Paneer",
        hsn_prefix="0406",
        gst_rate=GSTRate.FIVE,
        description="Fresh paneer (cottage cheese)"
    ),
    "SALT": GSTCategory(
        code="SALT",
        name="Salt",
        hsn_prefix="2501",
        gst_rate=GSTRate.FIVE,
        description="Table salt, rock salt, iodized salt"
    ),
    "BRANDED_ATTA": GSTCategory(
        code="ATTA",
        name="Branded Atta/Flour",
        hsn_prefix="1101",
        gst_rate=GSTRate.FIVE,
        description="Branded wheat flour, besan, maida"
    ),
    "PACKED_CEREALS": GSTCategory(
        code="CEREALS",
        name="Packed Cereals & Pulses",
        hsn_prefix="0713",
        gst_rate=GSTRate.FIVE,
        description="Branded dal, rajma, chana, etc."
    ),
    "HONEY": GSTCategory(
        code="HONEY",
        name="Honey",
        hsn_prefix="0409",
        gst_rate=GSTRate.FIVE,
        description="Natural honey"
    ),
    "DRY_FRUITS_UNPROCESSED": GSTCategory(
        code="DRY_FRUITS",
        name="Dry Fruits (Unprocessed)",
        hsn_prefix="0801-0802",
        gst_rate=GSTRate.FIVE,
        description="Almonds, cashews, raisins (unprocessed)"
    ),

    # ------------------------------------------------------------------------
    # 12% GST - PROCESSED FOODS
    # ------------------------------------------------------------------------
    "BUTTER_GHEE": GSTCategory(
        code="BUTTER",
        name="Butter & Ghee",
        hsn_prefix="0405",
        gst_rate=GSTRate.TWELVE,
        description="Butter, ghee, dairy spreads"
    ),
    "CHEESE": GSTCategory(
        code="CHEESE",
        name="Cheese Products",
        hsn_prefix="0406",
        gst_rate=GSTRate.TWELVE,
        description="Processed cheese, cheese slices"
    ),
    "FRUIT_JUICE": GSTCategory(
        code="JUICE",
        name="Fruit Juices",
        hsn_prefix="2009",
        gst_rate=GSTRate.TWELVE,
        description="Packaged fruit juices, fruit drinks"
    ),
    "NAMKEEN_BHUJIA": GSTCategory(
        code="NAMKEEN",
        name="Namkeen & Bhujia",
        hsn_prefix="1905",
        gst_rate=GSTRate.TWELVE,
        description="Packaged namkeen, bhujia, mixture"
    ),
    "PICKLES_MURABBA": GSTCategory(
        code="PICKLES",
        name="Pickles & Murabba",
        hsn_prefix="2001-2008",
        gst_rate=GSTRate.TWELVE,
        description="Pickles, achaar, murabba, chutneys"
    ),
    "FROZEN_VEGETABLES": GSTCategory(
        code="FROZEN_VEG",
        name="Frozen Vegetables",
        hsn_prefix="0710",
        gst_rate=GSTRate.TWELVE,
        description="Frozen peas, mixed vegetables"
    ),
    "SAUCES_KETCHUP": GSTCategory(
        code="SAUCES",
        name="Sauces & Ketchup",
        hsn_prefix="2103",
        gst_rate=GSTRate.TWELVE,
        description="Tomato ketchup, soya sauce, mayonnaise"
    ),
    "JAMS_JELLIES": GSTCategory(
        code="JAMS",
        name="Jams & Jellies",
        hsn_prefix="2007",
        gst_rate=GSTRate.TWELVE,
        description="Fruit jams, jellies, marmalades"
    ),
    "AYURVEDIC_MEDICINES": GSTCategory(
        code="AYURVEDIC",
        name="Ayurvedic Medicines",
        hsn_prefix="3003",
        gst_rate=GSTRate.TWELVE,
        description="Ayurvedic and homeopathic medicines"
    ),
    "UMBRELLA": GSTCategory(
        code="UMBRELLA",
        name="Umbrella",
        hsn_prefix="6601",
        gst_rate=GSTRate.TWELVE,
        description="Umbrellas and sun umbrellas"
    ),

    # ------------------------------------------------------------------------
    # 18% GST - FMCG / CONSUMER GOODS
    # ------------------------------------------------------------------------
    "BISCUITS": GSTCategory(
        code="BISCUITS",
        name="Biscuits",
        hsn_prefix="1905",
        gst_rate=GSTRate.EIGHTEEN,
        description="All types of biscuits and cookies"
    ),
    "CHIPS_SNACKS": GSTCategory(
        code="CHIPS",
        name="Chips & Snacks",
        hsn_prefix="2106",
        gst_rate=GSTRate.EIGHTEEN,
        description="Potato chips, corn snacks, etc."
    ),
    "INSTANT_NOODLES": GSTCategory(
        code="NOODLES",
        name="Instant Noodles & Pasta",
        hsn_prefix="1902",
        gst_rate=GSTRate.EIGHTEEN,
        description="Maggi, pasta, vermicelli"
    ),
    "SOAP": GSTCategory(
        code="SOAP",
        name="Soap",
        hsn_prefix="3401",
        gst_rate=GSTRate.EIGHTEEN,
        description="Bathing soap, handwash"
    ),
    "SHAMPOO": GSTCategory(
        code="SHAMPOO",
        name="Shampoo & Conditioner",
        hsn_prefix="3305",
        gst_rate=GSTRate.EIGHTEEN,
        description="Hair shampoo, conditioner, hair oil"
    ),
    "TOOTHPASTE": GSTCategory(
        code="TOOTHPASTE",
        name="Toothpaste & Oral Care",
        hsn_prefix="3306",
        gst_rate=GSTRate.EIGHTEEN,
        description="Toothpaste, mouthwash, toothbrush"
    ),
    "DETERGENT": GSTCategory(
        code="DETERGENT",
        name="Detergent & Cleaning",
        hsn_prefix="3402",
        gst_rate=GSTRate.EIGHTEEN,
        description="Washing powder, liquid detergent, dishwash"
    ),
    "HAIR_OIL": GSTCategory(
        code="HAIR_OIL",
        name="Hair Oil",
        hsn_prefix="3305",
        gst_rate=GSTRate.EIGHTEEN,
        description="Coconut oil, mustard oil for hair"
    ),
    "CREAM_LOTION": GSTCategory(
        code="CREAM",
        name="Cream & Lotion",
        hsn_prefix="3304",
        gst_rate=GSTRate.EIGHTEEN,
        description="Face cream, body lotion, sunscreen"
    ),
    "CHOCOLATES": GSTCategory(
        code="CHOCOLATES",
        name="Chocolates",
        hsn_prefix="1806",
        gst_rate=GSTRate.EIGHTEEN,
        description="Chocolates, cocoa products"
    ),
    "ICE_CREAM": GSTCategory(
        code="ICE_CREAM",
        name="Ice Cream",
        hsn_prefix="2105",
        gst_rate=GSTRate.EIGHTEEN,
        description="Ice cream and frozen desserts"
    ),
    "MINERAL_WATER": GSTCategory(
        code="WATER",
        name="Mineral/Packaged Water",
        hsn_prefix="2201",
        gst_rate=GSTRate.EIGHTEEN,
        description="Bottled water, mineral water"
    ),
    "READY_TO_EAT": GSTCategory(
        code="RTE",
        name="Ready to Eat Meals",
        hsn_prefix="2106",
        gst_rate=GSTRate.EIGHTEEN,
        description="Packaged ready-to-eat meals"
    ),
    "BREAKFAST_CEREALS": GSTCategory(
        code="BREAKFAST",
        name="Breakfast Cereals",
        hsn_prefix="1904",
        gst_rate=GSTRate.EIGHTEEN,
        description="Cornflakes, oats, muesli"
    ),
    "BATTERIES": GSTCategory(
        code="BATTERIES",
        name="Batteries",
        hsn_prefix="8506",
        gst_rate=GSTRate.EIGHTEEN,
        description="Dry cell batteries"
    ),
    "LIGHT_BULBS": GSTCategory(
        code="BULBS",
        name="Light Bulbs",
        hsn_prefix="8539",
        gst_rate=GSTRate.EIGHTEEN,
        description="LED bulbs, tube lights"
    ),
    "STATIONERY": GSTCategory(
        code="STATIONERY",
        name="Stationery",
        hsn_prefix="4820",
        gst_rate=GSTRate.EIGHTEEN,
        description="Notebooks, pens, pencils"
    ),
    "PLASTIC_CONTAINERS": GSTCategory(
        code="PLASTIC",
        name="Plastic Containers",
        hsn_prefix="3924",
        gst_rate=GSTRate.EIGHTEEN,
        description="Plastic containers, boxes, bottles"
    ),

    # ------------------------------------------------------------------------
    # 28% GST - LUXURY / SIN GOODS (with optional cess)
    # ------------------------------------------------------------------------
    "AERATED_DRINKS": GSTCategory(
        code="AERATED",
        name="Aerated/Soft Drinks",
        hsn_prefix="2202",
        gst_rate=GSTRate.TWENTY_EIGHT,
        cess_rate=Decimal("12"),
        description="Cola, soda, carbonated beverages"
    ),
    "TOBACCO_PRODUCTS": GSTCategory(
        code="TOBACCO",
        name="Tobacco Products",
        hsn_prefix="2401-2403",
        gst_rate=GSTRate.TWENTY_EIGHT,
        cess_rate=Decimal("290"),  # Specific cess varies by product
        description="Cigarettes, bidi, tobacco"
    ),
    "PAN_MASALA": GSTCategory(
        code="PAN_MASALA",
        name="Pan Masala",
        hsn_prefix="2106",
        gst_rate=GSTRate.TWENTY_EIGHT,
        cess_rate=Decimal("135"),
        description="Pan masala, gutka (where legal)"
    ),
    "LUXURY_CARS": GSTCategory(
        code="LUXURY_CARS",
        name="Luxury Items",
        hsn_prefix="8703",
        gst_rate=GSTRate.TWENTY_EIGHT,
        cess_rate=Decimal("15"),
        description="High-value items, luxury goods"
    ),
    "AIR_CONDITIONER": GSTCategory(
        code="AC",
        name="Air Conditioner",
        hsn_prefix="8415",
        gst_rate=GSTRate.TWENTY_EIGHT,
        description="AC units and parts"
    ),
}


# ============================================================================
# HSN CODE TO CATEGORY MAPPING
# ============================================================================

HSN_TO_CATEGORY: Dict[str, str] = {
    # 0% Items
    "0701": "FRESH_VEGETABLES",   # Potatoes
    "0702": "FRESH_VEGETABLES",   # Tomatoes
    "0703": "FRESH_VEGETABLES",   # Onions, garlic
    "0704": "FRESH_VEGETABLES",   # Cabbages, cauliflower
    "0705": "FRESH_VEGETABLES",   # Lettuce
    "0706": "FRESH_VEGETABLES",   # Carrots, turnips
    "0707": "FRESH_VEGETABLES",   # Cucumbers
    "0708": "FRESH_VEGETABLES",   # Leguminous vegetables
    "0709": "FRESH_VEGETABLES",   # Other vegetables
    "0710": "FROZEN_VEGETABLES",  # Frozen vegetables (12%)
    "0713": "PACKED_CEREALS",     # Dried legumes (5%)
    "0714": "FRESH_VEGETABLES",   # Roots and tubers

    "0801": "FRESH_FRUITS",       # Coconuts, Brazil nuts
    "0802": "DRY_FRUITS_UNPROCESSED",  # Other nuts
    "0803": "FRESH_FRUITS",       # Bananas
    "0804": "FRESH_FRUITS",       # Dates, figs, pineapples
    "0805": "FRESH_FRUITS",       # Citrus fruits
    "0806": "FRESH_FRUITS",       # Grapes
    "0807": "FRESH_FRUITS",       # Melons, papaya
    "0808": "FRESH_FRUITS",       # Apples, pears
    "0809": "FRESH_FRUITS",       # Apricots, cherries
    "0810": "FRESH_FRUITS",       # Other fruits

    "0401": "FRESH_MILK",         # Fresh milk
    "0402": "MILK_PACKAGED",      # UHT/packaged milk (5%)
    "0403": "CURD_LASSI_BUTTERMILK",  # Curd, lassi
    "0405": "BUTTER_GHEE",        # Butter, ghee (12%)
    "0406": "PANEER",             # Paneer (5%), Cheese (12%)
    "0407": "EGGS",               # Fresh eggs
    "0409": "HONEY",              # Honey

    "0201": "FRESH_MEAT",         # Beef
    "0202": "FRESH_MEAT",         # Beef frozen
    "0203": "FRESH_MEAT",         # Pork
    "0204": "FRESH_MEAT",         # Sheep/goat meat
    "0207": "FRESH_MEAT",         # Poultry
    "0208": "FRESH_MEAT",         # Other meat
    "0210": "FRESH_MEAT",         # Meat preparations

    "0301": "FRESH_FISH",         # Live fish
    "0302": "FRESH_FISH",         # Fresh fish
    "0303": "FRESH_FISH",         # Frozen fish
    "0304": "FRESH_FISH",         # Fish fillets
    "0305": "FRESH_FISH",         # Dried fish
    "0306": "FRESH_FISH",         # Crustaceans
    "0307": "FRESH_FISH",         # Molluscs

    # 5% Items
    "0901": "COFFEE_PACKAGED",    # Coffee
    "0902": "TEA_PACKAGED",       # Tea
    "0904": "SPICES_PACKAGED",    # Pepper
    "0905": "SPICES_PACKAGED",    # Vanilla
    "0906": "SPICES_PACKAGED",    # Cinnamon
    "0907": "SPICES_PACKAGED",    # Cloves
    "0908": "SPICES_PACKAGED",    # Nutmeg
    "0909": "SPICES_PACKAGED",    # Anise, cumin
    "0910": "SPICES_PACKAGED",    # Ginger, turmeric

    "1001": "RICE_WHEAT_GRAINS",  # Wheat
    "1002": "RICE_WHEAT_GRAINS",  # Rye
    "1003": "RICE_WHEAT_GRAINS",  # Barley
    "1004": "RICE_WHEAT_GRAINS",  # Oats
    "1005": "RICE_WHEAT_GRAINS",  # Maize/corn
    "1006": "RICE_WHEAT_GRAINS",  # Rice
    "1007": "RICE_WHEAT_GRAINS",  # Sorghum
    "1008": "RICE_WHEAT_GRAINS",  # Millets

    "1101": "BRANDED_ATTA",       # Wheat flour (5% branded, 0% unbranded)

    "1507": "EDIBLE_OIL",         # Soybean oil
    "1508": "EDIBLE_OIL",         # Groundnut oil
    "1509": "EDIBLE_OIL",         # Olive oil
    "1510": "EDIBLE_OIL",         # Other olive oils
    "1511": "EDIBLE_OIL",         # Palm oil
    "1512": "EDIBLE_OIL",         # Sunflower oil
    "1513": "EDIBLE_OIL",         # Coconut oil
    "1514": "EDIBLE_OIL",         # Rapeseed/mustard oil
    "1515": "EDIBLE_OIL",         # Other vegetable fats
    "1516": "EDIBLE_OIL",         # Animal/vegetable fats
    "1517": "EDIBLE_OIL",         # Margarine
    "1518": "EDIBLE_OIL",         # Other edible preparations

    "1701": "SUGAR",              # Sugar
    "2501": "SALT",               # Salt

    # 12% Items
    "2001": "PICKLES_MURABBA",    # Vegetables in vinegar
    "2002": "PICKLES_MURABBA",    # Tomatoes prepared
    "2003": "PICKLES_MURABBA",    # Mushrooms prepared
    "2004": "PICKLES_MURABBA",    # Other vegetables prepared
    "2005": "PICKLES_MURABBA",    # Other vegetables prepared
    "2006": "PICKLES_MURABBA",    # Vegetables in sugar
    "2007": "JAMS_JELLIES",       # Jams, jellies
    "2008": "PICKLES_MURABBA",    # Fruits/nuts prepared
    "2009": "FRUIT_JUICE",        # Fruit juices

    "2103": "SAUCES_KETCHUP",     # Sauces, ketchup

    # 18% Items
    "1806": "CHOCOLATES",         # Chocolate
    "1902": "INSTANT_NOODLES",    # Pasta, noodles
    "1904": "BREAKFAST_CEREALS",  # Cornflakes, cereals
    "1905": "BISCUITS",           # Biscuits, bread (varies)

    "2105": "ICE_CREAM",          # Ice cream
    "2106": "CHIPS_SNACKS",       # Food preparations (varies)

    "2201": "MINERAL_WATER",      # Mineral water

    "3003": "AYURVEDIC_MEDICINES",  # Medicaments

    "3304": "CREAM_LOTION",       # Beauty products
    "3305": "SHAMPOO",            # Hair preparations
    "3306": "TOOTHPASTE",         # Oral hygiene
    "3401": "SOAP",               # Soap
    "3402": "DETERGENT",          # Detergents

    "3924": "PLASTIC_CONTAINERS", # Plastic housewares
    "4820": "STATIONERY",         # Paper stationery
    "6601": "UMBRELLA",           # Umbrellas
    "8506": "BATTERIES",          # Batteries
    "8539": "LIGHT_BULBS",        # Light bulbs

    # 28% Items
    "2202": "AERATED_DRINKS",     # Aerated beverages
    "2401": "TOBACCO_PRODUCTS",   # Unmanufactured tobacco
    "2402": "TOBACCO_PRODUCTS",   # Cigars, cigarettes
    "2403": "TOBACCO_PRODUCTS",   # Other tobacco
    "8415": "AIR_CONDITIONER",    # Air conditioners
    "8703": "LUXURY_CARS",        # Motor vehicles
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_gst_rate_from_hsn(hsn_code: str) -> Optional[GSTCategory]:
    """
    Get GST category from HSN code.
    Supports both exact match and prefix match (first 4 digits).

    Args:
        hsn_code: HSN code (4-8 digits)

    Returns:
        GSTCategory if found, None otherwise
    """
    if not hsn_code:
        return None

    # Clean HSN code
    hsn_clean = hsn_code.strip().replace(" ", "")

    # Try exact match first
    if hsn_clean in HSN_TO_CATEGORY:
        category_key = HSN_TO_CATEGORY[hsn_clean]
        return GST_CATEGORIES.get(category_key)

    # Try 4-digit prefix match
    if len(hsn_clean) >= 4:
        prefix = hsn_clean[:4]
        if prefix in HSN_TO_CATEGORY:
            category_key = HSN_TO_CATEGORY[prefix]
            return GST_CATEGORIES.get(category_key)

    return None


def get_default_gst_rate() -> GSTRate:
    """
    Get default GST rate for products without HSN mapping.
    Returns 18% as a conservative default (covers most FMCG items).

    Returns:
        GSTRate.EIGHTEEN (18%)
    """
    return GSTRate.EIGHTEEN


def get_all_gst_rates() -> list:
    """
    Get list of all valid GST rates.

    Returns:
        List of Decimal values [0, 5, 12, 18, 28]
    """
    return [rate.value for rate in GSTRate]


def validate_hsn_code(hsn_code: str) -> bool:
    """
    Validate HSN code format.
    Valid HSN codes are 4, 6, or 8 digits.

    Args:
        hsn_code: HSN code to validate

    Returns:
        True if valid, False otherwise
    """
    if not hsn_code:
        return False

    hsn_clean = hsn_code.strip().replace(" ", "")

    # Must be numeric
    if not hsn_clean.isdigit():
        return False

    # Valid lengths: 4, 6, or 8 digits
    if len(hsn_clean) not in (4, 6, 8):
        return False

    return True


def get_category_by_name(category_name: str) -> Optional[GSTCategory]:
    """
    Get GST category by its key name.

    Args:
        category_name: Category key (e.g., 'BISCUITS', 'FRESH_VEGETABLES')

    Returns:
        GSTCategory if found, None otherwise
    """
    return GST_CATEGORIES.get(category_name.upper())


def suggest_category_from_product_name(product_name: str) -> Optional[str]:
    """
    Suggest GST category based on product name keywords.
    This is a basic implementation - can be enhanced with ML.

    Args:
        product_name: Product name to analyze

    Returns:
        Category key if match found, None otherwise
    """
    name_lower = product_name.lower()

    # Keyword to category mapping
    keyword_mapping = {
        # 0% Items
        "vegetable": "FRESH_VEGETABLES",
        "potato": "FRESH_VEGETABLES",
        "tomato": "FRESH_VEGETABLES",
        "onion": "FRESH_VEGETABLES",
        "fruit": "FRESH_FRUITS",
        "banana": "FRESH_FRUITS",
        "apple": "FRESH_FRUITS",
        "mango": "FRESH_FRUITS",
        "egg": "EGGS",
        "rice": "RICE_WHEAT_GRAINS",
        "wheat": "RICE_WHEAT_GRAINS",
        "dal": "PACKED_CEREALS",

        # 5% Items
        "tea": "TEA_PACKAGED",
        "coffee": "COFFEE_PACKAGED",
        "oil": "EDIBLE_OIL",
        "sugar": "SUGAR",
        "salt": "SALT",
        "atta": "BRANDED_ATTA",
        "flour": "BRANDED_ATTA",
        "spice": "SPICES_PACKAGED",
        "masala": "SPICES_PACKAGED",
        "milk": "MILK_PACKAGED",
        "paneer": "PANEER",

        # 12% Items
        "butter": "BUTTER_GHEE",
        "ghee": "BUTTER_GHEE",
        "cheese": "CHEESE",
        "juice": "FRUIT_JUICE",
        "pickle": "PICKLES_MURABBA",
        "achaar": "PICKLES_MURABBA",
        "sauce": "SAUCES_KETCHUP",
        "ketchup": "SAUCES_KETCHUP",
        "jam": "JAMS_JELLIES",
        "namkeen": "NAMKEEN_BHUJIA",
        "bhujia": "NAMKEEN_BHUJIA",

        # 18% Items
        "biscuit": "BISCUITS",
        "cookie": "BISCUITS",
        "chips": "CHIPS_SNACKS",
        "noodle": "INSTANT_NOODLES",
        "maggi": "INSTANT_NOODLES",
        "pasta": "INSTANT_NOODLES",
        "soap": "SOAP",
        "shampoo": "SHAMPOO",
        "toothpaste": "TOOTHPASTE",
        "detergent": "DETERGENT",
        "surf": "DETERGENT",
        "chocolate": "CHOCOLATES",
        "ice cream": "ICE_CREAM",
        "water": "MINERAL_WATER",

        # 28% Items
        "cola": "AERATED_DRINKS",
        "pepsi": "AERATED_DRINKS",
        "coke": "AERATED_DRINKS",
        "soda": "AERATED_DRINKS",
        "sprite": "AERATED_DRINKS",
        "fanta": "AERATED_DRINKS",
    }

    for keyword, category in keyword_mapping.items():
        if keyword in name_lower:
            return category

    return None
