from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from decimal import Decimal
import json

from app.services.inventory_service import InventoryService

router = APIRouter()
inventory_service = InventoryService()

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    subcategory: Optional[str] = None
    price: float
    mrp: Optional[float] = None
    cost_price: Optional[float] = None
    current_stock: int = 0
    min_stock_level: int = 10
    max_stock_level: int = 1000
    unit: str = "piece"
    brand: Optional[str] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_contact: Optional[str] = None
    supplier_email: Optional[str] = None
    is_featured: bool = False

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    price: Optional[float] = None
    mrp: Optional[float] = None
    cost_price: Optional[float] = None
    min_stock_level: Optional[int] = None
    max_stock_level: Optional[int] = None
    unit: Optional[str] = None
    brand: Optional[str] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_contact: Optional[str] = None
    supplier_email: Optional[str] = None
    is_featured: Optional[bool] = None
    status: Optional[str] = None

class StockUpdate(BaseModel):
    quantity: int
    movement_type: str  # "in", "out", "set", "adjustment"
    reason: Optional[str] = None
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None

class BulkStockUpdate(BaseModel):
    updates: List[Dict[str, Any]]

@router.get("/products")
async def list_products(
    category: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """List products with filtering and pagination"""
    
    try:
        result = inventory_service.get_all_products(category, status, search, page, limit)
        
        return {
            "success": True,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get products: {str(e)}")

@router.get("/products/{product_id}")
async def get_product(product_id: str):
    """Get product by ID"""
    
    try:
        product = inventory_service.get_product_by_id(product_id)
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return {
            "success": True,
            "product": product
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get product: {str(e)}")

@router.post("/products")
async def create_product(product_data: ProductCreate):
    """Create new product"""
    
    try:
        result = inventory_service.create_product(product_data.dict())
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Product creation failed: {str(e)}")

@router.put("/products/{product_id}")
async def update_product(product_id: str, update_data: ProductUpdate):
    """Update product details"""
    
    try:
        # Filter out None values
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        
        result = inventory_service.update_product(product_id, update_dict)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Product update failed: {str(e)}")

@router.put("/products/{product_id}/stock")
async def update_stock(product_id: str, stock_update: StockUpdate):
    """Update product stock levels"""
    
    try:
        result = inventory_service.update_stock(
            product_id,
            stock_update.quantity,
            stock_update.movement_type,
            stock_update.reason,
            stock_update.reference_id,
            stock_update.reference_type
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stock update failed: {str(e)}")

@router.get("/products/{product_id}/availability/{quantity}")
async def check_availability(product_id: str, quantity: int):
    """Check product availability for given quantity"""
    
    try:
        result = inventory_service.check_availability(product_id, quantity)
        
        return {
            "success": True,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Availability check failed: {str(e)}")

@router.get("/products/low-stock")
async def get_low_stock_products():
    """Get products with low stock levels"""
    
    try:
        products = inventory_service.get_low_stock_products()
        
        return {
            "success": True,
            "low_stock_products": products,
            "count": len(products)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get low stock products: {str(e)}")

@router.get("/products/{product_id}/stock-history")
async def get_stock_history(product_id: str, limit: int = Query(50, ge=1, le=100)):
    """Get stock movement history"""
    
    try:
        movements = inventory_service.get_stock_history(product_id, limit)
        
        return {
            "success": True,
            "stock_history": movements,
            "count": len(movements)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stock history: {str(e)}")

@router.post("/products/bulk-stock-update")
async def bulk_update_stock(bulk_update: BulkStockUpdate):
    """Bulk update stock for multiple products"""
    
    try:
        result = inventory_service.bulk_update_stock(bulk_update.updates)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk stock update failed: {str(e)}")

@router.get("/inventory/summary")
async def get_inventory_summary():
    """Get inventory summary statistics"""
    
    try:
        summary = inventory_service.get_inventory_summary()
        
        return {
            "success": True,
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get inventory summary: {str(e)}")

@router.get("/products/categories")
async def get_product_categories():
    """Get all product categories"""
    
    try:
        # Mock categories for now
        categories = [
            {"id": "cat_001", "name": "Grains", "description": "Rice, wheat, flour"},
            {"id": "cat_002", "name": "Essentials", "description": "Oil, sugar, salt"},
            {"id": "cat_003", "name": "Dairy", "description": "Milk, curd, butter"},
            {"id": "cat_004", "name": "Vegetables", "description": "Fresh vegetables"},
            {"id": "cat_005", "name": "Fruits", "description": "Fresh fruits"},
            {"id": "cat_006", "name": "Beverages", "description": "Tea, coffee, juices"},
            {"id": "cat_007", "name": "Snacks", "description": "Chips, biscuits, namkeen"},
            {"id": "cat_008", "name": "Personal Care", "description": "Soap, shampoo, toothpaste"}
        ]
        
        return {
            "success": True,
            "categories": categories,
            "count": len(categories)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")

@router.get("/products/units")
async def get_product_units():
    """Get available product units"""
    
    try:
        units = [
            {"value": "kg", "label": "Kilogram"},
            {"value": "gram", "label": "Gram"},
            {"value": "liter", "label": "Liter"},
            {"value": "ml", "label": "Milliliter"},
            {"value": "piece", "label": "Piece"},
            {"value": "packet", "label": "Packet"},
            {"value": "box", "label": "Box"},
            {"value": "dozen", "label": "Dozen"},
            {"value": "bottle", "label": "Bottle"},
            {"value": "can", "label": "Can"}
        ]
        
        return {
            "success": True,
            "units": units,
            "count": len(units)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get units: {str(e)}")

@router.delete("/products/{product_id}")
async def delete_product(product_id: str):
    """Delete product (soft delete by setting status to inactive)"""
    
    try:
        result = inventory_service.update_product(product_id, {"status": "inactive"})
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "message": "Product deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Product deletion failed: {str(e)}")

@router.post("/products/{product_id}/restore")
async def restore_product(product_id: str):
    """Restore inactive product"""
    
    try:
        result = inventory_service.update_product(product_id, {"status": "active"})
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "message": "Product restored successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Product restoration failed: {str(e)}")

