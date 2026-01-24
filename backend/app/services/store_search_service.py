"""
Enhanced Store Search Service
Provides fuzzy name matching and geocoded location-based search

Features:
- Fuzzy store name search using rapidfuzz (handles typos, similar names)
- Location search using Google Maps Geocoding API
- Distance-based sorting with Haversine formula
- All stores and addresses have pre-geocoded lat/lng for fast searches
"""

import math
import logging
from typing import List, Dict, Any, Optional, Tuple
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class StoreSearchService:
    """
    Service for searching stores by name and location.

    Architecture:
    - Stores and customer addresses are geocoded at registration time
    - Search queries are geocoded using Google Maps API
    - Distance calculations use pre-stored coordinates for speed
    """

    # Search configuration
    EXACT_MATCH_THRESHOLD = 95      # Score above this = exact match
    FUZZY_MATCH_THRESHOLD = 65      # Minimum score for fuzzy matches
    DEFAULT_SEARCH_RADIUS = 10      # km
    MAX_SEARCH_RADIUS = 50          # km
    MAX_NEARBY_STORES = 50          # Maximum stores to return

    # =========================================================================
    # Distance Calculation (Haversine Formula)
    # =========================================================================

    @staticmethod
    def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using Haversine formula.

        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates

        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth's radius in km

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    # =========================================================================
    # Fuzzy Name Search
    # =========================================================================

    @classmethod
    def fuzzy_search_stores_by_name(
        cls,
        stores: List[Dict],
        search_query: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        Search stores by name using fuzzy matching.

        Uses rapidfuzz for efficient fuzzy string matching:
        - Exact matches (score >= 95) returned first
        - Similar matches (score >= 65) returned after
        - Results sorted by match score

        Args:
            stores: List of store dictionaries
            search_query: Search query string
            limit: Maximum results to return

        Returns:
            List of matching stores with match_score and match_type
        """
        if not search_query or not stores:
            return []

        search_query = search_query.strip().lower()
        results = []

        for store in stores:
            store_name = store.get('name', '').lower()

            if not store_name:
                continue

            # Check for exact match
            if search_query == store_name:
                store_copy = store.copy()
                store_copy['match_score'] = 100
                store_copy['match_type'] = 'exact'
                results.append(store_copy)
                continue

            # Check for contains match
            if search_query in store_name:
                store_copy = store.copy()
                store_copy['match_score'] = 90
                store_copy['match_type'] = 'contains'
                results.append(store_copy)
                continue

            # Fuzzy match using token_sort_ratio (handles word order variations)
            score = fuzz.token_sort_ratio(search_query, store_name)

            if score >= cls.FUZZY_MATCH_THRESHOLD:
                store_copy = store.copy()
                store_copy['match_score'] = score
                store_copy['match_type'] = 'fuzzy'
                results.append(store_copy)

        # Sort by match score (highest first)
        results.sort(key=lambda x: x.get('match_score', 0), reverse=True)

        return results[:limit]

    # =========================================================================
    # Location-Based Search
    # =========================================================================

    @classmethod
    def search_stores_by_location(
        cls,
        stores: List[Dict],
        center_lat: float,
        center_lng: float,
        radius_km: float = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Search stores within radius of a center point.

        All stores should have pre-geocoded latitude/longitude from registration.

        Args:
            stores: List of store dictionaries (with latitude, longitude)
            center_lat: Center point latitude
            center_lng: Center point longitude
            radius_km: Search radius in km (default: 10km, max: 50km)
            limit: Maximum results to return

        Returns:
            List of stores within radius, sorted by distance
        """
        if not stores or center_lat is None or center_lng is None:
            return []

        # Apply radius limits
        if radius_km is None:
            radius_km = cls.DEFAULT_SEARCH_RADIUS
        radius_km = min(radius_km, cls.MAX_SEARCH_RADIUS)

        results = []

        for store in stores:
            store_lat = store.get('latitude')
            store_lng = store.get('longitude')

            # Skip stores without coordinates
            if store_lat is None or store_lng is None:
                logger.debug(f"Store {store.get('name')} has no coordinates, skipping")
                continue

            try:
                store_lat = float(store_lat)
                store_lng = float(store_lng)
            except (ValueError, TypeError):
                continue

            # Calculate distance
            distance = cls.calculate_haversine_distance(
                center_lat, center_lng,
                store_lat, store_lng
            )

            # Include if within radius
            if distance <= radius_km:
                store_copy = store.copy()
                store_copy['distance'] = round(distance, 2)
                store_copy['distanceText'] = cls._format_distance(distance)
                store_copy['match_type'] = 'nearby'
                results.append(store_copy)

        # Sort by distance (nearest first)
        results.sort(key=lambda x: x.get('distance', float('inf')))

        return results[:limit]

    @classmethod
    def search_stores_by_filters(
        cls,
        stores: List[Dict],
        city: str = None,
        state: str = None,
        pincode: str = None
    ) -> List[Dict]:
        """
        Filter stores by city, state, or pincode (exact match).

        Used when geocoding fails or for simple filtering.

        Args:
            stores: List of store dictionaries
            city: City to filter by
            state: State to filter by
            pincode: Pincode to filter by

        Returns:
            List of matching stores
        """
        results = []

        for store in stores:
            address = store.get('address', {})

            # Check pincode match
            if pincode:
                store_pincode = address.get('pincode', '')
                if store_pincode != pincode:
                    continue

            # Check city match (case-insensitive)
            if city:
                store_city = address.get('city', '').lower()
                if city.lower() not in store_city and store_city not in city.lower():
                    continue

            # Check state match (case-insensitive)
            if state:
                store_state = address.get('state', '').lower()
                if state.lower() not in store_state and store_state not in state.lower():
                    continue

            results.append(store.copy())

        return results

    # =========================================================================
    # Combined Search (Main Entry Point)
    # =========================================================================

    @classmethod
    async def search_stores(
        cls,
        stores: List[Dict],
        name: str = None,
        pincode: str = None,
        landmark: str = None,
        city: str = None,
        state: str = None,
        lat: float = None,
        lng: float = None,
        radius: int = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Combined store search supporting name, location, and filters.

        Search Strategy:
        1. If lat/lng provided → Use for location search
        2. If pincode/landmark provided → Geocode via Google Maps API
        3. If only city/state → Filter by text match
        4. If name provided → Apply fuzzy name matching

        Args:
            stores: List of all stores from database
            name: Store name to search (fuzzy)
            pincode: Pincode to search
            landmark: Landmark/area to search
            city: City to filter
            state: State to filter
            lat: Latitude (from GPS or previous geocoding)
            lng: Longitude (from GPS or previous geocoding)
            radius: Search radius in km
            limit: Maximum results

        Returns:
            Dict with stores, count, and metadata
        """
        from app.services.geocoding_service import geocoding_service

        results = []
        search_types = []
        filters_applied = {}

        # Step 1: Determine search center coordinates
        search_center = None

        # Priority 1: Direct coordinates (GPS or pre-geocoded)
        if lat is not None and lng is not None:
            search_center = (lat, lng)
            search_types.append("gps")
            logger.info(f"[Search] Using provided coordinates: ({lat}, {lng})")

        # Priority 2: Use existing store coordinates for pincode search (avoid API call)
        elif pincode:
            # First, try to find a store with this pincode that has coordinates
            for store in stores:
                store_pincode = store.get('address', {}).get('pincode', '')
                store_lat = store.get('latitude')
                store_lng = store.get('longitude')

                if store_pincode == pincode and store_lat is not None and store_lng is not None:
                    try:
                        search_center = (float(store_lat), float(store_lng))
                        search_types.append("pincode_cached")
                        logger.info(f"[Search] Using cached store coordinates for pincode {pincode}: {search_center}")
                        break
                    except (ValueError, TypeError):
                        continue

            # If no store found with that pincode, fall back to Google Maps API
            if not search_center:
                try:
                    geocode_result = await geocoding_service.geocode_search_query(
                        pincode=pincode,
                        city=city or "",
                        state=state or ""
                    )
                    if geocode_result:
                        search_center = geocode_result
                        search_types.append("pincode_geocoded")
                        logger.info(f"[Search] Geocoded pincode {pincode} via API: {search_center}")
                except Exception as e:
                    logger.warning(f"[Search] Pincode geocoding failed: {e}")

        # Priority 3: Use existing store coordinates for landmark search (avoid API call)
        elif landmark:
            landmark_lower = landmark.lower().strip()

            # First, try to find a store with this landmark in its address
            for store in stores:
                store_lat = store.get('latitude')
                store_lng = store.get('longitude')

                if store_lat is None or store_lng is None:
                    continue

                # Check landmark in various address fields
                address = store.get('address', {})
                searchable_text = ' '.join([
                    str(address.get('full', '')),
                    str(address.get('street', '')),
                    str(address.get('landmark', '')),
                    str(address.get('area', '')),
                    str(store.get('city', '')),
                ]).lower()

                # Also filter by city if provided
                if city:
                    store_city = str(address.get('city', '')).lower()
                    if city.lower() not in store_city and store_city not in city.lower():
                        continue

                if landmark_lower in searchable_text:
                    try:
                        search_center = (float(store_lat), float(store_lng))
                        search_types.append("landmark_cached")
                        logger.info(f"[Search] Using cached store coordinates for landmark '{landmark}': {search_center}")
                        break
                    except (ValueError, TypeError):
                        continue

            # If no store found with that landmark, fall back to Google Maps API
            if not search_center:
                try:
                    geocode_result = await geocoding_service.geocode_search_query(
                        landmark=landmark,
                        city=city or "",
                        state=state or ""
                    )
                    if geocode_result:
                        search_center = geocode_result
                        search_types.append("landmark_geocoded")
                        logger.info(f"[Search] Geocoded landmark '{landmark}' via API: {search_center}")
                except Exception as e:
                    logger.warning(f"[Search] Landmark geocoding failed: {e}")

        # Step 2: Perform location-based search if we have coordinates
        if search_center:
            center_lat, center_lng = search_center
            results = cls.search_stores_by_location(
                stores=stores,
                center_lat=center_lat,
                center_lng=center_lng,
                radius_km=radius or cls.DEFAULT_SEARCH_RADIUS,
                limit=limit
            )
            if pincode:
                filters_applied['pincode'] = pincode
            if landmark:
                filters_applied['landmark'] = landmark

        # Step 3: Fallback to text-based filtering if no coordinates
        elif city or state:
            results = cls.search_stores_by_filters(
                stores=stores,
                city=city,
                state=state,
                pincode=pincode
            )
            search_types.append("filter")
            if city:
                filters_applied['city'] = city
            if state:
                filters_applied['state'] = state

        # Step 4: If nothing else, return all stores
        else:
            results = [store.copy() for store in stores]
            search_types.append("all")

        # Step 5: Apply fuzzy name search on results
        if name:
            name_matches = cls.fuzzy_search_stores_by_name(
                stores=results if results else stores,
                search_query=name,
                limit=limit
            )
            results = name_matches
            search_types.append("name_fuzzy")
            filters_applied['name'] = name

        # Apply final limit
        results = results[:limit]

        return {
            "stores": results,
            "count": len(results),
            "metadata": {
                "total_stores": len(stores),
                "search_type": search_types,
                "filters_applied": filters_applied
            }
        }

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @staticmethod
    def _format_distance(distance_km: float) -> str:
        """Format distance for display"""
        if distance_km < 1:
            return f"{int(distance_km * 1000)} m"
        return f"{distance_km:.1f} km"


# Singleton instance
store_search_service = StoreSearchService()
