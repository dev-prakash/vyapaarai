# VyaparAI Testing Setup & Order Flow Verification

This document provides comprehensive instructions for setting up and testing the complete VyaparAI order flow from RCS/WhatsApp to the PWA dashboard.

## 🚀 Quick Start

### 1. Start Backend Services

```bash
# Navigate to the vyaparai directory
cd vyaparai

# Start all backend services using Docker Compose
docker-compose -f docker-compose.dev.yml up -d

# Verify services are running
docker-compose -f docker-compose.dev.yml ps
```

### 2. Start Frontend PWA

```bash
# Navigate to frontend directory
cd frontend-pwa

# Install dependencies (if not already done)
npm install

# Start development server
npm run dev
```

### 3. Run Complete Test Flow

```bash
# Run the automated test script
npm run test:order-flow

# Or run manually
../scripts/test-order-flow.sh
```

## 📋 Prerequisites

### Required Software
- **Docker & Docker Compose** - For backend services
- **Node.js 18+** - For frontend development
- **npm/yarn** - Package manager
- **curl** - For API testing

### Environment Variables
Create `.env.local` in the frontend-pwa directory:

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000

# Development Settings
VITE_ENV=development
VITE_ENABLE_MOCK_DATA=false
VITE_DEBUG_MODE=true
```

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   RCS/WhatsApp  │───▶│   Backend API   │───▶│   PWA Dashboard │
│   Messages      │    │   (FastAPI)     │    │   (React)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   WebSocket     │
                       │   (Socket.IO)   │
                       └─────────────────┘
```

## 🧪 Testing Components

### 1. Backend WebSocket Integration

**File**: `backend/app/websocket/socket_manager.py`

- **Socket.IO Server**: Handles real-time connections
- **Store-based Rooms**: Each store has its own WebSocket room
- **Event Broadcasting**: Emits order events to connected clients
- **Authentication**: Token-based store authentication

**Key Events**:
- `new_order` - When order is created
- `order_updated` - When order status changes
- `order_status_changed` - Status updates
- `store_stats` - Periodic statistics

### 2. Frontend Mock Server

**File**: `frontend-pwa/src/mocks/mockServer.ts`

- **Realistic Data Generation**: Indian names, products, addresses
- **Automatic Order Generation**: Random intervals (5-30 seconds)
- **Status Updates**: Simulates order processing flow
- **WebSocket Integration**: Connects to backend for testing

### 3. Test Panel

**File**: `frontend-pwa/src/pages/TestPanel.tsx`

- **Manual Order Generation**: Create orders on demand
- **Scenario Testing**: Breakfast rush, lunch rush, etc.
- **WebSocket Event Monitor**: Real-time event logging
- **Connection Status**: WebSocket health monitoring

### 4. Test Helpers

**File**: `frontend-pwa/src/utils/testHelpers.ts`

- **Indian Data**: Names, phone numbers, addresses
- **Product Catalog**: Realistic Indian grocery items
- **Order Patterns**: Different scenarios and time patterns
- **Regional Data**: North, South, East, West, Central India

## 🔄 Complete Order Flow

### 1. Customer Sends Message

```bash
# Test RCS message
curl -X POST http://localhost:8000/api/v1/webhooks/rcs \
  -H "Content-Type: application/json" \
  -d '{
    "message": "2 kg rice, 1 litre oil",
    "phone": "+919876543210",
    "store_id": "STORE-001"
  }'

# Test WhatsApp message
curl -X POST http://localhost:8000/api/v1/webhooks/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "message": "mujhe breakfast ke liye bread, milk chahiye",
    "phone": "+919876543210",
    "store_id": "STORE-001"
  }'
```

### 2. Backend Processing

1. **NLP Processing**: Intent classification and entity extraction
2. **Order Creation**: Generate order with customer details
3. **WebSocket Emission**: Broadcast `new_order` event
4. **Response Generation**: Send confirmation to customer

### 3. PWA Dashboard Updates

1. **WebSocket Reception**: Receive real-time order events
2. **Store Update**: Add order to local state
3. **UI Notification**: Show new order alert
4. **Sound Alert**: Play notification sound

### 4. Store Owner Actions

1. **Accept Order**: Click accept button
2. **Status Updates**: Process → Ready → Delivered
3. **Real-time Sync**: Updates reflected across all clients

## 🎯 Testing Scenarios

### Scenario 1: Single Order Flow
```bash
# Generate single test order
curl -X POST http://localhost:8000/api/v1/orders/test/generate-order \
  -H "Content-Type: application/json" \
  -d '{"store_id": "STORE-001", "order_type": "single"}'
```

### Scenario 2: Breakfast Rush
```bash
# Generate breakfast rush scenario
curl -X POST http://localhost:8000/api/v1/orders/test/generate-order \
  -H "Content-Type: application/json" \
  -d '{"store_id": "STORE-001", "order_type": "breakfast_rush"}'
```

### Scenario 3: Bulk Orders
```bash
# Generate bulk orders
curl -X POST http://localhost:8000/api/v1/orders/test/generate-order \
  -H "Content-Type: application/json" \
  -d '{"store_id": "STORE-001", "order_type": "bulk"}'
```

## 🔧 Development Commands

### Frontend Commands
```bash
# Start frontend only
npm run dev

# Start with mock data
npm run dev:mock

# Start backend and frontend together
npm run dev:all

# Run order flow test
npm run test:order-flow
```

### Backend Commands
```bash
# Start backend services
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f backend

# Stop services
docker-compose -f docker-compose.dev.yml down
```

### Database Management
```bash
# Access PostgreSQL
docker exec -it vyaparai_postgres_1 psql -U vyaparai -d vyaparai_dev

# Access Redis
docker exec -it vyaparai_redis_1 redis-cli

# View pgAdmin (http://localhost:5050)
# Email: admin@vyaparai.com, Password: admin123

# View Redis Commander (http://localhost:8081)
```

## 📊 Monitoring & Debugging

### WebSocket Connection Status
- **Frontend**: Check connection status in Test Panel
- **Backend**: Monitor logs for WebSocket events
- **Browser DevTools**: Network tab for WebSocket frames

### API Endpoints
- **Health Check**: `http://localhost:8000/health`
- **API Docs**: `http://localhost:8000/docs`
- **WebSocket**: `ws://localhost:8000/socket.io/`

### Logs
```bash
# Backend logs
docker-compose -f docker-compose.dev.yml logs -f backend

# Frontend logs (browser console)
# Check for WebSocket events and order updates
```

## 🐛 Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Check if backend is running: `curl http://localhost:8000/health`
   - Verify CORS settings in backend
   - Check browser console for errors

2. **Orders Not Appearing**
   - Verify WebSocket authentication
   - Check store ID matches
   - Monitor backend logs for order processing

3. **Mock Server Not Working**
   - Ensure backend is running
   - Check WebSocket connection status
   - Verify authentication token

4. **Database Connection Issues**
   - Check if PostgreSQL is running: `docker ps`
   - Verify environment variables
   - Check database logs

### Debug Mode
Enable debug mode in frontend:
```env
VITE_DEBUG_MODE=true
VITE_LOG_LEVEL=debug
```

## 📈 Performance Testing

### Load Testing
```bash
# Generate 50 orders rapidly
for i in {1..50}; do
  curl -X POST http://localhost:8000/api/v1/orders/test/generate-order \
    -H "Content-Type: application/json" \
    -d '{"store_id": "STORE-001", "order_type": "single"}' &
done
```

### WebSocket Stress Test
```bash
# Test multiple store connections
for i in {1..10}; do
  # Connect multiple stores
  curl -X POST http://localhost:8000/api/v1/orders/test/generate-order \
    -H "Content-Type: application/json" \
    -d "{\"store_id\": \"STORE-00$i\", \"order_type\": \"single\"}"
done
```

## 🎯 Expected Results

### Successful Test Flow
1. ✅ Backend services start without errors
2. ✅ Frontend connects to WebSocket
3. ✅ Test orders appear in dashboard
4. ✅ Real-time updates work
5. ✅ Order actions (accept/reject) function
6. ✅ Sound notifications play
7. ✅ Offline queue works when disconnected

### Performance Benchmarks
- **Order Processing**: < 100ms
- **WebSocket Latency**: < 50ms
- **UI Updates**: < 200ms
- **Database Queries**: < 10ms

## 📚 Additional Resources

- **API Documentation**: `http://localhost:8000/docs`
- **WebSocket Events**: See `backend/app/websocket/socket_manager.py`
- **Test Data**: See `frontend-pwa/src/utils/testHelpers.ts`
- **Mock Server**: See `frontend-pwa/src/mocks/mockServer.ts`

## 🤝 Contributing

When adding new test scenarios:
1. Update `testHelpers.ts` with new data patterns
2. Add corresponding API endpoints
3. Update Test Panel with new controls
4. Document the new scenario in this README

---

**Happy Testing! 🧪✨**
