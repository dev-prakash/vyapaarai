terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0"
    }
  }
  backend "local" {}
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "VyaparAI"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "environment" {
  type    = string
  default = "prod"
}

# Global Products Table
resource "aws_dynamodb_table" "global_products" {
  name         = "vyaparai-global-products-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "product_id"

  attribute {
    name = "product_id"
    type = "S"
  }

  # Attributes for GSIs
  attribute {
    name = "barcode"
    type = "S"
  }

  attribute {
    name = "image_hash"
    type = "S"
  }

  global_secondary_index {
    name            = "barcode-index"
    hash_key        = "barcode"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "image_hash-index"
    hash_key        = "image_hash"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Service     = "vyaparai-products-global"
    TableType   = "catalog-global"
  }
}

# Store Inventory Table
resource "aws_dynamodb_table" "store_inventory" {
  name         = "vyaparai-store-inventory-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "store_id"
  range_key    = "product_id"

  attribute {
    name = "store_id"
    type = "S"
  }

  attribute {
    name = "product_id"
    type = "S"
  }

  # GSI for cross-store product analytics
  attribute {
    name = "gsi_product_id"
    type = "S"
  }

  global_secondary_index {
    name            = "product_id-index"
    hash_key        = "gsi_product_id"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Service     = "vyaparai-store-inventory"
    TableType   = "inventory"
  }
}
