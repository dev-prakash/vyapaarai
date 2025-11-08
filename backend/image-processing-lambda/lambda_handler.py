import json
import base64
import boto3
from PIL import Image
import io
import os
from datetime import datetime
import uuid

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

# Configuration
BUCKET_NAME = 'vyapaarai-product-images-prod'
CLOUDFRONT_DOMAIN = 'd2asjaaus4m4w2.cloudfront.net'
TABLE_NAME = 'vyaparai-products-prod'

def lambda_handler(event, context):
    """
    Process product images and generate multiple sizes
    """
    try:
        # Parse the event
        body = json.loads(event['body']) if 'body' in event else event
        
        # Extract image data and product info
        image_data = body.get('image_data')  # base64 encoded image
        product_id = body.get('product_id')
        store_id = body.get('store_id')
        
        if not all([image_data, product_id, store_id]):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Missing required fields: image_data, product_id, store_id'
                })
            }
        
        # Decode base64 image
        try:
            # Remove data URL prefix if present
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': f'Invalid image data: {str(e)}'
                })
            }
        
        # Generate unique filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        base_filename = f"{store_id}/{product_id}_{timestamp}_{unique_id}"
        
        # Generate multiple image sizes
        image_urls = {}
        
        # Original size (max 1920x1920)
        original = resize_image(image, 1920, 1920, 90)
        original_key = f"{base_filename}_original.jpg"
        upload_to_s3(original, original_key)
        image_urls['original'] = f"https://{CLOUDFRONT_DOMAIN}/{original_key}"
        
        # Large size (800x800)
        large = resize_image(image, 800, 800, 85)
        large_key = f"{base_filename}_large.jpg"
        upload_to_s3(large, large_key)
        image_urls['large'] = f"https://{CLOUDFRONT_DOMAIN}/{large_key}"
        
        # Medium size (400x400)
        medium = resize_image(image, 400, 400, 80)
        medium_key = f"{base_filename}_medium.jpg"
        upload_to_s3(medium, medium_key)
        image_urls['medium'] = f"https://{CLOUDFRONT_DOMAIN}/{medium_key}"
        
        # Thumbnail (150x150)
        thumbnail = resize_image(image, 150, 150, 75)
        thumbnail_key = f"{base_filename}_thumbnail.jpg"
        upload_to_s3(thumbnail, thumbnail_key)
        image_urls['thumbnail'] = f"https://{CLOUDFRONT_DOMAIN}/{thumbnail_key}"
        
        # Update product in DynamoDB with image URLs
        update_product_images(product_id, store_id, image_urls)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'message': 'Images processed successfully',
                'image_urls': image_urls
            })
        }
        
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': f'Internal server error: {str(e)}'
            })
        }

def resize_image(image, max_width, max_height, quality):
    """
    Resize image while maintaining aspect ratio
    """
    # Convert to RGB if necessary
    if image.mode in ('RGBA', 'LA', 'P'):
        image = image.convert('RGB')
    
    # Calculate new dimensions
    width, height = image.size
    ratio = min(max_width/width, max_height/height)
    
    if ratio < 1:
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Convert to bytes
    output = io.BytesIO()
    image.save(output, format='JPEG', quality=quality, optimize=True)
    output.seek(0)
    
    return output.getvalue()

def upload_to_s3(image_bytes, key):
    """
    Upload image to S3
    """
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=image_bytes,
        ContentType='image/jpeg',
        CacheControl='max-age=31536000'  # 1 year cache
    )

def update_product_images(product_id, store_id, image_urls):
    """
    Update product in DynamoDB with image URLs
    """
    try:
        # Update the product with image URLs
        update_expression = "SET image_urls = :image_urls, updated_at = :updated_at"
        expression_values = {
            ':image_urls': {'S': json.dumps(image_urls)},
            ':updated_at': {'S': datetime.utcnow().isoformat()}
        }
        
        dynamodb.update_item(
            TableName=TABLE_NAME,
            Key={'id': {'S': product_id}},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ConditionExpression='store_id = :store_id',
            ExpressionAttributeValues={
                **expression_values,
                ':store_id': {'S': store_id}
            }
        )
    except Exception as e:
        print(f"Error updating product images: {str(e)}")
        raise

