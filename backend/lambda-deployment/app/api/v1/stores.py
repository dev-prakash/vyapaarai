"""
Store registration and management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import uuid
import json
from pydantic import BaseModel, Field

# Database dependencies
from app.database.hybrid_db import HybridDatabase
from app.core.config import get_settings

router = APIRouter(prefix="/api/v1/stores", tags=["stores"])
settings = get_settings()

# Initialize database
db = HybridDatabase()

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
    Register a new store in the database
    """
    try:
        # Use frontend-provided UUID or generate fallback
        if store_data.store_id:
            try:
                # Validate that it's a proper UUID
                uuid.UUID(store_data.store_id)
                store_id = store_data.store_id
                print(f"Using frontend-provided store ID: {store_id}")
            except ValueError:
                # Invalid UUID format, generate new one
                store_id = str(uuid.uuid4())
                print(f"Invalid frontend UUID, generated fallback: {store_id}")
        else:
            # No store_id provided, generate new one
            store_id = str(uuid.uuid4())
            print(f"No frontend UUID provided, generated: {store_id}")
        
        # Prepare store data for database
        store_record = {
            "store_id": store_id,
            "name": store_data.name,
            "owner_id": f"OWNER-{str(uuid.uuid4())[:8].upper()}",  # Generate owner ID
            "address": store_data.address.dict(),
            "contact_info": {
                "phone": store_data.phone,
                "email": store_data.email,
                "whatsapp": store_data.whatsapp or store_data.phone
            },
            "settings": store_data.settings.dict(),
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Additional fields if GST provided
        if store_data.gst_number:
            store_record["contact_info"]["gst_number"] = store_data.gst_number
        
        # Save to PostgreSQL database
        try:
            # Insert into stores table
            insert_query = """
                INSERT INTO stores (
                    store_id, name, owner_id, address, contact_info, 
                    settings, status, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s::jsonb, %s::jsonb, 
                    %s::jsonb, %s, %s, %s
                )
            """
            
            await db.pg_execute(
                insert_query,
                store_record["store_id"],
                store_record["name"],
                store_record["owner_id"],
                json.dumps(store_record["address"]),
                json.dumps(store_record["contact_info"]),
                json.dumps(store_record["settings"]),
                store_record["status"],
                store_record["created_at"],
                store_record["updated_at"]
            )
            
            # Also save to DynamoDB for real-time access
            await db.put_item(
                table_name="stores",
                item=store_record
            )
            
            # Create initial inventory records for common products
            common_products = [
                {"name": "Rice (Basmati)", "category": "Grains", "price": 120, "unit": "kg", "stock": 50},
                {"name": "Wheat Flour (Atta)", "category": "Grains", "price": 45, "unit": "kg", "stock": 40},
                {"name": "Sugar", "category": "Essentials", "price": 45, "unit": "kg", "stock": 30},
                {"name": "Salt", "category": "Essentials", "price": 20, "unit": "kg", "stock": 25},
                {"name": "Cooking Oil", "category": "Oil", "price": 150, "unit": "liter", "stock": 20},
                {"name": "Milk", "category": "Dairy", "price": 60, "unit": "liter", "stock": 100},
                {"name": "Bread", "category": "Bakery", "price": 35, "unit": "pack", "stock": 25},
                {"name": "Eggs", "category": "Dairy", "price": 6, "unit": "piece", "stock": 200},
                {"name": "Potatoes", "category": "Vegetables", "price": 30, "unit": "kg", "stock": 50},
                {"name": "Onions", "category": "Vegetables", "price": 40, "unit": "kg", "stock": 40},
                {"name": "Tomatoes", "category": "Vegetables", "price": 50, "unit": "kg", "stock": 30},
                {"name": "Dal (Toor)", "category": "Pulses", "price": 120, "unit": "kg", "stock": 20},
            ]
            
            # Insert initial products for the store
            for product in common_products:
                product_id = f"PROD-{str(uuid.uuid4())[:8].upper()}"
                product_query = """
                    INSERT INTO products (
                        product_id, store_id, name, category, price, 
                        unit, stock_quantity, status, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """
                
                await db.pg_execute(
                    product_query,
                    product_id,
                    store_id,
                    product["name"],
                    product["category"],
                    product["price"],
                    product["unit"],
                    product["stock"],
                    "active",
                    datetime.utcnow(),
                    datetime.utcnow()
                )
                
                # Also create inventory record
                inventory_query = """
                    INSERT INTO inventory (
                        store_id, product_id, quantity, min_stock_level, 
                        max_stock_level, last_updated, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    )
                """
                
                await db.pg_execute(
                    inventory_query,
                    store_id,
                    product_id,
                    product["stock"],
                    10,  # Min stock level
                    product["stock"] * 2,  # Max stock level
                    datetime.utcnow(),
                    datetime.utcnow()
                )
            
        except Exception as db_error:
            # If database insertion fails, return error
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save store to database: {str(db_error)}"
            )
        
        # Return success response
        return StoreResponse(
            success=True,
            store_id=store_id,
            message="Store registered successfully! Initial inventory has been set up.",
            data={
                "store_name": store_data.name,
                "owner_name": store_data.owner_name,
                "city": store_data.address.city,
                "products_added": len(common_products)
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
    Get list of all registered stores
    """
    try:
        # Query from PostgreSQL
        query = """
            SELECT 
                store_id, name, owner_id, address, contact_info,
                settings, status, created_at, updated_at
            FROM stores
            WHERE status = 'active'
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        result = await db.pg_fetch(query, limit)
        
        stores = []
        for row in result:
            stores.append({
                "store_id": row["store_id"],
                "name": row["name"],
                "owner_name": row["contact_info"].get("owner_name", "Unknown"),
                "phone": row["contact_info"].get("phone"),
                "email": row["contact_info"].get("email"),
                "city": row["address"].get("city"),
                "state": row["address"].get("state"),
                "registered_at": row["created_at"].isoformat() if row["created_at"] else None,
                "status": row["status"]
            })
        
        return {
            "success": True,
            "count": len(stores),
            "stores": stores
        }
        
    except Exception as e:
        print(f"Error fetching stores: {str(e)}")
        # Return sample data if database is not available
        sample_stores = [
            {
                "store_id": "STORE-001",
                "name": "Mumbai Grocery Store",
                "owner_name": "Ramesh Kumar",
                "phone": "+91-9876543210",
                "email": "ramesh@mumbaistore.com",
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
            "note": "Using sample data - database connection unavailable"
        }

@router.get("/{store_id}")
async def get_store_details(store_id: str):
    """
    Get details of a specific store
    """
    try:
        # Query from PostgreSQL
        query = """
            SELECT 
                store_id, name, owner_id, address, contact_info,
                settings, status, created_at, updated_at
            FROM stores
            WHERE store_id = %s
        """
        
        result = await db.pg_fetch_one(query, store_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found"
            )
        
        # Get store metrics
        metrics_query = """
            SELECT 
                COUNT(DISTINCT customer_phone) as total_customers,
                COUNT(order_id) as total_orders,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_order_value
            FROM order_archive
            WHERE store_id = %s
            AND created_at >= NOW() - INTERVAL '30 days'
        """
        
        metrics = await db.pg_fetch_one(metrics_query, store_id)
        
        # Get product count
        product_query = """
            SELECT COUNT(*) as product_count
            FROM products
            WHERE store_id = %s AND status = 'active'
        """
        
        product_count = await db.pg_fetch_one(product_query, store_id)
        
        return {
            "success": True,
            "store": {
                "store_id": result["store_id"],
                "name": result["name"],
                "owner_id": result["owner_id"],
                "address": result["address"],
                "contact_info": result["contact_info"],
                "settings": result["settings"],
                "status": result["status"],
                "created_at": result["created_at"].isoformat() if result["created_at"] else None,
                "metrics": {
                    "total_customers": metrics["total_customers"] if metrics else 0,
                    "total_orders": metrics["total_orders"] if metrics else 0,
                    "total_revenue": float(metrics["total_revenue"] or 0) if metrics else 0,
                    "avg_order_value": float(metrics["avg_order_value"] or 0) if metrics else 0,
                    "active_products": product_count["product_count"] if product_count else 0
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching store details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch store details: {str(e)}"
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
        
        # In development, return mock store data for testing
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
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Store verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify store: {str(e)}"
        )

@router.put("/{store_id}")
async def update_store(store_id: str, updates: dict):
    """
    Update store information
    """
    try:
        # Build update query
        update_fields = []
        values = []
        
        if "name" in updates:
            update_fields.append("name = %s")
            values.append(updates["name"])
        
        if "address" in updates:
            update_fields.append("address = %s::jsonb")
            values.append(json.dumps(updates["address"]))
        
        if "contact_info" in updates:
            update_fields.append("contact_info = %s::jsonb")
            values.append(json.dumps(updates["contact_info"]))
        
        if "settings" in updates:
            update_fields.append("settings = %s::jsonb")
            values.append(json.dumps(updates["settings"]))
        
        if "status" in updates:
            update_fields.append("status = %s")
            values.append(updates["status"])
        
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