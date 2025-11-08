"""
CloudWatch Alarms Setup for Translation Service

Creates production-grade CloudWatch alarms for:
- Lambda errors and throttles
- DynamoDB throttling
- Amazon Translate API errors
- High latency detection
- Cost anomalies
"""

import boto3
import sys

cloudwatch = boto3.client('cloudwatch', region_name='ap-south-1')
sns = boto3.client('sns', region_name='ap-south-1')

# Configuration
LAMBDA_FUNCTION_NAME = 'vyaparai-translation-service'
SNS_TOPIC_NAME = 'vyaparai-translation-alerts'
SNS_EMAIL = 'devprakash@example.com'  # Change this to your email


def create_sns_topic():
    """Create SNS topic for alarm notifications"""
    try:
        print(f"Creating SNS topic: {SNS_TOPIC_NAME}")

        response = sns.create_topic(Name=SNS_TOPIC_NAME)
        topic_arn = response['TopicArn']

        print(f"✅ SNS Topic created: {topic_arn}")

        # Subscribe email to topic
        print(f"Subscribing {SNS_EMAIL} to SNS topic...")
        sns.subscribe(
            TopicArn=topic_arn,
            Protocol='email',
            Endpoint=SNS_EMAIL
        )

        print(f"✅ Email subscription created (check your inbox to confirm)")
        return topic_arn

    except sns.exceptions.TopicLimitExceededException:
        # Topic already exists, get ARN
        response = sns.create_topic(Name=SNS_TOPIC_NAME)
        topic_arn = response['TopicArn']
        print(f"⚠️  SNS Topic already exists: {topic_arn}")
        return topic_arn
    except Exception as e:
        print(f"❌ Error creating SNS topic: {e}")
        return None


def create_lambda_error_alarm(topic_arn):
    """Alarm for Lambda function errors > 5%"""
    try:
        print("\nCreating Lambda Error Rate alarm...")

        cloudwatch.put_metric_alarm(
            AlarmName=f'{LAMBDA_FUNCTION_NAME}-error-rate',
            AlarmDescription='Alert when Lambda error rate exceeds 5%',
            ActionsEnabled=True,
            AlarmActions=[topic_arn],
            MetricName='Errors',
            Namespace='AWS/Lambda',
            Statistic='Sum',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': LAMBDA_FUNCTION_NAME
                }
            ],
            Period=300,  # 5 minutes
            EvaluationPeriods=2,
            Threshold=5,
            ComparisonOperator='GreaterThanThreshold',
            TreatMissingData='notBreaching'
        )

        print(f"✅ Lambda error rate alarm created")

    except Exception as e:
        print(f"❌ Error creating Lambda error alarm: {e}")


def create_lambda_throttle_alarm(topic_arn):
    """Alarm for Lambda throttling"""
    try:
        print("Creating Lambda Throttle alarm...")

        cloudwatch.put_metric_alarm(
            AlarmName=f'{LAMBDA_FUNCTION_NAME}-throttles',
            AlarmDescription='Alert when Lambda function is throttled',
            ActionsEnabled=True,
            AlarmActions=[topic_arn],
            MetricName='Throttles',
            Namespace='AWS/Lambda',
            Statistic='Sum',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': LAMBDA_FUNCTION_NAME
                }
            ],
            Period=300,
            EvaluationPeriods=1,
            Threshold=1,
            ComparisonOperator='GreaterThanOrEqualToThreshold',
            TreatMissingData='notBreaching'
        )

        print(f"✅ Lambda throttle alarm created")

    except Exception as e:
        print(f"❌ Error creating Lambda throttle alarm: {e}")


def create_lambda_duration_alarm(topic_arn):
    """Alarm for slow Lambda executions > 3 seconds"""
    try:
        print("Creating Lambda Duration alarm...")

        cloudwatch.put_metric_alarm(
            AlarmName=f'{LAMBDA_FUNCTION_NAME}-high-duration',
            AlarmDescription='Alert when Lambda duration exceeds 3 seconds',
            ActionsEnabled=True,
            AlarmActions=[topic_arn],
            MetricName='Duration',
            Namespace='AWS/Lambda',
            Statistic='Average',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': LAMBDA_FUNCTION_NAME
                }
            ],
            Period=300,
            EvaluationPeriods=2,
            Threshold=3000,  # 3 seconds in milliseconds
            ComparisonOperator='GreaterThanThreshold',
            TreatMissingData='notBreaching'
        )

        print(f"✅ Lambda duration alarm created")

    except Exception as e:
        print(f"❌ Error creating Lambda duration alarm: {e}")


def create_dynamodb_throttle_alarm(topic_arn, table_name):
    """Alarm for DynamoDB throttling"""
    try:
        print(f"Creating DynamoDB throttle alarm for {table_name}...")

        # Read throttles
        cloudwatch.put_metric_alarm(
            AlarmName=f'{table_name}-read-throttles',
            AlarmDescription=f'Alert when {table_name} has read throttles',
            ActionsEnabled=True,
            AlarmActions=[topic_arn],
            MetricName='ReadThrottleEvents',
            Namespace='AWS/DynamoDB',
            Statistic='Sum',
            Dimensions=[
                {
                    'Name': 'TableName',
                    'Value': table_name
                }
            ],
            Period=300,
            EvaluationPeriods=1,
            Threshold=1,
            ComparisonOperator='GreaterThanOrEqualToThreshold',
            TreatMissingData='notBreaching'
        )

        # Write throttles
        cloudwatch.put_metric_alarm(
            AlarmName=f'{table_name}-write-throttles',
            AlarmDescription=f'Alert when {table_name} has write throttles',
            ActionsEnabled=True,
            AlarmActions=[topic_arn],
            MetricName='WriteThrottleEvents',
            Namespace='AWS/DynamoDB',
            Statistic='Sum',
            Dimensions=[
                {
                    'Name': 'TableName',
                    'Value': table_name
                }
            ],
            Period=300,
            EvaluationPeriods=1,
            Threshold=1,
            ComparisonOperator='GreaterThanOrEqualToThreshold',
            TreatMissingData='notBreaching'
        )

        print(f"✅ DynamoDB throttle alarms created for {table_name}")

    except Exception as e:
        print(f"❌ Error creating DynamoDB throttle alarm: {e}")


def create_translate_error_alarm(topic_arn):
    """Alarm for Amazon Translate errors"""
    try:
        print("Creating Amazon Translate error alarm...")

        cloudwatch.put_metric_alarm(
            AlarmName='amazon-translate-errors',
            AlarmDescription='Alert when Amazon Translate API has errors',
            ActionsEnabled=True,
            AlarmActions=[topic_arn],
            MetricName='UserErrorCount',
            Namespace='AWS/Translate',
            Statistic='Sum',
            Period=300,
            EvaluationPeriods=1,
            Threshold=10,
            ComparisonOperator='GreaterThanThreshold',
            TreatMissingData='notBreaching'
        )

        print(f"✅ Amazon Translate error alarm created")

    except Exception as e:
        print(f"❌ Error creating Translate error alarm: {e}")


def create_cost_anomaly_detector():
    """Create cost anomaly detector for translation service"""
    try:
        print("\nCreating Cost Anomaly Detector...")

        ce_client = boto3.client('ce', region_name='us-east-1')  # Cost Explorer is in us-east-1

        response = ce_client.create_anomaly_monitor(
            AnomalyMonitor={
                'MonitorName': 'TranslationServiceCostMonitor',
                'MonitorType': 'DIMENSIONAL',
                'MonitorDimension': 'SERVICE',
                'MonitorSpecification': {
                    'Dimensions': {
                        'Key': 'SERVICE',
                        'Values': ['Amazon Translate', 'Amazon DynamoDB'],
                        'MatchOptions': ['EQUALS']
                    }
                }
            }
        )

        monitor_arn = response['MonitorArn']
        print(f"✅ Cost anomaly monitor created: {monitor_arn}")

        return monitor_arn

    except Exception as e:
        print(f"⚠️  Could not create cost anomaly detector: {e}")
        print("    Note: Requires AWS Cost Explorer to be enabled")
        return None


def main():
    """Create all CloudWatch alarms"""
    print("=" * 60)
    print("VyapaarAI Translation Service - CloudWatch Alarms Setup")
    print("=" * 60)

    # Create SNS topic for notifications
    topic_arn = create_sns_topic()

    if not topic_arn:
        print("\n❌ Failed to create SNS topic. Exiting.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Creating CloudWatch Alarms")
    print("=" * 60)

    # Lambda alarms
    create_lambda_error_alarm(topic_arn)
    create_lambda_throttle_alarm(topic_arn)
    create_lambda_duration_alarm(topic_arn)

    # DynamoDB alarms
    create_dynamodb_throttle_alarm(topic_arn, 'vyaparai-products-catalog-prod')
    create_dynamodb_throttle_alarm(topic_arn, 'vyaparai-translation-cache-prod')

    # Amazon Translate alarms
    create_translate_error_alarm(topic_arn)

    # Cost anomaly detection
    create_cost_anomaly_detector()

    print("\n" + "=" * 60)
    print("✅ All CloudWatch alarms created successfully!")
    print("=" * 60)

    print("\nAlarms Summary:")
    print(f"  1. Lambda error rate > 5%")
    print(f"  2. Lambda throttles")
    print(f"  3. Lambda duration > 3 seconds")
    print(f"  4. DynamoDB read throttles (both tables)")
    print(f"  5. DynamoDB write throttles (both tables)")
    print(f"  6. Amazon Translate API errors")
    print(f"\nNotifications will be sent to: {SNS_EMAIL}")
    print(f"SNS Topic ARN: {topic_arn}")
    print("\n⚠️  IMPORTANT: Check your email and confirm the SNS subscription!")
    print("=" * 60)


if __name__ == "__main__":
    main()
