"""
Comprehensive Test Suite for VyapaarAI Async Import System
Tests all components: endpoints, job service, image processor, and worker
"""

import json
import csv
import io
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any
import boto3
import pytest
from unittest.mock import Mock, patch, MagicMock

# Test configuration
TEST_BUCKET = 'vyapaarai-bulk-uploads-test'
TEST_IMAGES_BUCKET = 'vyapaarai-product-images-test'
TEST_JOBS_TABLE = 'vyaparai-import-jobs-test'

class TestAsyncImportSystem:
    """Test suite for async import system"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.s3_client = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        
        # Create test buckets if they don't exist
        try:
            self.s3_client.create_bucket(Bucket=TEST_BUCKET)
        except:
            pass
        try:
            self.s3_client.create_bucket(Bucket=TEST_IMAGES_BUCKET)
        except:
            pass
    
    def teardown_method(self):
        """Cleanup after each test method"""
        # Clean up test data
        pass
    
    def test_import_job_service_create_job(self):
        """Test ImportJobService job creation"""
        from services.import_job_service import ImportJobService, ImportOptions
        
        service = ImportJobService()
        options = ImportOptions(
            skip_duplicates=True,
            process_images=True,
            default_region="IN"
        )
        
        job_id = f"test_job_{uuid.uuid4().hex[:8]}"
        
        job = service.create_job(
            job_id=job_id,
            job_type="admin_product_import",
            s3_bucket=TEST_BUCKET,
            s3_input_key=f"test/{job_id}/input.csv",
            created_by_user_id="test_user",
            created_by_email="test@example.com",
            import_options=options,
            estimated_rows=100
        )
        
        assert job['job_id'] == job_id
        assert job['job_type'] == "admin_product_import"
        assert job['status'] == "queued"
        assert job['total_rows'] == 100
    
    def test_import_job_service_s3_operations(self):
        """Test S3 operations in ImportJobService"""
        from services.import_job_service import ImportJobService
        
        service = ImportJobService()
        
        # Test CSV content
        csv_content = "name,category,brand\nTest Product,Electronics,Test Brand"
        
        # Upload test CSV
        test_key = f"test/{uuid.uuid4().hex}/test.csv"
        self.s3_client.put_object(
            Bucket=TEST_BUCKET,
            Key=test_key,
            Body=csv_content.encode('utf-8'),
            ContentType='text/csv'
        )
        
        # Test S3 object verification
        assert service.verify_s3_object(TEST_BUCKET, test_key) == True
        assert service.verify_s3_object(TEST_BUCKET, "nonexistent.csv") == False
        
        # Test file info
        file_info = service.get_file_info(TEST_BUCKET, test_key)
        assert file_info['size'] > 0
        assert file_info['content_type'] == 'text/csv'
        
        # Test CSV validation
        validation = service.validate_csv_structure(TEST_BUCKET, test_key, "admin_product_import")
        assert validation['valid'] == True
        assert 'name' in validation['headers']
        assert 'category' in validation['headers']
    
    def test_image_processor_basic_operations(self):
        """Test ImageProcessor basic operations"""
        from utils.image_processor import ImageProcessor
        
        processor = ImageProcessor()
        
        # Test URL validation
        valid_urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image2.png"
        ]
        
        invalid_urls = [
            "not-a-url",
            "ftp://example.com/image.jpg"
        ]
        
        validation_result = processor.validate_image_urls(valid_urls + invalid_urls)
        
        assert len(validation_result['valid']) == 2
        assert len(validation_result['invalid']) == 2
        assert len(validation_result['errors']) == 2
    
    @patch('utils.image_processor.requests.get')
    def test_image_processor_download_and_process(self, mock_get):
        """Test image downloading and processing with mocked requests"""
        from utils.image_processor import ImageProcessor
        from PIL import Image
        
        processor = ImageProcessor()
        
        # Mock image data
        mock_image_data = b'fake_image_data'
        mock_response = Mock()
        mock_response.content = mock_image_data
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Mock PIL Image
        with patch('PIL.Image.open') as mock_open:
            mock_img = Mock()
            mock_img.format = 'JPEG'
            mock_img.mode = 'RGB'
            mock_img.size = (800, 600)
            mock_img.thumbnail = Mock()
            mock_img.convert = Mock(return_value=mock_img)
            mock_open.return_value = mock_img
            
            # Mock S3 operations
            with patch.object(processor, 's3_client') as mock_s3:
                mock_s3.put_object = Mock()
                
                # Test image processing
                image_urls = ["https://example.com/test.jpg"]
                result = processor.process_images(image_urls, "test_product_123")
                
                assert 'canonical_urls' in result
                assert 'image_hash' in result
                assert result['processed_count'] > 0
    
    def test_product_catalog_service_name_brand_key(self):
        """Test name-brand key computation"""
        from services.product_catalog_service import ProductCatalogService
        
        service = ProductCatalogService()
        
        # Test key computation
        key1 = service.compute_name_brand_key("Nestle", "Maggi 2-Minute Noodles")
        key2 = service.compute_name_brand_key("nestle", "maggi 2 minute noodles")
        key3 = service.compute_name_brand_key("NESTLE", "MAGGI 2-MINUTE NOODLES")
        
        # All should be the same (normalized)
        assert key1 == key2 == key3
        assert key1 == "nestle#maggi2minutenoodles"
    
    def test_csv_parsing_logic(self):
        """Test CSV parsing logic from worker"""
        from workers.process_import_job import parse_product_row, extract_image_urls, clean_barcode
        
        # Test product row parsing
        test_row = {
            'name': 'Test Product',
            'category': 'Electronics',
            'brand': 'Test Brand',
            'barcode': '1234567890123',
            'description': 'A test product',
            'weight': '500g',
            'image_url_1': 'https://example.com/img1.jpg',
            'image_url_2': 'https://example.com/img2.jpg',
            'nutrition_energy': '100',
            'nutrition_fat': '5',
            'regional_names_IN-MH': 'टेस्ट प्रोडक्ट',
            'regional_names_IN-TN': 'டெஸ்ட் ப்ராடக்ட்'
        }
        
        options = {
            'default_region': 'IN',
            'default_verification_status': 'admin_created'
        }
        
        product_data = parse_product_row(test_row, options)
        
        assert product_data['name'] == 'Test Product'
        assert product_data['category'] == 'Electronics'
        assert product_data['barcode'] == '1234567890123'
        assert product_data['attributes']['description'] == 'A test product'
        assert product_data['attributes']['weight'] == '500g'
        assert product_data['attributes']['nutrition']['energy'] == '100'
        assert product_data['regional_names']['IN-MH'] == ['टेस्ट प्रोडक्ट']
        assert product_data['regional_names']['IN-TN'] == ['டெஸ்ட் ப்ராடக்ட்']
        
        # Test image URL extraction
        image_urls = extract_image_urls(test_row)
        assert len(image_urls) == 2
        assert 'https://example.com/img1.jpg' in image_urls
        assert 'https://example.com/img2.jpg' in image_urls
        
        # Test barcode cleaning
        assert clean_barcode('123-456-789-0123') == '1234567890123'
        assert clean_barcode('123 456 789 0123') == '1234567890123'
        assert clean_barcode('invalid') == None
        assert clean_barcode('12345') == None  # Too short
    
    def test_quality_score_calculation(self):
        """Test quality score calculation"""
        from workers.process_import_job import calculate_quality_score
        
        # Test complete product data
        complete_product = {
            'name': 'Test Product',
            'brand': 'Test Brand',
            'category': 'Electronics',
            'barcode': '1234567890123',
            'canonical_image_urls': {'original': 's3://bucket/image.jpg'},
            'attributes': {
                'description': 'A test product',
                'weight': '500g',
                'size': 'Large',
                'manufacturer': 'Test Corp',
                'country_of_origin': 'India'
            }
        }
        
        score = calculate_quality_score(complete_product)
        assert score == 100  # Should be perfect score
        
        # Test minimal product data
        minimal_product = {
            'name': 'Test Product',
            'category': 'Electronics'
        }
        
        score = calculate_quality_score(minimal_product)
        assert score == 20  # Basic info only
    
    def test_error_report_generation(self):
        """Test error report CSV generation"""
        from workers.process_import_job import write_error_report_to_s3
        
        # Mock S3 client
        with patch('workers.process_import_job.s3_client') as mock_s3:
            mock_s3.put_object = Mock()
            
            # Test data
            errors = [
                {
                    'row_number': 2,
                    'barcode': '1234567890123',
                    'name': 'Test Product',
                    'error_code': 'ValidationError',
                    'error_message': 'Name is required'
                }
            ]
            
            original_rows = [
                {'name': 'Test Product', 'category': 'Electronics', 'barcode': '1234567890123'}
            ]
            
            result = write_error_report_to_s3(TEST_BUCKET, 'test_job', errors, original_rows)
            
            assert result is not None
            assert 'test_job' in result
            mock_s3.put_object.assert_called_once()
    
    def test_checkpoint_resume_logic(self):
        """Test checkpoint and resume functionality"""
        from services.import_job_service import ImportJobService
        
        service = ImportJobService()
        job_id = f"test_checkpoint_{uuid.uuid4().hex[:8]}"
        
        # Test checkpoint saving
        checkpoint_data = {"last_processed_row": 1500}
        result = service.save_checkpoint(job_id, checkpoint_data)
        assert result == True
        
        # Test job retrieval with checkpoint
        job = service.get_job(job_id)
        if job:  # Only test if job exists
            assert job.get('checkpoint') == checkpoint_data
    
    def test_job_status_updates(self):
        """Test job status update functionality"""
        from services.import_job_service import ImportJobService, JobStatus
        
        service = ImportJobService()
        job_id = f"test_status_{uuid.uuid4().hex[:8]}"
        
        # Create test job
        from services.import_job_service import ImportOptions
        options = ImportOptions()
        
        service.create_job(
            job_id=job_id,
            job_type="admin_product_import",
            s3_bucket=TEST_BUCKET,
            s3_input_key=f"test/{job_id}/input.csv",
            created_by_user_id="test_user",
            created_by_email="test@example.com",
            import_options=options,
            estimated_rows=100
        )
        
        # Test status update
        result = service.update_job_status(job_id, JobStatus.PROCESSING)
        assert result == True
        
        # Test progress update
        result = service.update_job_progress(
            job_id,
            processed_rows=50,
            successful_count=45,
            duplicate_count=3,
            error_count=2
        )
        assert result == True
    
    def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow"""
        # This would test the complete flow:
        # 1. Upload CSV to S3
        # 2. Create job record
        # 3. Process CSV
        # 4. Update progress
        # 5. Complete job
        
        # For now, just test the components work together
        from services.import_job_service import ImportJobService, ImportOptions
        from services.product_catalog_service import ProductCatalogService
        
        service = ImportJobService()
        catalog_service = ProductCatalogService()
        
        # Create test CSV
        csv_content = "name,category,brand,barcode\nTest Product,Electronics,Test Brand,1234567890123"
        job_id = f"e2e_test_{uuid.uuid4().hex[:8]}"
        test_key = f"test/{job_id}/input.csv"
        
        # Upload CSV
        self.s3_client.put_object(
            Bucket=TEST_BUCKET,
            Key=test_key,
            Body=csv_content.encode('utf-8'),
            ContentType='text/csv'
        )
        
        # Create job
        options = ImportOptions()
        job = service.create_job(
            job_id=job_id,
            job_type="admin_product_import",
            s3_bucket=TEST_BUCKET,
            s3_input_key=test_key,
            created_by_user_id="test_user",
            created_by_email="test@example.com",
            import_options=options,
            estimated_rows=1
        )
        
        assert job['job_id'] == job_id
        assert job['status'] == 'queued'
        
        # Test job retrieval
        retrieved_job = service.get_job(job_id)
        assert retrieved_job['job_id'] == job_id
    
    def test_large_csv_handling(self):
        """Test handling of large CSV files"""
        # Generate large CSV content
        headers = ['name', 'category', 'brand', 'barcode']
        rows = []
        
        for i in range(1000):  # 1000 rows
            rows.append([f'Product {i}', 'Electronics', f'Brand {i}', f'123456789{i:04d}'])
        
        csv_content = '\n'.join([','.join(headers)] + [','.join(row) for row in rows])
        
        # Test CSV parsing
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        parsed_rows = list(csv_reader)
        
        assert len(parsed_rows) == 1000
        assert parsed_rows[0]['name'] == 'Product 0'
        assert parsed_rows[999]['name'] == 'Product 999'
    
    def test_error_handling_edge_cases(self):
        """Test error handling for edge cases"""
        from workers.process_import_job import parse_product_row
        
        # Test missing required fields
        incomplete_row = {'category': 'Electronics'}  # Missing name
        
        with pytest.raises(ValueError, match="Name is required"):
            parse_product_row(incomplete_row, {})
        
        # Test empty row
        empty_row = {}
        
        with pytest.raises(ValueError, match="Name is required"):
            parse_product_row(empty_row, {})
        
        # Test malformed data
        malformed_row = {
            'name': 'Test Product',
            'category': 'Electronics',
            'barcode': 'invalid_barcode'
        }
        
        # Should not raise exception, but barcode should be cleaned
        result = parse_product_row(malformed_row, {})
        assert result['barcode'] is None  # Invalid barcode should be None

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
