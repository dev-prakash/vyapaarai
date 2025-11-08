from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from decimal import Decimal
import json

from app.services.inventory_service import inventory_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


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
    quantity_change: int  # Positive for add, negative for subtract
    reason: Optional[str] = None


class BulkStockUpdate(BaseModel):
    updates: List[Dict[str, Any]]


@router.get("/products")
async def list_products(
    store_id: str = Query(..., description="Store ID"),
    category: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """List products with filtering and pagination"""

    try:
        result = await inventory_service.get_products(
            store_id=store_id,
            category=category,
            status=status,
            search=search,
            page=page,
            limit=limit
        )

        return {
            "success": True,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get products: {str(e)}")


@router.get("/products/{store_id}/{product_id}")
async def get_product(store_id: str, product_id: str):
    """Get product by ID for a specific store"""

    try:
        product = await inventory_service.get_product(store_id, product_id)

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


@router.get("/search")
async def search_products(
    store_id: str = Query(..., description="Store ID"),
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(50, ge=1, le=100)
):
    """Search products by name"""

    try:
        products = await inventory_service.search_products(store_id, q, limit)

        return {
            "success": True,
            "products": products,
            "count": len(products)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.put("/products/{store_id}/{product_id}/stock")
async def update_stock(store_id: str, product_id: str, stock_update: StockUpdate):
    """Update product stock levels"""

    try:
        result = await inventory_service.update_stock(
            store_id=store_id,
            product_id=product_id,
            quantity_change=stock_update.quantity_change,
            reason=stock_update.reason
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Stock update failed"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stock update failed: {str(e)}")


@router.get("/products/{store_id}/{product_id}/availability")
async def check_availability(store_id: str, product_id: str, quantity: int = Query(..., ge=1)):
    """Check product availability for given quantity"""

    try:
        result = await inventory_service.check_availability(store_id, product_id, quantity)

        return {
            "success": True,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Availability check failed: {str(e)}")


@router.get("/low-stock")
async def get_low_stock_products(
    store_id: str = Query(..., description="Store ID"),
    threshold: Optional[int] = None
):
    """Get products with low stock levels"""

    try:
        products = await inventory_service.get_low_stock_products(store_id, threshold)

        return {
            "success": True,
            "low_stock_products": products,
            "count": len(products)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get low stock products: {str(e)}")


@router.get("/barcode/{barcode}")
async def get_product_by_barcode(barcode: str):
    """Search product by barcode in global catalog"""

    try:
        product = await inventory_service.get_product_by_barcode(barcode)

        if not product:
            raise HTTPException(status_code=404, detail="Product not found with this barcode")

        return {
            "success": True,
            "product": product
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Barcode search failed: {str(e)}")


@router.get("/summary")
async def get_inventory_summary(store_id: str = Query(..., description="Store ID")):
    """Get inventory summary statistics"""

    try:
        summary = await inventory_service.get_inventory_summary(store_id)

        return {
            "success": True,
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get inventory summary: {str(e)}")


@router.get("/categories")
async def get_product_categories():
    """Get all product categories"""

    try:
        # These are common categories - could be pulled from DynamoDB in future
        categories = [
            {"id": "cat_001", "name": "Grains & Cereals", "description": "Rice, wheat, flour"},
            {"id": "cat_002", "name": "Cooking Essentials", "description": "Oil, sugar, salt, spices"},
            {"id": "cat_003", "name": "Dairy & Eggs", "description": "Milk, curd, butter, eggs"},
            {"id": "cat_004", "name": "Vegetables", "description": "Fresh vegetables"},
            {"id": "cat_005", "name": "Fruits", "description": "Fresh fruits"},
            {"id": "cat_006", "name": "Beverages", "description": "Tea, coffee, juices"},
            {"id": "cat_007", "name": "Snacks & Biscuits", "description": "Chips, biscuits, namkeen"},
            {"id": "cat_008", "name": "Personal Care", "description": "Soap, shampoo, toothpaste"},
            {"id": "cat_009", "name": "Spices & Condiments", "description": "Spices, masalas, condiments"},
            {"id": "cat_010", "name": "Household", "description": "Cleaning supplies, kitchen items"}
        ]

        return {
            "success": True,
            "categories": categories,
            "count": len(categories)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")


@router.get("/units")
async def get_product_units():
    """Get available product units"""

    try:
        units = [
            {"value": "kg", "label": "Kilogram"},
            {"value": "g", "label": "Gram"},
            {"value": "liter", "label": "Liter"},
            {"value": "ml", "label": "Milliliter"},
            {"value": "piece", "label": "Piece"},
            {"value": "pieces", "label": "Pieces"},
            {"value": "packet", "label": "Packet"},
            {"value": "pack", "label": "Pack"},
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
