#!/usr/bin/env python3

import boto3
import json
import sys
import os
from datetime import datetime
from decimal import Decimal
import asyncio

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class CatalogCleanupService:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        self.s3 = boto3.client('s3')
        
        # Table references
        self.global_table = self.dynamodb.Table('vyaparai-global-products-prod')
        self.inventory_table = self.dynamodb.Table('vyaparai-store-inventory-prod')
        self.jobs_table = self.dynamodb.Table('vyaparai-bulk-upload-jobs-prod')
        self.legacy_table = self.dynamodb.Table('vyaparai-products-prod')
        
        self.backup_bucket = 'vyapaarai-bulk-uploads-prod'
        self.backup_timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    
    def decimal_to_float(self, obj):
        """Convert Decimal objects to float for JSON serialization"""
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self.decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.decimal_to_float(v) for v in obj]
        return obj
    
    async def create_comprehensive_backup(self):
        """Create backup of all product-related data"""
        print("Creating comprehensive backup of all product data...")
        
        backup_data = {
            'backup_timestamp': self.backup_timestamp,
            'backup_description': 'Pre-cleanup backup of shared catalog system',
            'tables': {}
        }
        
        # Backup global products
        try:
            print("Backing up global products...")
            response = self.global_table.scan()
            global_products = response['Items']
            
            while 'LastEvaluatedKey' in response:
                response = self.global_table.scan(
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                global_products.extend(response['Items'])
            
            backup_data['tables']['global_products'] = {
                'count': len(global_products),
                'items': self.decimal_to_float(global_products)
            }
            print(f"Global products backed up: {len(global_products)} items")
            
        except Exception as e:
            print(f"Error backing up global products: {e}")
            backup_data['tables']['global_products'] = {'error': str(e)}
        
        # Backup store inventory
        try:
            print("Backing up store inventory...")
            response = self.inventory_table.scan()
            inventory_items = response['Items']
            
            while 'LastEvaluatedKey' in response:
                response = self.inventory_table.scan(
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                inventory_items.extend(response['Items'])
            
            backup_data['tables']['store_inventory'] = {
                'count': len(inventory_items),
                'items': self.decimal_to_float(inventory_items)
            }
            print(f"Store inventory backed up: {len(inventory_items)} items")
            
        except Exception as e:
            print(f"Error backing up store inventory: {e}")
            backup_data['tables']['store_inventory'] = {'error': str(e)}
        
        # Backup CSV jobs (for reference)
        try:
            print("Backing up CSV job records...")
            response = self.jobs_table.scan()
            job_items = response['Items']
            
            while 'LastEvaluatedKey' in response:
                response = self.jobs_table.scan(
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                job_items.extend(response['Items'])
            
            backup_data['tables']['csv_jobs'] = {
                'count': len(job_items),
                'items': self.decimal_to_float(job_items)
            }
            print(f"CSV jobs backed up: {len(job_items)} items")
            
        except Exception as e:
            print(f"Error backing up CSV jobs: {e}")
            backup_data['tables']['csv_jobs'] = {'error': str(e)}
        
        # Save backup to S3
        backup_key = f'backups/complete-catalog-backup-{self.backup_timestamp}.json'
        
        try:
            self.s3.put_object(
                Bucket=self.backup_bucket,
                Key=backup_key,
                Body=json.dumps(backup_data, indent=2, default=str),
                ContentType='application/json'
            )
            print(f"Backup saved to S3: s3://{self.backup_bucket}/{backup_key}")
            return backup_key
            
        except Exception as e:
            print(f"Error saving backup to S3: {e}")
            raise
    
    async def clear_global_products(self):
        """Delete all items from global products table"""
        print("Clearing global products table...")
        
        try:
            # Scan all items
            response = self.global_table.scan()
            items = response['Items']
            
            while 'LastEvaluatedKey' in response:
                response = self.global_table.scan(
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items.extend(response['Items'])
            
            print(f"Found {len(items)} global products to delete")
            
            # Delete in batches
            deleted_count = 0
            batch_size = 25  # DynamoDB batch limit
            
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                
                with self.global_table.batch_writer() as batch_writer:
                    for item in batch:
                        batch_writer.delete_item(
                            Key={'product_id': item['product_id']}
                        )
                        deleted_count += 1
                
                if deleted_count % 100 == 0:
                    print(f"Deleted {deleted_count}/{len(items)} global products")
            
            print(f"Successfully deleted {deleted_count} global products")
            return deleted_count
            
        except Exception as e:
            print(f"Error clearing global products: {e}")
            raise
    
    async def clear_store_inventory(self):
        """Delete all items from store inventory table"""
        print("Clearing store inventory table...")
        
        try:
            # Scan all items
            response = self.inventory_table.scan()
            items = response['Items']
            
            while 'LastEvaluatedKey' in response:
                response = self.inventory_table.scan(
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items.extend(response['Items'])
            
            print(f"Found {len(items)} inventory items to delete")
            
            # Delete in batches
            deleted_count = 0
            batch_size = 25
            
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                
                with self.inventory_table.batch_writer() as batch_writer:
                    for item in batch:
                        batch_writer.delete_item(
                            Key={
                                'store_id': item['store_id'],
                                'product_id': item['product_id']
                            }
                        )
                        deleted_count += 1
                
                if deleted_count % 100 == 0:
                    print(f"Deleted {deleted_count}/{len(items)} inventory items")
            
            print(f"Successfully deleted {deleted_count} inventory items")
            return deleted_count
            
        except Exception as e:
            print(f"Error clearing store inventory: {e}")
            raise
    
    async def clear_csv_jobs(self, keep_recent_days=7):
        """Optionally clear old CSV job records"""
        print(f"Clearing CSV jobs older than {keep_recent_days} days...")
        
        try:
            # Scan all jobs
            response = self.jobs_table.scan()
            items = response['Items']
            
            while 'LastEvaluatedKey' in response:
                response = self.jobs_table.scan(
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items.extend(response['Items'])
            
            # Filter items to delete (older than keep_recent_days)
            cutoff_date = datetime.utcnow().timestamp() - (keep_recent_days * 24 * 60 * 60)
            items_to_delete = []
            
            for item in items:
                created_at = item.get('createdAt', '')
                try:
                    if created_at:
                        item_timestamp = datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp()
                        if item_timestamp < cutoff_date:
                            items_to_delete.append(item)
                except:
                    # If date parsing fails, keep the item
                    continue
            
            print(f"Found {len(items_to_delete)} old CSV jobs to delete (keeping {len(items) - len(items_to_delete)} recent)")
            
            # Delete old jobs
            deleted_count = 0
            batch_size = 25
            
            for i in range(0, len(items_to_delete), batch_size):
                batch = items_to_delete[i:i + batch_size]
                
                with self.jobs_table.batch_writer() as batch_writer:
                    for item in batch:
                        batch_writer.delete_item(
                            Key={'jobId': item['jobId']}
                        )
                        deleted_count += 1
            
            print(f"Successfully deleted {deleted_count} old CSV jobs")
            return deleted_count
            
        except Exception as e:
            print(f"Error clearing CSV jobs: {e}")
            return 0
    
    async def validate_cleanup(self):
        """Validate that cleanup was successful"""
        print("Validating cleanup completion...")
        
        validation_results = {}
        
        # Check global products
        try:
            response = self.global_table.scan(Select='COUNT', Limit=10)
            global_count = response['Count']
            validation_results['global_products'] = {
                'count': global_count,
                'cleaned': global_count == 0
            }
        except Exception as e:
            validation_results['global_products'] = {'error': str(e)}
        
        # Check store inventory
        try:
            response = self.inventory_table.scan(Select='COUNT', Limit=10)
            inventory_count = response['Count']
            validation_results['store_inventory'] = {
                'count': inventory_count,
                'cleaned': inventory_count == 0
            }
        except Exception as e:
            validation_results['store_inventory'] = {'error': str(e)}
        
        # Check CSV jobs
        try:
            response = self.jobs_table.scan(Select='COUNT', Limit=10)
            jobs_count = response['Count']
            validation_results['csv_jobs'] = {
                'count': jobs_count,
                'note': 'Recent jobs may be retained'
            }
        except Exception as e:
            validation_results['csv_jobs'] = {'error': str(e)}
        
        return validation_results
    
    async def run_full_cleanup(self, clear_csv_jobs=False):
        """Run complete cleanup process"""
        print("=== STARTING COMPLETE CATALOG CLEANUP ===")
        print(f"Timestamp: {self.backup_timestamp}")
        
        cleanup_summary = {
            'start_time': datetime.utcnow().isoformat(),
            'backup_created': False,
            'global_products_deleted': 0,
            'inventory_items_deleted': 0,
            'csv_jobs_deleted': 0,
            'errors': []
        }
        
        try:
            # Step 1: Create backup
            backup_key = await self.create_comprehensive_backup()
            cleanup_summary['backup_created'] = backup_key
            
            # Step 2: Clear global products
            global_deleted = await self.clear_global_products()
            cleanup_summary['global_products_deleted'] = global_deleted
            
            # Step 3: Clear store inventory
            inventory_deleted = await self.clear_store_inventory()
            cleanup_summary['inventory_items_deleted'] = inventory_deleted
            
            # Step 4: Clear CSV jobs (optional)
            if clear_csv_jobs:
                jobs_deleted = await self.clear_csv_jobs()
                cleanup_summary['csv_jobs_deleted'] = jobs_deleted
            
            # Step 5: Validate cleanup
            validation = await self.validate_cleanup()
            cleanup_summary['validation'] = validation
            
            cleanup_summary['end_time'] = datetime.utcnow().isoformat()
            cleanup_summary['success'] = True
            
            print("\n=== CLEANUP COMPLETED SUCCESSFULLY ===")
            print(f"Global products deleted: {global_deleted}")
            print(f"Inventory items deleted: {inventory_deleted}")
            if clear_csv_jobs:
                print(f"CSV jobs deleted: {cleanup_summary['csv_jobs_deleted']}")
            print(f"Backup location: s3://{self.backup_bucket}/{backup_key}")
            
            return cleanup_summary
            
        except Exception as e:
            cleanup_summary['errors'].append(str(e))
            cleanup_summary['success'] = False
            print(f"\n=== CLEANUP FAILED ===")
            print(f"Error: {e}")
            raise

# CLI interface
async def main():
    cleanup_service = CatalogCleanupService()
    
    print("Product Catalog Cleanup Tool")
    print("============================")
    print("This will DELETE ALL products from the shared catalog system")
    print("A backup will be created before deletion")
    print()
    
    # Confirmation
    confirm = input("Are you sure you want to proceed? (type 'DELETE ALL' to confirm): ")
    if confirm != 'DELETE ALL':
        print("Cleanup cancelled")
        return
    
    clear_jobs = input("Also clear old CSV job records? (y/n): ").lower() == 'y'
    
    print("\nStarting cleanup process...")
    summary = await cleanup_service.run_full_cleanup(clear_csv_jobs=clear_jobs)
    
    print(f"\nCleanup Summary:")
    print(json.dumps(summary, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())



