# Cart Migration Monitoring & Alerting Guide

Comprehensive monitoring and alerting infrastructure for VyaparAI cart migration functionality.

## Overview

The cart migration monitoring system provides:
- 📊 **Real-time Metrics** - Track migration success/failure rates
- 🚨 **Automated Alerts** - Get notified of issues via SNS/Email
- 📈 **CloudWatch Dashboard** - Visual monitoring of all metrics
- 🔍 **Structured Logging** - JSON logs for easy querying
- 📝 **Audit Trails** - Complete audit logs for compliance

## Quick Start

### 1. Setup Monitoring Infrastructure

```bash
cd /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend
./scripts/setup_cart_migration_monitoring.sh
```

This script will:
- Create SNS topic for alerts
- Setup metric filters for CloudWatch Logs
- Create CloudWatch alarms
- Build CloudWatch dashboard
- Provide sample CloudWatch Insights queries

### 2. Subscribe to Alerts

During setup, you'll be prompted for an email address. Alternatively, subscribe manually:

```bash
aws sns subscribe \
    --topic-arn arn:aws:sns:ap-south-1:YOUR_ACCOUNT:vyaparai-cart-migration-alerts \
    --protocol email \
    --notification-endpoint your-email@example.com \
    --region ap-south-1
```

**Important**: Check your email and confirm the subscription!

## Monitoring Dashboard

### Access Dashboard

https://console.aws.amazon.com/cloudwatch/home?region=ap-south-1#dashboards:name=VyaparAI-CartMigration

### Dashboard Widgets

1. **Migration Success vs Failure** - Line chart showing success/failure over time
2. **Rate Limiting Events** - Track when rate limits are triggered
3. **Merge Conflicts & No Guest Carts** - Special scenarios tracking
4. **Lambda Duration** - Performance monitoring (avg, min, max)
5. **Total Invocations** - Overall API usage
6. **Total Errors** - Lambda function errors
7. **Total Throttles** - Lambda throttling events
8. **Recent Migration Logs** - Last 20 migration-related log entries

## Metrics

### Custom Metrics (Namespace: `VyaparAI/CartMigration`)

| Metric Name | Description | Unit | Alarm Threshold |
|-------------|-------------|------|-----------------|
| `MigrationSuccessCount` | Successful migrations | Count | N/A |
| `MigrationFailureCount` | Failed migrations | Count | > 5 in 5 min |
| `RateLimitExceededCount` | Rate limit triggers | Count | > 20 in 5 min |
| `MergeConflictCount` | Cart merge conflicts | Count | N/A |
| `NoGuestCartsCount` | No guest carts found | Count | N/A |

### AWS Lambda Metrics

| Metric Name | Description | Alarm Threshold |
|-------------|-------------|-----------------|
| `Invocations` | Total Lambda calls | N/A |
| `Errors` | Lambda errors | > 5 in 5 min |
| `Duration` | Execution time | N/A |
| `Throttles` | Lambda throttling | > 1 in 5 min |

## CloudWatch Alarms

### Active Alarms

1. **VyaparAI-CartMigration-HighFailureRate**
   - **Condition**: Migration failures > 5 in 5 minutes
   - **Action**: SNS notification
   - **Response**: Check logs for error patterns

2. **VyaparAI-CartMigration-NoSuccessfulMigrations**
   - **Condition**: No successful migrations in 30 minutes
   - **Action**: SNS notification
   - **Response**: Verify service health, check Lambda logs

3. **VyaparAI-CartMigration-ExcessiveRateLimiting**
   - **Condition**: Rate limit exceeded > 20 times in 5 minutes
   - **Action**: SNS notification
   - **Response**: Review rate limit settings or investigate abuse

4. **VyaparAI-CartMigration-LambdaErrors**
   - **Condition**: Lambda errors > 5 in 5 minutes
   - **Action**: SNS notification
   - **Response**: Check Lambda logs and code errors

5. **VyaparAI-CartMigration-LambdaThrottles**
   - **Condition**: Any Lambda throttles
   - **Action**: SNS notification
   - **Response**: Review Lambda concurrency limits

### Alarm States

- **OK** (Green): System operating normally
- **ALARM** (Red): Threshold exceeded, action taken
- **INSUFFICIENT_DATA** (Gray): Not enough data to evaluate

## CloudWatch Logs Insights Queries

### Query 1: Migration Success Rate

```sql
fields @timestamp, @message
| filter @message like /Cart migration/
| stats count(*) as total,
        sum(case @message like /successful/ when 1 then 1 else 0 end) as success,
        sum(case @message like /failed/ when 1 then 1 else 0 end) as failed
by bin(5m)
```

### Query 2: Top Failure Reasons

```sql
fields @timestamp, @message
| filter @message like /Cart migration failed/
| parse @message '"error_message": "*"' as error
| stats count() by error
| sort count desc
| limit 10
```

### Query 3: Average Migration Response Time

```sql
fields @timestamp, @message
| filter @message like /Cart migration successful/
| parse @message '"duration_ms": *' as duration
| stats avg(duration) as avg_ms, max(duration) as max_ms, min(duration) as min_ms by bin(5m)
```

### Query 4: Merge Strategy Distribution

```sql
fields @timestamp, @message
| filter @message like /merge_strategy/
| parse @message '"merge_strategy": "*"' as strategy
| stats count() by strategy
```

### Query 5: Customers with Multiple Migrations

```sql
fields @timestamp, @message
| filter @message like /Cart migration successful/
| parse @message '"customer_id": "*"' as customer
| stats count() as migration_count by customer
| filter migration_count > 5
| sort migration_count desc
```

### Query 6: Rate Limit Analysis

```sql
fields @timestamp, @message
| filter @message like /Rate limit exceeded/
| parse @message '"customer_id": "*"' as customer
| stats count() as rate_limit_hits by customer, bin(1h)
| sort rate_limit_hits desc
```

### Query 7: Performance by Merge Strategy

```sql
fields @timestamp, @message
| filter @message like /Cart migration successful/
| parse @message '"merge_strategy": "*"' as strategy
| parse @message '"duration_ms": *' as duration
| stats avg(duration) as avg_duration by strategy
```

## Structured Logging

### Log Format

All cart migration events are logged in structured JSON format:

```json
{
  "timestamp": "2025-11-21T10:30:00.000Z",
  "level": "INFO",
  "message": "Cart migration successful",
  "event_type": "migration_success",
  "customer_id": "user-123456",
  "guest_session_id": "guest-abc-123",
  "migrated_carts": 2,
  "total_items": 5,
  "total_value": 1250.00,
  "merge_strategy": "merge",
  "duration_ms": 245.3
}
```

### Event Types

- `migration_start` - Migration initiated
- `migration_success` - Migration completed successfully
- `migration_failure` - Migration failed
- `no_guest_carts` - No guest carts found
- `merge_conflict` - Cart conflict resolved
- `rate_limit_exceeded` - Rate limit triggered
- `cleanup_success` - Guest cart cleaned up
- `store_cart_migrated` - Individual store cart migrated
- `auth_failure` - Authentication failed
- `validation_error` - Input validation failed
- `dynamo_error` - DynamoDB operation failed
- `performance_metric` - Performance timing logged
- `audit_log` - Audit trail entry

### Using Structured Logging

Import and use in your code:

```python
from app.utils.cart_migration_metrics import CartMigrationMetrics

# Log migration start
CartMigrationMetrics.log_migration_start(
    customer_id="user-123",
    guest_session_id="guest-abc-123",
    merge_strategy="merge",
    store_id="STORE-001"
)

# Log success
CartMigrationMetrics.log_migration_success(
    customer_id="user-123",
    guest_session_id="guest-abc-123",
    migrated_carts=2,
    total_items=5,
    total_value=1250.00,
    merge_strategy="merge",
    duration_ms=245.3
)

# Log failure
CartMigrationMetrics.log_migration_failure(
    customer_id="user-123",
    guest_session_id="guest-abc-123",
    error_message="DynamoDB timeout",
    error_type="ServiceUnavailable",
    merge_strategy="merge"
)
```

## Troubleshooting Guide

### High Failure Rate Alarm

**Symptoms**: Receiving "HighFailureRate" alarm notifications

**Investigation Steps**:
1. Check CloudWatch Logs Insights with Query 2 (Top Failure Reasons)
2. Review recent code deployments
3. Check DynamoDB throttling metrics
4. Verify JWT authentication is working

**Common Causes**:
- DynamoDB throttling or capacity issues
- JWT token validation failures
- Network connectivity issues
- Code bugs in merge logic

### No Successful Migrations Alarm

**Symptoms**: Receiving "NoSuccessfulMigrations" alarm

**Investigation Steps**:
1. Check if Lambda is receiving requests
2. Verify API Gateway is routing correctly
3. Check Lambda execution role permissions
4. Test migration endpoint manually

**Common Causes**:
- API Gateway misconfiguration
- Lambda cold start issues
- Authentication service down
- DynamoDB table issues

### Excessive Rate Limiting

**Symptoms**: Receiving "ExcessiveRateLimiting" alarm

**Investigation Steps**:
1. Run Query 6 (Rate Limit Analysis) to identify customers
2. Check if it's legitimate traffic or abuse
3. Review rate limit settings in code

**Common Causes**:
- Bot/automated traffic
- Mobile app bug causing retry loops
- Legitimate traffic surge (e.g., marketing campaign)
- Rate limits set too low

## Performance Benchmarks

### Target Metrics

| Operation | Target | Acceptable | Alert |
|-----------|--------|------------|-------|
| Single store migration | < 300ms | < 500ms | > 1000ms |
| Multi-store migration | < 500ms | < 800ms | > 2000ms |
| Get all carts | < 200ms | < 400ms | > 800ms |
| Cleanup guest cart | < 150ms | < 300ms | > 600ms |

### Success Rate Targets

- **Success Rate**: > 99.5%
- **Acceptable**: > 95%
- **Alert**: < 90%

## Maintenance

### Weekly Tasks

- [ ] Review CloudWatch dashboard for trends
- [ ] Check alarm history for patterns
- [ ] Review top failure reasons
- [ ] Analyze performance metrics

### Monthly Tasks

- [ ] Review and optimize CloudWatch Insights queries
- [ ] Analyze cost of CloudWatch resources
- [ ] Update alarm thresholds based on traffic
- [ ] Archive old logs if needed

### Quarterly Tasks

- [ ] Comprehensive performance review
- [ ] Update monitoring documentation
- [ ] Review SNS subscriber list
- [ ] Audit log retention policies

## Cost Optimization

### Current Costs (Estimated)

- **CloudWatch Logs**: ~$0.50/GB ingested
- **CloudWatch Metrics**: ~$0.30/metric/month
- **CloudWatch Alarms**: ~$0.10/alarm/month
- **CloudWatch Dashboard**: ~$3.00/month
- **SNS**: ~$0.50/million notifications

**Estimated Monthly Cost**: $10-20 for typical usage

### Optimization Tips

1. Use log sampling for high-volume events
2. Set appropriate log retention (30 days recommended)
3. Archive old logs to S3 for compliance
4. Review and remove unused metrics

## Security & Compliance

### PII Handling

**Never log**:
- Full customer email addresses
- Phone numbers
- Payment information
- Full names

**Use instead**:
- Hashed customer IDs
- Masked emails (user***@example.com)
- Session IDs only

### Audit Requirements

All cart migrations are audited with:
- Customer ID
- Timestamp
- Action performed
- IP address (optional)
- Success/failure status

Audit logs are retained for **90 days** in CloudWatch Logs.

## Support & Escalation

### Alert Priority Matrix

| Alarm | Priority | Response Time | Escalation |
|-------|----------|---------------|------------|
| High Failure Rate | P1 | < 15 min | Engineering team |
| No Successful Migrations | P1 | < 15 min | Engineering + Ops |
| Excessive Rate Limiting | P2 | < 1 hour | Engineering |
| Lambda Errors | P2 | < 1 hour | Engineering |
| Lambda Throttles | P3 | < 4 hours | Ops team |

### Contact Information

- **Engineering Team**: engineering@vyaparai.com
- **On-Call**: Use PagerDuty integration
- **AWS Support**: Premium support ticket

---

**Last Updated**: 2025-11-21
**Owner**: Engineering Team
**Review Cycle**: Quarterly
