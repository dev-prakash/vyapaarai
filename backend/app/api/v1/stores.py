"""
Store registration and management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import json
import re
import os
import hashlib
import secrets
from pydantic import BaseModel, Field, validator
from ulid import ULID

# Database dependencies
from app.database.hybrid_db import HybridDatabase
from app.core.config import settings
from app.core.validation import (
    validate_phone_indian, validate_email, sanitize_string,
    check_injection_patterns, sanitize_html_content,
    MAX_NAME_LENGTH, MAX_ADDRESS_LENGTH, MAX_DESCRIPTION_LENGTH
)
from app.core.security import get_current_store_owner
from app.core.database import get_dynamodb, STORES_TABLE, SESSIONS_TABLE
from app.services.store_search_service import store_search_service
from app.services.geocoding_service import geocoding_service

router = APIRouter(prefix="/stores", tags=["stores"])

# Initialize database
db = HybridDatabase()

# DynamoDB Configuration - using centralized DatabaseManager
# Initialization happens at module import time (during Lambda INIT phase)
# This provides Lambda-compatible credential handling and connection pooling
_dynamodb = get_dynamodb()
stores_table = _dynamodb.Table(STORES_TABLE) if _dynamodb else None
sessions_table = _dynamodb.Table(SESSIONS_TABLE) if _dynamodb else None

# Store ID generation and validation functions
def generate_store_id() -> str:
    """Generate a ULID-based store ID with STORE- prefix"""
    ulid = str(ULID())
    return f"STORE-{ulid}"

def is_valid_store_id(store_id: str) -> bool:
    """Validate if a string is a valid store ID format"""
    if not store_id:
        return False
    
    # Check ULID-based format: STORE- followed by 26-character ULID
    ulid_pattern = r'^STORE-[0-9A-HJKMNP-TV-Z]{26}$'
    if re.match(ulid_pattern, store_id, re.IGNORECASE):
        return True
    
    # Legacy UUID format support for backward compatibility
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    if re.match(uuid_pattern, store_id, re.IGNORECASE):
        return True
    
    # Legacy STORE- format support (STORE-8CHARS)
    legacy_pattern = r'^STORE-[A-Z0-9]{8}$'
    return bool(re.match(legacy_pattern, store_id, re.IGNORECASE))

# Pydantic models for request/response
class StoreAddress(BaseModel):
    street: str = Field(..., max_length=200)
    city: str = Field(..., max_length=100)
    state: str = Field(..., max_length=100)
    pincode: str = Field(..., max_length=10)

    @validator('street', 'city', 'state', pre=True)
    def sanitize_text_fields(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            return sanitize_string(v, max_length=MAX_ADDRESS_LENGTH, escape_html=True)
        return v

    @validator('pincode')
    def validate_pincode(cls, v):
        if v:
            cleaned = re.sub(r'\s+', '', v)
            if not re.match(r'^\d{6}$', cleaned):
                raise ValueError('Pincode must be 6 digits')
            return cleaned
        return v

class StoreSettings(BaseModel):
    store_type: str = Field(default="Kirana Store", max_length=100)
    delivery_radius: int = Field(default=3, ge=0, le=100)  # 0-100 km
    min_order_amount: int = Field(default=100, ge=0, le=1000000)
    business_hours: dict = Field(default={"open": "09:00", "close": "21:00"})

    @validator('store_type', pre=True)
    def sanitize_store_type(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            return sanitize_string(v, max_length=100, escape_html=True)
        return v

# Enhanced store profile models
class OwnerProfile(BaseModel):
    """Owner profile with bio and background"""
    name: str = Field(..., max_length=100)
    bio: Optional[str] = Field(None, max_length=2000)
    photo_url: Optional[str] = Field(None, max_length=500)
    education: Optional[str] = Field(None, max_length=200)
    experience_years: Optional[int] = Field(None, ge=0, le=100)
    family_members: Optional[list] = None  # e.g., [{"name": "Sunita Sharma", "role": "Co-owner"}]

    @validator('name', 'bio', 'education', pre=True)
    def sanitize_text_fields(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            return sanitize_string(v, max_length=MAX_DESCRIPTION_LENGTH, escape_html=True)
        return v

class HistoryTimeline(BaseModel):
    """Store history timeline entry"""
    year: int = Field(..., ge=1900, le=2100)
    milestone: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=1000)

    @validator('milestone', 'description', pre=True)
    def sanitize_text_fields(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            return sanitize_string(v, max_length=1000, escape_html=True)
        return v

class SocialImpact(BaseModel):
    """Social impact metrics"""
    food_donated_monthly_kg: Optional[int] = Field(None, ge=0, le=1000000)
    children_sponsored: Optional[int] = Field(None, ge=0, le=10000)
    education_fund_amount: Optional[int] = Field(None, ge=0, le=100000000)
    farmers_supported: Optional[int] = Field(None, ge=0, le=100000)
    families_served: Optional[int] = Field(None, ge=0, le=1000000)

class Certification(BaseModel):
    """Business certification"""
    name: str = Field(..., max_length=200)
    number: Optional[str] = Field(None, max_length=50)
    issued_by: Optional[str] = Field(None, max_length=200)
    issued_date: Optional[str] = Field(None, max_length=20)
    expiry_date: Optional[str] = Field(None, max_length=20)
    image_url: Optional[str] = Field(None, max_length=500)

    @validator('name', 'issued_by', pre=True)
    def sanitize_text_fields(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            return sanitize_string(v, max_length=200, escape_html=True)
        return v

class Award(BaseModel):
    """Award or recognition"""
    title: str = Field(..., max_length=200)
    year: int = Field(..., ge=1900, le=2100)
    awarded_by: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)

    @validator('title', 'awarded_by', 'description', pre=True)
    def sanitize_text_fields(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            return sanitize_string(v, max_length=1000, escape_html=True)
        return v

class CommunityProgram(BaseModel):
    """Community program"""
    name: str = Field(..., max_length=200)
    description: str = Field(..., max_length=1000)
    impact: Optional[str] = Field(None, max_length=500)

    @validator('name', 'description', 'impact', pre=True)
    def sanitize_text_fields(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            return sanitize_string(v, max_length=1000, escape_html=True)
        return v

class StoreProfile(BaseModel):
    """Enhanced store profile with trust-building elements"""
    tagline: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    founded_year: Optional[int] = Field(None, ge=1800, le=2100)
    generation: Optional[int] = Field(None, ge=1, le=10)  # 1st, 2nd, 3rd generation
    mission_statement: Optional[str] = Field(None, max_length=1000)
    core_values: Optional[list[str]] = None
    sustainability_initiatives: Optional[list[str]] = None

    @validator('tagline', 'description', 'mission_statement', pre=True)
    def sanitize_text_fields(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            return sanitize_string(v, max_length=MAX_DESCRIPTION_LENGTH, escape_html=True)
        return v

    @validator('core_values', 'sustainability_initiatives', pre=True)
    def sanitize_list_fields(cls, v):
        if v and isinstance(v, list):
            sanitized = []
            for item in v[:20]:  # Max 20 items
                if isinstance(item, str):
                    is_safe, threat_type = check_injection_patterns(item)
                    if not is_safe:
                        raise ValueError('Invalid input detected')
                    sanitized.append(sanitize_string(item, max_length=200, escape_html=True))
            return sanitized
        return v

class MediaImage(BaseModel):
    """Store image"""
    url: str
    caption: Optional[str] = None
    order: int = 1
    is_primary: bool = False

class MediaVideo(BaseModel):
    """Store video"""
    url: str
    thumbnail_url: Optional[str] = None
    caption: Optional[str] = None
    duration_seconds: Optional[int] = None

class MediaContent(BaseModel):
    """Store media content"""
    images: Optional[list[MediaImage]] = None
    videos: Optional[list[MediaVideo]] = None

class RichTextContent(BaseModel):
    """Rich text content with HTML formatting"""
    html: str = Field(..., max_length=50000)  # Allow up to 50KB of HTML
    plain_text: Optional[str] = Field(None, max_length=20000)
    last_updated: Optional[str] = Field(None, max_length=50)
    updated_by: Optional[str] = Field(None, max_length=100)

    @validator('html', pre=True)
    def sanitize_html(cls, v):
        if v:
            # For rich text, we sanitize but allow HTML tags (escaped for storage)
            return sanitize_html_content(v)
        return v

    @validator('plain_text', pre=True)
    def sanitize_plain_text(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            return sanitize_string(v, max_length=20000, escape_html=True)
        return v

class StoreContent(BaseModel):
    """Store content sections with rich text"""
    about: Optional[RichTextContent] = None
    story: Optional[RichTextContent] = None
    values: Optional[RichTextContent] = None
    trust: Optional[RichTextContent] = None

class StoreRegistration(BaseModel):
    store_id: Optional[str] = Field(None, max_length=50)  # Accept frontend-provided UUID
    name: str = Field(..., max_length=200)
    owner_name: str = Field(..., max_length=100)
    phone: str = Field(..., max_length=15)
    email: Optional[str] = Field(None, max_length=254)
    whatsapp: Optional[str] = Field(None, max_length=15)
    address: StoreAddress
    settings: StoreSettings
    gst_number: Optional[str] = Field(None, max_length=20)
    password: Optional[str] = Field(None, min_length=6, max_length=128)  # Login password
    # Enhanced profile fields (optional for backward compatibility)
    owner_profile: Optional[OwnerProfile] = None
    store_profile: Optional[StoreProfile] = None
    history_timeline: Optional[list[HistoryTimeline]] = None
    social_impact: Optional[SocialImpact] = None
    certifications: Optional[list[Certification]] = None
    awards: Optional[list[Award]] = None
    community_programs: Optional[list[CommunityProgram]] = None
    # Rich content fields
    media: Optional[MediaContent] = None
    content: Optional[StoreContent] = None

    @validator('name', 'owner_name', pre=True)
    def sanitize_names(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')
            return sanitize_string(v, max_length=MAX_NAME_LENGTH, escape_html=True, allow_newlines=False)
        return v

    @validator('phone', 'whatsapp')
    def validate_phone_fields(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')

            is_valid, result = validate_phone_indian(v)
            if not is_valid:
                raise ValueError(result)
            return result
        return v

    @validator('email')
    def validate_email_field(cls, v):
        if v:
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError('Invalid input detected')

            is_valid, result = validate_email(v)
            if not is_valid:
                raise ValueError(result)
            return result
        return v

    @validator('gst_number')
    def validate_gst(cls, v):
        if v:
            # GST format: 2 digit state code + 10 char PAN + 1 char entity + Z + checksum
            cleaned = v.strip().upper()
            if not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', cleaned):
                raise ValueError('Invalid GST number format')
            return cleaned
        return v

class StoreResponse(BaseModel):
    success: bool
    store_id: str
    message: str = "Store registered successfully"
    data: Optional[dict] = None

@router.post("/register", response_model=StoreResponse)
async def register_store(store_data: StoreRegistration):
    """
    Register a new store in the database
    """
    try:
        # Validate: if password is provided, email is required for login
        if store_data.password and not store_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required when setting a password. Please provide an email address to enable password login."
            )

        # Use frontend-provided store ID or generate new ULID-based one
        if store_data.store_id:
            # Validate the provided store ID format
            if is_valid_store_id(store_data.store_id):
                store_id = store_data.store_id
                print(f"Using frontend-provided store ID: {store_id}")
            else:
                # Invalid format, generate new ULID-based one
                store_id = generate_store_id()
                print(f"Invalid frontend store ID format, generated ULID-based fallback: {store_id}")
        else:
            # No store_id provided, generate new ULID-based one
            store_id = generate_store_id()
            print(f"No frontend store ID provided, generated ULID-based: {store_id}")
        
        # Auto-geocode store address to get lat/lng
        address_dict = store_data.address.dict()
        latitude = None
        longitude = None

        try:
            geocode_result = await geocoding_service.geocode_address(
                street=address_dict.get('street', ''),
                city=address_dict.get('city', ''),
                state=address_dict.get('state', ''),
                pincode=address_dict.get('pincode', '')
            )

            if geocode_result:
                latitude = geocode_result.get('latitude')
                longitude = geocode_result.get('longitude')
                print(f"[Store Registration] Geocoded address: ({latitude}, {longitude})")
            else:
                print(f"[Store Registration] Geocoding failed for address, continuing without coordinates")
        except Exception as geo_error:
            print(f"[Store Registration] Geocoding error: {str(geo_error)}, continuing without coordinates")

        # Prepare store data for database
        store_record = {
            "id": store_id,  # DynamoDB partition key
            "store_id": store_id,
            "name": store_data.name,
            "owner_id": f"OWNER-{str(uuid.uuid4())[:8].upper()}",  # Generate owner ID
            "owner_name": store_data.owner_name,
            "address": address_dict,
            "latitude": latitude,
            "longitude": longitude,
            "contact_info": {
                "phone": store_data.phone,
                "email": store_data.email,
                "whatsapp": store_data.whatsapp or store_data.phone
            },
            "settings": store_data.settings.dict(),
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Additional fields if GST provided
        if store_data.gst_number:
            store_record["contact_info"]["gst_number"] = store_data.gst_number

        # Enhanced profile fields (backward compatible - only add if provided)
        if store_data.owner_profile:
            store_record["owner_profile"] = store_data.owner_profile.dict()

        if store_data.store_profile:
            store_record["store_profile"] = store_data.store_profile.dict()

        if store_data.history_timeline:
            store_record["history_timeline"] = [item.dict() for item in store_data.history_timeline]

        if store_data.social_impact:
            store_record["social_impact"] = store_data.social_impact.dict()

        if store_data.certifications:
            store_record["certifications"] = [cert.dict() for cert in store_data.certifications]

        if store_data.awards:
            store_record["awards"] = [award.dict() for award in store_data.awards]

        if store_data.community_programs:
            store_record["community_programs"] = [program.dict() for program in store_data.community_programs]
        
        # Save to DynamoDB
        try:
            if not stores_table:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database not available"
                )

            # Save to DynamoDB stores table
            stores_table.put_item(Item=store_record)

            # If password provided, hash and store it for login
            if store_data.password and store_data.email and sessions_table:
                # Generate salt and hash password
                salt = secrets.token_hex(16)
                hash_input = f"{salt}{store_data.password}".encode('utf-8')
                password_hash = hashlib.sha256(hash_input).hexdigest()

                # Store password hash in sessions table (keyed by email)
                password_key = f"password_{store_data.email.lower()}"
                sessions_table.put_item(Item={
                    'pk': password_key,
                    'password_hash': f"{salt}${password_hash}",
                    'store_id': store_id,
                    'created_at': datetime.utcnow().isoformat()
                })

        except Exception as db_error:
            # If database insertion fails, return error
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save store to database: {str(db_error)}"
            )

        # Return success response
        password_msg = " Your login password has been set." if store_data.password and store_data.email else ""
        return StoreResponse(
            success=True,
            store_id=store_id,
            message=f"Store registered successfully!{password_msg} You can now add your inventory.",
            data={
                "store_name": store_data.name,
                "owner_name": store_data.owner_name,
                "city": store_data.address.city,
                "has_password": bool(store_data.password and store_data.email)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register store: {str(e)}"
        )

@router.get("/list")
async def list_stores(limit: int = 100):
    """
    Get list of all registered stores from DynamoDB
    """
    try:
        # Scan DynamoDB table
        response = stores_table.scan(
            FilterExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'active'},
            Limit=limit
        )

        stores = []
        for item in response.get('Items', []):
            # Parse address JSON string
            address = {}
            if 'address' in item:
                try:
                    address = json.loads(item['address']) if isinstance(item['address'], str) else item['address']
                except:
                    address = {}

            # Parse settings JSON string
            settings_obj = {}
            if 'settings' in item:
                try:
                    settings_obj = json.loads(item['settings']) if isinstance(item['settings'], str) else item['settings']
                except:
                    settings_obj = {}

            stores.append({
                "id": item.get('id', item.get('store_id', '')),
                "store_id": item.get('store_id', item.get('id', '')),
                "name": item.get('name', ''),
                "owner_name": item.get('owner_name', ''),
                "phone": item.get('phone', ''),
                "email": item.get('email', ''),
                "city": address.get('city', ''),
                "state": address.get('state', ''),
                "address": {
                    "full": f"{address.get('street', '')}, {address.get('city', '')}, {address.get('state', '')} {address.get('pincode', '')}".strip(),
                    "street": address.get('street', ''),
                    "city": address.get('city', ''),
                    "state": address.get('state', ''),
                    "pincode": address.get('pincode', '')
                },
                "latitude": float(item.get('latitude', 0)) if 'latitude' in item else None,
                "longitude": float(item.get('longitude', 0)) if 'longitude' in item else None,
                "category": settings_obj.get('store_type', 'General Store'),
                "rating": 4.5,
                "isOpen": True,
                "openingHours": f"{settings_obj.get('business_hours', {}).get('open', '09:00')} - {settings_obj.get('business_hours', {}).get('close', '21:00')}",
                "registered_at": item.get('created_at', ''),
                "status": item.get('status', 'active')
            })

        print(f"[/list] Found {len(stores)} stores from DynamoDB")

        return {
            "success": True,
            "count": len(stores),
            "stores": stores
        }

    except Exception as e:
        print(f"Error fetching stores from DynamoDB: {str(e)}")
        import traceback
        traceback.print_exc()

        # Return empty result on error
        return {
            "success": False,
            "count": 0,
            "stores": [],
            "error": str(e)
        }

@router.get("/nearby")
async def get_nearby_stores(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius: Optional[int] = 10,
    city: Optional[str] = None,
    state: Optional[str] = None,
    pincode: Optional[str] = None,
    landmark: Optional[str] = None,
    name: Optional[str] = None,
    limit: Optional[int] = 50
):
    """
    Enhanced store search with fuzzy name matching and geocoded location search.

    Search Priority:
    1. Store name (fuzzy) - Returns exact matches first, then similar names
    2. GPS coordinates (lat/lng) - Radius-based search
    3. Pincode - Exact matches first, then nearby stores within radius
    4. Landmark/Area - Exact matches first, then nearby stores within radius
    5. City/State - Filter by location

    Args:
        lat: Latitude for GPS-based search
        lng: Longitude for GPS-based search
        radius: Search radius in kilometers (default: 10, max: 50)
        city: City name for filtering
        state: State name for filtering
        pincode: Pincode for location search (returns exact + nearby)
        landmark: Landmark or area name (returns exact + nearby)
        name: Store name for fuzzy search
        limit: Maximum stores to return (default: 50)

    Returns:
        Filtered stores with exact matches first, then nearby stores sorted by distance.
    """
    try:
        # Get all stores first
        all_stores_response = await list_stores(limit=500)
        all_stores = all_stores_response.get('stores', [])

        if not all_stores:
            return {
                "success": True,
                "stores": [],
                "count": 0,
                "metadata": {"total_stores": 0}
            }

        # Use enhanced search service
        search_result = await store_search_service.search_stores(
            stores=all_stores,
            name=name,
            pincode=pincode,
            landmark=landmark,
            city=city,
            state=state,
            lat=lat,
            lng=lng,
            radius=radius,
            limit=limit or 50
        )

        print(f"[/nearby] Search completed: {search_result.get('count')} stores found")
        print(f"[/nearby] Metadata: {search_result.get('metadata')}")

        return search_result

    except Exception as e:
        print(f"[/nearby] Error fetching stores: {str(e)}")
        import traceback
        traceback.print_exc()

        # Return empty result on error
        return {
            "success": True,
            "stores": [],
            "count": 0
        }

@router.get("/{store_id}")
async def get_store_details(store_id: str):
    """
    Get details of a specific store from DynamoDB
    """
    try:
        print(f"[get_store_details] Fetching store: {store_id}")

        # Query from DynamoDB - table uses 'id' as primary key, not 'store_id'
        response = stores_table.get_item(
            Key={'id': store_id}
        )

        if 'Item' not in response:
            print(f"[get_store_details] Store not found in DynamoDB: {store_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found"
            )

        item = response['Item']
        print(f"[get_store_details] Found store, parsing fields...")

        # Parse address JSON string if needed
        address = {}
        if 'address' in item:
            try:
                address = json.loads(item['address']) if isinstance(item['address'], str) else item['address']
            except:
                address = {}

        # Parse settings JSON string if needed
        settings_obj = {}
        if 'settings' in item:
            try:
                settings_obj = json.loads(item['settings']) if isinstance(item['settings'], str) else item['settings']
            except:
                settings_obj = {}

        # Parse contact_info JSON string if needed
        contact_info = {}
        if 'contact_info' in item:
            try:
                contact_info = json.loads(item['contact_info']) if isinstance(item['contact_info'], str) else item['contact_info']
            except:
                contact_info = item.get('contact_info', {})

        # Parse enhanced profile fields (backward compatible)
        owner_profile = {}
        if 'owner_profile' in item:
            try:
                owner_profile = json.loads(item['owner_profile']) if isinstance(item['owner_profile'], str) else item['owner_profile']
            except:
                owner_profile = item.get('owner_profile', {})

        store_profile = {}
        if 'store_profile' in item:
            try:
                store_profile = json.loads(item['store_profile']) if isinstance(item['store_profile'], str) else item['store_profile']
            except:
                store_profile = item.get('store_profile', {})

        history_timeline = []
        if 'history_timeline' in item:
            try:
                history_timeline = json.loads(item['history_timeline']) if isinstance(item['history_timeline'], str) else item['history_timeline']
            except:
                history_timeline = item.get('history_timeline', [])

        social_impact = {}
        if 'social_impact' in item:
            try:
                social_impact = json.loads(item['social_impact']) if isinstance(item['social_impact'], str) else item['social_impact']
            except:
                social_impact = item.get('social_impact', {})

        certifications = []
        if 'certifications' in item:
            try:
                certifications = json.loads(item['certifications']) if isinstance(item['certifications'], str) else item['certifications']
            except:
                certifications = item.get('certifications', [])

        awards = []
        if 'awards' in item:
            try:
                awards = json.loads(item['awards']) if isinstance(item['awards'], str) else item['awards']
            except:
                awards = item.get('awards', [])

        community_programs = []
        if 'community_programs' in item:
            try:
                community_programs = json.loads(item['community_programs']) if isinstance(item['community_programs'], str) else item['community_programs']
            except:
                community_programs = item.get('community_programs', [])

        # Parse new media and content fields
        media = {}
        if 'media' in item:
            try:
                media = json.loads(item['media']) if isinstance(item['media'], str) else item['media']
            except:
                media = item.get('media', {})

        content = {}
        if 'content' in item:
            try:
                content = json.loads(item['content']) if isinstance(item['content'], str) else item['content']
            except:
                content = item.get('content', {})

        print(f"[get_store_details] All fields parsed, building response...")

        # Build response with comprehensive error handling
        try:
            store_response = {
                "success": True,
                "store": {
                    "id": item.get('id', item.get('store_id', '')),
                    "store_id": item.get('store_id', item.get('id', '')),
                    "name": item.get('name', ''),
                    "owner_name": item.get('owner_name', ''),
                    "phone": item.get('phone', contact_info.get('phone', '')),
                    "email": item.get('email', contact_info.get('email', '')),
                    "category": settings_obj.get('store_type', 'General Store'),
                    "address": {
                        "full": f"{address.get('street', '')}, {address.get('city', '')}, {address.get('state', '')} {address.get('pincode', '')}".strip(),
                        "street": address.get('street', ''),
                        "city": address.get('city', ''),
                        "state": address.get('state', ''),
                        "pincode": address.get('pincode', ''),
                        "latitude": str(item.get('latitude', '')) if 'latitude' in item else None,
                        "longitude": str(item.get('longitude', '')) if 'longitude' in item else None
                    },
                    "isOpen": True,
                    "openStatus": "Open",
                    "rating": 4.5,
                    "rating_count": 0,
                    "openingHours": f"{settings_obj.get('business_hours', {}).get('open', '09:00')} - {settings_obj.get('business_hours', {}).get('close', '21:00')}",
                    "status": item.get('status', 'active'),
                    # Include empty products and reviews arrays for frontend compatibility
                    "products": [],
                    "reviews": [],
                    "total_products": 0,
                    "description": store_profile.get('description', 'Your neighborhood store'),
                    "tagline": store_profile.get('tagline', ''),
                }
            }

            # Add enhanced profile fields only if they exist (backward compatible)
            if owner_profile:
                store_response["store"]["owner_profile"] = owner_profile
            if store_profile:
                store_response["store"]["store_profile"] = store_profile
            if history_timeline:
                store_response["store"]["history_timeline"] = history_timeline
            if social_impact:
                store_response["store"]["social_impact"] = social_impact
            if certifications:
                store_response["store"]["certifications"] = certifications
            if awards:
                store_response["store"]["awards"] = awards
            if community_programs:
                store_response["store"]["community_programs"] = community_programs

            # Add new media and content fields
            if media:
                store_response["store"]["media"] = media
            if content:
                store_response["store"]["content"] = content

            print(f"[get_store_details] Response built successfully for {store_id}")
            return store_response

        except Exception as build_error:
            print(f"[get_store_details] Error building response: {str(build_error)}")
            import traceback
            traceback.print_exc()
            raise

    except HTTPException:
        raise
    except Exception as e:
        print(f"[get_store_details] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch store details: {str(e)}"
        )

@router.post("/verify")
async def verify_store(request_data: dict):
    """
    Verify store for login using phone or email.
    Checks if store exists and whether a password has been set.
    """
    try:
        phone = request_data.get('phone')
        email = request_data.get('email')

        if not phone and not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone or email required"
            )

        if not stores_table:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Query store by email - check both top-level and contact_info.email
        store = None
        if email:
            email_lower = email.lower()
            try:
                # Scan for email in both top-level and nested contact_info
                response = stores_table.scan(
                    FilterExpression='email = :email OR #ci.#em = :email',
                    ExpressionAttributeNames={'#ci': 'contact_info', '#em': 'email'},
                    ExpressionAttributeValues={':email': email_lower}
                )
                if response.get('Items') and len(response['Items']) > 0:
                    store = response['Items'][0]
                    print(f"[verify_store] Found store by email: {store.get('store_id')}")
            except Exception as e:
                print(f"[verify_store] Email scan error: {e}")
                import traceback
                traceback.print_exc()

        # Query by phone if email search didn't find store
        if not store and phone:
            try:
                # Scan for phone in both top-level and nested contact_info
                response = stores_table.scan(
                    FilterExpression='phone = :phone OR #ci.#ph = :phone',
                    ExpressionAttributeNames={'#ci': 'contact_info', '#ph': 'phone'},
                    ExpressionAttributeValues={':phone': phone}
                )
                if response.get('Items') and len(response['Items']) > 0:
                    store = response['Items'][0]
                    print(f"[verify_store] Found store by phone: {store.get('store_id')}")
            except Exception as e:
                print(f"[verify_store] Phone scan error: {e}")

        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found. Please check your email or register a new store."
            )

        # Check if store owner has a password set
        has_password = False
        lookup_email = email or store.get('email') or store.get('contact_info', {}).get('email')

        if lookup_email and sessions_table:
            try:
                password_key = f"password_{lookup_email}"
                password_response = sessions_table.get_item(
                    Key={'pk': password_key}
                )
                has_password = 'Item' in password_response
                print(f"[verify_store] Password check for {lookup_email}: has_password={has_password}")
            except Exception as e:
                print(f"[verify_store] Password check error: {e}")
                # Continue without password check - don't block verification

        # Build response store data
        store_data = {
            "store_id": store.get('store_id'),
            "name": store.get('name'),
            "owner_name": store.get('owner_name'),
            "phone": store.get('phone') or store.get('contact_info', {}).get('phone'),
            "email": store.get('email') or store.get('contact_info', {}).get('email'),
            "has_password": has_password
        }

        return {
            "success": True,
            "store": store_data,
            "message": "Store verified successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Store verification error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify store: {str(e)}"
        )

class StoreUpdateRequest(BaseModel):
    """Validated store update request"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    address: Optional[Dict[str, Any]] = None
    contact_info: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive|suspended)$")

    @validator('name')
    def sanitize_name(cls, v):
        if v:
            return sanitize_string(v)
        return v


@router.put("/{store_id}")
async def update_store(
    store_id: str,
    updates: StoreUpdateRequest,
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Update store information (Store Owner Only)

    Requires authentication. Store owners can only update their own store.
    """
    # Verify store ownership
    if current_user.get('store_id') and current_user['store_id'] != store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own store"
        )

    try:
        # Build update query from validated model
        update_fields = []
        values = []
        updates_dict = updates.dict(exclude_none=True)

        if "name" in updates_dict:
            update_fields.append("name = %s")
            values.append(updates_dict["name"])

        if "address" in updates_dict:
            update_fields.append("address = %s::jsonb")
            values.append(json.dumps(updates_dict["address"]))

        if "contact_info" in updates_dict:
            update_fields.append("contact_info = %s::jsonb")
            values.append(json.dumps(updates_dict["contact_info"]))

        if "settings" in updates_dict:
            update_fields.append("settings = %s::jsonb")
            values.append(json.dumps(updates_dict["settings"]))

        if "status" in updates_dict:
            update_fields.append("status = %s")
            values.append(updates_dict["status"])

        update_fields.append("updated_at = %s")
        values.append(datetime.utcnow())

        # Add store_id to values
        values.append(store_id)

        query = f"""
            UPDATE stores
            SET {', '.join(update_fields)}
            WHERE store_id = %s
        """

        await db.pg_execute(query, *values)

        return {
            "success": True,
            "message": "Store updated successfully"
        }

    except Exception as e:
        print(f"Error updating store: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update store: {str(e)}"
        )

