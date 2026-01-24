# Implementation Plan: Enhanced Search & Market Prices

## Overview
This document outlines the implementation of:
1. State/City dropdown search with dependency
2. Pincode and Landmark search
3. Market prices integration with data.gov.in API

---

## 1. State & City Dropdown Search

### Frontend Implementation

#### Indian States List
```typescript
// src/constants/indianStates.ts
export const INDIAN_STATES = [
  { code: "AN", name: "Andaman and Nicobar Islands" },
  { code: "AP", name: "Andhra Pradesh" },
  { code: "AR", name: "Arunachal Pradesh" },
  { code: "AS", name: "Assam" },
  { code: "BR", name: "Bihar" },
  { code: "CH", name: "Chandigarh" },
  { code: "CT", name: "Chhattisgarh" },
  { code: "DN", name: "Dadra and Nagar Haveli and Daman and Diu" },
  { code: "DL", name: "Delhi" },
  { code: "GA", name: "Goa" },
  { code: "GJ", name: "Gujarat" },
  { code: "HR", name: "Haryana" },
  { code: "HP", name: "Himachal Pradesh" },
  { code: "JK", name: "Jammu and Kashmir" },
  { code: "JH", name: "Jharkhand" },
  { code: "KA", name: "Karnataka" },
  { code: "KL", name: "Kerala" },
  { code: "LA", name: "Ladakh" },
  { code: "LD", name: "Lakshadweep" },
  { code: "MP", name: "Madhya Pradesh" },
  { code: "MH", name: "Maharashtra" },
  { code: "MN", name: "Manipur" },
  { code: "ML", name: "Meghalaya" },
  { code: "MZ", name: "Mizoram" },
  { code: "NL", name: "Nagaland" },
  { code: "OR", name: "Odisha" },
  { code: "PY", name: "Puducherry" },
  { code: "PB", name: "Punjab" },
  { code: "RJ", name: "Rajasthan" },
  { code: "SK", name: "Sikkim" },
  { code: "TN", name: "Tamil Nadu" },
  { code: "TG", name: "Telangana" },
  { code: "TR", name: "Tripura" },
  { code: "UP", name: "Uttar Pradesh" },
  { code: "UT", name: "Uttarakhand" },
  { code: "WB", name: "West Bengal" }
];
```

#### City API Endpoint
```typescript
// Backend: /api/v1/location/cities?state=Karnataka

GET /api/v1/location/cities?state=Karnataka
Response: {
  state: "Karnataka",
  cities: [
    "Bangalore",
    "Mysore",
    "Mangalore",
    "Hubli",
    "Belgaum",
    // ... more cities
  ],
  total: 50
}
```

#### Frontend Component
```typescript
// src/pages/customer/StoreSelector.tsx

import { Autocomplete } from '@mui/material';
import { INDIAN_STATES } from '../../constants/indianStates';

const [selectedState, setSelectedState] = useState<string | null>(null);
const [selectedCity, setSelectedCity] = useState<string | null>(null);
const [cities, setCities] = useState<string[]>([]);
const [loadingCities, setLoadingCities] = useState(false);

// Fetch cities when state changes
useEffect(() => {
  if (selectedState) {
    fetchCitiesForState(selectedState);
  } else {
    setCities([]);
    setSelectedCity(null);
  }
}, [selectedState]);

const fetchCitiesForState = async (state: string) => {
  setLoadingCities(true);
  try {
    const response = await axios.get(`${API_BASE_URL}/api/v1/location/cities`, {
      params: { state }
    });
    setCities(response.data.cities);
  } catch (error) {
    console.error('Failed to fetch cities:', error);
    setCities([]);
  } finally {
    setLoadingCities(false);
  }
};

// State Dropdown
<Autocomplete
  options={INDIAN_STATES}
  getOptionLabel={(option) => option.name}
  value={INDIAN_STATES.find(s => s.name === selectedState) || null}
  onChange={(event, newValue) => {
    setSelectedState(newValue?.name || null);
  }}
  renderInput={(params) => (
    <TextField
      {...params}
      placeholder="Select State"
      size="small"
    />
  )}
/>

// City Dropdown
<Autocomplete
  options={cities}
  value={selectedCity}
  onChange={(event, newValue) => {
    setSelectedCity(newValue);
  }}
  loading={loadingCities}
  disabled={!selectedState}
  renderInput={(params) => (
    <TextField
      {...params}
      placeholder={selectedState ? "Select City" : "Select State First"}
      size="small"
    />
  )}
/>
```

---

## 2. Backend: Cities API

### Implementation
```python
# backend/app/api/location.py

from fastapi import APIRouter, Query
from typing import List
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Mapping of states to major cities
# This can be moved to a database or external service later
STATE_CITIES = {
    "Karnataka": [
        "Bangalore", "Mysore", "Mangalore", "Hubli", "Belgaum",
        "Dharwad", "Tumkur", "Bellary", "Bijapur", "Shimoga"
    ],
    "Maharashtra": [
        "Mumbai", "Pune", "Nagpur", "Thane", "Nashik",
        "Aurangabad", "Solapur", "Amravati", "Kolhapur", "Sangli"
    ],
    "Tamil Nadu": [
        "Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem",
        "Tirunelveli", "Tiruppur", "Erode", "Vellore", "Thanjavur"
    ],
    "Telangana": [
        "Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam",
        "Ramagundam", "Mahbubnagar", "Nalgonda", "Adilabad", "Suryapet"
    ],
    "Gujarat": [
        "Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar",
        "Jamnagar", "Junagadh", "Gandhinagar", "Anand", "Nadiad"
    ],
    # Add more states...
}

@router.get("/cities")
async def get_cities_by_state(
    state: str = Query(..., description="State name")
):
    """Get list of cities for a given state"""

    # Normalize state name
    state = state.strip()

    # Find matching state (case-insensitive)
    cities = None
    for state_key in STATE_CITIES.keys():
        if state_key.lower() == state.lower():
            cities = STATE_CITIES[state_key]
            break

    if not cities:
        return {
            "state": state,
            "cities": [],
            "total": 0,
            "message": "No cities found for this state"
        }

    # Sort alphabetically
    cities = sorted(cities)

    return {
        "state": state,
        "cities": cities,
        "total": len(cities)
    }

# Register router in main.py
# app.include_router(location.router, prefix="/api/v1/location", tags=["Location"])
```

---

## 3. Pincode & Landmark Search

### Backend: Enhanced Store Search

```python
# backend/app/api/stores.py

@router.get("/nearby")
async def get_nearby_stores(
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    city: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    pincode: Optional[str] = Query(None),  # NEW
    landmark: Optional[str] = Query(None),  # NEW
    radius: Optional[float] = Query(50, ge=1, le=200),
    limit: Optional[int] = Query(20, ge=1, le=100),
):
    """
    Search stores by multiple criteria:
    - GPS coordinates (lat/lng)
    - City/State
    - Pincode
    - Landmark/Area name
    """

    # Priority: lat/lng > pincode > city/state > landmark

    # 1. GPS-based search
    if lat and lng:
        return await _search_by_coordinates(lat, lng, radius, limit)

    # 2. Pincode-based search
    if pincode:
        return await _search_by_pincode(pincode, radius, limit)

    # 3. City/State search
    if city or state:
        return await _search_by_city_state(city, state, radius, limit)

    # 4. Landmark search
    if landmark:
        return await _search_by_landmark(landmark, radius, limit)

    raise HTTPException(
        status_code=400,
        detail="Please provide at least one search criterion"
    )


async def _search_by_pincode(
    pincode: str,
    radius: float,
    limit: int
) -> dict:
    """
    Search stores by pincode.
    Implementation:
    1. Query stores table with pincode filter
    2. If pincode has lat/lng, use distance calculation
    3. Otherwise, return all stores in that pincode
    """

    # Query DynamoDB with GSI on pincode
    response = await dynamodb.query_stores_by_pincode(pincode)

    stores = response.get("stores", [])

    # Sort by distance if coordinates available
    if stores and stores[0].get("latitude"):
        stores = sorted(stores, key=lambda s: s.get("distance", 999))

    return {
        "stores": stores[:limit],
        "total": len(stores),
        "search_type": "pincode",
        "pincode": pincode
    }


async def _search_by_landmark(
    landmark: str,
    radius: float,
    limit: int
) -> dict:
    """
    Search stores by landmark/area name.
    Implementation:
    1. Use fuzzy matching on store address/landmark fields
    2. Return stores that match the landmark
    """

    # Query stores with landmark in address
    response = await dynamodb.scan_stores_by_landmark(landmark)

    stores = response.get("stores", [])

    return {
        "stores": stores[:limit],
        "total": len(stores),
        "search_type": "landmark",
        "landmark": landmark
    }
```

### DynamoDB: Add GSI for Pincode
```python
# Add GSI-4 to stores table
GSI-4: pincode (PK) + city#state (SK)
- Query all stores in a pincode
- Sort by city/state for better organization
```

---

## 4. Market Prices Service

### Backend Service
```python
# backend/app/services/market_prices_service.py

import httpx
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.database.dynamodb import get_dynamodb_client
import json

logger = logging.getLogger(__name__)

# data.gov.in API configuration
DATA_GOV_API_BASE = "https://data.gov.in/api/datastore/resource.json"
DATA_GOV_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"  # Commodity prices
DATA_GOV_API_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"  # Public key

# Commodities to track
TRACKED_COMMODITIES = [
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
    def __init__(self):
        self.dynamodb = get_dynamodb_client()
        self.cache_table = "market_prices_cache"
        self.cache_ttl_hours = 24  # Refresh daily

    async def get_market_prices(
        self,
        commodities: Optional[List[str]] = None,
        state: Optional[str] = None,
        market: Optional[str] = None
    ) -> List[Dict]:
        """
        Get market prices for commodities.
        Uses cached data if available and fresh.
        """

        if not commodities:
            commodities = TRACKED_COMMODITIES

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
        """
        Fetch commodity prices from data.gov.in API.
        """

        all_results = []

        # Fetch each commodity (API limit: 10 at a time with public key)
        for commodity in commodities[:10]:  # Limit to 10 with public key
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

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(DATA_GOV_API_BASE, params=params)
                    response.raise_for_status()

                    data = response.json()
                    records = data.get("records", [])

                    if records:
                        record = records[0]
                        price_data = {
                            "commodity": commodity,
                            "modal_price": float(record.get("modal_price", 0)),
                            "min_price": float(record.get("min_price", 0)),
                            "max_price": float(record.get("max_price", 0)),
                            "market": record.get("market", "National Average"),
                            "state": record.get("state", ""),
                            "date": record.get("arrival_date", datetime.now().strftime("%Y-%m-%d")),
                            "unit": "kg",  # Assume kg for most commodities
                            "change_percent": None  # Calculate from historical data
                        }

                        # Calculate price change
                        price_data["change_percent"] = await self._calculate_price_change(
                            commodity, price_data["modal_price"]
                        )

                        all_results.append(price_data)

            except Exception as e:
                logger.error(f"Error fetching price for {commodity}: {e}")
                # Add placeholder data
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
        """
        Calculate percentage change from previous day's price.
        """

        try:
            # Get previous day's cached price
            cache_key = f"PRICE#{commodity}#previous"

            response = self.dynamodb.get_item(
                TableName=self.cache_table,
                Key={"cache_key": cache_key}
            )

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
        """
        Get prices from DynamoDB cache if fresh.
        """

        cache_key = f"PRICES#{','.join(sorted(commodities))}#{state or 'ALL'}#{market or 'ALL'}"

        try:
            response = self.dynamodb.get_item(
                TableName=self.cache_table,
                Key={"cache_key": cache_key}
            )

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
        """
        Save prices to DynamoDB cache.
        """

        cache_key = f"PRICES#{','.join(sorted(commodities))}#{state or 'ALL'}#{market or 'ALL'}"

        try:
            # Save current prices
            self.dynamodb.put_item(
                TableName=self.cache_table,
                Item={
                    "cache_key": cache_key,
                    "prices_data": json.dumps(prices),
                    "cached_at": datetime.now().isoformat(),
                    "ttl": int((datetime.now() + timedelta(hours=self.cache_ttl_hours)).timestamp())
                }
            )

            # Save individual commodity prices for change calculation
            for price in prices:
                prev_key = f"PRICE#{price['commodity']}#previous"
                self.dynamodb.put_item(
                    TableName=self.cache_table,
                    Item={
                        "cache_key": prev_key,
                        "price": price["modal_price"],
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "ttl": int((datetime.now() + timedelta(days=2)).timestamp())
                    }
                )

        except Exception as e:
            logger.error(f"Error saving to cache: {e}")


# Singleton instance
_market_prices_service = None

def get_market_prices_service() -> MarketPricesService:
    global _market_prices_service
    if _market_prices_service is None:
        _market_prices_service = MarketPricesService()
    return _market_prices_service
```

### API Endpoint
```python
# backend/app/api/market_prices.py

from fastapi import APIRouter, Query
from typing import List, Optional
from app.services.market_prices_service import get_market_prices_service

router = APIRouter()

@router.get("/market-prices")
async def get_market_prices(
    commodities: Optional[str] = Query(None, description="Comma-separated commodity names"),
    state: Optional[str] = Query(None, description="State name"),
    market: Optional[str] = Query(None, description="Market name")
):
    """
    Get current market prices for commodities.
    Data source: data.gov.in (Agmarknet)
    """

    service = get_market_prices_service()

    commodity_list = None
    if commodities:
        commodity_list = [c.strip() for c in commodities.split(",")]

    prices = await service.get_market_prices(
        commodities=commodity_list,
        state=state,
        market=market
    )

    return {
        "prices": prices,
        "total": len(prices),
        "source": "data.gov.in (Agmarknet)",
        "last_updated": prices[0]["date"] if prices else None
    }

# Register in main.py
# app.include_router(market_prices.router, prefix="/api/v1/public", tags=["Market Prices"])
```

---

## 5. Frontend: Market Prices Integration

```typescript
// src/services/marketPricesService.ts

import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL;

export interface MarketPrice {
  commodity: string;
  modal_price: number;
  min_price: number;
  max_price: number;
  market: string;
  state: string;
  date: string;
  unit: string;
  change_percent: number | null;
}

class MarketPricesService {
  async getMarketPrices(
    commodities?: string[],
    state?: string
  ): Promise<MarketPrice[]> {
    try {
      const params: any = {};

      if (commodities && commodities.length > 0) {
        params.commodities = commodities.join(',');
      }

      if (state) {
        params.state = state;
      }

      const response = await axios.get(
        `${API_BASE_URL}/api/v1/public/market-prices`,
        { params }
      );

      return response.data.prices;
    } catch (error) {
      console.error('Failed to fetch market prices:', error);
      return [];
    }
  }
}

export default new MarketPricesService();
```

### Update StoreSelector Component
```typescript
// src/pages/customer/StoreSelector.tsx

import marketPricesService, { MarketPrice } from '../../services/marketPricesService';

const [marketPrices, setMarketPrices] = useState<MarketPrice[]>([]);
const [loadingPrices, setLoadingPrices] = useState(true);

useEffect(() => {
  fetchMarketPrices();
}, []);

const fetchMarketPrices = async () => {
  setLoadingPrices(true);
  try {
    const prices = await marketPricesService.getMarketPrices([
      'Tomato', 'Onion', 'Potato', 'Rice', 'Wheat', 'Milk'
    ]);
    setMarketPrices(prices);
  } catch (error) {
    console.error('Failed to fetch market prices:', error);
  } finally {
    setLoadingPrices(false);
  }
};

// Update the market prices display
{marketPrices.map((item) => (
  <Box key={item.commodity} sx={{ /* styles */ }}>
    <Typography variant="body2" fontWeight={500}>
      {item.commodity}
    </Typography>
    <Box sx={{ textAlign: 'right' }}>
      <Typography variant="body2" fontWeight={600}>
        ₹{item.modal_price}/{item.unit}
      </Typography>
      {item.change_percent !== null && (
        <Typography
          variant="caption"
          sx={{
            color: item.change_percent >= 0 ? 'success.main' : 'error.main',
            fontWeight: 600,
          }}
        >
          {item.change_percent >= 0 ? '+' : ''}{item.change_percent}%
        </Typography>
      )}
    </Box>
  </Box>
))}
```

---

## 6. Implementation Steps

### Phase 1: Location Search (Week 1)
- [ ] Create `indianStates.ts` constants file
- [ ] Implement `/api/v1/location/cities` backend endpoint
- [ ] Update StoreSelector with Autocomplete dropdowns
- [ ] Test state/city dependency
- [ ] Deploy to staging

### Phase 2: Pincode & Landmark (Week 2)
- [ ] Add pincode/landmark fields to DynamoDB stores table
- [ ] Create GSI-4 for pincode search
- [ ] Implement pincode/landmark search in backend
- [ ] Update frontend to support these params
- [ ] Test all search combinations
- [ ] Deploy to staging

### Phase 3: Market Prices (Week 3)
- [ ] Create market_prices_cache DynamoDB table
- [ ] Implement MarketPricesService backend
- [ ] Create `/api/v1/public/market-prices` endpoint
- [ ] Register for data.gov.in API key (if needed for >10 commodities)
- [ ] Implement frontend marketPricesService
- [ ] Update StoreSelector to display live prices
- [ ] Test caching and refresh logic
- [ ] Deploy to staging

### Phase 4: Testing & Production (Week 4)
- [ ] End-to-end testing
- [ ] Performance testing (API latency, caching)
- [ ] Error handling and fallbacks
- [ ] Documentation
- [ ] Deploy to production
- [ ] Monitor API usage and costs

---

## 7. Environment Variables

Add to backend `.env`:
```bash
DATA_GOV_API_KEY=579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b
DATA_GOV_RESOURCE_ID=9ef84268-d588-465a-a308-a864a43d0070
MARKET_PRICES_CACHE_TTL_HOURS=24
```

---

END OF DOCUMENT
