# DynamoDB Tables for VyaparAI Hybrid Architecture
# Optimized for real-time operations with proper GSI design

# Orders Table - Primary table for real-time order processing
resource "aws_dynamodb_table" "orders" {
  name           = "vyaparai-orders-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "pk"
  range_key      = "sk"
  
  # Primary key attributes
  attribute {
    name = "pk"
    type = "S"
  }
  
  attribute {
    name = "sk"
    type = "S"
  }
  
  # GSI1 attributes for customer queries
  attribute {
    name = "gsi1pk"
    type = "S"
  }
  
  attribute {
    name = "gsi1sk"
    type = "S"
  }
  
  # GSI2 attributes for store queries
  attribute {
    name = "gsi2pk"
    type = "S"
  }
  
  attribute {
    name = "gsi2sk"
    type = "S"
  }
  
  # GSI3 attributes for status queries
  attribute {
    name = "gsi3pk"
    type = "S"
  }
  
  attribute {
    name = "gsi3sk"
    type = "S"
  }
  
  # Global Secondary Index 1: Customer Phone + Timestamp
  global_secondary_index {
    name            = "GSI1"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }
  
  # Global Secondary Index 2: Store ID + Timestamp
  global_secondary_index {
    name            = "GSI2"
    hash_key        = "gsi2pk"
    range_key       = "gsi2sk"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }
  
  # Global Secondary Index 3: Status + Timestamp
  global_secondary_index {
    name            = "GSI3"
    hash_key        = "gsi3pk"
    range_key       = "gsi3sk"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }
  
  # TTL for automatic cleanup
  ttl {
    enabled        = true
    attribute_name = "ttl"
  }
  
  # Streams for real-time processing
  stream_specification {
    stream_enabled   = true
    stream_view_type = "NEW_AND_OLD_IMAGES"
  }
  
  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }
  
  # Server-side encryption
  server_side_encryption {
    enabled = true
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-orders"
    TableType   = "hot-path"
  }
}

# Sessions Table - For session management and caching
resource "aws_dynamodb_table" "sessions" {
  name           = "vyaparai-sessions-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "pk"
  
  # Primary key attributes
  attribute {
    name = "pk"
    type = "S"
  }
  
  # GSI1 attributes for customer sessions
  attribute {
    name = "gsi1pk"
    type = "S"
  }
  
  attribute {
    name = "gsi1sk"
    type = "S"
  }
  
  # Global Secondary Index 1: Customer Phone + Session Type
  global_secondary_index {
    name            = "GSI1"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }
  
  # TTL for automatic session cleanup
  ttl {
    enabled        = true
    attribute_name = "ttl"
  }
  
  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }
  
  # Server-side encryption
  server_side_encryption {
    enabled = true
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-sessions"
    TableType   = "session-cache"
  }
}

# Rate Limits Table - For distributed rate limiting
resource "aws_dynamodb_table" "rate_limits" {
  name           = "vyaparai-rate-limits-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "pk"
  range_key      = "sk"
  
  # Primary key attributes
  attribute {
    name = "pk"
    type = "S"
  }
  
  attribute {
    name = "sk"
    type = "S"
  }
  
  # GSI1 attributes for time-based queries
  attribute {
    name = "gsi1pk"
    type = "S"
  }
  
  attribute {
    name = "gsi1sk"
    type = "S"
  }
  
  # Global Secondary Index 1: Time-based cleanup
  global_secondary_index {
    name            = "GSI1"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }
  
  # TTL for automatic cleanup of expired rate limits
  ttl {
    enabled        = true
    attribute_name = "ttl"
  }
  
  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }
  
  # Server-side encryption
  server_side_encryption {
    enabled = true
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-rate-limits"
    TableType   = "rate-limiting"
  }
}

# Stores Table - For store configuration and metadata
resource "aws_dynamodb_table" "stores" {
  name           = "vyaparai-stores-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "pk"
  
  # Primary key attributes
  attribute {
    name = "pk"
    type = "S"
  }
  
  # GSI1 attributes for owner queries
  attribute {
    name = "gsi1pk"
    type = "S"
  }
  
  attribute {
    name = "gsi1sk"
    type = "S"
  }
  
  # GSI2 attributes for location-based queries
  attribute {
    name = "gsi2pk"
    type = "S"
  }
  
  attribute {
    name = "gsi2sk"
    type = "S"
  }
  
  # Global Secondary Index 1: Owner ID + Store Type
  global_secondary_index {
    name            = "GSI1"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }
  
  # Global Secondary Index 2: Location + Store Status
  global_secondary_index {
    name            = "GSI2"
    hash_key        = "gsi2pk"
    range_key       = "gsi2sk"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }
  
  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }
  
  # Server-side encryption
  server_side_encryption {
    enabled = true
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-stores"
    TableType   = "master-data"
  }
}

# Products Table - For product catalog and search
resource "aws_dynamodb_table" "products" {
  name           = "vyaparai-products-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "pk"
  range_key      = "sk"
  
  # Primary key attributes
  attribute {
    name = "pk"
    type = "S"
  }
  
  attribute {
    name = "sk"
    type = "S"
  }
  
  # GSI1 attributes for category queries
  attribute {
    name = "gsi1pk"
    type = "S"
  }
  
  attribute {
    name = "gsi1sk"
    type = "S"
  }
  
  # GSI2 attributes for brand queries
  attribute {
    name = "gsi2pk"
    type = "S"
  }
  
  attribute {
    name = "gsi2sk"
    type = "S"
  }
  
  # GSI3 attributes for popularity queries
  attribute {
    name = "gsi3pk"
    type = "S"
  }
  
  attribute {
    name = "gsi3sk"
    type = "S"
  }
  
  # Global Secondary Index 1: Category + Product Name
  global_secondary_index {
    name            = "GSI1"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }
  
  # Global Secondary Index 2: Brand + Product Name
  global_secondary_index {
    name            = "GSI2"
    hash_key        = "gsi2pk"
    range_key       = "gsi2sk"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }
  
  # Global Secondary Index 3: Popularity + Product Name
  global_secondary_index {
    name            = "GSI3"
    hash_key        = "gsi3pk"
    range_key       = "gsi3sk"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }
  
  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }
  
  # Server-side encryption
  server_side_encryption {
    enabled = true
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-products"
    TableType   = "catalog"
  }
}

# Global Products Table - Shared product catalog (content-addressed, deduplicated)
resource "aws_dynamodb_table" "global_products" {
  name         = "vyaparai-global-products-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "product_id"

  # Primary key attribute
  attribute {
    name = "product_id"
    type = "S"
  }

  # GSI attributes
  attribute {
    name = "barcode"
    type = "S"
  }

  attribute {
    name = "image_hash"
    type = "S"
  }

  # GSI: barcode-index (for exact barcode lookups)
  global_secondary_index {
    name            = "barcode-index"
    hash_key        = "barcode"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }

  # GSI: image_hash-index (for duplicate detection)
  global_secondary_index {
    name            = "image_hash-index"
    hash_key        = "image_hash"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }

  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  # Server-side encryption
  server_side_encryption {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Service     = "vyaparai-products-global"
    TableType   = "catalog-global"
  }
}

# Store Inventory Table - Store-scoped inventory referencing global products
resource "aws_dynamodb_table" "store_inventory" {
  name         = "vyaparai-store-inventory-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "store_id"
  range_key    = "product_id"

  # Primary key attributes
  attribute {
    name = "store_id"
    type = "S"
  }

  attribute {
    name = "product_id"
    type = "S"
  }

  # GSI attributes
  # Cross-store analytics by product
  attribute {
    name = "gsi_product_id"
    type = "S"
  }

  # GSI: product_id-index (hash on product_id)
  global_secondary_index {
    name            = "product_id-index"
    hash_key        = "gsi_product_id"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }

  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  # Server-side encryption
  server_side_encryption {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Service     = "vyaparai-store-inventory"
    TableType   = "inventory"
  }
}

# Metrics Table - For real-time metrics and counters
resource "aws_dynamodb_table" "metrics" {
  name           = "vyaparai-metrics-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "pk"
  range_key      = "sk"
  
  # Primary key attributes
  attribute {
    name = "pk"
    type = "S"
  }
  
  attribute {
    name = "sk"
    type = "S"
  }
  
  # GSI1 attributes for time-based queries
  attribute {
    name = "gsi1pk"
    type = "S"
  }
  
  attribute {
    name = "gsi1sk"
    type = "S"
  }
  
  # Global Secondary Index 1: Time-based aggregation
  global_secondary_index {
    name            = "GSI1"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }
  
  # TTL for automatic cleanup of old metrics
  ttl {
    enabled        = true
    attribute_name = "ttl"
  }
  
  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }
  
  # Server-side encryption
  server_side_encryption {
    enabled = true
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-metrics"
    TableType   = "metrics"
  }
}

# GST Rates Table - Dynamic GST category rates (admin-managed)
resource "aws_dynamodb_table" "gst_rates" {
  name         = "vyaparai-gst-rates-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "category_code"

  # Primary key attribute
  attribute {
    name = "category_code"
    type = "S"
  }

  # GSI attribute for rate-based queries
  attribute {
    name = "gst_rate"
    type = "N"
  }

  # GSI: gst-rate-index (for querying categories by rate)
  global_secondary_index {
    name            = "gst-rate-index"
    hash_key        = "gst_rate"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }

  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  # Server-side encryption
  server_side_encryption {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Service     = "vyaparai-gst"
    TableType   = "reference-data"
  }
}

# HSN Mappings Table - HSN code to GST category mappings (admin-managed)
resource "aws_dynamodb_table" "hsn_mappings" {
  name         = "vyaparai-hsn-mappings-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "hsn_code"

  # Primary key attribute
  attribute {
    name = "hsn_code"
    type = "S"
  }

  # GSI attribute for category-based queries
  attribute {
    name = "category_code"
    type = "S"
  }

  # GSI: category-index (for querying HSN codes by category)
  global_secondary_index {
    name            = "category-index"
    hash_key        = "category_code"
    projection_type = "ALL"
    write_capacity  = null
    read_capacity   = null
  }

  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  # Server-side encryption
  server_side_encryption {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Service     = "vyaparai-gst"
    TableType   = "reference-data"
  }
}

# Outputs for DynamoDB tables
output "dynamodb_orders_table_name" {
  description = "Name of the Orders DynamoDB table"
  value       = aws_dynamodb_table.orders.name
}

output "dynamodb_orders_table_arn" {
  description = "ARN of the Orders DynamoDB table"
  value       = aws_dynamodb_table.orders.arn
}

output "dynamodb_orders_stream_arn" {
  description = "Stream ARN of the Orders DynamoDB table"
  value       = aws_dynamodb_table.orders.stream_arn
}

output "dynamodb_sessions_table_name" {
  description = "Name of the Sessions DynamoDB table"
  value       = aws_dynamodb_table.sessions.name
}

output "dynamodb_rate_limits_table_name" {
  description = "Name of the Rate Limits DynamoDB table"
  value       = aws_dynamodb_table.rate_limits.name
}

output "dynamodb_stores_table_name" {
  description = "Name of the Stores DynamoDB table"
  value       = aws_dynamodb_table.stores.name
}

output "dynamodb_products_table_name" {
  description = "Name of the Products DynamoDB table"
  value       = aws_dynamodb_table.products.name
}

output "dynamodb_metrics_table_name" {
  description = "Name of the Metrics DynamoDB table"
  value       = aws_dynamodb_table.metrics.name
}

output "dynamodb_gst_rates_table_name" {
  description = "Name of the GST Rates DynamoDB table"
  value       = aws_dynamodb_table.gst_rates.name
}

output "dynamodb_gst_rates_table_arn" {
  description = "ARN of the GST Rates DynamoDB table"
  value       = aws_dynamodb_table.gst_rates.arn
}

output "dynamodb_hsn_mappings_table_name" {
  description = "Name of the HSN Mappings DynamoDB table"
  value       = aws_dynamodb_table.hsn_mappings.name
}

output "dynamodb_hsn_mappings_table_arn" {
  description = "ARN of the HSN Mappings DynamoDB table"
  value       = aws_dynamodb_table.hsn_mappings.arn
}
