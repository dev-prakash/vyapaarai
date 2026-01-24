# VyaparAI FastAPI Backend

A comprehensive FastAPI-based order processing system for Indian grocery stores with multi-language support, AI-powered responses, and multi-channel communication.

## 🚀 Features

- **Multi-language Support**: Process orders in 18+ Indian languages
- **Multi-channel Support**: WhatsApp, RCS, SMS, and Web interfaces
- **AI-Powered Responses**: Gemini integration for natural conversations
- **Real-time Processing**: Sub-millisecond order processing
- **Comprehensive Analytics**: Detailed metrics and monitoring
- **Rate Limiting**: Distributed rate limiting with Redis
- **Production Ready**: Health checks, error handling, and monitoring

## 📋 Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Deployment](#deployment)
- [Architecture](#architecture)
- [Contributing](#contributing)

## 🛠 Installation

### Prerequisites

- Python 3.11+
- Redis (optional, for distributed rate limiting)
- Google Cloud API keys (optional, for Gemini and Translation)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd vyaparai/backend
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start the application**
   ```bash
   python run_app.py
   # Or directly with uvicorn:
   uvicorn app.main:app --reload --port 8000
   ```

5. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - ReDoc Documentation: http://localhost:8000/redoc
   - Health Check: http://localhost:8000/health

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Application
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000

# Redis (optional)
REDIS_URL=redis://localhost:6379

# Google Services (optional)
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_TRANSLATE_API_KEY=your_translate_api_key
GOOGLE_MAPS_API_KEY=your_google_maps_api_key  # For store/customer address geocoding

# Database (future)
DATABASE_URL=postgresql://user:password@localhost/vyaparai

# Security
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Optional Services

- **Redis**: For distributed rate limiting and caching
- **Google Gemini**: For AI-powered response generation
- **Google Translate**: For regional language support
- **Google Maps Geocoding**: For address-to-coordinates conversion (store discovery)
- **PostgreSQL**: For persistent data storage (future)

## 📖 Usage

### Basic Order Processing

```python
import httpx

async def process_order():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/orders/process",
            json={
                "message": "I want to order 2 kg rice and 1 packet salt",
                "channel": "whatsapp",
                "customer_phone": "+919876543210",
                "store_id": "store_001"
            }
        )
        return response.json()

# Usage
result = await process_order()
print(result)
```

### Multilingual Support

```python
# Hindi
order_data = {
    "message": "मुझे 2 किलो चावल और 1 पैकेट नमक चाहिए",
    "channel": "whatsapp"
}

# Hinglish
order_data = {
    "message": "bhaiya 3 packet maggi chahiye",
    "channel": "rcs"
}

# Tamil
order_data = {
    "message": "எனக்கு 2 கிலோ அரிசி வேண்டும்",
    "channel": "sms"
}
```

### Webhook Integration

```python
# WhatsApp Webhook
whatsapp_payload = {
    "entry": [{
        "changes": [{
            "value": {
                "messages": [{
                    "from": "+919876543210",
                    "text": {"body": "I want to order 2 kg rice"},
                    "id": "msg_123"
                }]
            }
        }]
    }]
}

response = await client.post(
    "http://localhost:8000/api/v1/orders/webhooks/whatsapp",
    json=whatsapp_payload
)
```

## 📚 API Documentation

### Core Endpoints

#### Process Order
```http
POST /api/v1/orders/process
Content-Type: application/json

{
  "message": "I want to order 2 kg rice",
  "channel": "whatsapp",
  "customer_phone": "+919876543210",
  "store_id": "store_001"
}
```

#### Get Order Status
```http
GET /api/v1/orders/{order_id}
```

#### Confirm Order
```http
POST /api/v1/orders/confirm/{order_id}
Content-Type: application/json

{
  "customer_details": {
    "name": "John Doe",
    "email": "john@example.com"
  },
  "delivery_address": "123 Main St, City",
  "payment_method": "cod"
}
```

#### Cancel Order
```http
POST /api/v1/orders/{order_id}/cancel?reason=Customer request
```

#### Get Order History
```http
GET /api/v1/orders/history/{customer_phone}?page=1&page_size=10
```

#### Get Metrics
```http
GET /api/v1/orders/metrics
```

### Webhook Endpoints

#### WhatsApp Webhook
```http
POST /api/v1/orders/webhooks/whatsapp
```

#### RCS Webhook
```http
POST /api/v1/orders/webhooks/rcs
```

#### SMS Webhook
```http
POST /api/v1/orders/webhooks/sms
```

### Store Discovery Endpoints

#### Search Nearby Stores
```http
GET /api/v1/stores/nearby?landmark=Connaught+Place&city=Delhi&radius=10
```
Response includes stores sorted by distance with lat/lng-based search.

**Search Strategies (automatically selected)**:
1. GPS coordinates (if lat/lng provided) - No API call
2. Cached pincode coordinates (if store with pincode exists) - No API call
3. Cached landmark coordinates (if store address contains landmark) - No API call
4. Google Maps Geocoding API (fallback when no cached coordinates)
5. Text-based filtering (city/state only)

### Health Check Endpoints

#### Basic Health
```http
GET /health
```

#### Detailed Health
```http
GET /health/detailed
```

## 🧪 Testing

### Run All Tests

```bash
# Test unified order service
python test_unified_order_service.py

# Test FastAPI application
python test_fastapi_app.py

# Test with running server
python test_fastapi_app.py
```

### Individual Test Components

```bash
# Test NLP components
python test_nlp_components.py

# Test multilingual service
python test_multilingual_service.py

# Test unified service
python test_unified_order_service.py
```

### API Testing with curl

```bash
# Process an order
curl -X POST "http://localhost:8000/api/v1/orders/process" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "I want to order 2 kg rice",
       "channel": "whatsapp",
       "customer_phone": "+919876543210"
     }'

# Get health status
curl "http://localhost:8000/health"

# Get metrics
curl "http://localhost:8000/api/v1/orders/metrics"
```

## 🏗 Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │  Rate Limiting  │    │   Redis Cache   │
│                 │    │                 │    │                 │
│  - REST API     │◄──►│  - Customer     │◄──►│  - Rate Limits  │
│  - Webhooks     │    │  - Store        │    │  - Sessions     │
│  - Health       │    │  - IP Address   │    │  - Metrics      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Unified Service │    │  Multilingual   │    │   NLP Engine    │
│                 │    │     Service     │    │                 │
│  - Order Proc   │◄──►│  - Translation  │◄──►│  - NER          │
│  - Response Gen │    │  - Language Det │    │  - Intent Class │
│  - Channel Fmt  │    │  - Context Pres │    │  - Entity Extr  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Gemini AI     │    │  Google Cloud   │    │   Templates     │
│                 │    │   Translate     │    │                 │
│  - AI Responses │    │  - Regional Lang│    │  - Fallback     │
│  - Context Gen  │    │  - Multi-lang   │    │  - Error Resp   │
│  - Natural Conv │    │  - Preserve     │    │  - Default Msgs │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow

1. **Request Reception**: FastAPI receives HTTP request
2. **Rate Limiting**: Check rate limits for customer/store/IP
3. **Language Detection**: Detect input language
4. **Translation**: Translate to English if needed
5. **NLP Processing**: Extract intent and entities
6. **Response Generation**: Use Gemini or templates
7. **Channel Formatting**: Format for specific channel
8. **Response Delivery**: Return formatted response

### Supported Languages

- **Primary**: English, Hindi, Hinglish
- **Regional**: Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Odia, Assamese, Urdu, Konkani, Sindhi, Nepali, Kashmiri

### Supported Channels

- **WhatsApp**: Rich media, emojis, interactive buttons
- **RCS**: Rich cards, suggestions, media
- **SMS**: 160-character segments, plain text
- **Web**: JSON responses, REST API

## 🚀 Deployment

### Development

```bash
# Start with auto-reload
uvicorn app.main:app --reload --port 8000

# Or use the startup script
python run_app.py
```

### Production

```bash
# Install production dependencies
pip install -r requirements.txt

# Set environment
export ENVIRONMENT=production

# Start with Gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production

```env
ENVIRONMENT=production
REDIS_URL=redis://redis:6379
GOOGLE_API_KEY=your_production_key
GOOGLE_TRANSLATE_API_KEY=your_production_key
GOOGLE_MAPS_API_KEY=your_production_maps_key  # Store/address geocoding
DATABASE_URL=postgresql://user:pass@db:5432/vyaparai
SECRET_KEY=your_production_secret
```

## 📊 Monitoring

### Health Checks

- **Basic Health**: `/health`
- **Detailed Health**: `/health/detailed`
- **Component Status**: Service-by-service health

### Metrics

- **Order Processing**: Total orders, success rate, processing time
- **Language Distribution**: Usage by language
- **Channel Distribution**: Usage by channel
- **Performance**: Response times, throughput
- **Errors**: Error rates, error types

### Logging

- **Structured Logging**: JSON format for production
- **Request Tracking**: Request IDs for tracing
- **Performance Logging**: Response times, processing metrics
- **Error Logging**: Detailed error information

## 🔧 Development

### Project Structure

```
vyaparai/backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── orders.py
│   ├── middleware/
│   │   └── rate_limit.py
│   ├── nlp/
│   │   ├── extracted_patterns.py
│   │   ├── indian_commerce_ner.py
│   │   └── intent_classifier.py
│   ├── services/
│   │   ├── indian_multilingual_service.py
│   │   └── unified_order_service.py
│   └── main.py
├── tests/
├── requirements.txt
├── run_app.py
├── test_*.py
└── README.md
```

### Adding New Features

1. **Create Service**: Add business logic in `app/services/`
2. **Create API**: Add endpoints in `app/api/v1/`
3. **Add Tests**: Create test files in `tests/`
4. **Update Docs**: Update this README and API docs

### Code Style

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking

```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Lint code
flake8 app/ tests/

# Type check
mypy app/
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd vyaparai/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Start development server
python run_app.py
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: [API Docs](http://localhost:8000/docs)
- **Issues**: Create an issue on GitHub
- **Discussions**: Use GitHub Discussions
- **Email**: support@vyaparai.com

## 🗺 Roadmap

- [ ] Database integration (PostgreSQL)
- [ ] Authentication and authorization
- [ ] Payment gateway integration
- [ ] Advanced analytics dashboard
- [ ] Mobile app API
- [ ] Webhook signature verification
- [ ] Advanced rate limiting strategies
- [ ] Caching layer
- [ ] Background job processing
- [ ] Real-time notifications
- [ ] Multi-tenant support
- [ ] API versioning
- [ ] GraphQL support
- [ ] WebSocket support
- [ ] Advanced monitoring
- [ ] Load balancing
- [ ] Auto-scaling
- [ ] Disaster recovery
- [ ] Security hardening
- [ ] Performance optimization

---

**VyaparAI** - Intelligent Order Processing for Indian Grocery Stores 🛒🇮🇳
