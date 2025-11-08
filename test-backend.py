#!/usr/bin/env python3
"""
Simple test backend to verify frontend changes
Run with: python3 test-backend.py
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid
import uvicorn
from datetime import datetime

app = FastAPI(title="Test VyapaarAI Backend")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
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

# Routes
@app.get("/")
async def root():
    return {"message": "Test VyapaarAI Backend", "version": "test-1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/stores/register", response_model=StoreResponse)
async def register_store(store_data: StoreRegistration):
    """
    Test store registration with UUID support
    """
    print(f"Received store registration: {store_data.dict()}")
    
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
        
        # Return success response
        return StoreResponse(
            success=True,
            store_id=store_id,
            message="Store registered successfully with UUID!",
            data={
                "store_name": store_data.name,
                "owner_name": store_data.owner_name,
                "city": store_data.address.city,
                "uuid_format": "proper" if len(store_id) > 20 else "legacy"
            }
        )
        
    except Exception as e:
        print(f"❌ Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to register store: {str(e)}")

@app.post("/api/v1/stores/verify")
async def verify_store(request_data: dict):
    """
    Test store verification for login
    """
    print(f"Store verification request: {request_data}")
    
    phone = request_data.get('phone')
    email = request_data.get('email')
    
    # Mock store verification - always return success for testing
    if phone or email:
        mock_store = {
            "store_id": str(uuid.uuid4()),
            "name": "Test Store",
            "owner_name": "Test Owner",
            "phone": phone or "+919876543210",
            "email": email or "test@example.com"
        }
        
        return {
            "success": True,
            "store": mock_store,
            "message": "Store verified successfully"
        }
    else:
        raise HTTPException(status_code=400, detail="Phone or email required")

@app.get("/api/v1/stores/{store_id}")
async def get_store(store_id: str):
    """
    Get store details
    """
    return {
        "success": True,
        "store": {
            "store_id": store_id,
            "name": "Test Store",
            "owner_name": "Test Owner",
            "metrics": {
                "total_orders": 0,
                "total_revenue": 0,
                "total_customers": 0,
                "active_products": 0
            }
        }
    }

@app.post("/api/v1/auth/send-email-passcode")
async def send_email_passcode(request_data: dict):
    """
    Mock email passcode sending - for testing
    """
    email = request_data.get('email')
    print(f"📧 Mock email passcode sent to: {email}")
    print(f"🔑 Test passcode: 123456")
    
    return {
        "success": True,
        "message": "Email passcode sent successfully",
        "test_passcode": "123456"  # For testing purposes
    }

@app.post("/api/v1/auth/verify-email-passcode")
async def verify_email_passcode(request_data: dict):
    """
    Mock email passcode verification - for testing
    """
    email = request_data.get('email')
    passcode = request_data.get('passcode')
    
    print(f"📧 Verifying email passcode for: {email}, code: {passcode}")
    
    # Accept 123456 as valid test passcode
    if passcode == "123456":
        return {
            "success": True,
            "message": "Email passcode verified successfully",
            "token": "test-auth-token-" + str(uuid.uuid4())[:8]
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid passcode")

@app.get("/api/v1/orders")
async def get_orders(store_id: Optional[str] = None):
    """
    Get orders - return empty for testing
    """
    return {
        "success": True,
        "orders": [],  # Empty orders to test real empty state
        "total": 0,
        "message": "No orders found - this is the real empty state!"
    }

if __name__ == "__main__":
    print("🚀 Starting Test VyapaarAI Backend...")
    print("📝 Features:")
    print("   ✅ UUID Store Registration")
    print("   ✅ Store Verification")
    print("   ✅ Email Passcode (test code: 123456)")
    print("   ✅ Empty Orders (for testing real empty state)")
    print("   ✅ CORS enabled for frontend")
    print("")
    print("🌐 Frontend should use: http://localhost:8001/api/v1")
    print("📊 Test at: http://localhost:8001/docs")
    print("")
    
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")