"""
Import Job Service - Manages async import job lifecycle
Handles job creation, status updates, progress tracking, and S3 operations
"""

import boto3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

# DynamoDB setup
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

# Table names
IMPORT_JOBS_TABLE = 'vyaparai-import-jobs-prod'
BULK_UPLOADS_BUCKET = 'vyapaarai-bulk-uploads-prod'
PRODUCT_IMAGES_BUCKET = 'vyapaarai-product-images-prod'

class JobStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class ImportOptions:
    """Configuration options for import jobs"""
    skip_duplicates: bool = True
    auto_verify: bool = False
    default_verification_status: str = "admin_created"
    process_images: bool = True
    default_region: str = "IN"
    match_strategy: str = "strict"  # strict | fuzzy
    notification_email: Optional[str] = None

class ImportJobService:
    """Service for managing import job lifecycle"""
    
    def __init__(self):
        self.jobs_table = dynamodb.Table(IMPORT_JOBS_TABLE)
    
    def create_job(self, 
                   job_id: str,
                   job_type: str,
                   s3_bucket: str,
                   s3_input_key: str,
                   created_by_user_id: str,
                   created_by_email: str,
                   import_options: ImportOptions,
                   estimated_rows: int = 0,
                   input_filename: str = None,
                   input_file_size_bytes: int = 0) -> Dict[str, Any]:
        """
        Create a new import job record
        
        Args:
            job_id: Unique job identifier
            job_type: "admin_product_import" or "store_inventory_upload"
            s3_bucket: S3 bucket containing the CSV
            s3_input_key: S3 key for the CSV file
            created_by_user_id: User ID who created the job
            created_by_email: Email of job creator
            import_options: Import configuration
            estimated_rows: Estimated number of rows in CSV
            input_filename: Original filename
            input_file_size_bytes: File size in bytes
        
        Returns:
            Job record dictionary
        """
        
        now = datetime.utcnow()
        ttl = int((now + timedelta(days=30)).timestamp())
        
        job_record = {
            # Primary Key
            "job_id": job_id,
            
            # Job Type & Owner
            "job_type": job_type,
            "store_id": None,  # Will be set for store inventory uploads
            "created_by_user_id": created_by_user_id,
            "created_by_email": created_by_email,
            
            # Status Tracking
            "status": JobStatus.QUEUED.value,
            "status_history": [
                {
                    "timestamp": now.isoformat(),
                    "status": JobStatus.QUEUED.value
                }
            ],
            
            # Timestamps
            "created_at": now.isoformat(),
            "started_at": None,
            "completed_at": None,
            "estimated_completion_at": (now + timedelta(minutes=30)).isoformat(),
            
            # Progress Tracking
            "total_rows": estimated_rows,
            "processed_rows": 0,
            "successful_count": 0,
            "duplicate_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            
            # File References
            "s3_bucket": s3_bucket,
            "s3_input_key": s3_input_key,
            "s3_error_report_key": None,
            "input_filename": input_filename or "import.csv",
            "input_file_size_bytes": input_file_size_bytes,
            "input_row_count_estimate": estimated_rows,
            
            # Configuration
            "import_options": {
                "skip_duplicates": import_options.skip_duplicates,
                "auto_verify": import_options.auto_verify,
                "default_verification_status": import_options.default_verification_status,
                "process_images": import_options.process_images,
                "default_region": import_options.default_region,
                "match_strategy": import_options.match_strategy,
                "notification_email": import_options.notification_email
            },
            
            # Error Tracking
            "recent_errors": [],
            
            # Processing Metadata
            "processing_lambda_arn": None,
            "processing_start_memory_mb": None,
            "processing_duration_seconds": None,
            "checkpoint": None,
            
            # TTL for auto-cleanup
            "ttl": ttl,
            
            # GSIs for queries
            "created_by_user_id_gsi": created_by_user_id,
            "created_at_gsi": now.isoformat(),
            "status_gsi": JobStatus.QUEUED.value,
            "job_type_gsi": job_type
        }
        
        # Store job record
        self.jobs_table.put_item(Item=job_record)
        
        return job_record
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job record by ID"""
        try:
            response = self.jobs_table.get_item(Key={"job_id": job_id})
            return response.get('Item')
        except Exception as e:
            print(f"Error getting job {job_id}: {e}")
            return None
    
    def update_job_status(self, 
                         job_id: str, 
                         status: JobStatus,
                         started_at: datetime = None,
                         completed_at: datetime = None,
                         s3_error_report_key: str = None) -> bool:
        """Update job status and timestamps"""
        try:
            update_expression = "SET #status = :status, status_gsi = :status, #status_history = list_append(#status_history, :status_entry)"
            expression_attributes = {
                "#status": "status",
                "#status_history": "status_history"
            }
            expression_values = {
                ":status": status.value,
                ":status_entry": [{
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": status.value
                }]
            }
            
            if started_at:
                update_expression += ", started_at = :started_at"
                expression_values[":started_at"] = started_at.isoformat()
            
            if completed_at:
                update_expression += ", completed_at = :completed_at"
                expression_values[":completed_at"] = completed_at.isoformat()
            
            if s3_error_report_key:
                update_expression += ", s3_error_report_key = :error_report"
                expression_values[":error_report"] = s3_error_report_key
            
            self.jobs_table.update_item(
                Key={"job_id": job_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attributes,
                ExpressionAttributeValues=expression_values
            )
            
            return True
        except Exception as e:
            print(f"Error updating job status: {e}")
            return False
    
    def update_job_progress(self,
                           job_id: str,
                           processed_rows: int = None,
                           successful_count: int = None,
                           duplicate_count: int = None,
                           error_count: int = None,
                           recent_errors: List[Dict] = None) -> bool:
        """Update job progress metrics"""
        try:
            update_expression_parts = []
            expression_values = {}
            
            if processed_rows is not None:
                update_expression_parts.append("processed_rows = :processed")
                expression_values[":processed"] = processed_rows
            
            if successful_count is not None:
                update_expression_parts.append("successful_count = :successful")
                expression_values[":successful"] = successful_count
            
            if duplicate_count is not None:
                update_expression_parts.append("duplicate_count = :duplicates")
                expression_values[":duplicates"] = duplicate_count
            
            if error_count is not None:
                update_expression_parts.append("error_count = :errors")
                expression_values[":errors"] = error_count
            
            if recent_errors is not None:
                update_expression_parts.append("recent_errors = :recent_errors")
                expression_values[":recent_errors"] = recent_errors
            
            if not update_expression_parts:
                return True
            
            update_expression = "SET " + ", ".join(update_expression_parts)
            
            self.jobs_table.update_item(
                Key={"job_id": job_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            
            return True
        except Exception as e:
            print(f"Error updating job progress: {e}")
            return False
    
    def save_checkpoint(self, job_id: str, checkpoint_data: Dict[str, Any]) -> bool:
        """Save processing checkpoint for resume capability"""
        try:
            self.jobs_table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET checkpoint = :checkpoint",
                ExpressionAttributeValues={":checkpoint": checkpoint_data}
            )
            return True
        except Exception as e:
            print(f"Error saving checkpoint: {e}")
            return False
    
    def verify_s3_object(self, bucket: str, key: str) -> bool:
        """Verify S3 object exists"""
        try:
            s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False
    
    def get_file_info(self, bucket: str, key: str) -> Dict[str, Any]:
        """Get S3 object metadata"""
        try:
            response = s3_client.head_object(Bucket=bucket, Key=key)
            return {
                "size": response['ContentLength'],
                "last_modified": response['LastModified'],
                "content_type": response.get('ContentType', '')
            }
        except Exception as e:
            raise ValueError(f"Failed to get file info: {e}")
    
    def validate_csv_structure(self, bucket: str, key: str, job_type: str) -> Dict[str, Any]:
        """
        Validate CSV structure and estimate row count
        
        Returns:
            {
                "valid": bool,
                "error": str (if invalid),
                "estimated_rows": int,
                "headers": List[str]
            }
        """
        try:
            # Download first 1MB for structure validation
            response = s3_client.get_object(
                Bucket=bucket, 
                Key=key, 
                Range='bytes=0-1048576'  # First 1MB
            )
            content = response['Body'].read().decode('utf-8')
            
            lines = content.split('\n')
            if len(lines) < 2:
                return {"valid": False, "error": "CSV must have at least a header and one data row"}
            
            # Parse headers
            import csv
            import io
            csv_reader = csv.DictReader(io.StringIO('\n'.join(lines[:10])))  # First 10 lines
            headers = csv_reader.fieldnames
            
            # Validate required headers based on job type
            if job_type == "admin_product_import":
                required_headers = ['name', 'category']
                missing_headers = [h for h in required_headers if h not in headers]
                if missing_headers:
                    return {
                        "valid": False, 
                        "error": f"Missing required headers: {', '.join(missing_headers)}"
                    }
            
            # Estimate total rows (rough calculation)
            file_info = self.get_file_info(bucket, key)
            file_size = file_info['size']
            sample_size = len(content)
            estimated_rows = max(1, int((file_size / sample_size) * len(lines)))
            
            return {
                "valid": True,
                "estimated_rows": estimated_rows,
                "headers": headers
            }
            
        except Exception as e:
            return {"valid": False, "error": f"CSV validation failed: {str(e)}"}
    
    def list_user_jobs(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent jobs for a user"""
        try:
            response = self.jobs_table.query(
                IndexName='created_by_user_id_gsi-index',
                KeyConditionExpression='created_by_user_id_gsi = :user_id',
                ScanIndexForward=False,  # Most recent first
                Limit=limit
            )
            return response.get('Items', [])
        except Exception as e:
            print(f"Error listing user jobs: {e}")
            return []
    
    def list_jobs_by_status(self, status: JobStatus, limit: int = 100) -> List[Dict[str, Any]]:
        """List jobs by status (for monitoring)"""
        try:
            response = self.jobs_table.query(
                IndexName='status_gsi-index',
                KeyConditionExpression='status_gsi = :status',
                ScanIndexForward=False,
                Limit=limit
            )
            return response.get('Items', [])
        except Exception as e:
            print(f"Error listing jobs by status: {e}")
            return []
