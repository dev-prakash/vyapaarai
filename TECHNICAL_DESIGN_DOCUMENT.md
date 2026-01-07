# VyaparAI - Technical Design Document

**Version:** 2.1
**Date:** January 6, 2026
**Status:** Production
**Document Owner:** Development Team

---

## Change History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 2.1 | Jan 6, 2026 | Dev Prakash | Added Section 9.5 Enterprise Token Management (Frontend) - centralized tokenManager, multi-tab sync, idle timeout |
| 2.0 | Dec 23, 2025 | Dev Team | Initial production release |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Architecture](#3-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Database Design](#5-database-design)
6. [Backend Architecture](#6-backend-architecture)
7. [Frontend Architecture](#7-frontend-architecture)
8. [API Specification](#8-api-specification)
9. [Security & Authentication](#9-security--authentication)
10. [Real-Time Features](#10-real-time-features)
11. [Payment Integration](#11-payment-integration)
12. [Deployment Architecture](#12-deployment-architecture)
13. [Customer Experience](#13-customer-experience)
14. [Store Owner Features](#14-store-owner-features)
15. [Admin Features](#15-admin-features)
16. [Future Roadmap](#16-future-roadmap)
17. [Appendices](#17-appendices)

---

## 1. Executive Summary

### 1.1 Project Overview

**VyaparAI** is an enterprise-grade AI-powered inventory and order management platform designed for Indian retail stores (kirana shops). The platform operates as a B2B2C marketplace connecting store owners with customers.

**Core Capabilities:**
- Real-time inventory management with DynamoDB
- Multi-channel order processing (Web, WhatsApp, RCS)
- Progressive Web App (PWA) with offline support
- Multi-language support (10+ Indian languages)
- AI-powered product matching and deduplication
- Enterprise WebSocket real-time notifications
- Razorpay payment integration
- Transactional order processing with Saga pattern

### 1.2 Business Value

| Metric | Value |
|--------|-------|
| Efficiency | Reduce inventory management time by 70% |
| Accuracy | AI-powered product matching reduces duplicates by 95% |
| Accessibility | Multi-language support in 10+ Indian languages |
| Cost | Serverless architecture reduces infrastructure costs by 80% |
| Scale | Built to handle 1M+ products and 100K+ stores |

### 1.3 Project Metrics (December 2025)

| Metric | Value |
|--------|----------|
| Total API Endpoints | 85+ |
| Backend Endpoint Modules | 18 modules |
| Frontend Pages | 70+ pages |
| Frontend Components | 40+ component categories |
| Frontend Services | 28 API services |
| Custom React Hooks | 13 hooks |
| DynamoDB Tables | 11 tables |
| Supported Languages | 10+ |
| Lines of Backend Code | ~15,000+ |
| Lines of Frontend Code | ~50,000+ |
| Deployment Region | AWS ap-south-1 (Mumbai) |
| Project Completion | ~85% |

### 1.4 Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Backend API | Production | Lambda + API Gateway |
| Frontend PWA | Production | CloudFront + S3 |
| DynamoDB Integration | Complete | 11 tables operational |
| Order Management | Complete | Saga pattern implemented |
| Inventory Management | Complete | Real-time stock tracking |
| Customer Portal | Complete | Full shopping flow |
| Store Owner Dashboard | Complete | Enhanced dashboard |
| Payment Integration | Partial | Razorpay integrated, mock mode |
| WebSocket Notifications | Complete | Real-time order alerts |
| Settlement System | Not Started | B2B2C marketplace feature |

---

## 2. System Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Web Browser │  │  Mobile PWA  │  │Chrome Extens.│  │  WhatsApp    │   │
│  │  (React 18)  │  │  (Installable)│  │  (Scanner)   │  │  (Webhook)   │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CDN & API GATEWAY                                  │
│  ┌────────────────────────────┐  ┌────────────────────────────────────┐    │
│  │  CloudFront (E1UY93SVXV8QOF)│  │  API Gateway (jxxi8dtx1f)        │    │
│  │  www.vyapaarai.com         │  │  HTTP API v2 + WebSocket API      │    │
│  └────────────────────────────┘  └────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            COMPUTE LAYER                                     │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                  AWS Lambda (vyaparai-backend-prod)                 │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │    │
│  │  │   FastAPI    │  │   Mangum     │  │   Services   │              │    │
│  │  │   Router     │  │   Adapter    │  │   Layer      │              │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │            WebSocket Lambda (vyaparai-websocket-handler)            │    │
│  │  - Connection management  - Order broadcast  - DynamoDB Streams     │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  DynamoDB    │  │  PostgreSQL  │  │  S3 Storage  │  │    Redis     │   │
│  │  (11 Tables) │  │  (Analytics) │  │  (Images)    │  │  (Rate Limit)│   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL INTEGRATIONS                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Razorpay    │  │  Google Maps │  │  Firebase    │  │  WhatsApp    │   │
│  │  Payments    │  │  Geocoding   │  │  FCM         │  │  Business    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 System Components

#### **Frontend Layer**
- **React PWA**: Progressive Web App with offline support, service worker caching
- **Chrome Extension**: Browser-based quick actions and barcode scanning
- **Mobile Scanner**: Native camera access for barcode scanning
- **Multi-language**: 10+ Indian languages via i18next

#### **API Layer**
- **API Gateway HTTP API v2**: REST API management with CORS
- **API Gateway WebSocket API**: Real-time bidirectional communication
- **CloudFront**: Global CDN for static assets and caching

#### **Business Logic Layer**
- **FastAPI Application**: Python REST API framework
- **Mangum Adapter**: ASGI to Lambda handler bridge
- **Service Layer**: Business logic services (inventory, orders, payments)
- **Saga Pattern**: Transactional order processing with compensating transactions

#### **Data Layer**
- **DynamoDB**: Primary NoSQL database (11 tables, on-demand mode)
- **PostgreSQL**: Analytics and complex queries (RDS)
- **S3**: Object storage for images and files
- **Redis**: Rate limiting and caching

#### **Integration Layer**
- **Razorpay**: Payment processing (UPI, Cards, Wallets, COD)
- **Google Maps**: Geocoding for store discovery
- **Firebase**: Push notifications via FCM
- **WhatsApp Business**: Order notifications and webhooks

---

## 3. Architecture

### 3.1 Architecture Pattern

| Aspect | Choice |
|--------|--------|
| Pattern Type | Serverless Microservices |
| Deployment Model | Function as a Service (FaaS) |
| Data Model | Event-driven NoSQL + SQL hybrid |
| Frontend | Single Page Application (SPA) / PWA |
| Communication | REST API + WebSocket |

### 3.2 Design Principles

1. **Serverless-First**: Zero server management, auto-scaling
2. **Event-Driven**: DynamoDB Streams for real-time updates
3. **API-First**: RESTful APIs with OpenAPI documentation
4. **Mobile-First**: Responsive design, PWA capabilities
5. **Security-First**: JWT authentication, CORS, rate limiting
6. **Multi-Tenant**: Store-level data isolation
7. **Transactional Safety**: Saga pattern for critical operations

### 3.3 Key Architectural Decisions

#### **Decision 1: FastAPI + Lambda**
- **Rationale**: Modern Python framework with async support
- **Benefit**: Type safety, auto OpenAPI docs, high performance
- **Trade-off**: Cold start latency (~500ms)

#### **Decision 2: DynamoDB + PostgreSQL Hybrid**
- **Rationale**: NoSQL for real-time operations, SQL for analytics
- **Benefit**: Best of both worlds - scale + complex queries
- **Trade-off**: Data consistency complexity

#### **Decision 3: Monolithic Lambda**
- **Rationale**: Simplified deployment, shared code
- **Benefit**: Lower cold starts, easier debugging
- **Trade-off**: Larger package size (~37MB)

#### **Decision 4: PWA over Native Apps**
- **Rationale**: Single codebase, instant updates
- **Benefit**: Lower development cost, wider reach
- **Trade-off**: Limited native features

#### **Decision 5: Saga Pattern for Orders**
- **Rationale**: Transactional safety without distributed transactions
- **Benefit**: Atomic stock + order creation with rollback
- **Trade-off**: Implementation complexity

### 3.4 Scalability Strategy

| Component | Scaling Method | Current Limit |
|-----------|---------------|---------------|
| API Gateway | Auto-scale | 10,000 RPS |
| Lambda | Concurrent executions | 1,000 (configurable) |
| DynamoDB | On-demand mode | Unlimited |
| S3 | Unlimited | N/A |
| CloudFront | Global CDN | Unlimited |
| WebSocket | Connection-based | 500 concurrent |

---

## 4. Technology Stack

### 4.1 Backend Stack

#### **Core Framework**
```
FastAPI         0.118.0    # Web framework
Mangum          0.19.0     # ASGI to Lambda adapter
Uvicorn         0.34.0     # ASGI server (local dev)
Pydantic        2.11.4     # Data validation
```

#### **AWS SDK**
```
boto3           1.40.45    # AWS SDK for Python
botocore        1.35.89    # Low-level AWS interface
```

#### **Authentication & Security**
```
PyJWT           2.10.1     # JSON Web Tokens
bcrypt          5.0.0      # Password hashing
python-jose     3.3.0      # JWT operations
passlib         1.7.4      # Password utilities
```

#### **Payment Processing**
```
razorpay        2.0.0      # Payment gateway SDK
```

#### **Data Processing**
```
Pillow          11.3.0     # Image processing
pandas          2.2.3      # Data manipulation (CSV)
python-ulid     3.1.0      # ULID generation
```

### 4.2 Frontend Stack

#### **Core Framework**
```json
{
  "react": "18.3.1",
  "typescript": "5.5.4",
  "vite": "5.4.3"
}
```

#### **UI Framework**
```json
{
  "@mui/material": "5.18.0",
  "@mui/icons-material": "5.18.0",
  "@mui/x-date-pickers": "7.20.0",
  "@mui/x-data-grid": "7.20.0",
  "tailwindcss": "3.4.0"
}
```

#### **State Management**
```json
{
  "zustand": "5.0.8",
  "@tanstack/react-query": "5.85.5"
}
```

#### **API & Real-time**
```json
{
  "axios": "1.11.0",
  "socket.io-client": "4.8.1"
}
```

#### **Payment**
```json
{
  "razorpay": "2.9.6",
  "react-razorpay": "3.0.1"
}
```

#### **PWA**
```json
{
  "vite-plugin-pwa": "0.20.5",
  "workbox-window": "7.3.0"
}
```

#### **Internationalization**
```json
{
  "i18next": "25.4.2",
  "react-i18next": "15.2.3"
}
```

### 4.3 Infrastructure

```
Terraform        # Infrastructure as Code
AWS CLI          # AWS management
Docker           # Containerization
GitHub Actions   # CI/CD
```

---

## 5. Database Design

### 5.1 DynamoDB Tables Overview

| Table | Purpose | Primary Key | GSIs |
|-------|---------|-------------|------|
| vyaparai-stores-prod | Store profiles | store_id | email-index, region-index |
| vyaparai-global-products-prod | Product catalog | product_id | barcode-index, category-index |
| vyaparai-store-inventory-prod | Store inventory | store_id + product_id | store-active-index |
| vyaparai-orders-prod | Orders | order_id | store-orders-index, status-index |
| vyaparai-users-prod | User accounts | user_id | email-index |
| vyaparai-sessions-prod | Auth sessions | email + session_id | - |
| vyaparai-passcodes-prod | OTP codes | email | TTL enabled |
| vyaparai-categories-prod | Categories | category_id | - |
| vyaparai-bulk-upload-jobs-prod | CSV jobs | job_id | store-jobs-index |
| vyaparai-customer-profiles-prod | Customers | customer_id | phone-index, email-index |
| vyaparai-customer-carts-prod | Carts | customer_id + store_id | TTL: 30 min |
| vyaparai-websocket-connections | WS connections | connectionId | storeId-index |

### 5.2 Core Table Schemas

#### **vyaparai-stores-prod**
```javascript
{
  store_id: string,              // Primary Key
  store_name: string,
  owner_name: string,
  email: string,                 // GSI
  phone: string,
  address: {
    full: string,
    street: string,
    city: string,
    state: string,
    pincode: string
  },
  latitude: number,              // Auto-geocoded
  longitude: number,             // Auto-geocoded
  region: string,                // IN-MH, IN-TN, etc.
  business_type: string,
  category: string,
  rating: number,
  openingHours: string,
  isOpen: boolean,
  status: string,                // active, inactive, suspended
  created_at: string,
  updated_at: string
}
```

#### **vyaparai-orders-prod**
```javascript
{
  order_id: string,              // Primary Key (ORD{timestamp})
  store_id: string,              // GSI
  customer_id: string,           // GSI
  order_number: string,          // Human-readable
  tracking_id: string,           // TRK-{uuid}

  // Customer Info
  customer_name: string,
  customer_phone: string,
  customer_email: string,
  delivery_address: object,

  // Order Items
  items: [{
    product_id: string,
    product_name: string,
    quantity: number,
    unit_price: decimal,
    item_total: decimal
  }],

  // Totals
  subtotal: decimal,
  tax_amount: decimal,
  delivery_fee: decimal,
  total_amount: decimal,

  // Status
  status: string,                // pending, confirmed, processing, out_for_delivery, delivered, cancelled
  payment_status: string,        // pending, completed, failed, refunded
  payment_method: string,        // upi, card, cod, wallet
  payment_id: string,

  // Timestamps
  created_at: string,
  updated_at: string,

  // Metadata
  channel: string,               // web, whatsapp, phone
  language: string,
  notes: string
}
```

#### **vyaparai-store-inventory-prod**
```javascript
{
  store_id: string,              // Partition Key
  product_id: string,            // Sort Key

  // Pricing
  cost_price: decimal,
  selling_price: decimal,
  mrp: decimal,
  discount_percentage: decimal,

  // Stock
  current_stock: number,
  min_stock_level: number,
  max_stock_level: number,

  // Product Info (denormalized)
  product_name: string,
  brand: string,
  category: string,
  barcode: string,
  image_url: string,

  // Metadata
  is_active: boolean,
  created_at: string,
  updated_at: string,
  last_sold_at: string
}
```

#### **vyaparai-customer-profiles-prod**
```javascript
{
  customer_id: string,           // Primary Key (CUST{timestamp})
  email: string,                 // GSI
  phone: string,                 // GSI (required for OTP)

  // Personal Info
  first_name: string,
  last_name: string,
  date_of_birth: string,
  gender: string,

  // Addresses
  addresses: [{
    address_id: string,
    type: string,                // home, work, other
    is_default: boolean,
    recipient_name: string,
    phone: string,
    street: string,
    landmark: string,
    city: string,
    state: string,
    pincode: string,
    coordinates: { latitude, longitude }
  }],

  // Payment Methods
  payment_methods: [{
    payment_id: string,
    type: string,                // upi, card, wallet, cod
    is_default: boolean,
    // Type-specific fields
  }],

  // Preferences
  preferences: {
    language: string,
    notifications: { email, sms, push, whatsapp }
  },

  // Stats
  total_orders: number,
  total_spent: decimal,
  favorite_stores: [string],

  // Status
  status: string,
  email_verified: boolean,
  phone_verified: boolean,
  created_at: string,
  updated_at: string
}
```

### 5.3 Data Access Patterns

| Pattern | Query | Index | Complexity |
|---------|-------|-------|------------|
| Get store by ID | store_id | Primary | O(1) |
| Get store by email | email | GSI | O(1) |
| Get inventory by store | store_id | Primary | O(n) |
| Get product by barcode | barcode | GSI | O(1) |
| Get orders by store | store_id + date | GSI | O(n) |
| Get customer orders | customer_id | GSI | O(n) |
| Get low stock items | store_id + stock < min | Scan + Filter | O(n) |

---

## 6. Backend Architecture

### 6.1 Application Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app initialization
│   ├── api/
│   │   └── v1/                    # API version 1
│   │       ├── __init__.py
│   │       ├── admin_auth.py      # Admin authentication
│   │       ├── admin_products.py  # Admin product management
│   │       ├── analytics.py       # Analytics endpoints
│   │       ├── auth.py            # Store owner authentication
│   │       ├── cart.py            # Shopping cart API
│   │       ├── customer_auth.py   # Customer authentication
│   │       ├── customer_orders.py # Customer order endpoints
│   │       ├── customers.py       # Customer management
│   │       ├── health.py          # Health check endpoints
│   │       ├── inventory.py       # Inventory management
│   │       ├── notifications.py   # Notification API
│   │       ├── orders.py          # Order management
│   │       ├── payments.py        # Payment processing
│   │       ├── public.py          # Public endpoints
│   │       └── stores.py          # Store management
│   ├── models/                    # Data models
│   │   ├── customer.py
│   │   ├── inventory.py
│   │   ├── notification.py
│   │   ├── order.py
│   │   └── product.py
│   ├── services/                  # Business logic
│   │   ├── email_service.py
│   │   ├── geocoding_service.py
│   │   ├── inventory_service.py
│   │   ├── notification_service.py
│   │   ├── order_transaction_service.py
│   │   ├── payment_service.py
│   │   ├── product_media_service.py
│   │   ├── store_search_service.py
│   │   └── unified_order_service.py
│   ├── core/                      # Core utilities
│   │   ├── audit.py
│   │   ├── cache.py
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   ├── logging_config.py
│   │   ├── monitoring.py
│   │   ├── password.py
│   │   ├── retry.py
│   │   ├── security.py
│   │   └── validation.py
│   ├── database/                  # Database layer
│   │   ├── hybrid_db.py           # PostgreSQL + DynamoDB
│   │   └── migrations/
│   ├── middleware/                # FastAPI middleware
│   │   └── rate_limit.py
│   └── security/
│       └── data_privacy.py
├── lambda_handler.py              # Lambda entry point
├── requirements.txt
└── .env.production
```

### 6.2 Services Layer

#### **InventoryService** (`inventory_service.py`)
Handles all inventory operations with DynamoDB.

**Key Methods:**
```python
get_products(store_id, page, limit, category, status)
get_product(store_id, product_id)
search_products(store_id, query)
update_stock(store_id, product_id, quantity)          # Atomic with conditional expression
update_stock_bulk_transactional(store_id, items)      # DynamoDB TransactWriteItems
check_availability(store_id, items)
get_low_stock_products(store_id, threshold)
get_inventory_summary(store_id)
```

**Key Features:**
- Atomic stock updates using conditional expressions
- Transaction support (max 100 items per transaction)
- Exponential backoff for throughput exceeded errors
- Prevents overselling with conditional checks

#### **OrderTransactionService** (`order_transaction_service.py`)
Implements Saga pattern for transactional order creation.

**Key Methods:**
```python
create_order_with_stock_reservation(store_id, items, order_data)
_reserve_stock(store_id, items, order_id)
_rollback_stock_reservation(store_id, items, order_id)
```

**Saga Flow:**
```
1. Reserve stock (atomic deduction) → TransactWriteItems
2. Create order in DynamoDB
3. On failure: Execute compensating transaction (restore stock)
```

#### **PaymentService** (`payment_service.py`)
Razorpay integration for payment processing.

**Key Methods:**
```python
create_payment(order_id, amount, currency)
verify_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature)
process_refund(payment_id, amount)
get_payment_status(payment_id)
```

**Supported Methods:** UPI, Card, Wallet, COD

#### **GeocodingService** (`geocoding_service.py`)
Google Maps API integration for store discovery.

**Key Methods:**
```python
geocode_address(street, city, state, pincode)
geocode_search_query(pincode, landmark, city, state)
```

**Features:**
- In-memory caching (reduces API costs)
- India-biased results
- Auto-geocoding at store registration

### 6.3 Middleware

#### **Rate Limiting** (`rate_limit.py`)
Distributed rate limiting using Redis.

**Rate Limits:**
| Endpoint Type | Limit |
|--------------|-------|
| General API | 100 req/min per phone |
| Store API | 1000 req/min per store |
| OTP Send | 5/min |
| OTP Verify | 10/min |
| Login | 10/min |
| Register | 5/min |
| IP-based | 200 req/min |

### 6.4 Security

**Security Headers (OWASP Compliant):**
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin
- Content-Security-Policy: Custom per request
- HSTS: Enabled in production

**Custom Middlewares:**
- `SecurityHeadersMiddleware`: OWASP security headers
- `RequestSizeLimitMiddleware`: 10MB max payload
- `ContentTypeValidationMiddleware`: Validate POST/PUT content
- `APIRequestAuditMiddleware`: Log all API requests
- `RequestTimeoutMiddleware`: 30s timeout

---

## 7. Frontend Architecture

### 7.1 Application Structure

```
frontend-pwa/
├── src/
│   ├── pages/                     # 70+ page components
│   │   ├── admin/                 # Admin pages
│   │   │   ├── AdminDashboard.tsx
│   │   │   ├── AdminLogin.tsx
│   │   │   └── AdminProductCatalog.tsx
│   │   ├── customer/              # Customer pages
│   │   │   ├── CartPage.tsx
│   │   │   ├── CheckoutPage.tsx
│   │   │   ├── CustomerOrders.tsx
│   │   │   ├── CustomerProductCatalog.tsx
│   │   │   ├── EnhancedStoreHomePage.tsx
│   │   │   ├── OrderConfirmation.tsx
│   │   │   ├── OrderDetails.tsx
│   │   │   ├── OrderTracking.tsx
│   │   │   └── StoreSelector.tsx
│   │   ├── marketing/
│   │   │   └── HomePage.tsx
│   │   ├── Dashboard.tsx
│   │   ├── Analytics.tsx
│   │   ├── InventoryManagement.tsx
│   │   ├── EnhancedInventoryManagement.tsx
│   │   ├── MobileBarcodeScanner.tsx
│   │   ├── Orders.tsx
│   │   ├── StoreOwnerDashboard.tsx
│   │   └── StoreOwnerDashboardEnhanced.tsx
│   ├── components/                # 40+ component categories
│   │   ├── Admin/
│   │   ├── Analytics/
│   │   ├── Auth/
│   │   ├── Cart/
│   │   ├── Checkout/
│   │   ├── common/
│   │   ├── Dashboard/
│   │   ├── Inventory/
│   │   ├── Layout/
│   │   ├── Orders/
│   │   ├── Payment/
│   │   └── customer/
│   ├── services/                  # 28 API services
│   │   ├── api.ts
│   │   ├── apiClient.ts
│   │   ├── authService.ts
│   │   ├── cartService.ts
│   │   ├── customerService.ts
│   │   ├── enterpriseWebSocket.ts
│   │   ├── inventoryService.ts
│   │   ├── orderService.ts
│   │   ├── paymentService.ts
│   │   ├── razorpayService.ts
│   │   ├── realtimeOrderService.ts
│   │   └── storeService.ts
│   ├── stores/                    # Zustand stores
│   │   ├── authStore.ts
│   │   ├── cartStore.ts
│   │   └── unifiedAuthStore.ts
│   ├── hooks/                     # 13 custom hooks
│   │   ├── useRealtimeOrder.ts
│   │   ├── useWebSocket.ts
│   │   ├── useRazorpayPayment.ts
│   │   └── useGeolocation.ts
│   ├── i18n/                      # 10+ languages
│   ├── sw.ts                      # Service Worker
│   ├── App.tsx
│   └── main.tsx
├── public/
│   └── manifest.json              # PWA manifest
├── vite.config.ts
└── package.json
```

### 7.2 State Management

**Zustand Stores:**

#### **authStore.ts**
```typescript
interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  signIn: (email, password) => Promise<void>;
  signUp: (data) => Promise<void>;
  verifyOTP: (email, otp) => Promise<void>;
  signOut: () => void;
}
```

#### **cartStore.ts**
```typescript
interface CartState {
  items: CartItem[];
  storeId: string | null;
  customerInfo: CustomerInfo;
  addItem: (item) => void;
  updateQuantity: (productId, quantity) => void;
  removeItem: (productId) => void;
  clearCart: () => void;
  syncWithBackend: () => Promise<void>;
}
// Persists to localStorage
// Backend sync with guest cart migration
```

### 7.3 Routing Structure

```typescript
// Authentication Routes
/signin                           // Role selection
/login                            // Main login
/signup                           // Registration
/email-login                      // Email auth
/email-verification               // Verification

// Admin Routes (Protected)
/nimdaaccess                      // Admin login (hidden)
/admin                            // Admin dashboard
/admin/products                   // Product catalog admin

// Customer Routes
/products                         // Product catalog
/customer/auth                    // Customer login
/customer/stores                  // Store selector
/customer/store/:storeId          // Store detail
/customer/products                // Products for store
/customer/cart                    // Shopping cart
/customer/checkout                // Checkout flow
/customer/orders                  // Order history
/customer/orders/:orderId         // Order details
/customer/orders/:orderId/tracking // Live tracking

// Store Owner Routes
/store-login                      // Store owner login
/store-dashboard                  // Basic dashboard
/store-dashboard-enhanced         // Enhanced dashboard
/inventory                        // Inventory management
/inventory-enhanced               // Advanced inventory
/mobile-scan                      // Barcode scanner

// Marketing Routes
/                                 // Home page
/nearby-stores                    // Store locator
/store/:storeId                   // Store detail (public)
```

### 7.4 PWA Features

**Service Worker Caching Strategies:**
| Resource | Strategy | TTL |
|----------|----------|-----|
| Static assets | CacheFirst | 30 days |
| API responses | NetworkFirst | 5 minutes |
| Images | CacheFirst | 30 days |
| Fonts | CacheFirst | 1 year |
| Orders API | StaleWhileRevalidate | - |

**Offline Capabilities:**
- Cached app shell for offline access
- Queued API calls with BackgroundSync
- Offline indicator UI
- Graceful degradation

**PWA Manifest Features:**
- Standalone display mode
- App shortcuts (Orders, Dashboard, Inventory)
- File handlers (Images, CSV, XLSX)
- Share target capability
- Protocol handlers (web+vyaparai://)

### 7.5 Custom Hooks

#### **useEnterpriseWebSocket**
```typescript
function useEnterpriseWebSocket(storeId: string) {
  // Returns
  return {
    status: ConnectionStatus,      // 'connecting' | 'connected' | 'disconnected' | 'error'
    isConnected: boolean,
    newOrders: OrderNotification[],
    clearNewOrders: () => void,
    reconnect: () => void,
    disconnect: () => void
  };
}
```

#### **useRazorpayPayment**
```typescript
function useRazorpayPayment() {
  return {
    initiatePayment: (order, options) => Promise<PaymentResult>,
    isLoading: boolean,
    error: string | null
  };
}
```

#### **useRealtimeOrder**
```typescript
function useRealtimeOrder(orderId: string) {
  return {
    order: Order,
    status: OrderStatus,
    isTracking: boolean,
    estimatedTime: string
  };
}
```

---

## 8. API Specification

### 8.1 API Overview

| Attribute | Value |
|-----------|-------|
| Base URL | `https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com` |
| Protocol | HTTPS only |
| Format | JSON |
| Authentication | JWT Bearer tokens |
| Versioning | URI versioning (`/api/v1/`) |

### 8.2 Authentication Endpoints

#### **Store Owner Authentication**
```
POST /api/v1/auth/send-otp              # Send OTP
POST /api/v1/auth/verify-otp            # Verify OTP, get token
POST /api/v1/auth/login                 # Login with phone/password
POST /api/v1/auth/send-email-passcode   # Email-based OTP
POST /api/v1/auth/verify-email-passcode # Verify email OTP
POST /api/v1/auth/setup-password        # Set up password
POST /api/v1/auth/login-with-password   # Email + password login
```

#### **Customer Authentication**
```
POST /api/v1/customer/auth/send-otp     # Send OTP to customer
POST /api/v1/customer/auth/verify-otp   # Verify customer OTP
POST /api/v1/customer/auth/register     # Register new customer
POST /api/v1/customer/auth/login        # Customer login
GET  /api/v1/customer/auth/profile      # Get profile
PUT  /api/v1/customer/auth/profile      # Update profile
```

#### **Admin Authentication**
```
POST /api/v1/admin/auth/login           # Admin login
```

### 8.3 Inventory Endpoints

```
GET    /api/v1/inventory/products                 # List products (paginated)
GET    /api/v1/inventory/products/{product_id}    # Get single product
POST   /api/v1/inventory/products                 # Add product
PUT    /api/v1/inventory/products/{product_id}    # Update product
DELETE /api/v1/inventory/products/{product_id}    # Delete product
POST   /api/v1/inventory/search                   # Search products
GET    /api/v1/inventory/stock/{product_id}       # Check stock
POST   /api/v1/inventory/stock/update             # Update stock (atomic)
POST   /api/v1/inventory/stock/bulk-update        # Bulk update (transactional)
GET    /api/v1/inventory/low-stock                # Low stock products
GET    /api/v1/inventory/summary                  # Inventory stats
```

### 8.4 Order Endpoints

#### **Store Owner Orders**
```
GET  /api/v1/orders                       # List orders
GET  /api/v1/orders/{order_id}            # Get order details
GET  /api/v1/orders/{order_id}/status     # Get status
POST /api/v1/orders                       # Create order
POST /api/v1/orders/{order_id}/cancel     # Cancel order
PUT  /api/v1/orders/{order_id}/status     # Update status
GET  /api/v1/orders/history               # Order history (paginated)
GET  /api/v1/orders/export                # Export CSV/PDF
GET  /api/v1/orders/stats/daily           # Daily statistics
POST /api/v1/orders/calculate-total       # Calculate total
```

#### **Customer Orders**
```
GET  /api/v1/customer/orders              # Customer's orders
POST /api/v1/customers/orders             # Create order (Saga)
GET  /api/v1/customer/orders/{id}         # Order details
POST /api/v1/customer/orders/{id}/track   # Track order
POST /api/v1/customer/orders/{id}/cancel  # Cancel order
```

### 8.5 Payment Endpoints

```
POST /api/v1/payments/create              # Create payment intent
POST /api/v1/payments/confirm             # Confirm payment
GET  /api/v1/payments/{payment_id}/status # Get payment status
POST /api/v1/payments/{payment_id}/refund # Refund payment
POST /api/v1/payments/cod                 # Cash on Delivery
GET  /api/v1/payments/methods             # Available methods
POST /api/v1/payments/calculate-total     # Calculate order total
```

### 8.6 Store Endpoints

```
GET    /api/v1/stores                     # List stores
GET    /api/v1/stores/{store_id}          # Get store details
POST   /api/v1/stores                     # Create store
PUT    /api/v1/stores/{store_id}          # Update store
DELETE /api/v1/stores/{store_id}          # Delete store
GET    /api/v1/stores/{store_id}/orders   # Store orders
```

### 8.7 Public Endpoints

```
GET /api/v1/public/stores                 # List active stores
GET /api/v1/public/stores/nearby          # Nearby stores (GPS)
GET /api/v1/public/stores/{id}/products   # Store products
GET /api/v1/public/categories             # Product categories
```

### 8.8 Webhook Endpoints

```
POST /api/v1/orders/webhooks/whatsapp     # WhatsApp Cloud API
POST /api/v1/orders/webhooks/rcs          # Google RCS
POST /api/v1/orders/webhooks/sms          # SMS gateway
POST /api/v1/payments/webhooks/razorpay   # Payment notifications
```

### 8.9 Error Response Format

```json
{
  "success": false,
  "error": "Error message",
  "error_code": "INVALID_TOKEN",
  "details": {
    "field": "token",
    "reason": "Token expired"
  }
}
```

**HTTP Status Codes:**
| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 429 | Rate Limit |
| 500 | Server Error |

---

## 9. Security & Authentication

### 9.1 Authentication Flows

#### **Phone OTP Flow (Store Owners)**
```
Enter Phone → Send OTP → Verify OTP → JWT Token
              ↓
First Time → Setup Password (optional)
Returning → Can use Password
```

#### **Customer Authentication**
```
Enter Phone → Send OTP → Verify OTP → JWT Token
              ↓
New Customer → Auto-create profile
Existing → Return profile + cart migration
```

### 9.2 JWT Token Structure

```json
{
  "header": {
    "alg": "HS256",
    "typ": "JWT"
  },
  "payload": {
    "user_id": "usr_123",
    "email": "shop@example.com",
    "store_id": "str_456",
    "role": "store_owner",
    "iat": 1728394857,
    "exp": 1730986857
  }
}
```

**Token Expiration:**
| Token Type | Expiry |
|------------|--------|
| Access Token | 30 minutes |
| Refresh Token | 7 days |
| Customer Token | 30 days |
| Admin Token | 24 hours |
| Store Owner Token | 7 days |

### 9.3 Role-Based Access Control

| Role | Permissions |
|------|------------|
| admin | Full system access, global products, user management |
| store_owner | Own store, inventory, orders, customers |
| customer | Place orders, track orders, manage profile |

### 9.4 Data Security

| Aspect | Implementation |
|--------|----------------|
| In Transit | TLS 1.3 (HTTPS) |
| At Rest | AES-256 (DynamoDB, S3) |
| Passwords | bcrypt (cost factor: 12) |
| Tokens | HMAC-SHA256 signed |
| Multi-tenancy | Store-level data isolation |

### 9.5 Enterprise Token Management (Frontend)

> **Updated: January 2026** - Centralized token management with enterprise-grade features.

#### 9.5.1 Architecture Overview

The frontend implements a centralized `TokenManager` singleton that provides:
- Single source of truth for all authentication tokens
- Multi-tab session synchronization
- Proactive token refresh detection
- Idle session timeout
- Legacy token migration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TokenManager (Singleton)                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐ │
│  │  Token Storage  │  │  Session Sync   │  │  Idle Timeout               │ │
│  │  - vyaparai_    │  │  - storage      │  │  - 30 min inactivity        │ │
│  │    token        │  │    events       │  │  - Activity tracking        │ │
│  │  - vyaparai_    │  │  - Cross-tab    │  │  - Auto logout              │ │
│  │    user_type    │  │    logout       │  │                             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌───────────┐   ┌───────────┐   ┌───────────┐
            │ apiClient │   │ unified   │   │  api.ts   │
            │    .ts    │   │ ApiClient │   │           │
            └───────────┘   └───────────┘   └───────────┘
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
                            ┌───────────────┐
                            │ Auth Stores   │
                            │ - unified     │
                            │ - appStore    │
                            └───────────────┘
```

#### 9.5.2 Token Configuration

| Configuration | Value | Description |
|---------------|-------|-------------|
| `PRIMARY_KEY` | `vyaparai_token` | Single unified token key |
| `USER_TYPE_KEY` | `vyaparai_user_type` | User role identifier |
| `USER_DATA_KEY` | `vyaparai_user_data` | Cached user profile |
| `REFRESH_THRESHOLD_MS` | 5 minutes | Time before expiry to trigger refresh |
| `IDLE_TIMEOUT_MS` | 30 minutes | Inactivity timeout |
| `SESSION_CHECK_INTERVAL_MS` | 1 minute | Session validity check frequency |

#### 9.5.3 Token Storage Keys (Unified)

**Primary Keys (Active):**
```typescript
const TOKEN_CONFIG = {
  PRIMARY_KEY: 'vyaparai_token',        // JWT token
  USER_TYPE_KEY: 'vyaparai_user_type',  // customer|store_owner|admin|super_admin
  USER_DATA_KEY: 'vyaparai_user_data',  // JSON user profile
}
```

**Legacy Keys (Migrated & Cleaned):**
```typescript
LEGACY_KEYS: [
  'vyaparai_auth_token',    // Old auth token
  'auth_token',             // Generic token
  'customer_token',         // Customer-specific
  'vyaparai_customer_token',
  'vyaparai_admin_token',
]
```

#### 9.5.4 TokenManager API

**File:** `frontend-pwa/src/utils/tokenManager.ts`

```typescript
// Core Token Operations
tokenManager.getToken(): string | null
tokenManager.getUserType(): UserType | null
tokenManager.getUserData(): UserData | null
tokenManager.setTokens(token: string, userType: UserType, userData?: UserData): void
tokenManager.updateToken(newToken: string): void
tokenManager.clearTokens(): void

// Authentication State
tokenManager.isAuthenticated(): boolean
tokenManager.needsRefresh(): boolean
tokenManager.getTokenData(): TokenData | null

// JWT Parsing
tokenManager.parseJWT(token: string): TokenPayload | null
tokenManager.getUserId(): string | null
tokenManager.getStoreId(): string | null

// Event Subscriptions
tokenManager.onTokenChange(callback): () => void  // Returns unsubscribe
tokenManager.onIdle(callback): () => void         // Returns unsubscribe

// Lifecycle
tokenManager.initialize(): void
tokenManager.cleanup(): void

// Utilities
tokenManager.getLoginPath(userType): string
tokenManager.getDashboardPath(userType): string
tokenManager.debugState(): void
```

#### 9.5.5 Multi-Tab Session Synchronization

```
┌─────────────────┐                    ┌─────────────────┐
│     Tab 1       │                    │     Tab 2       │
│  (Active)       │                    │  (Background)   │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         │  User clicks "Logout"                │
         │                                      │
         ▼                                      │
┌─────────────────┐                             │
│ tokenManager    │                             │
│ .clearTokens()  │                             │
└────────┬────────┘                             │
         │                                      │
         │  localStorage.removeItem()           │
         │                                      │
         ▼                                      ▼
┌─────────────────────────────────────────────────────────┐
│              Browser Storage Event                       │
│  key: 'vyaparai_token', oldValue: 'xxx', newValue: null │
└─────────────────────────────────────────────────────────┘
         │                                      │
         │                                      ▼
         │                             ┌─────────────────┐
         │                             │ handleStorage   │
         │                             │ Change()        │
         │                             └────────┬────────┘
         │                                      │
         │                                      ▼
         │                             ┌─────────────────┐
         │                             │ Auto-logout &   │
         │                             │ Redirect        │
         │                             └─────────────────┘
```

#### 9.5.6 Idle Session Timeout Flow

```
User Activity          TokenManager              Timer
     │                      │                      │
     │  mousedown/keydown   │                      │
     ├─────────────────────▶│                      │
     │                      │  resetIdleTimer()    │
     │                      ├─────────────────────▶│
     │                      │                      │ Clear existing
     │                      │                      │ Start 30min timer
     │                      │                      │
     │    [30 min passes]   │                      │
     │                      │◀─────────────────────┤ Timer fires
     │                      │                      │
     │                      │  notifyIdle()        │
     │                      │  → logout()          │
     │                      │  → redirect          │
```

#### 9.5.7 API Client Integration

All API clients use TokenManager for consistent token handling:

```typescript
// Request Interceptor (all clients)
apiClient.interceptors.request.use((config) => {
  const token = tokenManager.getToken();  // ← Single source
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response Interceptor (401 handling)
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !isLoginEndpoint(url)) {
      tokenManager.clearTokens();  // ← Centralized cleanup
      window.location.href = getLoginPath(tokenManager.getUserType());
    }
    return Promise.reject(error);
  }
);
```

#### 9.5.8 Auth Store Integration

Both Zustand stores sync with TokenManager:

**unifiedAuthStore.ts:**
```typescript
// On login
tokenManager.setTokens(token, 'store_owner', userData);

// On logout
tokenManager.clearTokens();

// On session validation
const isValid = tokenManager.isAuthenticated();
const storedToken = tokenManager.getToken();
```

**appStore.ts:**
```typescript
// Multi-tab sync subscription
tokenManager.onTokenChange((newToken, newUserType) => {
  if (!newToken) {
    // Logout from another tab
    useAppStore.setState({ isAuthenticated: false, user: null });
  }
});
```

#### 9.5.9 Initialization Flow

```typescript
// AppProviders.tsx
useEffect(() => {
  // 1. Initialize unified auth (includes tokenManager.initialize())
  initializeUnifiedAuth();

  // 2. Initialize app store (syncs with tokenManager)
  initializeApp();

  // 3. Cleanup on unmount
  return () => tokenManager.cleanup();
}, []);
```

#### 9.5.10 Security Features Summary

| Feature | Implementation | Status |
|---------|----------------|--------|
| Single Token Key | `vyaparai_token` | ✅ Active |
| Legacy Token Migration | Auto-migrate on init | ✅ Active |
| Multi-Tab Sync | Storage event listener | ✅ Active |
| Idle Timeout | 30-minute inactivity | ✅ Active |
| Token Refresh Detection | 5-min before expiry | ✅ Active |
| Session Validation | 1-minute interval | ✅ Active |
| JWT Expiration Check | On every API call | ✅ Active |
| Role-Based Redirects | User type aware | ✅ Active |

---

## 10. Real-Time Features

### 10.1 Enterprise WebSocket Architecture

```
┌─────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│   Frontend  │────▶│  API Gateway        │────▶│  WebSocket      │
│   PWA       │     │  WebSocket API      │     │  Lambda Handler │
└─────────────┘     └─────────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DynamoDB Connections Table                    │
│  connectionId (PK) | storeId | user_type | connected_at        │
└─────────────────────────────────────────────────────────────────┘
                                                        │
                                                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DynamoDB Orders Table (Streams)               │
│  NEW_IMAGE triggers → WebSocket broadcast to store connections  │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 WebSocket Endpoints

**Connection URL:** `wss://fjmrwbfi2m.execute-api.ap-south-1.amazonaws.com/prod`

**Query Parameters:**
- `store_id`: Store identifier
- `user_type`: `store_owner` or `customer`

**Events:**
```typescript
// Inbound (client → server)
{ action: 'subscribe', store_id: 'str_123' }
{ action: 'ping' }

// Outbound (server → client)
{ type: 'new_order', order: {...} }
{ type: 'order_updated', order: {...} }
{ type: 'pong' }
{ type: 'subscribed', store_id: 'str_123' }
```

### 10.3 Frontend Integration

```typescript
// Connect to WebSocket
const { status, isConnected, newOrders } = useEnterpriseWebSocket(storeId);

// Subscribe to new orders
enterpriseWebSocket.onNewOrder((notification) => {
  toast.success(`New order from ${notification.order.customer_name}`);
  playNotificationSound();
  refreshOrdersList();
});
```

### 10.4 DynamoDB Streams Integration

- **Trigger**: INSERT/MODIFY on vyaparai-orders-prod
- **Lambda**: vyaparai-stream-processor
- **Action**: Broadcast to all connected store owners
- **Latency**: <500ms from order creation to notification

---

## 11. Payment Integration

### 11.1 Razorpay Integration Status

| Component | Status |
|-----------|--------|
| Razorpay SDK (Backend) | Integrated (v2.0.0) |
| Razorpay SDK (Frontend) | Integrated (v2.9.6) |
| Payment API Endpoints | Complete (7 endpoints) |
| Payment Methods | UPI, Card, COD, Wallet |
| Checkout Flow | Complete |
| Production Credentials | Not configured |
| Webhooks | Not implemented |
| Settlement System | Not implemented |

### 11.2 Payment Flow

```
Customer → Select Items → Checkout
                           ↓
            Create Razorpay Order (backend)
                           ↓
            Open Razorpay Checkout (frontend)
                           ↓
            Payment Success/Failure
                           ↓
            Verify Signature (backend)
                           ↓
            Update Order Status
```

### 11.3 Payment Methods

```python
class PaymentMethod(Enum):
    UPI = "upi"        # Google Pay, PhonePe, Paytm
    CARD = "card"      # Debit/Credit Card
    COD = "cod"        # Cash on Delivery
    WALLET = "wallet"  # Paytm, Mobikwik, etc.
```

### 11.4 Configuration Required

**Backend (.env.production):**
```
RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxx
PAYMENT_MOCK_MODE=false
```

**Frontend (.env.production):**
```
VITE_RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxx
```

---

## 12. Deployment Architecture

### 12.1 Current Production Deployment

#### **Backend (Lambda)**

| Setting | Value |
|---------|-------|
| Function Name | vyaparai-backend-prod |
| Runtime | Python 3.11 |
| Architecture | x86_64 |
| Memory | 1024 MB |
| Timeout | 30 seconds |
| Handler | lambda_handler.handler |
| Package Size | ~37 MB |

**Lambda Function URL:**
`https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com`

#### **Frontend (S3 + CloudFront)**

| Setting | Value |
|---------|-------|
| S3 Bucket | www.vyapaarai.com |
| CloudFront Distribution | E1UY93SVXV8QOF |
| Domain | https://www.vyapaarai.com |
| Build Tool | Vite |

### 12.2 Deployment Procedures

#### **Backend Deployment**
```bash
# 1. Package application
cd backend
zip -r deployment.zip app/ lambda_handler.py -x "*.pyc" -x "*__pycache__*"

# 2. Upload to S3
aws s3 cp deployment.zip s3://vyaparai-lambda-deployments/backend/

# 3. Update Lambda
aws lambda update-function-code \
  --function-name vyaparai-backend-prod \
  --s3-bucket vyaparai-lambda-deployments \
  --s3-key backend/deployment.zip

# 4. Verify
curl https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com/api/v1/health
```

#### **Frontend Deployment**
```bash
# 1. Build
cd frontend-pwa
npm run build

# 2. Deploy to S3
aws s3 sync dist/ s3://www.vyapaarai.com/ --delete

# 3. Invalidate CloudFront
aws cloudfront create-invalidation \
  --distribution-id E1UY93SVXV8QOF \
  --paths "/*"
```

### 12.3 Environment Variables

**Backend Lambda:**
```
ENVIRONMENT=production
AWS_REGION=ap-south-1
USE_DYNAMODB=true
USE_POSTGRESQL=true

# DynamoDB Tables
DYNAMODB_ORDERS_TABLE=vyaparai-orders-prod
DYNAMODB_CUSTOMERS_TABLE=vyaparai-customers-prod
DYNAMODB_STORES_TABLE=vyaparai-stores-prod
DYNAMODB_STOCK_TABLE=vyaparai-stock-prod

# Authentication
JWT_SECRET=<32+ chars secure secret>
JWT_ALGORITHM=HS256

# External APIs
GOOGLE_MAPS_API_KEY=<api_key>
RAZORPAY_KEY_ID=<key_id>
RAZORPAY_KEY_SECRET=<key_secret>
```

**Frontend:**
```
VITE_API_URL=https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com
VITE_WS_URL=wss://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com
VITE_REALTIME_WS_URL=wss://fjmrwbfi2m.execute-api.ap-south-1.amazonaws.com/prod
VITE_ENV=production
VITE_ENABLE_MOCK_DATA=false
VITE_RAZORPAY_KEY_ID=<key_id>
```

---

## 13. Customer Experience

### 13.1 Customer Journey

```
1. Store Discovery
   ├── GPS-based search (nearby stores)
   ├── Pincode/landmark search
   └── City/state filter
           ↓
2. Store Selection
   ├── View store details
   ├── Check opening hours
   └── Browse products inline
           ↓
3. Shopping
   ├── Add products to cart
   ├── Adjust quantities
   └── 30-minute cart expiration timer
           ↓
4. Checkout
   ├── Select/add delivery address
   ├── Choose payment method
   └── Place order (Saga pattern)
           ↓
5. Order Tracking
   ├── Real-time status updates
   ├── Push notifications
   └── Order history
```

### 13.2 Customer Pages

| Page | Route | Purpose |
|------|-------|---------|
| Auth | /customer/auth | Login/Register with OTP |
| Store Selector | /customer/stores | Find nearby stores |
| Store Details | /customer/store/:id | View store + products |
| Product Catalog | /customer/products | Browse products |
| Cart | /customer/cart | Shopping cart (30min TTL) |
| Checkout | /customer/checkout | Order placement |
| Orders | /customer/orders | Order history |
| Order Details | /customer/orders/:id | Single order |
| Tracking | /customer/orders/:id/tracking | Live tracking |

### 13.3 Cart Features

- **30-minute expiration timer** with visual countdown
- **Backend sync** for persistent carts
- **Guest cart migration** on login
- **Stock validation** before checkout
- **Special instructions** per item

---

## 14. Store Owner Features

### 14.1 Dashboard

**StoreOwnerDashboardEnhanced** provides:
- Real-time order feed with WebSocket
- Daily/weekly/monthly sales stats
- Low stock alerts
- Quick order actions (accept/reject)
- Revenue analytics

### 14.2 Inventory Management

- **Product CRUD**: Add, edit, delete products
- **Barcode scanning**: Mobile camera integration
- **Bulk upload**: CSV/XLSX import
- **Stock alerts**: Low stock notifications
- **Atomic updates**: Race condition prevention

### 14.3 Order Management

- **Real-time notifications**: WebSocket + push
- **Status workflow**: pending → confirmed → processing → out_for_delivery → delivered
- **Order details modal**: Customer info, items, totals
- **Export**: CSV/PDF export
- **History**: Paginated order history with filters

---

## 15. Admin Features

### 15.1 Admin Dashboard

- Global product catalog management
- Store verification
- User management
- Analytics overview

### 15.2 Product Catalog

- View all global products
- Create/edit/delete products
- Verification workflow
- Quality scoring

---

## 16. Future Roadmap

### 16.1 Short-term (Q1 2026)

| Feature | Priority | Status |
|---------|----------|--------|
| Production Razorpay keys | High | Pending |
| Payment webhooks | High | Not started |
| Settlement system | High | Not started |
| Commission engine | High | Not started |

### 16.2 Mid-term (Q2-Q3 2026)

| Feature | Priority |
|---------|----------|
| Multi-store management | Medium |
| Advanced analytics | Medium |
| Supplier management | Medium |
| AI demand forecasting | Medium |

### 16.3 Long-term (Q4 2026+)

| Feature | Priority |
|---------|----------|
| Mobile native apps | Low |
| Voice commerce | Low |
| Blockchain traceability | Low |
| IoT integration | Low |

---

## 17. Appendices

### 17.1 Glossary

| Term | Definition |
|------|------------|
| Kirana | Traditional Indian retail store |
| SKU | Stock Keeping Unit |
| HSN | Harmonized System Nomenclature (tax code) |
| MRP | Maximum Retail Price |
| GST | Goods and Services Tax |
| PWA | Progressive Web App |
| JWT | JSON Web Token |
| ASGI | Asynchronous Server Gateway Interface |
| Saga | Distributed transaction pattern |

### 17.2 Quick Reference

**API Base URL:** `https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com`

**WebSocket URL:** `wss://fjmrwbfi2m.execute-api.ap-south-1.amazonaws.com/prod`

**Frontend URL:** `https://www.vyapaarai.com`

**Health Check:** `GET /api/v1/health`

### 17.3 Useful Commands

```bash
# Deploy backend
aws lambda update-function-code --function-name vyaparai-backend-prod ...

# Deploy frontend
aws s3 sync dist/ s3://www.vyapaarai.com/ --delete
aws cloudfront create-invalidation --distribution-id E1UY93SVXV8QOF --paths "/*"

# Check logs
aws logs tail /aws/lambda/vyaparai-backend-prod --follow

# Test API
curl https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com/api/v1/health
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-08 | Dev Team | Initial TDD |
| 1.1 | 2025-11-11 | Dev Team | Customer experience section |
| 1.2 | 2025-12-04 | Dev Team | Store discovery geocoding |
| 1.3 | 2025-12-12 | Dev Team | Saga pattern checkout |
| 2.0 | 2025-12-23 | Dev Team | **Complete rewrite**: Full codebase documentation, WebSocket real-time features, payment integration analysis, updated metrics, all API endpoints, all services, all frontend components |

---

**End of Technical Design Document**

*For questions: dev@vyaparai.com*
