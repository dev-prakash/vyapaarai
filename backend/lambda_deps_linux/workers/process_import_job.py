"""
Background Processing Lambda Worker
Handles async CSV import processing with checkpoint/resume capability
"""

import csv
import io
import json
import boto3
import uuid
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

# AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')

# Configuration
CHUNK_SIZE = 50  # Process 50 rows at a time
MAX_LAMBDA_DURATION_MS = 14 * 60 * 1000  # 14 minutes (leave 1 min buffer)
BULK_UPLOADS_BUCKET = 'vyapaarai-bulk-uploads-prod'
PRODUCT_IMAGES_BUCKET = 'vyapaarai-product-images-prod'

# Import services
import sys
sys.path.append('/opt/python')  # For Lambda layer
from services.import_job_service import ImportJobService, JobStatus
from services.product_catalog_service import ProductCatalogService
from utils.image_processor import ImageProcessor

def lambda_handler(event, context):
    """
    Background job processor for CSV imports
    
    Event payload:
    {
        "job_id": "admin_import_20250106_abc123",
        "checkpoint": null  # or {"last_processed_row": 1500} for resume
    }
    """
    
    job_id = event['job_id']
    checkpoint = event.get('checkpoint')
    
    import_service = ImportJobService()
    product_service = ProductCatalogService()
    image_processor = ImageProcessor()
    
    try:
        # Load job record
        job = import_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        # Update status to processing
        import_service.update_job_status(job_id, JobStatus.PROCESSING, started_at=datetime.utcnow())
        
        # Download CSV from S3
        s3_response = s3_client.get_object(Bucket=job['s3_bucket'], Key=job['s3_input_key'])
        csv_content = s3_response['Body'].read().decode('utf-8')
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)
        total_rows = len(rows)
        
        # Initialize or resume from checkpoint
        start_row = checkpoint['last_processed_row'] if checkpoint else 0
        processed = start_row
        success = job.get('successful_count', 0)
        duplicates = job.get('duplicate_count', 0)
        errors = []
        
        # Process in chunks
        for chunk_start in range(start_row, total_rows, CHUNK_SIZE):
            # Check remaining Lambda time
            remaining_time_ms = context.get_remaining_time_in_millis()
            if remaining_time_ms < 30000:  # Less than 30 seconds remaining
                # Save checkpoint and re-invoke
                checkpoint_data = {"last_processed_row": processed}
                import_service.save_checkpoint(job_id, checkpoint_data)
                reinvoke_lambda(job_id, checkpoint_data, context.function_name)
                return {"status": "checkpointed", "processed": processed}
            
            chunk_end = min(chunk_start + CHUNK_SIZE, total_rows)
            chunk = rows[chunk_start:chunk_end]
            
            # Process each row in chunk
            for idx, row in enumerate(chunk):
                row_number = chunk_start + idx + 2  # +2 for header and 0-indexing
                
                try:
                    # Parse row into product data
                    product_data = parse_product_row(row, job['import_options'])
                    
                    # Dedupe check
                    existing = await product_service.find_existing_product(
                        barcode=product_data.get('barcode'),
                        image_hash=product_data.get('image_hash'),
                        name=product_data.get('name'),
                        brand=product_data.get('brand')
                    )
                    
                    if existing:
                        duplicates += 1
                        continue
                    
                    # Process images (if admin import and option enabled)
                    if job['job_type'] == 'admin_product_import' and job['import_options'].get('process_images', True):
                        image_urls = extract_image_urls(row)
                        if image_urls:
                            processed_images = image_processor.process_images(
                                image_urls,
                                product_id=product_data['product_id']
                            )
                            product_data['canonical_image_urls'] = processed_images['canonical_urls']
                            product_data['image_hash'] = processed_images['image_hash']
                    
                    # Compute quality score
                    product_data['quality_score'] = calculate_quality_score(product_data)
                    
                    # Set verification status
                    product_data['verification_status'] = job['import_options'].get('default_verification_status', 'admin_created')
                    product_data['created_by'] = job['created_by_user_id']
                    product_data['created_at'] = datetime.utcnow().isoformat()
                    
                    # Create product
                    await product_service.create_global_product(product_data)
                    success += 1
                    
                except Exception as e:
                    errors.append({
                        "row_number": row_number,
                        "barcode": row.get('barcode', 'N/A'),
                        "name": row.get('name', 'N/A'),
                        "error_code": type(e).__name__,
                        "error_message": str(e)
                    })
            
            # Update progress after each chunk
            processed = chunk_end
            import_service.update_job_progress(
                job_id,
                processed_rows=processed,
                successful_count=success,
                duplicate_count=duplicates,
                error_count=len(errors),
                recent_errors=errors[-10:]  # Keep last 10 errors
            )
        
        # Job complete - finalize
        final_status = JobStatus.COMPLETED if len(errors) == 0 else JobStatus.COMPLETED_WITH_ERRORS
        
        # Write error report if errors exist
        error_report_key = None
        if errors:
            error_report_key = write_error_report_to_s3(job['s3_bucket'], job_id, errors, rows)
        
        # Update job to completed
        import_service.update_job_status(
            job_id,
            final_status,
            completed_at=datetime.utcnow(),
            s3_error_report_key=error_report_key
        )
        
        # Send notification email
        send_completion_email(job)
        
        return {
            "statusCode": 200,
            "job_id": job_id,
            "status": final_status.value,
            "summary": {
                "total": total_rows,
                "processed": processed,
                "successful": success,
                "duplicates": duplicates,
                "errors": len(errors)
            }
        }
        
    except Exception as e:
        # Mark job as failed
        import_service.update_job_status(job_id, JobStatus.FAILED)
        return {
            "statusCode": 500,
            "error": str(e),
            "job_id": job_id
        }


def parse_product_row(row: Dict[str, str], options: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse CSV row into product data structure
    
    Handles:
    - Basic fields: name, brand, category, barcode
    - Attributes: description, size, weight, etc.
    - Nutrition: nutrition_* columns → attributes.nutrition map
    - Regional names: regional_names_* → regional_names map
    - Images: image_url_1 to image_url_10
    """
    
    product_id = f"GP{int(datetime.utcnow().timestamp() * 1000)}"
    
    product_data = {
        "product_id": product_id,
        "name": row.get('name', '').strip(),
        "brand": row.get('brand', '').strip(),
        "category": row.get('category', '').strip(),
        "barcode": clean_barcode(row.get('barcode', '')),
        "additional_barcodes": parse_additional_barcodes(row.get('additional_barcodes', '')),
        "attributes": {},
        "regional_names": {},
        "primary_regions": options.get('default_region', 'IN').split(',')
    }
    
    # Validate required fields
    if not product_data['name']:
        raise ValueError("Name is required")
    if not product_data['category']:
        raise ValueError("Category is required")
    
    # Parse attributes
    attribute_fields = ['description', 'size', 'unit', 'weight', 'pack_size', 
                       'manufacturer', 'country_of_origin', 'ingredients']
    for field in attribute_fields:
        if row.get(field):
            product_data['attributes'][field] = row[field].strip()
    
    # Parse nutrition
    nutrition = {}
    for key in row.keys():
        if key.startswith('nutrition_'):
            nutrient_name = key.replace('nutrition_', '')
            nutrition[nutrient_name] = row[key].strip()
    if nutrition:
        product_data['attributes']['nutrition'] = nutrition
    
    # Parse regional names
    for key in row.keys():
        if key.startswith('regional_names_'):
            region_code = key.replace('regional_names_', '').upper()
            names = [n.strip() for n in row[key].split('|') if n.strip()]
            if names:
                product_data['regional_names'][region_code] = names
    
    return product_data


def extract_image_urls(row: Dict[str, str]) -> List[str]:
    """Extract up to 10 image URLs from row"""
    urls = []
    for i in range(1, 11):
        url = row.get(f'image_url_{i}', '').strip()
        if url:
            urls.append(url)
    return urls


def clean_barcode(barcode: str) -> Optional[str]:
    """Clean and validate barcode"""
    if not barcode:
        return None
    
    # Remove spaces and non-digits
    cleaned = re.sub(r'[^\d]', '', barcode)
    
    # Validate length (8-13 digits)
    if len(cleaned) < 8 or len(cleaned) > 13:
        return None
    
    return cleaned


def parse_additional_barcodes(barcodes_str: str) -> List[str]:
    """Parse comma-separated additional barcodes"""
    if not barcodes_str:
        return []
    
    barcodes = []
    for barcode in barcodes_str.split(','):
        cleaned = clean_barcode(barcode.strip())
        if cleaned:
            barcodes.append(cleaned)
    
    return barcodes


def calculate_quality_score(product_data: Dict[str, Any]) -> int:
    """Calculate quality score based on data completeness"""
    score = 0
    max_score = 100
    
    # Basic info (30 points)
    if product_data.get('name'): score += 10
    if product_data.get('brand'): score += 10
    if product_data.get('category'): score += 10
    
    # Barcode (20 points)
    if product_data.get('barcode'): score += 20
    
    # Images (20 points)
    if product_data.get('canonical_image_urls'): score += 20
    
    # Attributes (30 points)
    attributes = product_data.get('attributes', {})
    if attributes.get('description'): score += 10
    if attributes.get('weight'): score += 5
    if attributes.get('size'): score += 5
    if attributes.get('manufacturer'): score += 5
    if attributes.get('country_of_origin'): score += 5
    
    return min(score, max_score)


def write_error_report_to_s3(bucket: str, job_id: str, errors: List[Dict], original_rows: List[Dict]) -> str:
    """
    Write detailed error report CSV to S3
    
    Format: Original CSV columns + Error_Code + Error_Message columns
    """
    
    error_key = f"admin-imports/{job_id}/errors.csv"
    
    # Map errors by row number
    error_map = {e['row_number']: e for e in errors}
    
    # Build error CSV
    if not original_rows:
        return None
    
    fieldnames = list(original_rows[0].keys()) + ['Error_Code', 'Error_Message']
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for idx, row in enumerate(original_rows):
        row_number = idx + 2  # +2 for header and 0-indexing
        if row_number in error_map:
            error_info = error_map[row_number]
            row_with_error = {**row, 
                            'Error_Code': error_info['error_code'],
                            'Error_Message': error_info['error_message']}
            writer.writerow(row_with_error)
    
    # Upload to S3
    s3_client.put_object(
        Bucket=bucket,
        Key=error_key,
        Body=output.getvalue().encode('utf-8'),
        ContentType='text/csv'
    )
    
    return error_key


def reinvoke_lambda(job_id: str, checkpoint: Dict, function_name: str):
    """Re-invoke self with checkpoint for continuation"""
    lambda_client.invoke(
        FunctionName=function_name,
        InvocationType='Event',  # Async
        Payload=json.dumps({
            "job_id": job_id,
            "checkpoint": checkpoint
        })
    )


def send_completion_email(job: Dict[str, Any]):
    """Send completion notification email"""
    try:
        # This would integrate with SES
        # For now, just log
        print(f"Job {job['job_id']} completed. Status: {job['status']}")
    except Exception as e:
        print(f"Failed to send completion email: {e}")
