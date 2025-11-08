import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import boto3
import json
from decimal import Decimal
from datetime import datetime
from services.product_catalog_service import ProductCatalogService
from utils.product_matching import extract_barcodes_from_data, find_all_matches

class ProductMigrationService:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        self.legacy_table = self.dynamodb.Table('vyaparai-products-prod')
        self.catalog_service = ProductCatalogService()
        
    async def backup_legacy_data(self):
        """Create backup of legacy data"""
        print("Creating backup of legacy product data...")
        
        # Scan all legacy products
        response = self.legacy_table.scan()
        products = response['Items']
        
        # Continue scanning if there are more items
        while 'LastEvaluatedKey' in response:
            response = self.legacy_table.scan(
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            products.extend(response['Items'])
        
        # Save backup to S3
        s3 = boto3.client('s3')
        backup_data = {
            'backup_date': datetime.utcnow().isoformat(),
            'total_products': len(products),
            'products': products
        }
        
        s3.put_object(
            Bucket='vyapaarai-bulk-uploads-prod',
            Key=f'backups/legacy-products-backup-{datetime.utcnow().strftime("%Y%m%d-%H%M%S")}.json',
            Body=json.dumps(backup_data, default=str),
            ContentType='application/json'
        )
        
        print(f"Backup completed: {len(products)} products backed up")
        return products
    
    async def migrate_products(self, dry_run=True):
        """Migrate products from legacy to shared catalog"""
        legacy_products = await self.backup_legacy_data()
        
        migration_stats = {
            'total_legacy': len(legacy_products),
            'migrated_as_new': 0,
            'merged_with_existing': 0,
            'errors': 0,
            'store_inventory_created': 0
        }
        
        # Group products by store
        products_by_store = {}
        for product in legacy_products:
            store_id = product.get('store_id')
            if store_id:
                if store_id not in products_by_store:
                    products_by_store[store_id] = []
                products_by_store[store_id].append(product)
        
        print(f"Found products for {len(products_by_store)} stores")
        
        for store_id, store_products in products_by_store.items():
            print(f"Migrating {len(store_products)} products for store {store_id}")
            
            for legacy_product in store_products:
                try:
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
                    
                    if not dry_run:
                        # Try to find existing product
                        existing_product = await self.catalog_service.find_existing_product(
                            barcode=product_data['barcodes'][0] if product_data['barcodes'] else None,
                            name=product_data['name'],
                            brand=product_data['brand']
                        )
                        
                        if existing_product:
                            # Merge with existing
                            product_id = existing_product['product_id']
                            migration_stats['merged_with_existing'] += 1
                        else:
                            # Create new global product
                            product_id = await self.catalog_service.create_global_product(product_data)
                            migration_stats['migrated_as_new'] += 1
                        
                        # Add to store inventory
                        await self.catalog_service.add_to_store_inventory(
                            store_id, product_id, inventory_data
                        )
                        migration_stats['store_inventory_created'] += 1
                    
                    else:
                        # Dry run - just count what would happen
                        migration_stats['migrated_as_new'] += 1
                        migration_stats['store_inventory_created'] += 1
                
                except Exception as e:
                    print(f"Error migrating product {legacy_product.get('id')}: {e}")
                    migration_stats['errors'] += 1
        
        return migration_stats

# Run migration
async def run_migration():
    migrator = ProductMigrationService()
    
    # First do a dry run
    print("=== DRY RUN ===")
    dry_run_stats = await migrator.migrate_products(dry_run=True)
    print("Dry run results:", dry_run_stats)
    
    # Ask for confirmation
    confirm = input("Proceed with actual migration? (yes/no): ")
    if confirm.lower() == 'yes':
        print("=== ACTUAL MIGRATION ===")
        actual_stats = await migrator.migrate_products(dry_run=False)
        print("Migration completed:", actual_stats)
        return actual_stats
    else:
        print("Migration cancelled")
        return None

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_migration())
