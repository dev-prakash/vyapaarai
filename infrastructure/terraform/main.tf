# VyaparAI AWS Infrastructure
# Terraform configuration for production-ready serverless architecture

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "vyaparai-terraform-state"
    key    = "infrastructure/terraform.tfstate"
    region = "ap-south-1"
  }
}

# Configure AWS Provider
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "VyaparAI"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "VyaparAI Team"
    }
  }
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "vyaparai.com"
}

variable "api_domain" {
  description = "API domain name"
  type        = string
  default     = "api.vyaparai.com"
}

variable "app_domain" {
  description = "Application domain name"
  type        = string
  default     = "app.vyaparai.com"
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# VPC Configuration
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  version = "5.0.0"
  
  name = "vyaparai-vpc-${var.environment}"
  cidr = "10.0.0.0/16"
  
  azs             = ["${var.aws_region}a", "${var.aws_region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]
  
  enable_nat_gateway = true
  single_nat_gateway = true
  enable_vpn_gateway = false
  
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-vpc"
  }
}

# DynamoDB tables are defined in dynamodb.tf

# ElastiCache Redis Cluster
resource "aws_elasticache_subnet_group" "redis" {
  name       = "vyaparai-redis-subnet-group-${var.environment}"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name_prefix = "vyaparai-redis-${var.environment}"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "vyaparai-redis-sg-${var.environment}"
  }
}

resource "aws_elasticache_parameter_group" "redis" {
  family = "redis7"
  name   = "vyaparai-redis-params-${var.environment}"
  
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }
  
  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "vyaparai-redis-${var.environment}"
  replication_group_description = "VyaparAI Redis cluster for ${var.environment}"
  node_type                  = "cache.t3.micro"
  port                       = 6379
  parameter_group_name       = aws_elasticache_parameter_group.redis.name
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.redis.id]
  
  automatic_failover_enabled = true
  multi_az_enabled          = true
  
  num_cache_clusters = 2
  
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-redis"
  }
}

# Lambda Security Group
resource "aws_security_group" "lambda" {
  name_prefix = "vyaparai-lambda-${var.environment}"
  vpc_id      = module.vpc.vpc_id
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "vyaparai-lambda-sg-${var.environment}"
  }
}

# S3 Buckets
resource "aws_s3_bucket" "static_assets" {
  bucket = "vyaparai-static-${var.environment}"
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-static"
  }
}

resource "aws_s3_bucket_versioning" "static_assets" {
  bucket = aws_s3_bucket.static_assets.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "static_assets" {
  bucket = aws_s3_bucket.static_assets.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "static_assets" {
  bucket = aws_s3_bucket.static_assets.id
  
  rule {
    id     = "delete_old_versions"
    status = "Enabled"
    
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_bucket" "logs" {
  bucket = "vyaparai-logs-${var.environment}"
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-logs"
  }
}

resource "aws_s3_bucket_versioning" "logs" {
  bucket = aws_s3_bucket.logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket = aws_s3_bucket.logs.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id
  
  rule {
    id     = "delete_old_logs"
    status = "Enabled"
    
    expiration {
      days = 90
    }
  }
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "static_assets" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  
  aliases = [var.app_domain]
  
  origin {
    domain_name = aws_s3_bucket.static_assets.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.static_assets.id}"
    
    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.static_assets.cloudfront_access_identity_path
    }
  }
  
  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.static_assets.id}"
    
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    
    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }
  
  # Cache behavior for API
  ordered_cache_behavior {
    path_pattern     = "/api/*"
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.static_assets.id}"
    
    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Origin"]
      cookies {
        forward = "all"
      }
    }
    
    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
  }
  
  # Cache behavior for static assets
  ordered_cache_behavior {
    path_pattern     = "/static/*"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.static_assets.id}"
    
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    
    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 86400
    max_ttl                = 31536000
  }
  
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  
  viewer_certificate {
    acm_certificate_arn = aws_acm_certificate.app.arn
    ssl_support_method  = "sni-only"
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-cloudfront"
  }
}

resource "aws_cloudfront_origin_access_identity" "static_assets" {
  comment = "OAI for VyaparAI static assets"
}

# Route53 DNS
data "aws_route53_zone" "main" {
  name = var.domain_name
}

resource "aws_route53_record" "app" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.app_domain
  type    = "A"
  
  alias {
    name                   = aws_cloudfront_distribution.static_assets.domain_name
    zone_id                = aws_cloudfront_distribution.static_assets.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "api" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.api_domain
  type    = "A"
  
  alias {
    name                   = aws_cloudfront_distribution.static_assets.domain_name
    zone_id                = aws_cloudfront_distribution.static_assets.hosted_zone_id
    evaluate_target_health = false
  }
}

# ACM Certificates
resource "aws_acm_certificate" "app" {
  domain_name       = var.app_domain
  validation_method = "DNS"
  
  subject_alternative_names = [
    var.api_domain,
    "*.${var.domain_name}"
  ]
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-cert"
  }
}

resource "aws_route53_record" "app_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.app.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }
  
  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main.zone_id
}

resource "aws_acm_certificate_validation" "app" {
  certificate_arn         = aws_acm_certificate.app.arn
  validation_record_fqdns = [for record in aws_route53_record.app_cert_validation : record.fqdn]
}

# Secrets Manager
resource "aws_secretsmanager_secret" "vyaparai_secrets" {
  name        = "vyaparai/${var.environment}/secrets"
  description = "Secrets for VyaparAI ${var.environment} environment"
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-secrets"
  }
}

resource "aws_secretsmanager_secret_version" "vyaparai_secrets" {
  secret_id = aws_secretsmanager_secret.vyaparai_secrets.id
  secret_string = jsonencode({
    GOOGLE_API_KEY           = "your_google_api_key_here"
    GOOGLE_TRANSLATE_API_KEY = "your_google_translate_key_here"
    WHATSAPP_ACCESS_TOKEN    = "your_whatsapp_token_here"
    RCS_API_KEY             = "your_rcs_api_key_here"
    SMS_API_KEY             = "your_sms_api_key_here"
  })
}

# SSM Parameters
resource "aws_ssm_parameter" "whatsapp_verify_token" {
  name  = "/vyaparai/${var.environment}/whatsapp/verify_token"
  type  = "SecureString"
  value = "your_whatsapp_verify_token_here"
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-ssm"
  }
}

resource "aws_ssm_parameter" "redis_endpoint" {
  name  = "/vyaparai/${var.environment}/redis/endpoint"
  type  = "String"
  value = aws_elasticache_replication_group.redis.primary_endpoint_address
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-ssm"
  }
}

resource "aws_ssm_parameter" "redis_port" {
  name  = "/vyaparai/${var.environment}/redis/port"
  type  = "String"
  value = aws_elasticache_replication_group.redis.port
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-ssm"
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "vyaparai_api" {
  name              = "/aws/lambda/vyaparai-api-${var.environment}"
  retention_in_days = 14
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-logs"
  }
}

resource "aws_cloudwatch_log_group" "vyaparai_orders" {
  name              = "/aws/lambda/vyaparai-orders-${var.environment}"
  retention_in_days = 14
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-logs"
  }
}

resource "aws_cloudwatch_log_group" "vyaparai_webhooks" {
  name              = "/aws/lambda/vyaparai-webhooks-${var.environment}"
  retention_in_days = 14
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-logs"
  }
}

# IAM Roles and Policies
resource "aws_iam_role" "lambda_execution" {
  name = "vyaparai-lambda-execution-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-iam"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_policy" "lambda_dynamodb" {
  name = "vyaparai-lambda-dynamodb-${var.environment}"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.orders.arn,
          "${aws_dynamodb_table.orders.arn}/index/*",
          aws_dynamodb_table.sessions.arn,
          "${aws_dynamodb_table.sessions.arn}/index/*",
          aws_dynamodb_table.stores.arn,
          "${aws_dynamodb_table.stores.arn}/index/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_dynamodb" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = aws_iam_policy.lambda_dynamodb.arn
}

resource "aws_iam_policy" "lambda_secrets" {
  name = "vyaparai-lambda-secrets-${var.environment}"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.vyaparai_secrets.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_secrets" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = aws_iam_policy.lambda_secrets.arn
}

resource "aws_iam_policy" "lambda_ssm" {
  name = "vyaparai-lambda-ssm-${var.environment}"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/vyaparai/${var.environment}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_ssm" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = aws_iam_policy.lambda_ssm.arn
}

# Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnets" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnets
}

output "dynamodb_orders_table" {
  description = "Orders DynamoDB table name"
  value       = aws_dynamodb_table.orders.name
}

output "dynamodb_sessions_table" {
  description = "Sessions DynamoDB table name"
  value       = aws_dynamodb_table.sessions.name
}

output "dynamodb_stores_table" {
  description = "Stores DynamoDB table name"
  value       = aws_dynamodb_table.stores.name
}

output "redis_endpoint" {
  description = "Redis cluster endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_port" {
  description = "Redis cluster port"
  value       = aws_elasticache_replication_group.redis.port
}

output "s3_static_bucket" {
  description = "Static assets S3 bucket name"
  value       = aws_s3_bucket.static_assets.bucket
}

output "s3_logs_bucket" {
  description = "Logs S3 bucket name"
  value       = aws_s3_bucket.logs.bucket
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.static_assets.id
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.static_assets.domain_name
}

output "app_domain" {
  description = "Application domain name"
  value       = var.app_domain
}

output "api_domain" {
  description = "API domain name"
  value       = var.api_domain
}

output "secrets_arn" {
  description = "Secrets Manager ARN"
  value       = aws_secretsmanager_secret.vyaparai_secrets.arn
}

output "lambda_execution_role_arn" {
  description = "Lambda execution role ARN"
  value       = aws_iam_role.lambda_execution.arn
}
