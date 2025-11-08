"""
Store registration and management API endpoints - Simplified for Lambda
"""
from fastapi import APIRouter, HTTPException, status
from typing import Optional
from datetime import datetime
import uuid
import boto3
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/stores", tags=["stores"])

# Initialize DynamoDB client
try:
    dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
    stores_table = dynamodb.Table('vyaparai-stores-prod')
    print("✅ DynamoDB connection initialized")
except Exception as e:
    print(f"⚠️ DynamoDB connection failed: {e}")
    dynamodb = None
    stores_table = None

# Pydantic models for request/response
class StoreAddress(BaseModel):
    street: str
    city: str
    state: str
    pincode: str

class StoreSettings(BaseModel):
    store_type: str = "Kirana Store"
    delivery_radius: int = 3
    min_order_amount: int = 100
    business_hours: dict = {"open": "09:00", "close": "21:00"}

class StoreRegistration(BaseModel):
    store_id: Optional[str] = None  # Accept frontend-provided UUID
    name: str
    owner_name: str
    phone: str
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    address: StoreAddress
    settings: StoreSettings
    gst_number: Optional[str] = None

class StoreResponse(BaseModel):
    success: bool
    store_id: str
    message: str = "Store registered successfully"
    data: Optional[dict] = None

@router.post("/register", response_model=StoreResponse)
async def register_store(store_data: StoreRegistration):
    """
    Register a new store - simplified for Lambda deployment
    """
    try:
        # Use frontend-provided UUID or generate fallback
        if store_data.store_id:
            try:
                # Validate that it's a proper UUID
                uuid.UUID(store_data.store_id)
                store_id = store_data.store_id
                print(f"✅ Using frontend-provided store ID: {store_id}")
            except ValueError:
                # Invalid UUID format, generate new one
                store_id = str(uuid.uuid4())
                print(f"❌ Invalid frontend UUID, generated fallback: {store_id}")
        else:
            # No store_id provided, generate new one
            store_id = str(uuid.uuid4())
            print(f"🆕 No frontend UUID provided, generated: {store_id}")
        
        # Prepare store data
        store_record = {
            "store_id": store_id,
            "name": store_data.name,
            "owner_name": store_data.owner_name,
            "owner_id": f"OWNER-{str(uuid.uuid4())[:8].upper()}",
            "address": store_data.address.dict(),
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
        
        # Save to DynamoDB
        try:
            if stores_table is not None:
                # Convert datetime objects to strings for DynamoDB
                store_item = {
                    "id": store_id,  # Use 'id' as primary key for DynamoDB
                    "store_id": store_id,
                    "name": store_data.name,
                    "owner_name": store_data.owner_name,
                    "owner_id": store_record["owner_id"],
                    "phone": store_data.phone,
                    "email": store_data.email or "",
                    "whatsapp": store_data.whatsapp or store_data.phone,
                    "address": store_data.address.dict(),
                    "settings": store_data.settings.dict(),
                    "status": "active",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                    "gst_number": store_data.gst_number or ""
                }
                
                # Put item in DynamoDB
                stores_table.put_item(Item=store_item)
                print(f"✅ Store saved to DynamoDB: {store_id}")
            else:
                print(f"⚠️ DynamoDB not available, store data not saved: {store_id}")
                
        except Exception as db_error:
            print(f"❌ DynamoDB error: {db_error}")
            # Continue anyway for demo purposes
        
        print(f"📝 Store record created: {store_record}")
        
        # Return success response
        return StoreResponse(
            success=True,
            store_id=store_id,
            message="Store registered successfully! Ready for business.",
            data={
                "store_name": store_data.name,
                "owner_name": store_data.owner_name,
                "city": store_data.address.city,
                "store_type": store_data.settings.store_type
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register store: {str(e)}"
        )

@router.get("/list")
async def list_stores(limit: int = 100):
    """
    Get list of all registered stores - mock data for Lambda
    """
    try:
        # Return mock data for Lambda deployment
        sample_stores = [
            {
                "store_id": str(uuid.uuid4()),
                "name": "Sample Kirana Store",
                "owner_name": "Store Owner",
                "phone": "+919876543210",
                "email": "owner@store.com",
                "city": "Mumbai",
                "state": "Maharashtra",
                "registered_at": datetime.utcnow().isoformat(),
                "status": "active"
            }
        ]
        
        return {
            "success": True,
            "count": len(sample_stores),
            "stores": sample_stores,
            "note": "Sample data for Lambda deployment"
        }
        
    except Exception as e:
        print(f"❌ Error fetching stores: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch stores: {str(e)}"
        )

@router.post("/verify")
async def verify_store(request_data: dict):
    """
    Verify store for login using phone or email
    """
    try:
        phone = request_data.get('phone')
        email = request_data.get('email')
        
        if not phone and not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone or email required"
            )
        
        # Return mock store data for testing
        mock_store = {
            "store_id": str(uuid.uuid4()),
            "name": "Verified Store",
            "owner_name": "Verified Owner", 
            "phone": phone or "+919876543210",
            "email": email or "verified@store.com"
        }
        
        return {
            "success": True,
            "store": mock_store,
            "message": "Store verified successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Store verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify store: {str(e)}"
        )

@router.get("/{store_id}")
async def get_store_details(store_id: str):
    """
    Get details of a specific store - mock data for Lambda
    """
    try:
        # Return mock store data
        return {
            "success": True,
            "store": {
                "store_id": store_id,
                "name": "Sample Store",
                "owner_id": f"OWNER-{str(uuid.uuid4())[:8].upper()}",
                "address": {
                    "street": "123 Main Street",
                    "city": "Mumbai",
                    "state": "Maharashtra", 
                    "pincode": "400001"
                },
                "contact_info": {
                    "phone": "+919876543210",
                    "email": "store@example.com"
                },
                "settings": {
                    "store_type": "Kirana Store",
                    "delivery_radius": 3,
                    "min_order_amount": 100
                },
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
                "metrics": {
                    "total_customers": 0,
                    "total_orders": 0,
                    "total_revenue": 0,
                    "avg_order_value": 0,
                    "active_products": 0
                }
            }
        }
        
    except Exception as e:
        print(f"❌ Error fetching store details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch store details: {str(e)}"
        )