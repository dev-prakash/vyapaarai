import boto3
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
from decimal import Decimal
import os

# DynamoDB table names from environment variables
GLOBAL_PRODUCTS_TABLE = os.environ.get('GLOBAL_PRODUCTS_TABLE', 'vyaparai-global-products-prod')
STORE_INVENTORY_TABLE = os.environ.get('STORE_INVENTORY_TABLE', 'vyaparai-store-inventory-prod')

# Product status constants
PRODUCT_STATUSES = {
    'admin_created': 'Pre-populated by admin with high quality data',
    'pending': 'Added by store owner, awaiting admin approval',
    'verified': 'Admin approved, high quality and accurate',
    'community': 'Store-created, basic validation passed',
    'flagged': 'Flagged for review due to quality issues',
    'migrated': 'Migrated from legacy system'
}

QUALITY_SCORES = {
    'excellent': {'score': 100, 'criteria': 'Professional images, complete data, verified barcodes'},
    'good': {'score': 80, 'criteria': 'Good images, mostly complete data'},
    'fair': {'score': 60, 'criteria': 'Basic data, acceptable images'},
    'poor': {'score': 40, 'criteria': 'Incomplete data, poor images'},
    'needs_review': {'score': 20, 'criteria': 'Missing critical information'}
}

class GlobalProduct:
    def __init__(self, product_id=None, name=None, brand=None, category=None, barcodes=None, canonical_image_urls=None, attributes=None, created_by=None, verification_status="pending", image_hash=None, regional_names=None, primary_regions=None, contributed_names=None, quality_score=None, import_source=None, last_updated_by=None, admin_notes=None, status_history=None):
        self.product_id = product_id or f"prod_{uuid.uuid4().hex[:12]}"
        self.name = name
        self.brand = brand
        self.category = category
        self.barcodes = barcodes or []  # List of barcodes
        self.barcode = barcodes[0] if barcodes else None  # Primary barcode for GSI
        self.additional_barcodes = barcodes[1:] if len(barcodes or []) > 1 else []
        self.canonical_image_urls = canonical_image_urls or {}
        self.attributes = attributes or {}
        self.created_by = created_by
        self.verification_status = verification_status
        self.image_hash = image_hash
        self.stores_using_count = 0
        
        # NEW: Regional name support
        self.regional_names = regional_names or {}  # {"IN-MH": ["बैंगन 500g", "Vangi 500g"], "IN-TN": ["கத்திரிக்காய் 500g"]}
        self.primary_regions = primary_regions or []  # ["IN-MH", "IN-TN", "IN-KA"]
        self.contributed_names = contributed_names or {}  # {"store_123": [{"region": "IN-MH", "name": "वांगी 500g", "verified": false, "votes": 3}]}
        
        # NEW: Admin workflow and quality tracking
        self.quality_score = quality_score
        self.import_source = import_source
        self.last_updated_by = last_updated_by
        self.admin_notes = admin_notes
        self.status_history = status_history or []
        
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self):
        item_dict = {
            'product_id': self.product_id,
            'name': self.name,
            'brand': self.brand,
            'category': self.category,
            'additional_barcodes': self.additional_barcodes,
            'canonical_image_urls': self.canonical_image_urls,
            'attributes': self.attributes,
            'created_by': self.created_by,
            'verification_status': self.verification_status,
            'stores_using_count': self.stores_using_count,
            'regional_names': self.regional_names,
            'primary_regions': self.primary_regions,
            'contributed_names': self.contributed_names,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        
        # Only include barcode if it exists (GSI requirement)
        if self.barcode:
            item_dict['barcode'] = self.barcode
        
        # Only include image_hash if it exists
        if self.image_hash:
            item_dict['image_hash'] = self.image_hash
        
        # Add new admin workflow fields
        if self.quality_score is not None:
            item_dict['quality_score'] = self.quality_score
        if self.import_source:
            item_dict['import_source'] = self.import_source
        if self.last_updated_by:
            item_dict['last_updated_by'] = self.last_updated_by
        if self.admin_notes:
            item_dict['admin_notes'] = self.admin_notes
        if self.status_history:
            item_dict['status_history'] = self.status_history
        
        return item_dict

class StoreInventoryItem:
    def __init__(self, store_id, product_id, quantity=0, cost_price=None, selling_price=None, reorder_level=None, supplier=None, location=None, custom_image_urls=None, notes=None):
        self.store_id = store_id
        self.product_id = product_id
        self.gsi_product_id = product_id  # For GSI
        self.quantity = quantity
        self.cost_price = float(cost_price) if cost_price else None
        self.selling_price = float(selling_price) if selling_price else None
        self.reorder_level = reorder_level
        self.supplier = supplier
        self.location = location
        self.custom_image_urls = custom_image_urls or {}
        self.notes = notes
        self.last_updated = datetime.utcnow().isoformat()

    def to_dict(self):
        return {
            'store_id': self.store_id,
            'product_id': self.product_id,
            'gsi_product_id': self.gsi_product_id,
            'quantity': self.quantity,
            'cost_price': self.cost_price,
            'selling_price': self.selling_price,
            'reorder_level': self.reorder_level,
            'supplier': self.supplier,
            'location': self.location,
            'custom_image_urls': self.custom_image_urls,
            'notes': self.notes,
            'last_updated': self.last_updated
        }

class ProductCatalogService:
    def __init__(self, dynamodb_client=None):
        self.dynamodb = dynamodb_client or boto3.resource('dynamodb', region_name='ap-south-1')
        from lambda_handler import GLOBAL_PRODUCTS_TABLE, STORE_INVENTORY_TABLE
        self.global_table = self.dynamodb.Table(GLOBAL_PRODUCTS_TABLE)
        self.inventory_table = self.dynamodb.Table(STORE_INVENTORY_TABLE)
    
    async def find_existing_product(self, barcode=None, name=None, brand=None, image_hash=None):
        """Find existing product by various criteria"""
        try:
            # 1. Exact barcode match (fastest)
            if barcode:
                response = self.global_table.query(
                    IndexName='barcode-index',
                    KeyConditionExpression='barcode = :barcode',
                    ExpressionAttributeValues={':barcode': barcode}
                )
                if response['Items']:
                    return response['Items'][0]
            
            # 2. Image hash match
            if image_hash:
                response = self.global_table.query(
                    IndexName='image_hash-index', 
                    KeyConditionExpression='image_hash = :hash',
                    ExpressionAttributeValues={':hash': image_hash}
                )
                if response['Items']:
                    return response['Items'][0]
            
            # 3. Name + brand fuzzy match (scan - expensive, use sparingly)
            if name and brand:
                # For now, exact match. Can add fuzzy matching later
                response = self.global_table.scan(
                    FilterExpression='#name = :name AND brand = :brand',
                    ExpressionAttributeNames={'#name': 'name'},
                    ExpressionAttributeValues={
                        ':name': name,
                        ':brand': brand
                    }
                )
                if response['Items']:
                    return response['Items'][0]
            
            return None
            
        except Exception as e:
            print(f"Error finding existing product: {e}")
            return None
            
    async def create_global_product(self, product_data) -> str:
        """Create new global product, return product_id"""
        try:
            global_product = GlobalProduct(
                name=product_data.get('name'),
                brand=product_data.get('brand'),
                category=product_data.get('category'),
                barcodes=product_data.get('barcodes', []),
                canonical_image_urls=product_data.get('image_urls', {}),
                attributes=product_data.get('attributes', {}),
                created_by=product_data.get('created_by'),
                verification_status=product_data.get('verification_status', 'pending'),
                image_hash=product_data.get('image_hash'),
                quality_score=product_data.get('quality_score'),
                import_source=product_data.get('import_source'),
                last_updated_by=product_data.get('last_updated_by'),
                admin_notes=product_data.get('admin_notes'),
                status_history=product_data.get('status_history')
            )
            
            # Convert to dict and remove None values for GSI compatibility
            item_dict = global_product.to_dict()
            # The to_dict method now handles popping None values for barcode and image_hash
            
            self.global_table.put_item(Item=item_dict)
            return global_product.product_id
            
        except Exception as e:
            print(f"Error creating global product: {e}")
            raise
            
    async def add_to_store_inventory(self, store_id, product_id, inventory_data):
        """Add product reference to store inventory"""
        try:
            inventory_item = StoreInventoryItem(
                store_id=store_id,
                product_id=product_id,
                quantity=inventory_data.get('quantity', 0),
                cost_price=inventory_data.get('cost_price'),
                selling_price=inventory_data.get('selling_price'), 
                reorder_level=inventory_data.get('reorder_level'),
                supplier=inventory_data.get('supplier'),
                location=inventory_data.get('location'),
                custom_image_urls=inventory_data.get('custom_image_urls'),
                notes=inventory_data.get('notes')
            )
            
            # Convert to dict and handle Decimal conversion
            item_dict = inventory_item.to_dict()
            if item_dict.get('cost_price') is not None:
                item_dict['cost_price'] = Decimal(str(item_dict['cost_price']))
            if item_dict.get('selling_price') is not None:
                item_dict['selling_price'] = Decimal(str(item_dict['selling_price']))
            
            self.inventory_table.put_item(Item=item_dict)
            
            # Increment stores_using_count
            self.global_table.update_item(
                Key={'product_id': product_id},
                UpdateExpression='ADD stores_using_count :inc',
                ExpressionAttributeValues={':inc': 1}
            )
            
            return inventory_item.to_dict()
            
        except Exception as e:
            print(f"Error adding to store inventory: {e}")
            raise
        
    async def get_store_inventory(self, store_id, limit=None, last_key=None):
        """Get store inventory with global product details joined"""
        try:
            query_params = {
                'KeyConditionExpression': 'store_id = :store_id',
                'ExpressionAttributeValues': {':store_id': store_id}
            }
            
            if limit:
                query_params['Limit'] = limit
            if last_key:
                query_params['ExclusiveStartKey'] = last_key
                
            response = self.inventory_table.query(**query_params)
            
            # Join with global product data
            enriched_items = []
            for item in response['Items']:
                global_product = self.global_table.get_item(
                    Key={'product_id': item['product_id']}
                )['Item']
                
                # Merge inventory and global product data
                enriched_item = {
                    **item,
                    'global_product': global_product
                }
                enriched_items.append(enriched_item)
            
            return {
                'items': enriched_items,
                'last_key': response.get('LastEvaluatedKey')
            }
            
        except Exception as e:
            print(f"Error getting store inventory: {e}")
            raise

    async def update_store_inventory(self, store_id, product_id, updates):
        """Update store-specific inventory data"""
        try:
            # Build update expression
            update_expr = "SET "
            expr_attr_values = {}
            
            for key, value in updates.items():
                if key not in ['store_id', 'product_id']:  # Don't update keys
                    update_expr += f"{key} = :{key}, "
                    expr_attr_values[f":{key}"] = value
            
            update_expr += "last_updated = :last_updated"
            expr_attr_values[':last_updated'] = datetime.utcnow().isoformat()
            
            self.inventory_table.update_item(
                Key={'store_id': store_id, 'product_id': product_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_attr_values
            )
            
        except Exception as e:
            print(f"Error updating store inventory: {e}")
            raise

    async def add_regional_name(self, product_id: str, region_code: str, regional_name: str, contributed_by_store: str = None):
        """Add regional name to product"""
        try:
            if contributed_by_store:
                # Add to contributed_names for verification
                contribution = {
                    "region": region_code,
                    "name": regional_name,
                    "verified": False,
                    "votes": 1,
                    "contributed_at": datetime.utcnow().isoformat()
                }
                
                # Check if product exists first
                response = self.global_table.get_item(Key={'product_id': product_id})
                if 'Item' not in response:
                    raise Exception(f"Product {product_id} not found")
                
                # Update with contribution
                self.global_table.update_item(
                    Key={'product_id': product_id},
                    UpdateExpression='SET contributed_names = if_not_exists(contributed_names, :empty_map)',
                    ExpressionAttributeValues={':empty_map': {}}
                )
                
                # Add contribution to store's list
                self.global_table.update_item(
                    Key={'product_id': product_id},
                    UpdateExpression='SET contributed_names.#store = list_append(if_not_exists(contributed_names.#store, :empty_list), :contribution)',
                    ExpressionAttributeNames={'#store': contributed_by_store},
                    ExpressionAttributeValues={
                        ':contribution': [contribution],
                        ':empty_list': []
                    }
                )
            else:
                # Add directly to regional_names (for admin/verified additions)
                self.global_table.update_item(
                    Key={'product_id': product_id},
                    UpdateExpression='SET regional_names = if_not_exists(regional_names, :empty_map)',
                    ExpressionAttributeValues={':empty_map': {}}
                )
                
                self.global_table.update_item(
                    Key={'product_id': product_id},
                    UpdateExpression='SET regional_names.#region = list_append(if_not_exists(regional_names.#region, :empty_list), :name)',
                    ExpressionAttributeNames={'#region': region_code},
                    ExpressionAttributeValues={
                        ':name': [regional_name],
                        ':empty_list': []
                    }
                )
                    
            return True
            
        except Exception as e:
            print(f"Error adding regional name: {e}")
            raise

    async def get_regional_display_name(self, product_id: str, region_code: str, fallback_to_primary: bool = True) -> str:
        """Get the best regional name for display"""
        try:
            response = self.global_table.get_item(Key={'product_id': product_id})
            
            if 'Item' not in response:
                return None
                
            product = response['Item']
            regional_names = product.get('regional_names', {})
            
            # Check if region has verified regional names
            if region_code in regional_names and regional_names[region_code]:
                return regional_names[region_code][0]  # Return first/primary regional name
            
            # Fallback to primary name if requested
            if fallback_to_primary:
                return product.get('name')
            
            return None
            
        except Exception as e:
            print(f"Error getting regional display name: {e}")
            return None

    async def search_by_regional_name(self, regional_name: str, region_code: str = None) -> list:
        """Search products by regional name"""
        try:
            # This requires a scan since we can't index nested maps efficiently
            # For production, consider a separate regional_names lookup table
            
            filter_expression = 'contains(#regional_names, :search_name)'
            expression_attr_names = {'#regional_names': 'regional_names'}
            expression_attr_values = {':search_name': regional_name}
            
            # If region specified, add region filter
            if region_code:
                filter_expression += ' AND attribute_exists(regional_names.#region)'
                expression_attr_names['#region'] = region_code
            
            response = self.global_table.scan(
                FilterExpression=filter_expression,
                ExpressionAttributeNames=expression_attr_names,
                ExpressionAttributeValues=expression_attr_values,
                Limit=50  # Limit for performance
            )
            
            matches = []
            for item in response['Items']:
                # Calculate match confidence
                confidence = 0.8  # Base confidence for regional name match
                
                # Check exact match vs partial match
                regional_names = item.get('regional_names', {})
                for region, names in regional_names.items():
                    if regional_name.lower() in [name.lower() for name in names]:
                        if region == region_code:
                            confidence = 1.0  # Exact region match
                        break
                
                matches.append({
                    'product': item,
                    'confidence': confidence,
                    'match_reason': f'regional_name_match_{region_code or "any"}'
                })
            
            return sorted(matches, key=lambda x: x['confidence'], reverse=True)
            
        except Exception as e:
            print(f"Error searching by regional name: {e}")
            return []

    async def get_regional_name_variants(self, product_id: str) -> dict:
        """Return all regional name variants for a product"""
        try:
            response = self.global_table.get_item(Key={'product_id': product_id})
            
            if 'Item' not in response:
                return {}
                
            product = response['Item']
            return {
                'primary_name': product.get('name'),
                'regional_names': product.get('regional_names', {}),
                'contributed_names': product.get('contributed_names', {}),
                'primary_regions': product.get('primary_regions', [])
            }
            
        except Exception as e:
            print(f"Error getting regional name variants: {e}")
            return {}

    async def update_product_status(self, product_id: str, new_status: str, updated_by: str, notes: str = None):
        """Update product verification status with admin tracking"""
        try:
            if new_status not in PRODUCT_STATUSES:
                raise ValueError(f"Invalid status: {new_status}")
            
            # Get current status for history
            current_response = self.global_table.get_item(Key={'product_id': product_id})
            if 'Item' not in current_response:
                raise Exception(f"Product {product_id} not found")
            
            current_status = current_response['Item'].get('verification_status', 'unknown')
            
            update_data = {
                'verification_status': new_status,
                'updated_at': datetime.utcnow().isoformat(),
                'last_updated_by': updated_by
            }
            
            if notes:
                update_data['admin_notes'] = notes
            
            # Add to status history
            status_change = {
                'timestamp': datetime.utcnow().isoformat(),
                'from_status': current_status,
                'to_status': new_status,
                'updated_by': updated_by,
                'notes': notes or ''
            }
            
            self.global_table.update_item(
                Key={'product_id': product_id},
                UpdateExpression='SET verification_status = :status, updated_at = :updated, last_updated_by = :updater, status_history = list_append(if_not_exists(status_history, :empty_list), :change)',
                ExpressionAttributeValues={
                    ':status': new_status,
                    ':updated': update_data['updated_at'],
                    ':updater': updated_by,
                    ':change': [status_change],
                    ':empty_list': []
                }
            )
            
            return True
            
        except Exception as e:
            print(f"Error updating product status: {e}")
            raise

    async def bulk_import_products(self, products_data: list, imported_by: str, source: str = 'admin'):
        """Bulk import products for admin seeding"""
        import_stats = {
            'total_imported': 0,
            'successful': 0,
            'failed': 0,
            'duplicates_found': 0,
            'errors': []
        }
        
        for product_data in products_data:
            try:
                import_stats['total_imported'] += 1
                
                # Check for existing product
                existing = await self.find_existing_product(
                    barcode=product_data.get('barcode'),
                    name=product_data.get('name'),
                    brand=product_data.get('brand')
                )
                
                if existing:
                    import_stats['duplicates_found'] += 1
                    continue
                
                # Prepare product data with admin status
                admin_product_data = {
                    **product_data,
                    'verification_status': 'admin_created',
                    'created_by': imported_by,
                    'import_source': source,
                    'quality_score': self.calculate_quality_score(product_data)
                }
                
                # Create global product
                product_id = await self.create_global_product(admin_product_data)
                import_stats['successful'] += 1
                
            except Exception as e:
                import_stats['failed'] += 1
                import_stats['errors'].append({
                    'product': product_data.get('name', 'Unknown'),
                    'error': str(e)
                })
        
        return import_stats

    def calculate_quality_score(self, product_data: dict) -> int:
        """Calculate quality score based on data completeness"""
        score = 0
        max_score = 100
        
        # Required fields (40 points)
        if product_data.get('name'): score += 15
        if product_data.get('brand'): score += 10
        if product_data.get('category'): score += 15
        
        # Identification (30 points)
        if product_data.get('barcode'): score += 30
        
        # Images (20 points)
        images = product_data.get('canonical_image_urls', {})
        if images.get('original'): score += 10
        if images.get('thumbnail'): score += 5
        if images.get('medium'): score += 5
        
        # Additional data (10 points)
        if product_data.get('attributes', {}).get('description'): score += 5
        if product_data.get('attributes', {}).get('weight'): score += 5
        
        return min(score, max_score)

    async def get_products_by_status(self, status: str, limit: int = 50, last_key: str = None):
        """Get products filtered by verification status"""
        try:
            if status not in PRODUCT_STATUSES:
                raise ValueError(f"Invalid status: {status}")
            
            scan_params = {
                'FilterExpression': 'verification_status = :status',
                'ExpressionAttributeValues': {':status': status},
                'Limit': limit
            }
            
            if last_key:
                scan_params['ExclusiveStartKey'] = json.loads(last_key)
            
            response = self.global_table.scan(**scan_params)
            
            return {
                'products': response['Items'],
                'last_key': json.dumps(response.get('LastEvaluatedKey')) if response.get('LastEvaluatedKey') else None,
                'count': len(response['Items'])
            }
            
        except Exception as e:
            print(f"Error getting products by status: {e}")
            raise

    async def get_products_needing_review(self, limit: int = 50, last_key: str = None):
        """Get products that need admin review (pending, flagged, or low quality)"""
        try:
            scan_params = {
                'FilterExpression': 'verification_status IN (:pending, :flagged) OR quality_score < :min_score',
                'ExpressionAttributeValues': {
                    ':pending': 'pending',
                    ':flagged': 'flagged',
                    ':min_score': 40
                },
                'Limit': limit
            }
            
            if last_key:
                scan_params['ExclusiveStartKey'] = json.loads(last_key)
            
            response = self.global_table.scan(**scan_params)
            
            return {
                'products': response['Items'],
                'last_key': json.dumps(response.get('LastEvaluatedKey')) if response.get('LastEvaluatedKey') else None,
                'count': len(response['Items'])
            }
            
        except Exception as e:
            print(f"Error getting products needing review: {e}")
            raise

    async def bulk_update_product_status(self, product_ids: list, new_status: str, updated_by: str, notes: str = None):
        """Bulk update product statuses"""
        try:
            if new_status not in PRODUCT_STATUSES:
                raise ValueError(f"Invalid status: {new_status}")
            
            results = {
                'total_requested': len(product_ids),
                'successful': 0,
                'failed': 0,
                'errors': []
            }
            
            for product_id in product_ids:
                try:
                    await self.update_product_status(product_id, new_status, updated_by, notes)
                    results['successful'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'product_id': product_id,
                        'error': str(e)
                    })
            
            return results
            
        except Exception as e:
            print(f"Error in bulk update product status: {e}")
            raise


def extract_region_from_store_data(store_data: dict) -> str:
    """Extract region code from store address/location"""
    state_mappings = {
        'andhra pradesh': 'IN-AP',
        'arunachal pradesh': 'IN-AR', 
        'assam': 'IN-AS',
        'bihar': 'IN-BR',
        'chhattisgarh': 'IN-CG',
        'goa': 'IN-GA',
        'gujarat': 'IN-GJ',
        'haryana': 'IN-HR',
        'himachal pradesh': 'IN-HP',
        'jharkhand': 'IN-JH',
        'karnataka': 'IN-KA',
        'kerala': 'IN-KL',
        'madhya pradesh': 'IN-MP',
        'maharashtra': 'IN-MH',
        'manipur': 'IN-MN',
        'meghalaya': 'IN-ML',
        'mizoram': 'IN-MZ',
        'nagaland': 'IN-NL',
        'odisha': 'IN-OR',
        'punjab': 'IN-PB',
        'rajasthan': 'IN-RJ',
        'sikkim': 'IN-SK',
        'tamil nadu': 'IN-TN',
        'telangana': 'IN-TG',
        'tripura': 'IN-TR',
        'uttar pradesh': 'IN-UP',
        'uttarakhand': 'IN-UK',
        'west bengal': 'IN-WB',
        'delhi': 'IN-DL',
        'mumbai': 'IN-MH',
        'chennai': 'IN-TN',
        'kolkata': 'IN-WB',
        'bangalore': 'IN-KA',
        'hyderabad': 'IN-TG',
        'pune': 'IN-MH'
    }
    
    address = store_data.get('address', '').lower()
    state = store_data.get('state', '').lower()
    city = store_data.get('city', '').lower()
    
    # Check state field first
    if state in state_mappings:
        return state_mappings[state]
    
    # Check city
    if city in state_mappings:
        return state_mappings[city]
    
    # Check address for state/city names
    for location, code in state_mappings.items():
        if location in address:
            return code
    
    return 'IN-DL'  # Default to Delhi if can't determine