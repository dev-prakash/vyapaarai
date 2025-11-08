# RDS PostgreSQL for VyaparAI Analytics
# Handles complex queries, reporting, and analytics

# Random password for database
resource "random_password" "db_password" {
  length  = 32
  special = true
  upper   = true
  lower   = true
  numeric = true
}

# RDS Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "vyaparai-rds-subnet-group-${var.environment}"
  subnet_ids = module.vpc.private_subnets
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-rds"
  }
}

# RDS Security Group
resource "aws_security_group" "rds" {
  name_prefix = "vyaparai-rds-${var.environment}"
  vpc_id      = module.vpc.vpc_id
  
  # Allow PostgreSQL access from Lambda functions
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }
  
  # Allow PostgreSQL access from Bastion host (if needed)
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "vyaparai-rds-sg-${var.environment}"
  }
}

# RDS Parameter Group
resource "aws_db_parameter_group" "main" {
  family = "postgres15"
  name   = "vyaparai-postgres-params-${var.environment}"
  
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }
  
  parameter {
    name  = "log_statement"
    value = "all"
  }
  
  parameter {
    name  = "log_connections"
    value = "1"
  }
  
  parameter {
    name  = "log_disconnections"
    value = "1"
  }
  
  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }
  
  parameter {
    name  = "pg_stat_statements.track"
    value = "all"
  }
  
  parameter {
    name  = "max_connections"
    value = var.environment == "prod" ? "200" : "100"
  }
  
  parameter {
    name  = "work_mem"
    value = var.environment == "prod" ? "16MB" : "8MB"
  }
  
  parameter {
    name  = "maintenance_work_mem"
    value = var.environment == "prod" ? "256MB" : "128MB"
  }
  
  parameter {
    name  = "effective_cache_size"
    value = var.environment == "prod" ? "2GB" : "1GB"
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-rds"
  }
}

# RDS Option Group
resource "aws_db_option_group" "main" {
  name                     = "vyaparai-postgres-options-${var.environment}"
  engine_name              = "postgres"
  major_engine_version     = "15"
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-rds"
  }
}

# Main RDS Instance
resource "aws_db_instance" "analytics" {
  identifier = "vyaparai-analytics-${var.environment}"
  
  # Engine configuration
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.environment == "prod" ? "db.t3.medium" : "db.t3.micro"
  
  # Storage configuration
  allocated_storage     = var.environment == "prod" ? 100 : 20
  max_allocated_storage = var.environment == "prod" ? 500 : 100
  storage_type          = "gp3"
  storage_encrypted     = true
  
  # Database configuration
  db_name  = "vyaparai"
  username = "vyaparai_admin"
  password = random_password.db_password.result
  port     = 5432
  
  # Network configuration
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  publicly_accessible    = false
  multi_az               = var.environment == "prod"
  
  # Backup configuration
  backup_retention_period = var.environment == "prod" ? 30 : 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  # Monitoring and logging
  enabled_cloudwatch_logs_exports = ["postgresql"]
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn
  
  # Performance Insights
  performance_insights_enabled          = true
  performance_insights_retention_period = var.environment == "prod" ? 7 : 3
  
  # Parameter and option groups
  parameter_group_name = aws_db_parameter_group.main.name
  option_group_name    = aws_db_option_group.main.name
  
  # Deletion protection
  deletion_protection = var.environment == "prod"
  skip_final_snapshot = var.environment != "prod"
  
  # Final snapshot configuration
  final_snapshot_identifier = var.environment == "prod" ? "vyaparai-analytics-${var.environment}-final" : null
  
  # Tags
  tags = {
    Environment = var.environment
    Service     = "vyaparai-analytics"
    DatabaseType = "analytics"
  }
  
  # Lifecycle
  lifecycle {
    ignore_changes = [
      password,
      final_snapshot_identifier
    ]
  }
}

# Read Replica for Production
resource "aws_db_instance" "analytics_replica" {
  count = var.environment == "prod" ? 1 : 0
  
  identifier = "vyaparai-analytics-${var.environment}-replica"
  
  # Replica configuration
  replicate_source_db = aws_db_instance.analytics.identifier
  instance_class     = "db.t3.micro"
  
  # Storage configuration
  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true
  
  # Network configuration
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  publicly_accessible    = false
  
  # Backup configuration
  backup_retention_period = 7
  backup_window          = "04:00-05:00"
  maintenance_window     = "sun:05:00-sun:06:00"
  
  # Monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn
  
  # Performance Insights
  performance_insights_enabled          = true
  performance_insights_retention_period = 3
  
  # Deletion protection
  deletion_protection = false
  skip_final_snapshot = true
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-analytics"
    DatabaseType = "replica"
  }
}

# RDS Monitoring Role
resource "aws_iam_role" "rds_monitoring" {
  name = "vyaparai-rds-monitoring-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# RDS Proxy for connection pooling
resource "aws_db_proxy" "main" {
  count = var.environment == "prod" ? 1 : 0
  
  name                   = "vyaparai-rds-proxy-${var.environment}"
  debug_logging          = false
  engine_family          = "POSTGRESQL"
  idle_client_timeout    = 1800
  require_tls            = true
  role_arn               = aws_iam_role.rds_proxy.arn
  vpc_security_group_ids = [aws_security_group.rds.id]
  vpc_subnet_ids         = module.vpc.private_subnets
  
  auth {
    auth_scheme = "SECRETS"
    iam_auth    = "DISABLED"
    secret_arn  = aws_secretsmanager_secret.rds_credentials.arn
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-rds"
  }
}

# RDS Proxy Role
resource "aws_iam_role" "rds_proxy" {
  count = var.environment == "prod" ? 1 : 0
  
  name = "vyaparai-rds-proxy-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_proxy" {
  count = var.environment == "prod" ? 1 : 0
  
  role       = aws_iam_role.rds_proxy[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSProxyServiceRolePolicy"
}

# RDS Proxy Default Target Group
resource "aws_db_proxy_default_target_group" "main" {
  count = var.environment == "prod" ? 1 : 0
  
  db_proxy_name = aws_db_proxy.main[0].name
  
  connection_pool_config {
    connection_borrow_timeout    = 120
    init_query                   = "SET timezone = 'UTC'"
    max_connections_percent      = 100
    max_idle_connections_percent = 50
    session_pinning_filters      = ["EXCLUDE_VARIABLE_SETS"]
  }
}

# RDS Proxy Target
resource "aws_db_proxy_target" "main" {
  count = var.environment == "prod" ? 1 : 0
  
  db_cluster_identifier = null
  db_instance_identifier = aws_db_instance.analytics.id
  db_proxy_name         = aws_db_proxy.main[0].name
  target_group_name     = aws_db_proxy_default_target_group.main[0].name
}

# Secrets Manager for RDS credentials
resource "aws_secretsmanager_secret" "rds_credentials" {
  name        = "vyaparai/rds/${var.environment}/credentials"
  description = "RDS credentials for VyaparAI ${var.environment} environment"
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-rds"
  }
}

resource "aws_secretsmanager_secret_version" "rds_credentials" {
  secret_id = aws_secretsmanager_secret.rds_credentials.id
  secret_string = jsonencode({
    username = aws_db_instance.analytics.username
    password = random_password.db_password.result
    engine   = "postgres"
    host     = aws_db_instance.analytics.endpoint
    port     = aws_db_instance.analytics.port
    dbname   = aws_db_instance.analytics.db_name
  })
}

# CloudWatch Alarms for RDS
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "vyaparai-rds-cpu-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "RDS CPU utilization is high"
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.analytics.id
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-rds"
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  alarm_name          = "vyaparai-rds-connections-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = var.environment == "prod" ? "150" : "80"
  alarm_description   = "RDS database connections are high"
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.analytics.id
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-rds"
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  alarm_name          = "vyaparai-rds-storage-${var.environment}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "1000000000" # 1GB in bytes
  alarm_description   = "RDS free storage space is low"
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.analytics.id
  }
  
  tags = {
    Environment = var.environment
    Service     = "vyaparai-rds"
  }
}

# Outputs for RDS
output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.analytics.endpoint
}

output "rds_port" {
  description = "RDS instance port"
  value       = aws_db_instance.analytics.port
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.analytics.db_name
}

output "rds_username" {
  description = "RDS master username"
  value       = aws_db_instance.analytics.username
  sensitive   = true
}

output "rds_password" {
  description = "RDS master password"
  value       = random_password.db_password.result
  sensitive   = true
}

output "rds_proxy_endpoint" {
  description = "RDS proxy endpoint"
  value       = var.environment == "prod" ? aws_db_proxy.main[0].endpoint : null
}

output "rds_replica_endpoint" {
  description = "RDS read replica endpoint"
  value       = var.environment == "prod" ? aws_db_instance.analytics_replica[0].endpoint : null
}

output "rds_secrets_arn" {
  description = "RDS credentials secrets ARN"
  value       = aws_secretsmanager_secret.rds_credentials.arn
}
