"""
Market Prices Service - Integration with data.gov.in (Agmarknet)
"""

import httpx
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
import json
import os

logger = logging.getLogger(__name__)

# data.gov.in API configuration
DATA_GOV_API_BASE = "https://data.gov.in/api/datastore/resource.json"
DATA_GOV_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
DATA_GOV_API_KEY = os.getenv(
    "DATA_GOV_API_KEY",
    "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"  # Public key
)

# DynamoDB configuration
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "market_prices_cache")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

# Commodities to track (limited to 10 with public API key)
DEFAULT_COMMODITIES = [
    "Tomato",
    "Onion",
    "Potato",
    "Rice",
    "Wheat",
    "Milk",
    "Sugar",
    "Cooking Oil",
    "Pulses (Tur/Arhar)",
    "Pulses (Moong)"
]


class MarketPricesService:
    """Service for fetching and caching commodity market prices"""

    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        self.cache_table_name = DYNAMODB_TABLE_NAME
        self.cache_ttl_hours = 24  # Refresh daily
        self._cache_table = None

    def _get_cache_table(self):
        """Get or create cache table reference"""
        if self._cache_table is None:
            try:
                self._cache_table = self.dynamodb.Table(self.cache_table_name)
            except Exception as e:
                logger.warning(f"Cache table not available: {e}")
                self._cache_table = None
        return self._cache_table

    async def get_market_prices(
        self,
        commodities: Optional[List[str]] = None,
        state: Optional[str] = None,
        market: Optional[str] = None
    ) -> List[Dict]:
        """
        Get market prices for commodities.
        Uses cached data if available and fresh.

        Args:
            commodities: List of commodity names (max 10 with public key)
            state: Optional state filter
            market: Optional market filter

        Returns:
            List of price dictionaries
        """
        if not commodities:
            commodities = DEFAULT_COMMODITIES[:10]  # Limit to 10

        # Limit to 10 commodities with public API key
        if len(commodities) > 10:
            logger.warning(f"Limiting to 10 commodities (public API key limit)")
            commodities = commodities[:10]

        # Check cache first
        cached_prices = await self._get_from_cache(commodities, state, market)
        if cached_prices:
            logger.info(f"Returning cached prices for {len(commodities)} commodities")
            return cached_prices

        # Fetch from data.gov.in API
        logger.info(f"Fetching fresh prices from data.gov.in API")
        fresh_prices = await self._fetch_from_api(commodities, state, market)

        # Cache the results
        if fresh_prices:
            await self._save_to_cache(fresh_prices, commodities, state, market)

        return fresh_prices

    async def _fetch_from_api(
        self,
        commodities: List[str],
        state: Optional[str],
        market: Optional[str]
    ) -> List[Dict]:
        """Fetch commodity prices from data.gov.in API"""

        all_results = []

        for commodity in commodities:
            try:
                params = {
                    "api-key": DATA_GOV_API_KEY,
                    "format": "json",
                    "resource_id": DATA_GOV_RESOURCE_ID,
                    "limit": 1,  # Get latest price
                    "filters[commodity]": commodity
                }

                if state:
                    params["filters[state]"] = state
                if market:
                    params["filters[market]"] = market

                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    response = await client.get(DATA_GOV_API_BASE, params=params)
                    response.raise_for_status()

                    data = response.json()
                    records = data.get("records", [])

                    if records:
                        record = records[0]

                        # Parse price values
                        try:
                            modal_price = float(record.get("modal_price", 0))
                            min_price = float(record.get("min_price", 0))
                            max_price = float(record.get("max_price", 0))
                        except (ValueError, TypeError):
                            modal_price = min_price = max_price = 0.0

                        price_data = {
                            "commodity": commodity,
                            "modal_price": modal_price,
                            "min_price": min_price,
                            "max_price": max_price,
                            "market": record.get("market", "National Average"),
                            "state": record.get("state", ""),
                            "date": record.get("arrival_date", datetime.now().strftime("%Y-%m-%d")),
                            "unit": "kg",
                            "change_percent": None
                        }

                        # Calculate price change
                        price_data["change_percent"] = await self._calculate_price_change(
                            commodity, modal_price
                        )

                        all_results.append(price_data)

                    else:
                        # No data found, add placeholder
                        all_results.append({
                            "commodity": commodity,
                            "modal_price": 0,
                            "min_price": 0,
                            "max_price": 0,
                            "market": "Data not available",
                            "state": "",
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "unit": "kg",
                            "change_percent": None,
                            "error": "No data available"
                        })

            except httpx.HTTPError as e:
                logger.error(f"HTTP error fetching price for {commodity}: {e}")
                all_results.append({
                    "commodity": commodity,
                    "modal_price": 0,
                    "error": f"API error: {str(e)}",
                    "date": datetime.now().strftime("%Y-%m-%d")
                })
            except Exception as e:
                logger.error(f"Error fetching price for {commodity}: {e}")
                all_results.append({
                    "commodity": commodity,
                    "modal_price": 0,
                    "error": str(e),
                    "date": datetime.now().strftime("%Y-%m-%d")
                })

        return all_results

    async def _calculate_price_change(
        self,
        commodity: str,
        current_price: float
    ) -> Optional[float]:
        """Calculate percentage change from previous day's price"""

        table = self._get_cache_table()
        if not table:
            return None

        try:
            cache_key = f"PRICE#{commodity}#previous"

            response = table.get_item(Key={"cache_key": cache_key})

            if "Item" in response:
                previous_price = float(response["Item"]["price"])
                if previous_price > 0:
                    change = ((current_price - previous_price) / previous_price) * 100
                    return round(change, 1)

        except Exception as e:
            logger.error(f"Error calculating price change: {e}")

        return None

    async def _get_from_cache(
        self,
        commodities: List[str],
        state: Optional[str],
        market: Optional[str]
    ) -> Optional[List[Dict]]:
        """Get prices from DynamoDB cache if fresh"""

        table = self._get_cache_table()
        if not table:
            return None

        cache_key = f"PRICES#{','.join(sorted(commodities))}#{state or 'ALL'}#{market or 'ALL'}"

        try:
            response = table.get_item(Key={"cache_key": cache_key})

            if "Item" in response:
                item = response["Item"]
                cached_at = datetime.fromisoformat(item["cached_at"])

                # Check if cache is still fresh
                if datetime.now() - cached_at < timedelta(hours=self.cache_ttl_hours):
                    return json.loads(item["prices_data"])

        except Exception as e:
            logger.error(f"Error reading from cache: {e}")

        return None

    async def _save_to_cache(
        self,
        prices: List[Dict],
        commodities: List[str],
        state: Optional[str],
        market: Optional[str]
    ) -> None:
        """Save prices to DynamoDB cache"""

        table = self._get_cache_table()
        if not table:
            logger.warning("Cache table not available, skipping cache save")
            return

        cache_key = f"PRICES#{','.join(sorted(commodities))}#{state or 'ALL'}#{market or 'ALL'}"

        try:
            # Save current prices
            ttl = int((datetime.now() + timedelta(hours=self.cache_ttl_hours)).timestamp())

            table.put_item(
                Item={
                    "cache_key": cache_key,
                    "prices_data": json.dumps(prices),
                    "cached_at": datetime.now().isoformat(),
                    "ttl": ttl
                }
            )

            # Save individual commodity prices for change calculation
            for price in prices:
                if price.get("modal_price", 0) > 0:  # Only save valid prices
                    prev_key = f"PRICE#{price['commodity']}#previous"
                    prev_ttl = int((datetime.now() + timedelta(days=2)).timestamp())

                    table.put_item(
                        Item={
                            "cache_key": prev_key,
                            "price": str(price["modal_price"]),
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "ttl": prev_ttl
                        }
                    )

            logger.info(f"Saved {len(prices)} prices to cache")

        except ClientError as e:
            logger.error(f"DynamoDB error saving to cache: {e}")
        except Exception as e:
            logger.error(f"Error saving to cache: {e}")


# Singleton instance
_market_prices_service = None


def get_market_prices_service() -> MarketPricesService:
    """Get or create singleton instance of MarketPricesService"""
    global _market_prices_service
    if _market_prices_service is None:
        _market_prices_service = MarketPricesService()
    return _market_prices_service
