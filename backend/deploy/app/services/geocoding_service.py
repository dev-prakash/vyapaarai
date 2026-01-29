"""
Geocoding Service using Google Maps API

Provides address-to-coordinates conversion for:
- Store addresses during registration
- Customer addresses when saved
- Search queries (pincode, landmark, area)

Features:
- Automatic geocoding on address save
- Caching to reduce API calls
- Fallback handling for failed geocoding
"""

import os
import logging
import httpx
from typing import Optional, Tuple, Dict, Any
from functools import lru_cache
import hashlib

logger = logging.getLogger(__name__)

# Google Maps API configuration
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
GEOCODING_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Cache for geocoding results (in-memory, resets on Lambda cold start)
# For persistent caching, consider DynamoDB
_geocode_cache: Dict[str, Tuple[float, float]] = {}


class GeocodingService:
    """Google Maps Geocoding Service for Indian addresses"""

    # India bounding box for biasing results
    INDIA_BOUNDS = {
        "southwest": {"lat": 6.5546, "lng": 68.1097},
        "northeast": {"lat": 35.6745, "lng": 97.3956}
    }

    @staticmethod
    def _get_cache_key(address: str) -> str:
        """Generate cache key from address"""
        normalized = address.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()

    @classmethod
    def _check_cache(cls, address: str) -> Optional[Tuple[float, float]]:
        """Check if address is in cache"""
        cache_key = cls._get_cache_key(address)
        return _geocode_cache.get(cache_key)

    @classmethod
    def _save_to_cache(cls, address: str, lat: float, lng: float):
        """Save geocoding result to cache"""
        cache_key = cls._get_cache_key(address)
        _geocode_cache[cache_key] = (lat, lng)

        # Limit cache size to prevent memory issues
        if len(_geocode_cache) > 10000:
            # Remove oldest entries (simple approach)
            keys_to_remove = list(_geocode_cache.keys())[:1000]
            for key in keys_to_remove:
                del _geocode_cache[key]

    @classmethod
    async def geocode_address(
        cls,
        street: str = "",
        city: str = "",
        state: str = "",
        pincode: str = "",
        country: str = "India"
    ) -> Optional[Dict[str, Any]]:
        """
        Geocode an address to get latitude and longitude.

        Args:
            street: Street address
            city: City name
            state: State name
            pincode: PIN code
            country: Country (default: India)

        Returns:
            Dict with lat, lng, formatted_address, and place_id
            None if geocoding fails
        """
        if not GOOGLE_MAPS_API_KEY:
            logger.warning("[Geocoding] GOOGLE_MAPS_API_KEY not configured")
            return None

        # Build full address string
        address_parts = [part.strip() for part in [street, city, state, pincode, country] if part and part.strip()]
        full_address = ", ".join(address_parts)

        if not full_address or full_address == "India":
            logger.warning("[Geocoding] Empty address provided")
            return None

        # Check cache first
        cached = cls._check_cache(full_address)
        if cached:
            logger.info(f"[Geocoding] Cache hit for: {full_address[:50]}...")
            return {
                "latitude": cached[0],
                "longitude": cached[1],
                "formatted_address": full_address,
                "source": "cache"
            }

        try:
            # Build API request
            params = {
                "address": full_address,
                "key": GOOGLE_MAPS_API_KEY,
                "region": "in",  # Bias to India
                "components": "country:IN"  # Restrict to India
            }

            logger.info(f"[Geocoding] Requesting coordinates for: {full_address[:50]}...")

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(GEOCODING_API_URL, params=params)
                response.raise_for_status()
                data = response.json()

            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                location = result["geometry"]["location"]
                lat = location["lat"]
                lng = location["lng"]

                # Save to cache
                cls._save_to_cache(full_address, lat, lng)

                logger.info(f"[Geocoding] Success: {full_address[:30]}... -> ({lat}, {lng})")

                return {
                    "latitude": lat,
                    "longitude": lng,
                    "formatted_address": result.get("formatted_address", full_address),
                    "place_id": result.get("place_id"),
                    "source": "google_maps"
                }

            elif data.get("status") == "ZERO_RESULTS":
                logger.warning(f"[Geocoding] No results for: {full_address[:50]}...")
                return None

            else:
                logger.error(f"[Geocoding] API error: {data.get('status')} - {data.get('error_message', 'Unknown')}")
                return None

        except httpx.TimeoutException:
            logger.error(f"[Geocoding] Timeout for: {full_address[:50]}...")
            return None
        except httpx.HTTPError as e:
            logger.error(f"[Geocoding] HTTP error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"[Geocoding] Unexpected error: {str(e)}")
            return None

    @classmethod
    async def geocode_pincode(cls, pincode: str) -> Optional[Dict[str, Any]]:
        """
        Geocode a pincode to get its center coordinates.

        Args:
            pincode: Indian PIN code (6 digits)

        Returns:
            Dict with lat, lng, city, state
        """
        if not pincode or len(pincode.strip()) != 6:
            return None

        return await cls.geocode_address(pincode=pincode.strip())

    @classmethod
    async def geocode_landmark(cls, landmark: str, city: str = "", state: str = "") -> Optional[Dict[str, Any]]:
        """
        Geocode a landmark or area name.

        Args:
            landmark: Landmark or area name
            city: Optional city for better accuracy
            state: Optional state for better accuracy

        Returns:
            Dict with lat, lng, formatted_address
        """
        if not landmark:
            return None

        return await cls.geocode_address(street=landmark, city=city, state=state)

    @classmethod
    async def geocode_search_query(
        cls,
        pincode: str = "",
        landmark: str = "",
        city: str = "",
        state: str = ""
    ) -> Optional[Tuple[float, float]]:
        """
        Geocode a search query to get center coordinates for nearby search.
        Tries multiple strategies to get coordinates.

        Args:
            pincode: PIN code
            landmark: Landmark or area name
            city: City name
            state: State name

        Returns:
            Tuple of (latitude, longitude) or None
        """
        # Strategy 1: Full address with all components
        if pincode or landmark:
            result = await cls.geocode_address(
                street=landmark,
                city=city,
                state=state,
                pincode=pincode
            )
            if result:
                return (result["latitude"], result["longitude"])

        # Strategy 2: Just pincode
        if pincode:
            result = await cls.geocode_pincode(pincode)
            if result:
                return (result["latitude"], result["longitude"])

        # Strategy 3: Just landmark with city
        if landmark:
            result = await cls.geocode_landmark(landmark, city, state)
            if result:
                return (result["latitude"], result["longitude"])

        # Strategy 4: Just city and state
        if city or state:
            result = await cls.geocode_address(city=city, state=state)
            if result:
                return (result["latitude"], result["longitude"])

        return None

    @classmethod
    def format_address_for_geocoding(cls, address_dict: Dict[str, Any]) -> str:
        """
        Format an address dictionary into a geocoding-friendly string.

        Args:
            address_dict: Dictionary with street, city, state, pincode

        Returns:
            Formatted address string
        """
        parts = []

        for field in ['street', 'area', 'landmark', 'city', 'state', 'pincode']:
            value = address_dict.get(field, '')
            if value and str(value).strip():
                parts.append(str(value).strip())

        return ", ".join(parts) + ", India" if parts else ""


# Singleton instance
geocoding_service = GeocodingService()
