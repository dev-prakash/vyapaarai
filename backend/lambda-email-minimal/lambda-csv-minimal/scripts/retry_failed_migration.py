import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import boto3
import json
from decimal import Decimal
from datetime import datetime
from services.product_catalog_service import ProductCatalogService

class FailedProductRetryService:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        self.legacy_table = self.dynamodb.Table('vyaparai-products-prod')
        self.catalog_service = ProductCatalogService()
        
    async def retry_failed_product(self, product_id):
        """Retry migration for a specific failed product"""
        print(f"Retrying migration for product: {product_id}")
        
        try:
            # Get the specific product from legacy table
            response = self.legacy_table.get_item(
                Key={'id': product_id}
            )
            
            if 'Item' not in response:
                print(f"Product {product_id} not found in legacy table")
                return False
                
            legacy_product = response['Item']
            store_id = legacy_product.get('store_id')
            
            if not store_id:
                print(f"No store_id found for product {product_id}")
                return False
            
            print(f"Found product in store: {store_id}")
            
            # Extract product data
            product_data = {
                'name': legacy_product.get('name'),
                'brand': legacy_product.get('brand'),
                'category': legacy_product.get('category'),
                'barcodes': [legacy_product.get('barcode')] if legacy_product.get('barcode') else [],
                'attributes': {
                    'description': legacy_product.get('description'),
                    'weight': legacy_product.get('weight'),
                    'unit': legacy_product.get('unit')
                },
                'created_by': store_id,
                'verification_status': 'migrated'
            }
            
            # Extract inventory data
            inventory_data = {
                'quantity': legacy_product.get('current_stock', 0),
                'cost_price': float(legacy_product.get('cost_price')) if legacy_product.get('cost_price') else None,
                'selling_price': float(legacy_product.get('price')) if legacy_product.get('price') else None,
                'reorder_level': legacy_product.get('reorder_level'),
                'supplier': legacy_product.get('supplier'),
                'location': legacy_product.get('location'),
                'notes': f"Migrated from legacy system. Original ID: {legacy_product.get('id')}"
            }
            
            print(f"Product data: {product_data}")
            print(f"Inventory data: {inventory_data}")
            
            # Try to find existing product
            existing_product = await self.catalog_service.find_existing_product(
                barcode=product_data['barcodes'][0] if product_data['barcodes'] else None,
                name=product_data['name'],
                brand=product_data['brand']
            )
            
            if existing_product:
                # Merge with existing
                product_id_new = existing_product['product_id']
                print(f"Merging with existing product: {product_id_new}")
            else:
                # Create new global product
                product_id_new = await self.catalog_service.create_global_product(product_data)
                print(f"Created new global product: {product_id_new}")
            
            # Add to store inventory
            await self.catalog_service.add_to_store_inventory(
                store_id, product_id_new, inventory_data
            )
            print(f"Added to store inventory successfully")
            
            return True
            
        except Exception as e:
            print(f"Error retrying migration for product {product_id}: {e}")
            return False

# Run retry for specific product
async def retry_failed_product():
    retry_service = FailedProductRetryService()
    
    # Retry the failed product
    success = await retry_service.retry_failed_product('PROD1758814881975')
    
    if success:
        print("Migration retry completed successfully!")
    else:
        print("Migration retry failed!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(retry_failed_product())

