from typing import List, Dict, Optional, Any
from decimal import Decimal
import uuid
from datetime import datetime, timedelta
import json

from app.models.product import Product, StockMovement, ProductCategory, Supplier, ProductStatus, MovementType

class InventoryService:
    def __init__(self, db_session=None):
        """Initialize inventory service with database session"""
        self.db = db_session
        # For Lambda environment, we'll use mock data
        self.mock_mode = True
    
    def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        """Get product by ID"""
        if self.mock_mode:
            # Return mock product data
            mock_products = self._get_mock_products()
            return next((p for p in mock_products if p["id"] == product_id), None)
        
        # In production, this would query the database
        # product = self.db.query(Product).filter(Product.id == product_id).first()
        # return product.to_dict() if product else None
        return None
    
    def get_all_products(self, category: str = None, status: str = None, 
                        search: str = None, page: int = 1, limit: int = 50) -> Dict:
        """Get products with filtering and pagination"""
        
        if self.mock_mode:
            products = self._get_mock_products()
            
            # Apply filters
            if category:
                products = [p for p in products if p["category"].lower() == category.lower()]
            
            if status:
                products = [p for p in products if p["status"] == status]
            
            if search:
                search_lower = search.lower()
                products = [p for p in products if 
                           search_lower in p["name"].lower() or 
                           search_lower in p.get("description", "").lower() or
                           search_lower in p.get("barcode", "").lower()]
            
            # Get total count
            total = len(products)
            
            # Apply pagination
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_products = products[start_idx:end_idx]
            
            return {
                "products": paginated_products,
                "total": total,
                "page": page,
                "pages": (total + limit - 1) // limit,
                "has_next": end_idx < total,
                "has_prev": page > 1
            }
        
        # In production, this would query the database
        return {"products": [], "total": 0, "page": 1, "pages": 1, "has_next": False, "has_prev": False}
    
    def create_product(self, product_data: Dict) -> Dict:
        """Create new product"""
        
        try:
            product_id = str(uuid.uuid4())
            
            # Create product object
            product = {
                "id": product_id,
                "store_id": product_data.get("store_id", "STORE-001"),
                "name": product_data["name"],
                "description": product_data.get("description"),
                "category": product_data["category"],
                "subcategory": product_data.get("subcategory"),
                "price": float(product_data["price"]),
                "mrp": float(product_data.get("mrp", 0)) if product_data.get("mrp") else None,
                "cost_price": float(product_data.get("cost_price", 0)) if product_data.get("cost_price") else None,
                "current_stock": product_data.get("current_stock", 0),
                "min_stock_level": product_data.get("min_stock_level", 10),
                "max_stock_level": product_data.get("max_stock_level", 1000),
                "unit": product_data.get("unit", "piece"),
                "brand": product_data.get("brand"),
                "barcode": product_data.get("barcode"),
                "sku": product_data.get("sku"),
                "status": ProductStatus.ACTIVE.value,
                "is_featured": product_data.get("is_featured", False),
                "is_available": True,
                "supplier_name": product_data.get("supplier_name"),
                "supplier_contact": product_data.get("supplier_contact"),
                "supplier_email": product_data.get("supplier_email"),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Calculate stock status
            product["stock_status"] = self._calculate_stock_status(product)
            product["is_low_stock"] = product["current_stock"] <= product["min_stock_level"]
            product["is_out_of_stock"] = product["current_stock"] <= 0
            
            # Log initial stock if provided
            if product_data.get("current_stock", 0) > 0:
                self._log_stock_movement(
                    product_id,
                    "in",
                    product_data.get("current_stock", 0),
                    0,
                    product_data.get("current_stock", 0),
                    "Initial stock",
                    "product_creation"
                )
            
            return {
                "success": True,
                "product": product,
                "message": "Product created successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Product creation failed: {str(e)}"
            }
    
    def update_product(self, product_id: str, update_data: Dict) -> Dict:
        """Update product details"""
        
        try:
            # Get existing product
            product = self.get_product_by_id(product_id)
            if not product:
                return {"success": False, "error": "Product not found"}
            
            # Update fields
            for field, value in update_data.items():
                if field in product and field not in ["id", "created_at"]:
                    product[field] = value
            
            product["updated_at"] = datetime.utcnow().isoformat()
            
            # Recalculate stock status
            product["stock_status"] = self._calculate_stock_status(product)
            product["is_low_stock"] = product["current_stock"] <= product["min_stock_level"]
            product["is_out_of_stock"] = product["current_stock"] <= 0
            
            return {
                "success": True,
                "product": product,
                "message": "Product updated successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Product update failed: {str(e)}"
            }
    
    def update_stock(self, product_id: str, quantity: int, 
                    movement_type: str, reason: str = None, 
                    reference_id: str = None, reference_type: str = None) -> Dict:
        """Update product stock levels"""
        
        try:
            # Get product
            product = self.get_product_by_id(product_id)
            if not product:
                return {"success": False, "error": "Product not found"}
            
            previous_stock = product["current_stock"]
            
            # Calculate new stock based on movement type
            if movement_type == "in":
                new_stock = previous_stock + quantity
            elif movement_type == "out":
                new_stock = max(0, previous_stock - quantity)
            elif movement_type == "set":
                new_stock = quantity
            elif movement_type == "adjustment":
                new_stock = previous_stock + quantity  # Can be positive or negative
            else:
                return {"success": False, "error": "Invalid movement type"}
            
            # Update product stock
            product["current_stock"] = new_stock
            product["updated_at"] = datetime.utcnow().isoformat()
            
            # Update status based on stock level
            if new_stock <= 0:
                product["status"] = ProductStatus.OUT_OF_STOCK.value
            elif product["status"] == ProductStatus.OUT_OF_STOCK.value and new_stock > 0:
                product["status"] = ProductStatus.ACTIVE.value
            
            # Recalculate stock status
            product["stock_status"] = self._calculate_stock_status(product)
            product["is_low_stock"] = product["current_stock"] <= product["min_stock_level"]
            product["is_out_of_stock"] = product["current_stock"] <= 0
            
            # Log stock movement
            self._log_stock_movement(
                product_id, movement_type, quantity, 
                previous_stock, new_stock, reason, reference_id, reference_type
            )
            
            return {
                "success": True,
                "previous_stock": previous_stock,
                "new_stock": new_stock,
                "stock_status": product["stock_status"],
                "product": product,
                "message": "Stock updated successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Stock update failed: {str(e)}"
            }
    
    def check_availability(self, product_id: str, required_quantity: int) -> Dict:
        """Check if product is available in required quantity"""
        
        try:
            product = self.get_product_by_id(product_id)
            if not product:
                return {"available": False, "error": "Product not found"}
            
            if product["status"] != ProductStatus.ACTIVE.value:
                return {"available": False, "error": "Product not active"}
            
            available = product["current_stock"] >= required_quantity
            
            return {
                "available": available,
                "current_stock": product["current_stock"],
                "requested": required_quantity,
                "shortage": max(0, required_quantity - product["current_stock"]),
                "product": product
            }
            
        except Exception as e:
            return {
                "available": False,
                "error": f"Availability check failed: {str(e)}"
            }
    
    def get_low_stock_products(self) -> List[Dict]:
        """Get products with low stock levels"""
        
        try:
            all_products = self._get_mock_products()
            low_stock_products = [
                p for p in all_products 
                if p["current_stock"] <= p["min_stock_level"] and 
                p["status"] == ProductStatus.ACTIVE.value
            ]
            
            return low_stock_products
            
        except Exception as e:
            return []
    
    def get_stock_history(self, product_id: str, limit: int = 50) -> List[Dict]:
        """Get stock movement history for a product"""
        
        try:
            # In production, this would query the database
            # movements = self.db.query(StockMovement).filter(
            #     StockMovement.product_id == product_id
            # ).order_by(StockMovement.created_at.desc()).limit(limit).all()
            
            # For now, return mock data
            mock_movements = [
                {
                    "id": str(uuid.uuid4()),
                    "product_id": product_id,
                    "movement_type": "in",
                    "quantity": 50,
                    "previous_stock": 0,
                    "new_stock": 50,
                    "reason": "Initial stock",
                    "reference_id": None,
                    "reference_type": "product_creation",
                    "created_by": "system",
                    "notes": "Initial stock setup",
                    "created_at": datetime.utcnow().isoformat()
                },
                {
                    "id": str(uuid.uuid4()),
                    "product_id": product_id,
                    "movement_type": "out",
                    "quantity": 5,
                    "previous_stock": 50,
                    "new_stock": 45,
                    "reason": "Order fulfillment",
                    "reference_id": "ORD123",
                    "reference_type": "order",
                    "created_by": "system",
                    "notes": "Order ORD123 processed",
                    "created_at": (datetime.utcnow() - timedelta(hours=2)).isoformat()
                }
            ]
            
            return mock_movements[:limit]
            
        except Exception as e:
            return []
    
    def bulk_update_stock(self, updates: List[Dict]) -> Dict:
        """Bulk update stock for multiple products"""
        
        try:
            results = []
            success_count = 0
            error_count = 0
            
            for update in updates:
                result = self.update_stock(
                    update["product_id"],
                    update["quantity"],
                    update["movement_type"],
                    update.get("reason"),
                    update.get("reference_id"),
                    update.get("reference_type")
                )
                
                results.append(result)
                if result["success"]:
                    success_count += 1
                else:
                    error_count += 1
            
            return {
                "success": True,
                "total_updates": len(updates),
                "successful_updates": success_count,
                "failed_updates": error_count,
                "results": results
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Bulk update failed: {str(e)}"
            }
    
    def get_inventory_summary(self) -> Dict:
        """Get inventory summary statistics"""
        
        try:
            all_products = self._get_mock_products()
            
            total_products = len(all_products)
            active_products = len([p for p in all_products if p["status"] == ProductStatus.ACTIVE.value])
            out_of_stock = len([p for p in all_products if p["is_out_of_stock"]])
            low_stock = len([p for p in all_products if p["is_low_stock"] and not p["is_out_of_stock"]])
            
            total_stock_value = sum(p["current_stock"] * p["price"] for p in all_products)
            
            return {
                "total_products": total_products,
                "active_products": active_products,
                "out_of_stock": out_of_stock,
                "low_stock": low_stock,
                "total_stock_value": total_stock_value,
                "categories": self._get_category_summary(all_products)
            }
            
        except Exception as e:
            return {
                "total_products": 0,
                "active_products": 0,
                "out_of_stock": 0,
                "low_stock": 0,
                "total_stock_value": 0,
                "categories": {}
            }
    
    def _calculate_stock_status(self, product: Dict) -> str:
        """Calculate stock status for a product"""
        if product["current_stock"] <= 0:
            return "out_of_stock"
        elif product["current_stock"] <= product["min_stock_level"]:
            return "low_stock"
        else:
            return "in_stock"
    
    def _log_stock_movement(self, product_id: str, movement_type: str, 
                           quantity: int, previous_stock: int, new_stock: int,
                           reason: str = None, reference_id: str = None, 
                           reference_type: str = None):
        """Log stock movement for audit trail"""
        
        # In production, this would save to database
        # movement = StockMovement(
        #     id=str(uuid.uuid4()),
        #     product_id=product_id,
        #     movement_type=movement_type,
        #     quantity=quantity,
        #     previous_stock=previous_stock,
        #     new_stock=new_stock,
        #     reason=reason,
        #     reference_id=reference_id,
        #     reference_type=reference_type
        # )
        # self.db.add(movement)
        # self.db.commit()
        
        # For now, just log to console
        print(f"Stock movement logged: {product_id} - {movement_type} {quantity} units")
    
    def _get_mock_products(self) -> List[Dict]:
        """Get mock product data for development"""
        
        return [
            {
                "id": "prod_001",
                "store_id": "STORE-001",
                "name": "Basmati Rice",
                "description": "Premium quality basmati rice",
                "category": "Grains",
                "subcategory": "Rice",
                "price": 120.0,
                "mrp": 150.0,
                "cost_price": 100.0,
                "current_stock": 50,
                "min_stock_level": 10,
                "max_stock_level": 200,
                "unit": "kg",
                "brand": "Premium",
                "barcode": "8901234567890",
                "sku": "RICE-BASMATI-1KG",
                "status": ProductStatus.ACTIVE.value,
                "is_featured": True,
                "is_available": True,
                "supplier_name": "Rice Supplier Co.",
                "supplier_contact": "+919876543210",
                "supplier_email": "rice@supplier.com",
                "created_at": "2025-08-25T10:00:00",
                "updated_at": "2025-08-25T10:00:00",
                "stock_status": "in_stock",
                "is_low_stock": False,
                "is_out_of_stock": False
            },
            {
                "id": "prod_002",
                "store_id": "STORE-001",
                "name": "Wheat Flour",
                "description": "Whole wheat flour for healthy cooking",
                "category": "Grains",
                "subcategory": "Flour",
                "price": 45.0,
                "mrp": 55.0,
                "cost_price": 35.0,
                "current_stock": 5,
                "min_stock_level": 10,
                "max_stock_level": 100,
                "unit": "kg",
                "brand": "Healthy",
                "barcode": "8901234567891",
                "sku": "FLOUR-WHEAT-1KG",
                "status": ProductStatus.ACTIVE.value,
                "is_featured": False,
                "is_available": True,
                "supplier_name": "Flour Supplier Co.",
                "supplier_contact": "+919876543211",
                "supplier_email": "flour@supplier.com",
                "created_at": "2025-08-25T10:00:00",
                "updated_at": "2025-08-25T10:00:00",
                "stock_status": "low_stock",
                "is_low_stock": True,
                "is_out_of_stock": False
            },
            {
                "id": "prod_003",
                "store_id": "STORE-001",
                "name": "Sugar",
                "description": "Refined white sugar",
                "category": "Essentials",
                "subcategory": "Sweeteners",
                "price": 50.0,
                "mrp": 60.0,
                "cost_price": 40.0,
                "current_stock": 0,
                "min_stock_level": 5,
                "max_stock_level": 50,
                "unit": "kg",
                "brand": "Sweet",
                "barcode": "8901234567892",
                "sku": "SUGAR-WHITE-1KG",
                "status": ProductStatus.OUT_OF_STOCK.value,
                "is_featured": False,
                "is_available": False,
                "supplier_name": "Sugar Supplier Co.",
                "supplier_contact": "+919876543212",
                "supplier_email": "sugar@supplier.com",
                "created_at": "2025-08-25T10:00:00",
                "updated_at": "2025-08-25T10:00:00",
                "stock_status": "out_of_stock",
                "is_low_stock": True,
                "is_out_of_stock": True
            },
            {
                "id": "prod_004",
                "store_id": "STORE-001",
                "name": "Cooking Oil",
                "description": "Pure vegetable cooking oil",
                "category": "Essentials",
                "subcategory": "Oils",
                "price": 180.0,
                "mrp": 200.0,
                "cost_price": 150.0,
                "current_stock": 25,
                "min_stock_level": 10,
                "max_stock_level": 100,
                "unit": "liter",
                "brand": "Pure",
                "barcode": "8901234567893",
                "sku": "OIL-VEG-1L",
                "status": ProductStatus.ACTIVE.value,
                "is_featured": True,
                "is_available": True,
                "supplier_name": "Oil Supplier Co.",
                "supplier_contact": "+919876543213",
                "supplier_email": "oil@supplier.com",
                "created_at": "2025-08-25T10:00:00",
                "updated_at": "2025-08-25T10:00:00",
                "stock_status": "in_stock",
                "is_low_stock": False,
                "is_out_of_stock": False
            },
            {
                "id": "prod_005",
                "store_id": "STORE-001",
                "name": "Milk",
                "description": "Fresh cow milk",
                "category": "Dairy",
                "subcategory": "Milk",
                "price": 60.0,
                "mrp": 70.0,
                "cost_price": 50.0,
                "current_stock": 15,
                "min_stock_level": 20,
                "max_stock_level": 50,
                "unit": "liter",
                "brand": "Fresh",
                "barcode": "8901234567894",
                "sku": "MILK-COW-1L",
                "status": ProductStatus.ACTIVE.value,
                "is_featured": False,
                "is_available": True,
                "supplier_name": "Dairy Supplier Co.",
                "supplier_contact": "+919876543214",
                "supplier_email": "dairy@supplier.com",
                "created_at": "2025-08-25T10:00:00",
                "updated_at": "2025-08-25T10:00:00",
                "stock_status": "low_stock",
                "is_low_stock": True,
                "is_out_of_stock": False
            }
        ]
    
    def _get_category_summary(self, products: List[Dict]) -> Dict:
        """Get summary by category"""
        
        categories = {}
        for product in products:
            category = product["category"]
            if category not in categories:
                categories[category] = {
                    "total_products": 0,
                    "active_products": 0,
                    "out_of_stock": 0,
                    "low_stock": 0,
                    "total_value": 0
                }
            
            categories[category]["total_products"] += 1
            if product["status"] == ProductStatus.ACTIVE.value:
                categories[category]["active_products"] += 1
            if product["is_out_of_stock"]:
                categories[category]["out_of_stock"] += 1
            elif product["is_low_stock"]:
                categories[category]["low_stock"] += 1
            
            categories[category]["total_value"] += product["current_stock"] * product["price"]
        
        return categories
