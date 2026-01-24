"""
Public API endpoints (no authentication required)
- Market prices
- Location data (states, cities)
"""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
import logging
from app.services.market_prices_service import get_market_prices_service

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== MARKET PRICES ====================

@router.get("/market-prices")
async def get_market_prices(
    commodities: Optional[str] = Query(
        None,
        description="Comma-separated commodity names (e.g., 'Tomato,Onion,Potato')"
    ),
    state: Optional[str] = Query(None, description="State name for regional prices"),
    market: Optional[str] = Query(None, description="Specific market name")
):
    """
    Get current market prices for commodities.

    **Data Source**: data.gov.in (Agmarknet Portal)
    **Update Frequency**: Daily
    **Limit**: 10 commodities per request (public API key)

    **Example**:
    ```
    GET /api/v1/public/market-prices?commodities=Tomato,Onion,Potato
    ```

    **Response**:
    ```json
    {
      "prices": [
        {
          "commodity": "Tomato",
          "modal_price": 40.0,
          "min_price": 35.0,
          "max_price": 45.0,
          "market": "Bangalore",
          "state": "Karnataka",
          "date": "2025-12-02",
          "unit": "kg",
          "change_percent": 5.2
        }
      ],
      "total": 1,
      "source": "data.gov.in (Agmarknet)",
      "last_updated": "2025-12-02"
    }
    ```
    """
    try:
        service = get_market_prices_service()

        # Parse commodity list
        commodity_list = None
        if commodities:
            commodity_list = [c.strip() for c in commodities.split(",") if c.strip()]
            if len(commodity_list) > 10:
                raise HTTPException(
                    status_code=400,
                    detail="Maximum 10 commodities allowed per request with public API key"
                )

        # Fetch prices
        prices = await service.get_market_prices(
            commodities=commodity_list,
            state=state,
            market=market
        )

        return {
            "prices": prices,
            "total": len(prices),
            "source": "data.gov.in (Agmarknet)",
            "last_updated": prices[0]["date"] if prices else None,
            "api_limit": "10 commodities per request"
        }

    except Exception as e:
        logger.error(f"Error fetching market prices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch market prices: {str(e)}")


# ==================== LOCATION DATA ====================

# Mapping of Indian states to major cities
STATE_CITIES = {
    "Andhra Pradesh": [
        "Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool",
        "Kadapa", "Rajahmundry", "Kakinada", "Tirupati", "Anantapur"
    ],
    "Arunachal Pradesh": [
        "Itanagar", "Naharlagun", "Pasighat", "Tawang", "Ziro",
        "Bomdila", "Tezu", "Changlang", "Roing", "Seppa"
    ],
    "Assam": [
        "Guwahati", "Silchar", "Dibrugarh", "Jorhat", "Nagaon",
        "Tinsukia", "Tezpur", "Bongaigaon", "Dhubri", "Goalpara"
    ],
    "Bihar": [
        "Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia",
        "Darbhanga", "Bihar Sharif", "Arrah", "Begusarai", "Katihar"
    ],
    "Chhattisgarh": [
        "Raipur", "Bhilai", "Bilaspur", "Korba", "Durg",
        "Rajnandgaon", "Jagdalpur", "Raigarh", "Ambikapur", "Dhamtari"
    ],
    "Delhi": [
        "New Delhi", "Central Delhi", "North Delhi", "South Delhi", "East Delhi",
        "West Delhi", "North East Delhi", "North West Delhi", "South East Delhi", "South West Delhi"
    ],
    "Goa": [
        "Panaji", "Margao", "Vasco da Gama", "Mapusa", "Ponda",
        "Bicholim", "Curchorem", "Sanquelim", "Valpoi", "Quepem"
    ],
    "Gujarat": [
        "Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar",
        "Jamnagar", "Junagadh", "Gandhinagar", "Anand", "Nadiad"
    ],
    "Haryana": [
        "Faridabad", "Gurgaon", "Hisar", "Rohtak", "Panipat",
        "Karnal", "Sonipat", "Yamunanagar", "Panchkula", "Ambala"
    ],
    "Himachal Pradesh": [
        "Shimla", "Dharamshala", "Solan", "Mandi", "Palampur",
        "Kullu", "Hamirpur", "Una", "Bilaspur", "Chamba"
    ],
    "Jharkhand": [
        "Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Deoghar",
        "Hazaribagh", "Giridih", "Ramgarh", "Medininagar", "Chatra"
    ],
    "Karnataka": [
        "Bangalore", "Mysore", "Mangalore", "Hubli", "Belgaum",
        "Dharwad", "Tumkur", "Bellary", "Bijapur", "Shimoga"
    ],
    "Kerala": [
        "Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Kollam",
        "Palakkad", "Alappuzha", "Kannur", "Kottayam", "Malappuram"
    ],
    "Madhya Pradesh": [
        "Indore", "Bhopal", "Jabalpur", "Gwalior", "Ujjain",
        "Sagar", "Dewas", "Satna", "Ratlam", "Rewa"
    ],
    "Maharashtra": [
        "Mumbai", "Pune", "Nagpur", "Thane", "Nashik",
        "Aurangabad", "Solapur", "Amravati", "Kolhapur", "Sangli"
    ],
    "Manipur": [
        "Imphal", "Thoubal", "Bishnupur", "Churachandpur", "Kakching",
        "Ukhrul", "Senapati", "Tamenglong", "Chandel", "Jiribam"
    ],
    "Meghalaya": [
        "Shillong", "Tura", "Jowai", "Nongstoin", "Baghmara",
        "Williamnagar", "Resubelpara", "Nongpoh", "Mairang", "Cherrapunji"
    ],
    "Mizoram": [
        "Aizawl", "Lunglei", "Champhai", "Serchhip", "Kolasib",
        "Lawngtlai", "Saiha", "Mamit", "Khawzawl", "Zawlnuam"
    ],
    "Nagaland": [
        "Kohima", "Dimapur", "Mokokchung", "Tuensang", "Wokha",
        "Zunheboto", "Phek", "Mon", "Longleng", "Kiphire"
    ],
    "Odisha": [
        "Bhubaneswar", "Cuttack", "Rourkela", "Berhampur", "Sambalpur",
        "Puri", "Balasore", "Bhadrak", "Baripada", "Jharsuguda"
    ],
    "Punjab": [
        "Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda",
        "Mohali", "Pathankot", "Hoshiarpur", "Batala", "Moga"
    ],
    "Rajasthan": [
        "Jaipur", "Jodhpur", "Kota", "Bikaner", "Ajmer",
        "Udaipur", "Bhilwara", "Alwar", "Bharatpur", "Sikar"
    ],
    "Sikkim": [
        "Gangtok", "Namchi", "Gyalshing", "Mangan", "Rangpo",
        "Singtam", "Jorethang", "Nayabazar", "Pelling", "Ravangla"
    ],
    "Tamil Nadu": [
        "Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem",
        "Tirunelveli", "Tiruppur", "Erode", "Vellore", "Thanjavur"
    ],
    "Telangana": [
        "Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam",
        "Ramagundam", "Mahbubnagar", "Nalgonda", "Adilabad", "Suryapet"
    ],
    "Tripura": [
        "Agartala", "Udaipur", "Dharmanagar", "Kailasahar", "Belonia",
        "Khowai", "Ambassa", "Sabroom", "Sonamura", "Teliamura"
    ],
    "Uttar Pradesh": [
        "Lucknow", "Kanpur", "Ghaziabad", "Agra", "Varanasi",
        "Meerut", "Allahabad", "Bareilly", "Aligarh", "Moradabad"
    ],
    "Uttarakhand": [
        "Dehradun", "Haridwar", "Roorkee", "Haldwani", "Rudrapur",
        "Kashipur", "Rishikesh", "Kotdwar", "Ramnagar", "Pithoragarh"
    ],
    "West Bengal": [
        "Kolkata", "Howrah", "Durgapur", "Asansol", "Siliguri",
        "Darjeeling", "Jalpaiguri", "Malda", "Bardhaman", "Kharagpur"
    ]
}


@router.get("/cities")
async def get_cities_by_state(
    state: str = Query(..., description="State name (e.g., 'Karnataka')")
):
    """
    Get list of major cities for a given Indian state.

    **Example**:
    ```
    GET /api/v1/public/cities?state=Karnataka
    ```

    **Response**:
    ```json
    {
      "state": "Karnataka",
      "cities": ["Bangalore", "Mysore", "Mangalore", ...],
      "total": 10
    }
    ```
    """
    # Normalize state name
    state = state.strip()

    # Find matching state (case-insensitive)
    cities = None
    matched_state = None

    for state_key in STATE_CITIES.keys():
        if state_key.lower() == state.lower():
            cities = STATE_CITIES[state_key]
            matched_state = state_key
            break

    if not cities:
        # Try partial match
        for state_key in STATE_CITIES.keys():
            if state.lower() in state_key.lower() or state_key.lower() in state.lower():
                cities = STATE_CITIES[state_key]
                matched_state = state_key
                break

    if not cities:
        return {
            "state": state,
            "cities": [],
            "total": 0,
            "message": f"No cities found for state: {state}"
        }

    # Sort alphabetically
    cities = sorted(cities)

    return {
        "state": matched_state,
        "cities": cities,
        "total": len(cities)
    }


@router.get("/states")
async def get_indian_states():
    """
    Get list of all Indian states and union territories.

    **Example**:
    ```
    GET /api/v1/public/states
    ```

    **Response**:
    ```json
    {
      "states": ["Andhra Pradesh", "Arunachal Pradesh", ...],
      "total": 36
    }
    ```
    """
    states = sorted(STATE_CITIES.keys())

    return {
        "states": states,
        "total": len(states)
    }
