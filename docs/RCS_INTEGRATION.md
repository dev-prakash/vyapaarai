# RCS Integration Guide for VyaparAI

## Overview

Google RCS (Rich Communication Services) Business Messaging provides rich messaging capabilities for Android phones, enabling VyaparAI to deliver enhanced customer experiences with rich cards, suggested replies, and interactive elements.

## Features

- ✅ **Rich Cards**: Order confirmations with images and actions
- ✅ **Product Carousels**: Browse products with visual cards
- ✅ **Suggested Replies**: Quick action buttons for common tasks
- ✅ **Typing Indicators**: Real-time typing feedback
- ✅ **Read Receipts**: Message delivery confirmation
- ✅ **Multi-language Support**: Localized content in 10+ Indian languages
- ✅ **Order Status Tracking**: Real-time order updates
- ✅ **Verified Business Badge**: Trust and credibility
- ✅ **Web Integration**: Seamless web-to-mobile experience

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   RCS Client    │    │  Webhook Handler │    │ Hybrid Database │
│   (rcs_client)  │◄──►│ (webhook_handler)│◄──►│  (hybrid_db)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Rich Cards     │    │ Order Service    │    │ PostgreSQL      │
│ (rich_cards)    │    │ (hybrid_order)   │    │ (Analytics)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Setup Instructions

### 1. Prerequisites

- Google Cloud Project with billing enabled
- Google Cloud SDK installed
- Service account with RCS Business Messaging API access
- Python 3.11+ environment
- Required Python packages (see requirements.txt)

### 2. Google Cloud Setup

#### Enable APIs
```bash
# Enable required APIs
gcloud services enable rcsbusinessmessaging.googleapis.com
gcloud services enable businesscommunications.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

#### Create Service Account
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to IAM & Admin > Service Accounts
3. Create new service account with name `vyaparai-rcs-agent`
4. Grant roles:
   - RCS Business Messaging API Admin
   - Business Communications API Admin
5. Create and download JSON key as `rcs-service-account.json`

### 3. Environment Configuration

Create `.env.rcs` file:
```bash
# RCS Configuration
RCS_AGENT_ID=vyaparai-agent
GOOGLE_CLOUD_PROJECT_ID=your-project-id
RCS_SERVICE_ACCOUNT_PATH=rcs-service-account.json
RCS_WEBHOOK_URL=https://api.vyaparai.com/api/v1/webhooks/rcs

# Stage-specific configuration
STAGE=dev
ENVIRONMENT=dev

# API Configuration
API_BASE_URL=https://api.vyaparai.com
WEBHOOK_SECRET=your_webhook_secret_here

# Test Configuration
TEST_PHONE_NUMBERS=+919999999999,+918888888888,+917777777777
```

### 4. Automated Setup

Run the setup script:
```bash
# Make script executable
chmod +x scripts/rcs-setup.sh

# Run setup
./scripts/rcs-setup.sh
```

The script will:
- Check prerequisites
- Authenticate with Google Cloud
- Enable required APIs
- Create agent configuration
- Register webhook
- Add test numbers
- Create environment files
- Test messaging functionality

### 5. Manual Setup (Alternative)

If automated setup fails, follow these manual steps:

#### Register Agent
```bash
# Get access token
ACCESS_TOKEN=$(gcloud auth print-access-token)

# Register agent
curl -X POST \
  "https://rcsbusinessmessaging.googleapis.com/v1/agents" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d @rcs-agent-config.json
```

#### Register Webhook
```bash
curl -X POST \
  "https://rcsbusinessmessaging.googleapis.com/v1/phones/agentWebhookConfig" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "vyaparai-agent",
    "webhookUri": "https://api.vyaparai.com/api/v1/webhooks/rcs"
  }'
```

#### Add Test Numbers
```bash
curl -X POST \
  "https://rcsbusinessmessaging.googleapis.com/v1/phones/+919999999999/testers" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agentId": "vyaparai-agent"}'
```

## API Reference

### RCS Client (`rcs_client.py`)

#### Initialize Client
```python
from app.channels.rcs.rcs_client import rcs_client

# Client is automatically initialized with environment variables
```

#### Send Text Message
```python
result = await rcs_client.send_message(
    phone="+919999999999",
    text="Hello! How can I help you?",
    suggestions=[
        {
            "reply": {
                "text": "Place Order",
                "postbackData": "action=place_order"
            }
        }
    ]
)
```

#### Send Rich Card
```python
from app.channels.rcs.rich_cards import OrderConfirmationCard

card = OrderConfirmationCard(
    order_id="ORD-123",
    items=[{"product": "rice", "quantity": 2, "unit": "kg"}],
    total=100.0,
    language="en"
)

result = await rcs_client.send_rich_card(
    phone="+919999999999",
    card=card.build()
)
```

#### Send Carousel
```python
from app.channels.rcs.rich_cards import ProductCarousel

carousel = ProductCarousel(products, language="en")
result = await rcs_client.send_carousel(
    phone="+919999999999",
    cards=carousel.build()
)
```

#### Send Typing Indicator
```python
await rcs_client.send_typing_indicator("+919999999999")
```

### Webhook Handler (`webhook_handler.py`)

#### Message Processing Flow
1. **Receive Webhook**: Incoming RCS messages
2. **Parse Message**: Extract text, suggestions, location, images
3. **Process with NLP**: Use hybrid order service
4. **Generate Response**: Rich cards, text, or carousels
5. **Send Response**: Via RCS client

#### Supported Message Types
- **Text Messages**: Natural language order processing
- **Suggestion Responses**: Button clicks and actions
- **Location Messages**: Delivery address capture
- **Image Messages**: Product photos (future enhancement)

#### Action Handlers
- `action=place_order`: Start order process
- `action=confirm_order`: Confirm order
- `action=cancel_order`: Cancel order
- `action=track_order`: Track order status
- `action=browse`: Browse products
- `action=check_status`: Check order status

### Rich Cards (`rich_cards.py`)

#### OrderConfirmationCard
```python
card = OrderConfirmationCard(
    order_id="ORD-123",
    items=[{"product": "rice", "quantity": 2, "unit": "kg"}],
    total=100.0,
    language="en"
)
```

#### ProductCarousel
```python
carousel = ProductCarousel(
    products=[
        {
            "product_id": "prod-1",
            "name": "Basmati Rice",
            "price": 50.0,
            "unit": "kg",
            "brand": "Tilda"
        }
    ],
    language="en"
)
```

#### OrderStatusCard
```python
status_card = OrderStatusCard(
    order_id="ORD-123",
    status="confirmed",
    language="en",
    order_details={"total_amount": 100.0}
)
```

#### WelcomeCard
```python
welcome_card = WelcomeCard(
    language="en",
    user_name="John"
)
```

## Message Flow Examples

### 1. Order Placement Flow
```
User: "2 kg rice, 1 liter oil"
↓
NLP Processing: Intent=place_order, Entities=[rice:2kg, oil:1L]
↓
Rich Card: Order confirmation with items and total
↓
User clicks "Confirm"
↓
Order saved to database, status updated
↓
Confirmation message sent
```

### 2. Product Browsing Flow
```
User: "Show me rice products"
↓
NLP Processing: Intent=browse_products, Query=rice
↓
Database Query: Search products matching "rice"
↓
Product Carousel: Multiple rice products with images
↓
User clicks "Order 1" on product
↓
Order confirmation card sent
```

### 3. Order Status Flow
```
User: "Check my order status"
↓
NLP Processing: Intent=check_status
↓
Database Query: Get recent orders for user
↓
Order Status Card: Current status with tracking info
↓
User clicks "Track Order"
↓
Detailed tracking information sent
```

## Localization Support

### Supported Languages
- English (`en`)
- Hindi (`hi`)
- Tamil (`ta`)
- Bengali (`bn`)
- Telugu (`te`)
- Marathi (`mr`)
- Gujarati (`gu`)
- Kannada (`kn`)
- Malayalam (`ml`)
- Punjabi (`pa`)

### Language Detection
The system automatically detects the user's language and responds accordingly:
- Text messages are processed in the detected language
- Rich cards display localized content
- Suggestions use appropriate language

### Example Localized Content
```python
# Hindi
"स्वागत है! किसी भी भाषा में किराने का सामान ऑर्डर करें।"

# Tamil
"வரவேற்கிறோம்! எந்த மொழியிலும் கடை பொருட்களை ஆர்டர் செய்யுங்கள்."

# Bengali
"স্বাগতম! যেকোনো ভাষায় মুদি সামগ্রী অর্ডার করুন।"
```

## Testing

### 1. Test Setup
```bash
# Run automated tests
python -m pytest tests/test_rcs_integration.py

# Test specific components
python -m pytest tests/test_rcs_client.py
python -m pytest tests/test_webhook_handler.py
python -m pytest tests/test_rich_cards.py
```

### 2. Manual Testing
```bash
# Test RCS messaging
python scripts/test_rcs_message.py

# Test webhook endpoint
curl -X POST http://localhost:8000/api/v1/webhooks/rcs \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "vyaparai-agent",
    "messageId": "test-msg-001",
    "msisdn": "+919999999999",
    "message": {
      "text": "2 kg rice"
    }
  }'
```

### 3. Test Numbers
Configure these test numbers in Google RCS Console:
- `+919999999999`
- `+918888888888`
- `+917777777777`

## Monitoring and Debugging

### 1. Health Checks
```bash
# Check webhook health
curl https://api.vyaparai.com/api/v1/webhooks/rcs/health

# Check agent status
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://rcsbusinessmessaging.googleapis.com/v1/agents/vyaparai-agent"
```

### 2. Logs
```bash
# View application logs
tail -f logs/vyaparai.log | grep RCS

# View webhook logs
tail -f logs/webhook.log
```

### 3. Monitoring Script
```bash
# Run monitoring script
./monitor-rcs.sh
```

### 4. Common Issues

#### Authentication Errors
```bash
# Check service account
gcloud auth list
gcloud config get-value project

# Refresh credentials
gcloud auth application-default login
```

#### Webhook Errors
```bash
# Check webhook registration
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://rcsbusinessmessaging.googleapis.com/v1/phones/agentWebhookConfig"

# Test webhook endpoint
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"test": "message"}'
```

#### Message Delivery Issues
```bash
# Check message status
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://rcsbusinessmessaging.googleapis.com/v1/phones/+919999999999/agentMessages"
```

## Deployment

### 1. AWS Lambda Deployment
```bash
# Deploy with Serverless Framework
serverless deploy --stage dev

# Deploy RCS-specific functions
serverless deploy function --function webhookRCS
```

### 2. Environment Variables
Ensure these environment variables are set in your deployment:
```bash
RCS_AGENT_ID=vyaparai-agent
GOOGLE_CLOUD_PROJECT_ID=your-project-id
RCS_SERVICE_ACCOUNT_PATH=/path/to/service-account.json
RCS_WEBHOOK_URL=https://api.vyaparai.com/api/v1/webhooks/rcs
```

### 3. SSL Certificate
Ensure your webhook endpoint has a valid SSL certificate:
```bash
# Check SSL certificate
openssl s_client -connect api.vyaparai.com:443 -servername api.vyaparai.com
```

## Security Considerations

### 1. Authentication
- Use service account authentication for API calls
- Implement webhook signature verification
- Store credentials securely (AWS Secrets Manager)

### 2. Rate Limiting
- Implement rate limiting for webhook endpoints
- Monitor API usage and quotas
- Handle rate limit errors gracefully

### 3. Data Privacy
- Encrypt sensitive data in transit and at rest
- Implement data retention policies
- Comply with GDPR and local privacy laws

## Performance Optimization

### 1. Caching
- Cache product information
- Cache user sessions
- Use Redis for rate limiting

### 2. Database Optimization
- Use database indexes for queries
- Implement connection pooling
- Monitor query performance

### 3. API Optimization
- Use async/await for I/O operations
- Implement request batching
- Monitor API response times

## Troubleshooting Guide

### Common Error Messages

#### "Invalid agent ID"
- Check `RCS_AGENT_ID` environment variable
- Verify agent exists in Google RCS Console
- Ensure proper authentication

#### "Webhook not found"
- Check webhook registration
- Verify webhook URL is accessible
- Check SSL certificate validity

#### "Message delivery failed"
- Verify phone number format (+91XXXXXXXXXX)
- Check if number is registered as tester
- Ensure agent is approved and active

#### "Authentication failed"
- Refresh service account credentials
- Check API permissions
- Verify project ID configuration

### Debug Mode
Enable debug logging:
```python
import logging
logging.getLogger('app.channels.rcs').setLevel(logging.DEBUG)
```

### Support Resources
- [RCS Business Messaging API Documentation](https://developers.google.com/business-communications/rcs-business-messaging)
- [Google Cloud Console](https://console.cloud.google.com)
- [Business Messages Console](https://business.messages.google.com/console)
- [VyaparAI Support](mailto:support@vyaparai.com)

## Future Enhancements

### Planned Features
- **Voice Messages**: Audio order processing
- **Image Recognition**: Product identification from photos
- **Payment Integration**: In-chat payment processing
- **Advanced Analytics**: Customer behavior insights
- **Multi-store Support**: Store-specific agents
- **AI-powered Recommendations**: Smart product suggestions

### Integration Opportunities
- **Google Maps**: Store location and delivery tracking
- **Google Pay**: Seamless payment processing
- **Google Analytics**: Enhanced customer insights
- **Google Ads**: Retargeting and marketing campaigns

---

## Quick Reference

### Environment Variables
```bash
RCS_AGENT_ID=vyaparai-agent
GOOGLE_CLOUD_PROJECT_ID=your-project-id
RCS_SERVICE_ACCOUNT_PATH=rcs-service-account.json
RCS_WEBHOOK_URL=https://api.vyaparai.com/api/v1/webhooks/rcs
```

### Key Endpoints
- Webhook: `POST /api/v1/webhooks/rcs`
- Health Check: `GET /api/v1/webhooks/rcs/health`
- RCS API: `https://rcsbusinessmessaging.googleapis.com/v1`

### Useful Commands
```bash
# Setup RCS integration
./scripts/rcs-setup.sh

# Deploy to AWS
./deploy-rcs.sh

# Monitor integration
./monitor-rcs.sh

# Test messaging
python scripts/test_rcs_message.py
```

### Support Contacts
- **Technical Support**: tech@vyaparai.com
- **Business Support**: business@vyaparai.com
- **Emergency**: +91-9876543210
