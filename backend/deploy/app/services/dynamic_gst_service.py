"""
Dynamic GST Service - GST Rate Lookup with Database and Fallback
Provides GST category and HSN lookups from DynamoDB with caching and static fallback.

Author: DevPrakash
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, Any, List

from app.repositories.gst_repository import gst_repository
from app.services.gst_cache import gst_cache
from app.core import gst_config

logger = logging.getLogger(__name__)


class DynamicGSTService:
    """
    Dynamic GST service with database lookup, caching, and static fallback.

    Priority:
    1. Check cache (in-memory, fast)
    2. Query DynamoDB (slower, authoritative)
    3. Fall back to static gst_config.py (if DB unavailable)
    """

    def __init__(self):
        """Initialize the dynamic GST service."""
        self.repository = gst_repository
        self.cache = gst_cache
        self._static_fallback_used = False

    # =========================================================================
    # CATEGORIES
    # =========================================================================

    async def get_all_categories(self) -> Dict[str, Any]:
        """
        Get all GST categories with caching.

        Returns:
            Dictionary of category_code -> category data
        """
        # 1. Try cache
        cached = await self.cache.get_categories()
        if cached:
            return cached

        # 2. Try database
        try:
            categories_list = await self.repository.get_all_categories()

            if categories_list:
                # Convert list to dict keyed by category_code
                categories = {
                    cat["category_code"]: cat
                    for cat in categories_list
                }
                await self.cache.set_categories(categories)
                self._static_fallback_used = False
                return categories

        except Exception as e:
            logger.warning(f"Database error fetching categories, using fallback: {e}")

        # 3. Fall back to static config
        logger.info("Using static GST categories fallback")
        self._static_fallback_used = True
        return self._get_static_categories()

    def _get_static_categories(self) -> Dict[str, Any]:
        """
        Get categories from static gst_config.py.

        Returns:
            Dictionary of category_code -> category data
        """
        categories = {}
        for key, cat in gst_config.GST_CATEGORIES.items():
            categories[key] = {
                "category_code": key,
                "category_name": cat.name,
                "gst_rate": cat.gst_rate.value,
                "hsn_prefix": cat.hsn_prefix,
                "cess_rate": cat.cess_rate,
                "description": cat.description,
                "keywords": [],
                "is_active": True
            }
        return categories

    async def get_category(self, category_code: str) -> Optional[Dict[str, Any]]:
        """
        Get a single GST category.

        Args:
            category_code: Category code (e.g., "BISCUITS")

        Returns:
            Category dict if found, None otherwise
        """
        # Try getting from all categories (uses cache efficiently)
        categories = await self.get_all_categories()
        return categories.get(category_code)

    # =========================================================================
    # HSN MAPPINGS
    # =========================================================================

    async def get_all_hsn_mappings(self) -> Dict[str, Any]:
        """
        Get all HSN mappings with caching.

        Returns:
            Dictionary of hsn_code -> mapping data
        """
        # 1. Try cache
        cached = await self.cache.get_hsn_mappings()
        if cached:
            return cached

        # 2. Try database
        try:
            mappings_list = await self.repository.get_all_hsn_mappings()

            if mappings_list:
                mappings = {
                    m["hsn_code"]: m
                    for m in mappings_list
                }
                await self.cache.set_hsn_mappings(mappings)
                return mappings

        except Exception as e:
            logger.warning(f"Database error fetching HSN mappings, using fallback: {e}")

        # 3. Fall back to static config
        return self._get_static_hsn_mappings()

    def _get_static_hsn_mappings(self) -> Dict[str, Any]:
        """
        Get HSN mappings from static gst_config.py.

        Returns:
            Dictionary of hsn_code -> mapping data
        """
        mappings = {}
        for hsn_code, category_code in gst_config.HSN_TO_CATEGORY.items():
            mappings[hsn_code] = {
                "hsn_code": hsn_code,
                "category_code": category_code,
                "description": "",
                "is_active": True
            }
        return mappings

    async def get_hsn_mapping(self, hsn_code: str) -> Optional[Dict[str, Any]]:
        """
        Get HSN mapping for a code.

        Args:
            hsn_code: HSN code (4-8 digits)

        Returns:
            Mapping dict if found, None otherwise
        """
        if not hsn_code:
            return None

        hsn_clean = hsn_code.strip().replace(" ", "")

        # Try cache first
        cached = await self.cache.get_hsn_mapping(hsn_clean)
        if cached:
            return cached

        # Get all mappings (will use cache or DB)
        all_mappings = await self.get_all_hsn_mappings()

        # Try exact match
        if hsn_clean in all_mappings:
            return all_mappings[hsn_clean]

        # Try 4-digit prefix
        if len(hsn_clean) >= 4:
            prefix = hsn_clean[:4]
            if prefix in all_mappings:
                return all_mappings[prefix]

        return None

    # =========================================================================
    # GST RATE LOOKUP
    # =========================================================================

    async def get_gst_rate_from_hsn(self, hsn_code: str) -> Optional[Decimal]:
        """
        Get GST rate for an HSN code.

        Args:
            hsn_code: HSN code to lookup

        Returns:
            GST rate as Decimal if found, None otherwise
        """
        mapping = await self.get_hsn_mapping(hsn_code)
        if not mapping:
            return None

        category_code = mapping.get("category_code")
        if not category_code:
            return None

        category = await self.get_category(category_code)
        if not category:
            return None

        gst_rate = category.get("gst_rate")
        if gst_rate is not None:
            return Decimal(str(gst_rate))

        return None

    async def get_cess_rate_from_hsn(self, hsn_code: str) -> Decimal:
        """
        Get cess rate for an HSN code.

        Args:
            hsn_code: HSN code to lookup

        Returns:
            Cess rate as Decimal (0 if not found)
        """
        mapping = await self.get_hsn_mapping(hsn_code)
        if not mapping:
            return Decimal("0")

        category_code = mapping.get("category_code")
        if not category_code:
            return Decimal("0")

        category = await self.get_category(category_code)
        if not category:
            return Decimal("0")

        cess_rate = category.get("cess_rate", 0)
        return Decimal(str(cess_rate))

    # =========================================================================
    # CATEGORY SUGGESTION
    # =========================================================================

    async def suggest_category_from_product_name(self, product_name: str) -> Optional[str]:
        """
        Suggest GST category based on product name keywords.

        Args:
            product_name: Product name to analyze

        Returns:
            Category code if match found, None otherwise
        """
        if not product_name:
            return None

        name_lower = product_name.lower()

        # Get all categories and their keywords
        categories = await self.get_all_categories()

        # First check database categories with keywords
        for code, cat in categories.items():
            keywords = cat.get("keywords", [])
            for keyword in keywords:
                if keyword.lower() in name_lower:
                    return code

        # Fall back to static keyword matching from gst_config
        return gst_config.suggest_category_from_product_name(product_name)

    # =========================================================================
    # CACHE MANAGEMENT
    # =========================================================================

    async def refresh_cache(self) -> Dict[str, Any]:
        """
        Force refresh of all caches.

        Returns:
            Dictionary with refresh results
        """
        await self.cache.invalidate_all()

        # Reload data
        categories = await self.get_all_categories()
        hsn_mappings = await self.get_all_hsn_mappings()

        return {
            "categories_loaded": len(categories),
            "hsn_mappings_loaded": len(hsn_mappings),
            "static_fallback_used": self._static_fallback_used
        }

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        stats = await self.cache.get_stats()
        stats["static_fallback_used"] = self._static_fallback_used
        return stats

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    async def get_categories_by_rate(self, rate: Decimal) -> List[Dict[str, Any]]:
        """
        Get all categories with a specific GST rate.

        Args:
            rate: GST rate (0, 5, 12, 18, 28)

        Returns:
            List of matching categories
        """
        categories = await self.get_all_categories()
        return [
            cat for cat in categories.values()
            if Decimal(str(cat.get("gst_rate", 0))) == rate
        ]

    async def validate_hsn_code(self, hsn_code: str) -> Dict[str, Any]:
        """
        Validate an HSN code and return info.

        Args:
            hsn_code: HSN code to validate

        Returns:
            Dictionary with validation results
        """
        if not hsn_code:
            return {"valid": False, "error": "HSN code is required"}

        hsn_clean = hsn_code.strip().replace(" ", "")

        # Check format
        if not hsn_clean.isdigit():
            return {"valid": False, "error": "HSN code must be numeric"}

        if len(hsn_clean) not in (4, 6, 8):
            return {"valid": False, "error": "HSN code must be 4, 6, or 8 digits"}

        # Check if mapping exists
        mapping = await self.get_hsn_mapping(hsn_clean)
        if mapping:
            category = await self.get_category(mapping["category_code"])
            return {
                "valid": True,
                "hsn_code": hsn_clean,
                "category_code": mapping["category_code"],
                "category_name": category.get("category_name") if category else None,
                "gst_rate": category.get("gst_rate") if category else None,
                "cess_rate": category.get("cess_rate") if category else None
            }

        # Valid format but no mapping
        return {
            "valid": True,
            "hsn_code": hsn_clean,
            "category_code": None,
            "warning": "No GST category mapping found for this HSN code"
        }


# Singleton instance
dynamic_gst_service = DynamicGSTService()
