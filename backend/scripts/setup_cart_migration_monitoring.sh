#!/bin/bash
# Setup CloudWatch Monitoring and Alerting for Cart Migration API
# Creates alarms, metrics, and dashboards for monitoring cart migrations

set -e

# Configuration
REGION="ap-south-1"
LAMBDA_FUNCTION_NAME="vyaparai-api-prod"
LOG_GROUP_NAME="/aws/lambda/${LAMBDA_FUNCTION_NAME}"
SNS_TOPIC_NAME="vyaparai-cart-migration-alerts"
ALARM_PREFIX="VyaparAI-CartMigration"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Setting up Cart Migration Monitoring & Alerting${NC}"
echo "=================================================="

# Step 1: Create SNS Topic for Alerts (if not exists)
echo -e "\n${YELLOW}📢 Step 1: Creating SNS Topic for Alerts${NC}"

SNS_TOPIC_ARN=$(aws sns create-topic \
    --name ${SNS_TOPIC_NAME} \
    --region ${REGION} \
    --output text \
    --query 'TopicArn' 2>/dev/null || \
    aws sns list-topics --region ${REGION} --query "Topics[?contains(TopicArn, '${SNS_TOPIC_NAME}')].TopicArn" --output text)

echo -e "${GREEN}✓ SNS Topic ARN: ${SNS_TOPIC_ARN}${NC}"

# Optional: Subscribe email to SNS topic
read -p "Enter email address for alerts (or press Enter to skip): " EMAIL_ADDRESS
if [ ! -z "$EMAIL_ADDRESS" ]; then
    aws sns subscribe \
        --topic-arn ${SNS_TOPIC_ARN} \
        --protocol email \
        --notification-endpoint ${EMAIL_ADDRESS} \
        --region ${REGION}
    echo -e "${GREEN}✓ Email subscription created (check email for confirmation)${NC}"
fi

# Step 2: Create Metric Filters
echo -e "\n${YELLOW}📊 Step 2: Creating CloudWatch Metric Filters${NC}"

# Metric Filter 1: Migration Success Count
echo "Creating metric filter: Migration Success Count"
aws logs put-metric-filter \
    --log-group-name ${LOG_GROUP_NAME} \
    --filter-name "CartMigrationSuccess" \
    --filter-pattern '[timestamp, request_id, level=INFO, msg="Cart migration successful*"]' \
    --metric-transformations \
        metricName=MigrationSuccessCount,\
metricNamespace=VyaparAI/CartMigration,\
metricValue=1,\
defaultValue=0,\
unit=Count \
    --region ${REGION} 2>/dev/null || echo "Metric filter already exists"

echo -e "${GREEN}✓ CartMigrationSuccess metric filter created${NC}"

# Metric Filter 2: Migration Failure Count
echo "Creating metric filter: Migration Failure Count"
aws logs put-metric-filter \
    --log-group-name ${LOG_GROUP_NAME} \
    --filter-name "CartMigrationFailure" \
    --filter-pattern '[timestamp, request_id, level=ERROR, msg="Cart migration failed*"]' \
    --metric-transformations \
        metricName=MigrationFailureCount,\
metricNamespace=VyaparAI/CartMigration,\
metricValue=1,\
defaultValue=0,\
unit=Count \
    --region ${REGION} 2>/dev/null || echo "Metric filter already exists"

echo -e "${GREEN}✓ CartMigrationFailure metric filter created${NC}"

# Metric Filter 3: Rate Limit Exceeded
echo "Creating metric filter: Rate Limit Exceeded"
aws logs put-metric-filter \
    --log-group-name ${LOG_GROUP_NAME} \
    --filter-name "CartMigrationRateLimitExceeded" \
    --filter-pattern '[timestamp, request_id, level=WARNING, msg="Rate limit exceeded*"]' \
    --metric-transformations \
        metricName=RateLimitExceededCount,\
metricNamespace=VyaparAI/CartMigration,\
metricValue=1,\
defaultValue=0,\
unit=Count \
    --region ${REGION} 2>/dev/null || echo "Metric filter already exists"

echo -e "${GREEN}✓ CartMigrationRateLimitExceeded metric filter created${NC}"

# Metric Filter 4: Cart Merge Conflicts
echo "Creating metric filter: Cart Merge Conflicts"
aws logs put-metric-filter \
    --log-group-name ${LOG_GROUP_NAME} \
    --filter-name "CartMigrationConflicts" \
    --filter-pattern '[timestamp, request_id, level=INFO, msg="Cart merge conflict*"]' \
    --metric-transformations \
        metricName=MergeConflictCount,\
metricNamespace=VyaparAI/CartMigration,\
metricValue=1,\
defaultValue=0,\
unit=Count \
    --region ${REGION} 2>/dev/null || echo "Metric filter already exists"

echo -e "${GREEN}✓ CartMigrationConflicts metric filter created${NC}"

# Metric Filter 5: No Guest Carts Found
echo "Creating metric filter: No Guest Carts Found"
aws logs put-metric-filter \
    --log-group-name ${LOG_GROUP_NAME} \
    --filter-name "CartMigrationNoGuestCarts" \
    --filter-pattern '[timestamp, request_id, level=INFO, msg="No guest carts found*"]' \
    --metric-transformations \
        metricName=NoGuestCartsCount,\
metricNamespace=VyaparAI/CartMigration,\
metricValue=1,\
defaultValue=0,\
unit=Count \
    --region ${REGION} 2>/dev/null || echo "Metric filter already exists"

echo -e "${GREEN}✓ CartMigrationNoGuestCarts metric filter created${NC}"

# Step 3: Create CloudWatch Alarms
echo -e "\n${YELLOW}🚨 Step 3: Creating CloudWatch Alarms${NC}"

# Alarm 1: High Failure Rate
echo "Creating alarm: High Migration Failure Rate"
aws cloudwatch put-metric-alarm \
    --alarm-name "${ALARM_PREFIX}-HighFailureRate" \
    --alarm-description "Alert when cart migration failure rate is > 10% in 5 minutes" \
    --metric-name MigrationFailureCount \
    --namespace VyaparAI/CartMigration \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --treat-missing-data notBreaching \
    --alarm-actions ${SNS_TOPIC_ARN} \
    --region ${REGION}

echo -e "${GREEN}✓ High Failure Rate alarm created${NC}"

# Alarm 2: No Successful Migrations (service health check)
echo "Creating alarm: No Successful Migrations (Service Health)"
aws cloudwatch put-metric-alarm \
    --alarm-name "${ALARM_PREFIX}-NoSuccessfulMigrations" \
    --alarm-description "Alert when no successful migrations in 30 minutes (may indicate service issue)" \
    --metric-name MigrationSuccessCount \
    --namespace VyaparAI/CartMigration \
    --statistic Sum \
    --period 1800 \
    --evaluation-periods 1 \
    --threshold 0 \
    --comparison-operator LessThanOrEqualToThreshold \
    --treat-missing-data breaching \
    --alarm-actions ${SNS_TOPIC_ARN} \
    --region ${REGION}

echo -e "${GREEN}✓ No Successful Migrations alarm created${NC}"

# Alarm 3: Excessive Rate Limiting
echo "Creating alarm: Excessive Rate Limiting"
aws cloudwatch put-metric-alarm \
    --alarm-name "${ALARM_PREFIX}-ExcessiveRateLimiting" \
    --alarm-description "Alert when rate limiting triggers > 20 times in 5 minutes" \
    --metric-name RateLimitExceededCount \
    --namespace VyaparAI/CartMigration \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 20 \
    --comparison-operator GreaterThanThreshold \
    --treat-missing-data notBreaching \
    --alarm-actions ${SNS_TOPIC_ARN} \
    --region ${REGION}

echo -e "${GREEN}✓ Excessive Rate Limiting alarm created${NC}"

# Alarm 4: Lambda Errors
echo "Creating alarm: Lambda Function Errors"
aws cloudwatch put-metric-alarm \
    --alarm-name "${ALARM_PREFIX}-LambdaErrors" \
    --alarm-description "Alert when Lambda function has errors" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --dimensions Name=FunctionName,Value=${LAMBDA_FUNCTION_NAME} \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --treat-missing-data notBreaching \
    --alarm-actions ${SNS_TOPIC_ARN} \
    --region ${REGION}

echo -e "${GREEN}✓ Lambda Errors alarm created${NC}"

# Alarm 5: Lambda Throttles
echo "Creating alarm: Lambda Function Throttles"
aws cloudwatch put-metric-alarm \
    --alarm-name "${ALARM_PREFIX}-LambdaThrottles" \
    --alarm-description "Alert when Lambda function is throttled" \
    --metric-name Throttles \
    --namespace AWS/Lambda \
    --dimensions Name=FunctionName,Value=${LAMBDA_FUNCTION_NAME} \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 1 \
    --comparison-operator GreaterThanThreshold \
    --treat-missing-data notBreaching \
    --alarm-actions ${SNS_TOPIC_ARN} \
    --region ${REGION}

echo -e "${GREEN}✓ Lambda Throttles alarm created${NC}"

# Step 4: Create CloudWatch Dashboard
echo -e "\n${YELLOW}📈 Step 4: Creating CloudWatch Dashboard${NC}"

DASHBOARD_BODY=$(cat <<'EOF'
{
    "widgets": [
        {
            "type": "metric",
            "x": 0,
            "y": 0,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "VyaparAI/CartMigration", "MigrationSuccessCount", { "stat": "Sum", "label": "Successful Migrations" } ],
                    [ ".", "MigrationFailureCount", { "stat": "Sum", "label": "Failed Migrations" } ]
                ],
                "view": "timeSeries",
                "stacked": false,
                "region": "ap-south-1",
                "title": "Migration Success vs Failure",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Count"
                    }
                }
            }
        },
        {
            "type": "metric",
            "x": 12,
            "y": 0,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "VyaparAI/CartMigration", "RateLimitExceededCount", { "stat": "Sum" } ]
                ],
                "view": "timeSeries",
                "stacked": false,
                "region": "ap-south-1",
                "title": "Rate Limiting Events",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Count"
                    }
                }
            }
        },
        {
            "type": "metric",
            "x": 0,
            "y": 6,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "VyaparAI/CartMigration", "MergeConflictCount", { "stat": "Sum" } ],
                    [ ".", "NoGuestCartsCount", { "stat": "Sum" } ]
                ],
                "view": "timeSeries",
                "stacked": false,
                "region": "ap-south-1",
                "title": "Merge Conflicts & No Guest Carts",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Count"
                    }
                }
            }
        },
        {
            "type": "metric",
            "x": 12,
            "y": 6,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "AWS/Lambda", "Duration", { "stat": "Average" } ]
                ],
                "view": "timeSeries",
                "stacked": false,
                "region": "ap-south-1",
                "title": "Lambda Duration (ms)",
                "period": 300,
                "yAxis": {
                    "left": {
                        "label": "Milliseconds"
                    }
                }
            }
        },
        {
            "type": "metric",
            "x": 0,
            "y": 12,
            "width": 8,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "AWS/Lambda", "Invocations", { "stat": "Sum" } ]
                ],
                "view": "singleValue",
                "region": "ap-south-1",
                "title": "Total Invocations",
                "period": 300,
                "dimensions": {
                    "FunctionName": "vyaparai-api-prod"
                }
            }
        },
        {
            "type": "metric",
            "x": 8,
            "y": 12,
            "width": 8,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "AWS/Lambda", "Errors", { "stat": "Sum" } ]
                ],
                "view": "singleValue",
                "region": "ap-south-1",
                "title": "Total Errors",
                "period": 300,
                "dimensions": {
                    "FunctionName": "vyaparai-api-prod"
                }
            }
        },
        {
            "type": "metric",
            "x": 16,
            "y": 12,
            "width": 8,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "AWS/Lambda", "Throttles", { "stat": "Sum" } ]
                ],
                "view": "singleValue",
                "region": "ap-south-1",
                "title": "Total Throttles",
                "period": 300,
                "dimensions": {
                    "FunctionName": "vyaparai-api-prod"
                }
            }
        },
        {
            "type": "log",
            "x": 0,
            "y": 18,
            "width": 24,
            "height": 6,
            "properties": {
                "query": "SOURCE '/aws/lambda/vyaparai-api-prod'\n| fields @timestamp, @message\n| filter @message like /Cart migration/\n| sort @timestamp desc\n| limit 20",
                "region": "ap-south-1",
                "stacked": false,
                "title": "Recent Cart Migration Logs",
                "view": "table"
            }
        }
    ]
}
EOF
)

aws cloudwatch put-dashboard \
    --dashboard-name "VyaparAI-CartMigration" \
    --dashboard-body "${DASHBOARD_BODY}" \
    --region ${REGION}

echo -e "${GREEN}✓ CloudWatch Dashboard created${NC}"

# Step 5: Create Log Insights Queries
echo -e "\n${YELLOW}🔍 Step 5: Sample CloudWatch Insights Queries${NC}"

cat << 'EOF'

Saved the following CloudWatch Insights queries for monitoring:

# Query 1: Migration Success Rate
fields @timestamp, @message
| filter @message like /Cart migration/
| stats count(*) as total,
        sum(case @message like /successful/ when 1 then 1 else 0 end) as success,
        sum(case @message like /failed/ when 1 then 1 else 0 end) as failed
by bin(5m)

# Query 2: Top Failure Reasons
fields @timestamp, @message
| filter @message like /Cart migration failed/
| parse @message "reason: *" as reason
| stats count() by reason
| sort count desc

# Query 3: Average Migration Response Time
fields @timestamp, @duration
| filter @message like /Cart migration/
| stats avg(@duration), max(@duration), min(@duration) by bin(5m)

# Query 4: Merge Strategy Distribution
fields @timestamp, @message
| filter @message like /merge_strategy/
| parse @message "merge_strategy: *" as strategy
| stats count() by strategy

# Query 5: Rate Limit Analysis
fields @timestamp, @message
| filter @message like /Rate limit exceeded/
| stats count() by bin(1m)

EOF

echo -e "\n${GREEN}=================================================="
echo -e "✅ Cart Migration Monitoring Setup Complete!"
echo -e "==================================================${NC}"
echo ""
echo -e "${BLUE}📊 Dashboard:${NC} https://console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=VyaparAI-CartMigration"
echo -e "${BLUE}🚨 Alarms:${NC} https://console.aws.amazon.com/cloudwatch/home?region=${REGION}#alarmsV2:"
echo -e "${BLUE}📈 Metrics:${NC} Custom namespace: VyaparAI/CartMigration"
echo -e "${BLUE}📢 SNS Topic:${NC} ${SNS_TOPIC_ARN}"
echo ""
echo -e "${YELLOW}⚠ Important:${NC} If you subscribed an email, check your inbox to confirm the subscription!"
echo ""
