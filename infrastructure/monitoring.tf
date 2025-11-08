# VyaparAI Production Monitoring Infrastructure
# Comprehensive CloudWatch monitoring, alarms, and dashboards

# Variables
variable "alert_email" {
  description = "Email address for receiving alerts"
  type        = string
  default     = "alerts@vyaparai.com"
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  default     = ""
}

variable "discord_webhook_url" {
  description = "Discord webhook URL for notifications"
  type        = string
  default     = ""
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/vyaparai-production"
  retention_in_days = 30
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "lambda"
  }
}

resource "aws_cloudwatch_log_group" "api_gateway_logs" {
  name              = "/aws/apigateway/vyaparai-production"
  retention_in_days = 30
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "api-gateway"
  }
}

resource "aws_cloudwatch_log_group" "dynamodb_logs" {
  name              = "/aws/dynamodb/vyaparai-production"
  retention_in_days = 30
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "dynamodb"
  }
}

# SNS Topics for Alerts
resource "aws_sns_topic" "critical_alerts" {
  name = "vyaparai-critical-alerts"
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    AlertLevel  = "critical"
  }
}

resource "aws_sns_topic" "warning_alerts" {
  name = "vyaparai-warning-alerts"
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    AlertLevel  = "warning"
  }
}

resource "aws_sns_topic" "info_alerts" {
  name = "vyaparai-info-alerts"
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    AlertLevel  = "info"
  }
}

# SNS Subscriptions
resource "aws_sns_topic_subscription" "critical_email" {
  topic_arn = aws_sns_topic.critical_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_sns_topic_subscription" "warning_email" {
  topic_arn = aws_sns_topic.warning_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_sns_topic_subscription" "info_email" {
  topic_arn = aws_sns_topic.info_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Lambda Function Alarms
resource "aws_cloudwatch_metric_alarm" "lambda_error_rate" {
  alarm_name          = "vyaparai-lambda-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "Lambda function error rate is too high"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.info_alerts.arn]
  
  dimensions = {
    FunctionName = "vyaparai-production"
  }
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "lambda"
    Metric      = "error-rate"
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "vyaparai-lambda-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "10000"
  alarm_description   = "Lambda function duration is too high"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.info_alerts.arn]
  
  dimensions = {
    FunctionName = "vyaparai-production"
  }
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "lambda"
    Metric      = "duration"
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "vyaparai-lambda-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "Lambda function is being throttled"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.info_alerts.arn]
  
  dimensions = {
    FunctionName = "vyaparai-production"
  }
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "lambda"
    Metric      = "throttles"
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_invocations" {
  alarm_name          = "vyaparai-lambda-invocations"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Invocations"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "Lambda function has no invocations"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.info_alerts.arn]
  
  dimensions = {
    FunctionName = "vyaparai-production"
  }
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "lambda"
    Metric      = "invocations"
  }
}

# DynamoDB Alarms
resource "aws_cloudwatch_metric_alarm" "dynamodb_throttled_requests" {
  alarm_name          = "vyaparai-dynamodb-throttled-requests"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ThrottledRequests"
  namespace           = "AWS/DynamoDB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "DynamoDB is throttling requests"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.info_alerts.arn]
  
  dimensions = {
    TableName = "vyaparai-orders-prod"
  }
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "dynamodb"
    Metric      = "throttled-requests"
  }
}

resource "aws_cloudwatch_metric_alarm" "dynamodb_consumed_read_capacity" {
  alarm_name          = "vyaparai-dynamodb-consumed-read-capacity"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ConsumedReadCapacityUnits"
  namespace           = "AWS/DynamoDB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1000"
  alarm_description   = "DynamoDB read capacity consumption is high"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.info_alerts.arn]
  
  dimensions = {
    TableName = "vyaparai-orders-prod"
  }
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "dynamodb"
    Metric      = "consumed-read-capacity"
  }
}

resource "aws_cloudwatch_metric_alarm" "dynamodb_consumed_write_capacity" {
  alarm_name          = "vyaparai-dynamodb-consumed-write-capacity"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ConsumedWriteCapacityUnits"
  namespace           = "AWS/DynamoDB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1000"
  alarm_description   = "DynamoDB write capacity consumption is high"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.info_alerts.arn]
  
  dimensions = {
    TableName = "vyaparai-orders-prod"
  }
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "dynamodb"
    Metric      = "consumed-write-capacity"
  }
}

# API Gateway Alarms
resource "aws_cloudwatch_metric_alarm" "api_gateway_4xx_errors" {
  alarm_name          = "vyaparai-api-gateway-4xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "API Gateway 4XX errors are high"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.info_alerts.arn]
  
  dimensions = {
    ApiName = "vyaparai-production"
  }
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "api-gateway"
    Metric      = "4xx-errors"
  }
}

resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx_errors" {
  alarm_name          = "vyaparai-api-gateway-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "API Gateway 5XX errors are high"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.info_alerts.arn]
  
  dimensions = {
    ApiName = "vyaparai-production"
  }
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "api-gateway"
    Metric      = "5xx-errors"
  }
}

resource "aws_cloudwatch_metric_alarm" "api_gateway_latency" {
  alarm_name          = "vyaparai-api-gateway-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Latency"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Average"
  threshold           = "2000"
  alarm_description   = "API Gateway latency is too high"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.info_alerts.arn]
  
  dimensions = {
    ApiName = "vyaparai-production"
  }
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "api-gateway"
    Metric      = "latency"
  }
}

# Custom Business Metrics
resource "aws_cloudwatch_metric_alarm" "order_processing_time" {
  alarm_name          = "vyaparai-order-processing-time"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "OrderProcessingTime"
  namespace           = "VyaparAI/Production"
  period              = "300"
  statistic           = "Average"
  threshold           = "5000"
  alarm_description   = "Order processing time is too high"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.info_alerts.arn]
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "business-metrics"
    Metric      = "order-processing-time"
  }
}

resource "aws_cloudwatch_metric_alarm" "failed_orders" {
  alarm_name          = "vyaparai-failed-orders"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "FailedOrders"
  namespace           = "VyaparAI/Production"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "Too many failed orders"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.info_alerts.arn]
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "business-metrics"
    Metric      = "failed-orders"
  }
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "vyaparai_production_dashboard" {
  dashboard_name = "VyaparAI-Production"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", "vyaparai-production"],
            [".", "Errors", ".", "."],
            [".", "Invocations", ".", "."],
            [".", "Throttles", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = "ap-south-1"
          title  = "Lambda Function Metrics"
          view   = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiName", "vyaparai-production"],
            [".", "4XXError", ".", "."],
            [".", "5XXError", ".", "."],
            [".", "Latency", ".", "."]
          ]
          period = 300
          stat   = "Sum"
          region = "ap-south-1"
          title  = "API Gateway Metrics"
          view   = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "vyaparai-orders-prod"],
            [".", "ConsumedWriteCapacityUnits", ".", "."],
            [".", "ThrottledRequests", ".", "."]
          ]
          period = 300
          stat   = "Sum"
          region = "ap-south-1"
          title  = "DynamoDB Metrics"
          view   = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["VyaparAI/Production", "OrderProcessingTime"],
            [".", "FailedOrders"],
            [".", "SuccessfulOrders"],
            [".", "ActiveUsers"]
          ]
          period = 300
          stat   = "Average"
          region = "ap-south-1"
          title  = "Business Metrics"
          view   = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "log"
        width  = 24
        height = 6
        properties = {
          query = "SOURCE '/aws/lambda/vyaparai-production'\n| fields @timestamp, @message\n| filter @message like /ERROR/\n| sort @timestamp desc\n| limit 100"
          region = "ap-south-1"
          title  = "Recent Errors"
          view   = "table"
        }
      }
    ]
  })
}

# CloudWatch Synthetics Canary for Health Checks
resource "aws_synthetics_canary" "health_check" {
  name                 = "vyaparai-health-check"
  artifact_s3_location = "s3://vyaparai-monitoring/canary-artifacts/"
  execution_role_arn   = aws_iam_role.synthetics_role.arn
  handler              = "index.handler"
  zip_file             = "health-check-canary.zip"
  runtime_version      = "syn-nodejs-puppeteer-3.9"
  
  schedule {
    expression = "rate(5 minutes)"
  }
  
  run_config {
    timeout_in_seconds = 60
  }
  
  success_retention_period = 7
  failure_retention_period = 30
  
  tags = {
    Environment = "production"
    Application = "vyaparai"
    Component   = "health-check"
  }
}

# IAM Role for Synthetics Canary
resource "aws_iam_role" "synthetics_role" {
  name = "vyaparai-synthetics-role"
  
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
}

resource "aws_iam_role_policy" "synthetics_policy" {
  name = "vyaparai-synthetics-policy"
  role = aws_iam_role.synthetics_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "arn:aws:s3:::vyaparai-monitoring/*"
      }
    ]
  })
}

# Outputs
output "critical_alerts_topic_arn" {
  description = "ARN of the critical alerts SNS topic"
  value       = aws_sns_topic.critical_alerts.arn
}

output "warning_alerts_topic_arn" {
  description = "ARN of the warning alerts SNS topic"
  value       = aws_sns_topic.warning_alerts.arn
}

output "dashboard_url" {
  description = "URL of the CloudWatch dashboard"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=ap-south-1#dashboards:name=VyaparAI-Production"
}
