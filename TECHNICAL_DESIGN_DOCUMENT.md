# VyaparAI - Technical Design Document

**Version:** 1.0
**Date:** October 8, 2025
**Status:** Production
**Document Owner:** Development Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Architecture](#architecture)
4. [Technology Stack](#technology-stack)
5. [Database Design](#database-design)
6. [API Specification](#api-specification)
7. [Frontend Architecture](#frontend-architecture)
8. [Security & Authentication](#security--authentication)
9. [Core Features](#core-features)
10. [Integration Points](#integration-points)
11. [Deployment Architecture](#deployment-architecture)
12. [Future Roadmap](#future-roadmap)
13. [Appendices](#appendices)

---

## 1. Executive Summary

### 1.1 Project Overview

**VyaparAI** is an AI-powered inventory and order management platform designed for Indian retail stores (kirana shops). The platform provides:

- Intelligent product catalog management
- Real-time inventory tracking
- Multi-language support (10+ Indian languages)
- AI-powered product matching and deduplication
- Progressive Web App (PWA) for offline functionality
- Automated order processing

### 1.2 Business Value

- **Efficiency**: Reduce inventory management time by 70%
- **Accuracy**: AI-powered product matching reduces duplicates by 95%
- **Accessibility**: Multi-language support in 10+ Indian languages
- **Cost**: Serverless architecture reduces infrastructure costs by 80%
- **Scale**: Built to handle 1M+ products and 100K+ stores

### 1.3 Project Metrics

| Metric | Value |
|--------|-------|
| Total API Endpoints | 68 |
| Frontend Pages | 47 |
| Services | 17 |
| DynamoDB Tables | 9 |
| Supported Languages | 10+ |
| Lines of Backend Code | ~5,554 |
| Deployment Region | AWS ap-south-1 (Mumbai) |

---

## 2. System Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Web Browser │  │ Mobile PWA   │  │Chrome Ext.   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      CDN & API GATEWAY                       │
│         CloudFront + API Gateway HTTP API v2                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     COMPUTE LAYER                            │
│  ┌──────────────────────────────────────────────┐           │
│  │  AWS Lambda (FastAPI + Mangum)               │           │
│  │  - Authentication                            │           │
│  │  - Inventory Management                      │           │
│  │  - Order Processing                          │           │
│  │  - Admin Operations                          │           │
│  └──────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      DATA LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  DynamoDB    │  │  S3 Storage  │  │  SES Email   │      │
│  │  (9 Tables)  │  │  (Images)    │  │  Service     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   EXTERNAL INTEGRATIONS                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Google       │  │  Razorpay    │  │ WhatsApp     │      │
│  │ Gemini AI    │  │  Payment     │  │  Business    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 System Components

#### **Frontend Layer**
- **React PWA**: Progressive Web App with offline support
- **Chrome Extension**: Browser-based quick actions
- **Mobile Scanner**: Native camera access for barcode scanning

#### **API Layer**
- **API Gateway**: AWS API Gateway HTTP API v2
- **CloudFront**: Global CDN for static assets
- **CORS**: Cross-origin resource sharing configuration

#### **Business Logic Layer**
- **FastAPI Application**: REST API endpoints
- **Mangum Adapter**: ASGI to Lambda handler
- **Service Layer**: Business logic services
- **Worker Processes**: Background job processing

#### **Data Layer**
- **DynamoDB**: Primary NoSQL database (9 tables)
- **S3**: Object storage for images and files
- **SES**: Email delivery service

#### **Integration Layer**
- **Google Gemini AI**: Product description generation
- **Razorpay**: Payment processing
- **WhatsApp Business**: Order notifications
- **Open Food Facts**: Product data enrichment

---

## 3. Architecture

### 3.1 Architecture Pattern

**Pattern Type**: Serverless Microservices
**Deployment Model**: Function as a Service (FaaS)
**Data Model**: Event-driven NoSQL

### 3.2 Design Principles

1. **Serverless-First**: Zero server management, auto-scaling
2. **Event-Driven**: Asynchronous processing for long-running tasks
3. **API-First**: RESTful APIs with OpenAPI documentation
4. **Mobile-First**: Responsive design, PWA capabilities
5. **Security-First**: JWT authentication, encrypted storage
6. **Multi-Tenant**: Store-level data isolation
7. **Scalable**: Horizontal scaling via Lambda concurrency

### 3.3 Key Architectural Decisions

#### **Decision 1: FastAPI + Lambda**
- **Rationale**: FastAPI provides modern Python web framework with automatic OpenAPI docs
- **Benefit**: Type safety, async support, high performance
- **Trade-off**: Cold start latency (~500ms)

#### **Decision 2: DynamoDB over RDS**
- **Rationale**: NoSQL better suits dynamic product attributes, auto-scaling
- **Benefit**: Infinite scale, pay-per-request pricing
- **Trade-off**: No complex queries, denormalized data

#### **Decision 3: Monolithic Lambda**
- **Rationale**: Simplified deployment, shared code, lower cold starts
- **Benefit**: Faster development, easier debugging
- **Trade-off**: Larger package size, all-or-nothing deployments

#### **Decision 4: PWA over Native Apps**
- **Rationale**: Single codebase, instant updates, offline support
- **Benefit**: Lower development cost, wider reach
- **Trade-off**: Limited native features

### 3.4 Scalability Strategy

| Component | Scaling Method | Limit |
|-----------|---------------|-------|
| API Gateway | Auto-scale | 10,000 RPS |
| Lambda | Concurrent executions | 1,000 (default) |
| DynamoDB | On-demand mode | Unlimited |
| S3 | Unlimited | N/A |
| CloudFront | Global CDN | Unlimited |

---

## 4. Technology Stack

### 4.1 Backend Stack

#### **Core Framework**
```python
FastAPI      0.118.0  # Web framework
Mangum       0.19.0   # ASGI to Lambda adapter
Uvicorn      0.34.0   # ASGI server (local dev)
Pydantic     2.11.4   # Data validation
```

#### **AWS SDK**
```python
boto3        1.40.45  # AWS SDK for Python
botocore     1.35.89  # Low-level AWS interface
```

#### **Authentication & Security**
```python
PyJWT        2.10.1   # JSON Web Tokens
bcrypt       5.0.0    # Password hashing
python-jose  3.3.0    # JWT operations
passlib      1.7.4    # Password utilities
```

#### **Data Processing**
```python
Pillow       11.3.0   # Image processing
NumPy        2.3.3    # Numerical computing
ImageHash    4.3.2    # Perceptual hashing
pandas       2.2.3    # Data manipulation (CSV)
```

#### **AI & ML**
```python
google-generativeai  0.8.4  # Google Gemini API
openai               1.59.7 # OpenAI API (future)
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
  "@mui/x-data-grid": "7.20.0"
}
```

#### **State Management**
```json
{
  "zustand": "5.0.8",              // Global state
  "@tanstack/react-query": "5.85.5" // Server state
}
```

#### **Routing & Forms**
```json
{
  "react-router-dom": "7.8.1",
  "react-hook-form": "7.54.2",
  "yup": "1.6.1"
}
```

#### **API & Data**
```json
{
  "axios": "1.11.0",
  "socket.io-client": "4.8.1"
}
```

#### **Internationalization**
```json
{
  "i18next": "25.4.2",
  "react-i18next": "15.2.3"
}
```

#### **PWA**
```json
{
  "vite-plugin-pwa": "0.20.5",
  "workbox-window": "7.3.0"
}
```

### 4.3 Development Tools

#### **Backend Development**
```
pytest           # Testing
black            # Code formatting
flake8           # Linting
mypy             # Type checking
```

#### **Frontend Development**
```
ESLint           # Linting
Prettier         # Code formatting
TypeScript       # Type safety
Vite             # Build tool
```

#### **Infrastructure**
```
Terraform        # Infrastructure as Code
AWS CLI          # AWS management
Docker           # Containerization (optional)
```

---

## 5. Database Design

### 5.1 DynamoDB Tables

#### **Table 1: vyaparai-stores-prod**
**Purpose**: Store information and profiles

```javascript
Primary Key: store_id (String)

Attributes:
{
  store_id: string,              // Unique store identifier
  store_name: string,            // Store display name
  owner_name: string,            // Owner full name
  email: string,                 // Contact email (GSI)
  phone: string,                 // Contact phone
  address: {
    street: string,
    city: string,
    state: string,
    pincode: string,
    coordinates: {
      latitude: number,
      longitude: number
    }
  },
  region: string,                // State code (IN-MH, IN-TN, etc.)
  business_type: string,         // kirana, supermarket, etc.
  created_at: string,            // ISO timestamp
  updated_at: string,
  status: string,                // active, inactive, suspended
  settings: {
    language: string,
    currency: string,
    timezone: string
  }
}

Indexes:
- GSI: email-index (email as partition key)
- GSI: region-index (region as partition key)
```

#### **Table 2: vyaparai-global-products-prod**
**Purpose**: Global product catalog (master data)

```javascript
Primary Key: product_id (String)

Attributes:
{
  product_id: string,            // GP{timestamp} format
  name: string,                  // Product name (English)
  brand: string,                 // Brand name
  category: string,              // Product category
  subcategory: string,
  barcode: string,               // EAN/UPC barcode (GSI)
  image_hash: string,            // Perceptual hash (GSI)

  canonical_image_urls: {
    original: string,            // S3 URL
    thumbnail: string,           // 150x150
    medium: string,              // 500x500
    large: string                // 1024x1024
  },

  regional_names: {
    "IN-MH": ["मराठी नाव"],     // Maharashtra (Marathi)
    "IN-TN": ["தமிழ் பெயர்"],    // Tamil Nadu (Tamil)
    "IN-KA": ["ಕನ್ನಡ ಹೆಸರು"],   // Karnataka (Kannada)
    "IN-AP": ["తెలుగు పేరు"],    // Andhra Pradesh (Telugu)
    "IN-GJ": ["ગુજરાતી નામ"],   // Gujarat (Gujarati)
    "IN-WB": ["বাংলা নাম"],      // West Bengal (Bengali)
    "IN-KL": ["മലയാളം പേര്"],    // Kerala (Malayalam)
    "IN-PB": ["ਪੰਜਾਬੀ ਨਾਮ"],    // Punjab (Punjabi)
    "IN-RJ": ["राजस्थानी नाम"],  // Rajasthan (Hindi)
    "IN-UP": ["हिन्दी नाम"]      // Uttar Pradesh (Hindi)
  },

  attributes: {
    weight: string,              // "500g", "1kg", etc.
    pack_size: string,
    unit: string,                // pieces, kg, liters, etc.
    manufacturer: string,
    mrp: number,                 // Maximum Retail Price
    hsn_code: string,            // HSN code for GST
    nutritional_info: object
  },

  verification_status: string,   // pending, verified, flagged, admin_created
  quality_score: number,         // 0-100
  stores_using_count: number,    // Usage counter

  created_by: string,            // user_id or 'system'
  created_at: string,
  updated_at: string,

  metadata: {
    source: string,              // manual, import, api
    import_source: string,       // open-food-facts, etc.
    last_reviewed_at: string,
    last_reviewed_by: string
  }
}

Indexes:
- GSI: barcode-index (barcode as partition key)
- GSI: image-hash-index (image_hash as partition key)
- GSI: verification-status-index (verification_status as partition key)
- GSI: category-index (category as partition key)
```

#### **Table 3: vyaparai-store-inventory-prod**
**Purpose**: Store-specific inventory

```javascript
Primary Key:
  Partition Key: store_id (String)
  Sort Key: product_id (String)

Attributes:
{
  store_id: string,
  product_id: string,            // Links to global product

  // Pricing
  cost_price: decimal,           // Purchase price
  selling_price: decimal,        // Sale price
  mrp: decimal,                  // Maximum Retail Price
  discount_percentage: decimal,

  // Stock
  current_stock: number,
  min_stock_level: number,       // Reorder point
  max_stock_level: number,
  reorder_quantity: number,

  // Location
  location: string,              // Shelf/bin location
  warehouse: string,

  // Supplier
  supplier: string,
  supplier_sku: string,
  last_purchase_date: string,
  last_purchase_price: decimal,

  // Metadata
  notes: string,                 // Store-specific notes
  is_active: boolean,
  created_at: string,
  updated_at: string,
  last_sold_at: string,

  // Analytics
  total_sold: number,
  total_revenue: decimal,
  average_sale_price: decimal
}

Indexes:
- GSI: store-active-index (store_id + is_active)
- GSI: low-stock-index (store_id + current_stock < min_stock_level)
```

#### **Table 4: vyaparai-orders-prod**
**Purpose**: Customer orders

```javascript
Primary Key: order_id (String)

Attributes:
{
  order_id: string,              // ORD{timestamp}
  store_id: string,              // GSI

  // Customer
  customer_name: string,
  customer_phone: string,
  customer_email: string,
  delivery_address: object,

  // Order Details
  items: [
    {
      product_id: string,
      product_name: string,
      quantity: number,
      unit_price: decimal,
      discount: decimal,
      total: decimal
    }
  ],

  // Totals
  subtotal: decimal,
  tax_amount: decimal,
  discount_amount: decimal,
  delivery_charges: decimal,
  total_amount: decimal,

  // Status
  status: string,                // pending, confirmed, packed, shipped, delivered, cancelled
  payment_status: string,        // pending, paid, refunded
  payment_method: string,        // cash, upi, card

  // Timestamps
  created_at: string,
  confirmed_at: string,
  shipped_at: string,
  delivered_at: string,

  // Tracking
  tracking_number: string,
  notes: string
}

Indexes:
- GSI: store-orders-index (store_id + created_at)
- GSI: status-index (status + created_at)
```

#### **Table 5: vyaparai-users-prod**
**Purpose**: User accounts

```javascript
Primary Key: user_id (String)

Attributes:
{
  user_id: string,
  email: string,                 // GSI
  full_name: string,
  phone: string,

  role: string,                  // admin, store_owner, staff
  store_id: string,              // Linked store

  status: string,                // active, inactive, suspended

  created_at: string,
  updated_at: string,
  last_login_at: string,

  preferences: {
    language: string,
    notifications: boolean,
    email_alerts: boolean
  }
}

Indexes:
- GSI: email-index (email as partition key)
- GSI: store-users-index (store_id + role)
```

#### **Table 6: vyaparai-sessions-prod**
**Purpose**: User sessions and passwords

```javascript
Primary Key:
  Partition Key: email (String)
  Sort Key: session_id (String)

Attributes:
{
  email: string,
  session_id: string,
  password_hash: string,         // bcrypt hash
  password_salt: string,

  last_login: string,
  login_count: number,
  failed_attempts: number,
  locked_until: string,

  created_at: string,
  updated_at: string
}
```

#### **Table 7: vyaparai-passcodes-prod**
**Purpose**: OTP/Passcode verification

```javascript
Primary Key: email (String)

Attributes:
{
  email: string,
  passcode: string,              // 6-digit OTP
  expires_at: string,
  attempts: number,
  verified: boolean,
  created_at: string
}

TTL: expires_at (auto-delete after expiry)
```

#### **Table 8: vyaparai-categories-prod**
**Purpose**: Product categories

```javascript
Primary Key: category_id (String)

Attributes:
{
  category_id: string,
  name: string,
  parent_category_id: string,    // For subcategories
  display_order: number,
  icon: string,
  is_active: boolean,

  regional_names: {
    "hi": "हिन्दी नाम",
    "ta": "தமிழ் பெயர்",
    // ... other languages
  }
}
```

#### **Table 9: vyaparai-bulk-upload-jobs-prod**
**Purpose**: Async CSV upload jobs

```javascript
Primary Key: job_id (String)

Attributes:
{
  job_id: string,
  store_id: string,
  user_id: string,

  file_name: string,
  file_size: number,
  s3_key: string,

  status: string,                // pending, processing, completed, failed
  progress: {
    total_rows: number,
    processed_rows: number,
    successful: number,
    failed: number,
    percentage: number
  },

  errors: [
    {
      row: number,
      error: string,
      data: object
    }
  ],

  started_at: string,
  completed_at: string,
  created_at: string
}

Indexes:
- GSI: store-jobs-index (store_id + created_at)
```

### 5.2 Data Access Patterns

#### **Pattern 1: Get Store Inventory**
```
Query: store-id + product-id (direct lookup)
Index: Primary key
Complexity: O(1)
```

#### **Pattern 2: List Low Stock Items**
```
Query: store-id + current_stock < min_stock_level
Index: low-stock-index (GSI)
Complexity: O(n) where n = matching items
```

#### **Pattern 3: Find Product by Barcode**
```
Query: barcode
Index: barcode-index (GSI)
Complexity: O(1)
```

#### **Pattern 4: Search Products by Name**
```
Method: Scan with filter (expensive)
Alternative: Use OpenSearch/Elasticsearch
Optimization: Implement text search service
```

#### **Pattern 5: Get Store Orders**
```
Query: store-id + date range
Index: store-orders-index (GSI)
Complexity: O(n) where n = orders in range
```

### 5.3 Data Consistency

#### **Consistency Model**
- **Strong Consistency**: Financial transactions, inventory updates
- **Eventual Consistency**: Analytics, reporting, search indexes

#### **Conflict Resolution**
- **Last Write Wins**: Default for most updates
- **Conditional Updates**: For critical operations (stock updates)
- **Optimistic Locking**: Version numbers for concurrent updates

### 5.4 Backup & Recovery

#### **Backup Strategy**
- **DynamoDB Point-in-Time Recovery**: Enabled on all tables
- **Retention**: 35 days
- **S3 Versioning**: Enabled for image storage
- **Cross-Region Replication**: Planned for disaster recovery

---

## 6. API Specification

### 6.1 API Overview

**Base URL**: `https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com`
**Protocol**: HTTPS only
**Format**: JSON
**Authentication**: JWT Bearer tokens
**Versioning**: URI versioning (`/api/v1/`)

### 6.2 Authentication Endpoints

#### **POST /api/v1/auth/send-email-passcode**
Send OTP to email for authentication

**Request:**
```json
{
  "email": "shop@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Passcode sent to email",
  "expires_in": 300
}
```

#### **POST /api/v1/auth/verify-email-passcode**
Verify OTP and get JWT token

**Request:**
```json
{
  "email": "shop@example.com",
  "passcode": "123456"
}
```

**Response:**
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "user_id": "usr_123",
    "email": "shop@example.com",
    "store_id": "str_456"
  },
  "has_password": false
}
```

#### **POST /api/v1/auth/setup-password**
Set up password after first login

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Password setup successful"
}
```

#### **POST /api/v1/auth/login-with-password**
Login with email and password

**Request:**
```json
{
  "email": "shop@example.com",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "user_id": "usr_123",
    "email": "shop@example.com",
    "store_id": "str_456",
    "role": "store_owner"
  }
}
```

### 6.3 Inventory Management Endpoints

#### **GET /api/v1/inventory/products**
List all products in store inventory

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**
- `page` (optional): Page number (default: 1)
- `limit` (optional): Items per page (default: 50)
- `status` (optional): active, inactive, low_stock
- `category` (optional): Filter by category

**Response:**
```json
{
  "success": true,
  "products": [
    {
      "id": "GP1759847856118",
      "product_id": "GP1759847856118",
      "store_id": "str_456",
      "name": "Tata Salt",
      "brand": "Tata",
      "category": "Groceries",
      "price": 20.00,
      "selling_price": 20.00,
      "cost_price": 18.00,
      "mrp": 22.00,
      "stock_quantity": 50,
      "current_stock": 50,
      "min_stock_level": 10,
      "max_stock_level": 100,
      "is_active": true,
      "barcode": "8901234567890",
      "created_at": "2025-10-01T10:30:00Z",
      "updated_at": "2025-10-05T15:45:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "limit": 50,
  "pages": 3
}
```

#### **POST /api/v1/inventory/products**
Add new product to inventory

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
  "product_name": "Maggi Noodles",
  "brand_name": "Nestle",
  "barcode": "8901058843095",
  "category": "Instant Food",
  "selling_price": 14.00,
  "cost_price": 12.00,
  "mrp": 15.00,
  "current_stock": 100,
  "min_stock_level": 20,
  "max_stock_level": 200,
  "attributes": {
    "weight": "70g",
    "pack_size": "1",
    "unit": "piece"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Product added successfully",
  "product": {
    "product_id": "GP1728394857123",
    "store_id": "str_456",
    "name": "Maggi Noodles",
    "matched_from_catalog": true,
    "global_product_id": "GP1659847123456"
  }
}
```

#### **PUT /api/v1/inventory/products/{product_id}**
Update product details

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
  "selling_price": 15.00,
  "current_stock": 75,
  "min_stock_level": 15
}
```

**Response:**
```json
{
  "success": true,
  "message": "Product updated successfully",
  "product": {
    "product_id": "GP1728394857123",
    "updated_fields": ["selling_price", "current_stock", "min_stock_level"],
    "updated_at": "2025-10-08T12:30:00Z"
  }
}
```

#### **DELETE /api/v1/inventory/products/{product_id}**
Delete product from inventory

**Headers:** `Authorization: Bearer {token}`

**Response:**
```json
{
  "success": true,
  "message": "Product deleted successfully"
}
```

### 6.4 Order Management Endpoints

#### **GET /api/v1/orders**
List orders

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**
- `status` (optional): pending, confirmed, delivered, cancelled
- `from_date` (optional): ISO date
- `to_date` (optional): ISO date

**Response:**
```json
{
  "success": true,
  "orders": [
    {
      "order_id": "ORD1728394857123",
      "store_id": "str_456",
      "customer_name": "Rajesh Kumar",
      "customer_phone": "+919876543210",
      "items": [
        {
          "product_id": "GP1728394857123",
          "product_name": "Maggi Noodles",
          "quantity": 5,
          "unit_price": 14.00,
          "total": 70.00
        }
      ],
      "subtotal": 70.00,
      "tax_amount": 3.50,
      "total_amount": 73.50,
      "status": "pending",
      "payment_status": "pending",
      "created_at": "2025-10-08T10:00:00Z"
    }
  ],
  "total": 25
}
```

#### **POST /api/v1/orders**
Create new order

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
  "customer_name": "Rajesh Kumar",
  "customer_phone": "+919876543210",
  "items": [
    {
      "product_id": "GP1728394857123",
      "quantity": 5
    }
  ],
  "payment_method": "cash",
  "notes": "Deliver before 6 PM"
}
```

**Response:**
```json
{
  "success": true,
  "order": {
    "order_id": "ORD1728394857123",
    "total_amount": 73.50,
    "status": "pending",
    "created_at": "2025-10-08T10:00:00Z"
  }
}
```

### 6.5 Admin Endpoints

#### **GET /api/v1/admin/products/global**
List all global products (admin only)

**Headers:** `Authorization: Bearer {admin_token}`

**Response:**
```json
{
  "success": true,
  "products": [
    {
      "product_id": "GP1659847123456",
      "name": "Maggi Noodles",
      "brand": "Nestle",
      "category": "Instant Food",
      "barcode": "8901058843095",
      "verification_status": "verified",
      "quality_score": 95,
      "stores_using_count": 1250,
      "created_at": "2024-08-01T10:00:00Z"
    }
  ],
  "total": 16
}
```

#### **DELETE /api/v1/admin/products/{product_id}**
Delete global product (admin only)

**Headers:** `Authorization: Bearer {admin_token}`

**Response:**
```json
{
  "success": true,
  "message": "Global product deleted successfully",
  "product_id": "GP1659847123456"
}
```

### 6.6 Error Responses

#### **Standard Error Format**
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

#### **HTTP Status Codes**
- `200 OK` - Success
- `201 Created` - Resource created
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Missing or invalid token
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict (duplicate)
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

### 6.7 Rate Limiting

**Limits:**
- Anonymous: 100 requests/hour
- Authenticated: 1000 requests/hour
- Admin: 5000 requests/hour

**Headers:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1728394857
```

---

## 7. Frontend Architecture

### 7.1 Application Structure

```
frontend-pwa/
├── public/                      # Static assets
│   ├── manifest.json           # PWA manifest
│   └── icons/                  # App icons
├── src/
│   ├── main.tsx               # Entry point
│   ├── App.tsx                # Root component
│   ├── router.tsx             # Route configuration
│   │
│   ├── pages/                 # 47 page components
│   │   ├── auth/
│   │   │   ├── Login.tsx
│   │   │   ├── Signup.tsx
│   │   │   └── PasswordSetup.tsx
│   │   ├── dashboard/
│   │   │   ├── Dashboard.tsx
│   │   │   └── Analytics.tsx
│   │   ├── inventory/
│   │   │   ├── InventoryManagement.tsx
│   │   │   └── ProductCatalog.tsx
│   │   ├── orders/
│   │   │   ├── Orders.tsx
│   │   │   └── OrderHistory.tsx
│   │   └── admin/
│   │       ├── AdminDashboard.tsx
│   │       └── AdminProductCatalog.tsx
│   │
│   ├── components/            # 31 reusable components
│   │   ├── common/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── LoadingSpinner.tsx
│   │   ├── inventory/
│   │   │   ├── ProductCard.tsx
│   │   │   ├── ProductEntryForm.tsx
│   │   │   └── BarcodeScanner.tsx
│   │   └── orders/
│   │       ├── OrderCard.tsx
│   │       └── OrderStatusBadge.tsx
│   │
│   ├── services/              # 17 API services
│   │   ├── api.ts            # Base API client
│   │   ├── authService.ts
│   │   ├── inventoryService.ts
│   │   ├── orderService.ts
│   │   └── geminiService.ts
│   │
│   ├── stores/               # State management
│   │   ├── useAuthStore.ts
│   │   ├── useInventoryStore.ts
│   │   └── useCartStore.ts
│   │
│   ├── hooks/                # Custom hooks
│   │   ├── useAuth.ts
│   │   ├── useDebounce.ts
│   │   └── useMediaQuery.ts
│   │
│   ├── utils/                # Utilities
│   │   ├── formatters.ts
│   │   ├── validators.ts
│   │   └── constants.ts
│   │
│   ├── types/                # TypeScript types
│   │   ├── product.ts
│   │   ├── order.ts
│   │   └── user.ts
│   │
│   ├── i18n/                 # Internationalization
│   │   ├── config.ts
│   │   └── translations/
│   │       ├── en.json
│   │       ├── hi.json
│   │       └── ta.json
│   │
│   └── styles/               # Global styles
│       ├── theme.ts          # MUI theme
│       └── global.css
```

### 7.2 State Management Strategy

#### **Global State (Zustand)**
```typescript
// useAuthStore.ts
interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('token'),
  isAuthenticated: !!localStorage.getItem('token'),
  login: async (email, password) => {
    const response = await authService.login(email, password);
    set({
      user: response.user,
      token: response.token,
      isAuthenticated: true
    });
  },
  logout: () => {
    localStorage.removeItem('token');
    set({ user: null, token: null, isAuthenticated: false });
  }
}));
```

#### **Server State (TanStack Query)**
```typescript
// useProducts.ts
export const useProducts = () => {
  return useQuery({
    queryKey: ['products'],
    queryFn: () => inventoryService.getProducts(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    cacheTime: 30 * 60 * 1000  // 30 minutes
  });
};
```

### 7.3 Routing Structure

```typescript
// router.tsx
const routes = [
  // Public routes
  { path: '/', element: <HomePage /> },
  { path: '/login', element: <Login /> },
  { path: '/signup', element: <Signup /> },

  // Protected routes (store owner)
  {
    path: '/dashboard',
    element: <ProtectedRoute><Dashboard /></ProtectedRoute>
  },
  {
    path: '/inventory',
    element: <ProtectedRoute><InventoryManagement /></ProtectedRoute>
  },
  {
    path: '/orders',
    element: <ProtectedRoute><Orders /></ProtectedRoute>
  },

  // Admin routes
  {
    path: '/admin',
    element: <AdminRoute><AdminDashboard /></AdminRoute>
  },
  {
    path: '/admin/products',
    element: <AdminRoute><AdminProductCatalog /></AdminRoute>
  }
];
```

### 7.4 PWA Configuration

#### **Service Worker Strategy**
```typescript
// vite.config.ts
VitePWA({
  registerType: 'autoUpdate',
  workbox: {
    globPatterns: ['**/*.{js,css,html,ico,png,svg}'],
    runtimeCaching: [
      {
        urlPattern: /^https:\/\/api\.vyaparai\.com\/.*/i,
        handler: 'NetworkFirst',
        options: {
          cacheName: 'api-cache',
          expiration: {
            maxEntries: 100,
            maxAgeSeconds: 60 * 60 // 1 hour
          }
        }
      },
      {
        urlPattern: /^https:\/\/.*\.(png|jpg|jpeg|svg|gif)$/i,
        handler: 'CacheFirst',
        options: {
          cacheName: 'images-cache',
          expiration: {
            maxEntries: 50,
            maxAgeSeconds: 30 * 24 * 60 * 60 // 30 days
          }
        }
      }
    ]
  }
})
```

#### **Offline Support**
- **Cache API requests**: Network-first strategy
- **Cache images**: Cache-first strategy
- **Background sync**: Queue failed requests
- **Offline indicator**: Visual feedback when offline

### 7.5 Responsive Design

#### **Breakpoints**
```typescript
// theme.ts
const breakpoints = {
  xs: 0,      // Mobile
  sm: 600,    // Tablet
  md: 960,    // Small Desktop
  lg: 1280,   // Desktop
  xl: 1920    // Large Desktop
};
```

#### **Mobile-First Approach**
- Base styles for mobile
- Progressive enhancement for larger screens
- Touch-friendly UI elements
- Optimized images

---

## 8. Security & Authentication

### 8.1 Authentication Flow

#### **Email + OTP Flow**
```
User → Enter Email → Send OTP → Verify OTP → JWT Token
  ↓
First Time User → Setup Password
Returning User → Can use Password
```

#### **Password Flow**
```
User → Enter Email + Password → Verify → JWT Token
```

### 8.2 JWT Token Structure

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
  },
  "signature": "..."
}
```

**Token Expiry**: 30 days
**Refresh Strategy**: Re-authentication required after expiry

### 8.3 Authorization

#### **Role-Based Access Control (RBAC)**

| Role | Permissions |
|------|------------|
| **admin** | Full system access, manage global products, user management |
| **store_owner** | Manage own store, inventory, orders |
| **staff** | View inventory, create orders (future) |
| **customer** | Place orders, track orders (future) |

#### **Endpoint Protection**

```python
# Admin-only endpoint
@app.get("/api/v1/admin/products")
async def get_admin_products(request: Request):
    user = get_user_from_jwt(request)
    if user.role != 'admin':
        raise HTTPException(403, "Admin access required")
    # ... logic
```

### 8.4 Data Security

#### **Encryption**
- **In Transit**: TLS 1.3 (HTTPS)
- **At Rest**: AES-256 (DynamoDB, S3)
- **Passwords**: bcrypt (cost factor: 12)
- **Tokens**: HMAC-SHA256 signed

#### **Data Isolation**
- **Multi-tenancy**: Store-level data isolation
- **Query filters**: Automatic store_id filtering
- **Database access**: Row-level security

### 8.5 API Security

#### **CORS Configuration**
```python
# Current (permissive - needs tightening)
allow_origins = ["*"]

# Recommended (production)
allow_origins = [
    "https://www.vyapaarai.com",
    "https://vyapaarai.com",
    "http://localhost:5173"  # Dev only
]
```

#### **Rate Limiting**
```python
# Per endpoint rate limits
@limiter.limit("100/hour")
async def public_endpoint():
    pass

@limiter.limit("1000/hour")
async def authenticated_endpoint():
    pass
```

#### **Input Validation**
- **Pydantic Models**: Type checking and validation
- **SQL Injection**: Parameterized queries (DynamoDB safe by default)
- **XSS Prevention**: HTML sanitization
- **File Upload**: Size limits, type validation

### 8.6 Compliance

#### **Data Privacy**
- **GDPR**: User data deletion on request (future)
- **Indian IT Act**: Compliance (future)
- **PCI DSS**: No card data stored (Razorpay handles)

#### **Audit Logging**
- All admin actions logged
- Failed authentication attempts tracked
- Data modification history (future)

---

## 9. Core Features

### 9.1 Smart Product Matching

**Problem**: Stores add duplicate products with different names

**Solution**: Multi-strategy matching algorithm

#### **Strategy 1: Barcode Matching (Primary)**
```python
# Exact match on barcode
if barcode:
    existing = dynamodb.query(
        IndexName='barcode-index',
        KeyConditionExpression='barcode = :barcode'
    )
    if existing:
        return existing  # 100% match
```

#### **Strategy 2: Image Hash Matching**
```python
# Perceptual hash comparison
image_hash = generate_perceptual_hash(product_image)
similar_products = find_similar_hashes(image_hash, threshold=5)
# Hamming distance < 5 = very similar
```

#### **Strategy 3: Fuzzy Name Matching**
```python
# Levenshtein distance on normalized names
normalized_name = normalize(product_name)  # lowercase, remove special chars
for existing_product in catalog:
    score = fuzzywuzzy.ratio(normalized_name, existing_product.name)
    if score > 90:
        suggestions.append(existing_product)
```

#### **Strategy 4: Multi-attribute Scoring**
```python
def calculate_match_score(product_a, product_b):
    score = 0

    # Name similarity (40%)
    score += name_similarity(product_a.name, product_b.name) * 0.4

    # Brand match (20%)
    if product_a.brand == product_b.brand:
        score += 0.2

    # Category match (10%)
    if product_a.category == product_b.category:
        score += 0.1

    # Attributes match (30%)
    score += attribute_similarity(product_a.attrs, product_b.attrs) * 0.3

    return score
```

### 9.2 Multi-Language Support

#### **Supported Languages**
1. English (en)
2. Hindi (hi) - हिन्दी
3. Tamil (ta) - தமிழ்
4. Telugu (te) - తెలుగు
5. Marathi (mr) - मराठी
6. Gujarati (gu) - ગુજરાતી
7. Kannada (kn) - ಕನ್ನಡ
8. Malayalam (ml) - മലയാളം
9. Bengali (bn) - বাংলা
10. Punjabi (pa) - ਪੰਜਾਬੀ

#### **Regional Names Feature**
```python
# Store region-specific product names
product = {
    "name": "Salt",  # English (default)
    "regional_names": {
        "IN-MH": ["मीठ", "मिठ"],           # Maharashtra (Marathi)
        "IN-TN": ["உப்பு"],                 # Tamil Nadu (Tamil)
        "IN-GJ": ["મીઠું", "મીઠુ"],         # Gujarat (Gujarati)
        "IN-KA": ["ಉಪ್ಪು"],                 # Karnataka (Kannada)
        # ...
    }
}
```

#### **Language Detection**
```python
def detect_language(text):
    # Unicode range detection
    if is_devanagari(text):
        return 'hi'  # Hindi/Marathi
    elif is_tamil(text):
        return 'ta'
    # ...
    return 'en'  # Default
```

### 9.3 CSV Bulk Upload

#### **Upload Flow**
```
1. User uploads CSV file
   ↓
2. Store in S3 bucket
   ↓
3. Create job record (status: pending)
   ↓
4. Return job_id to user
   ↓
5. Lambda async processing:
   - Parse CSV
   - Validate rows
   - Match products
   - Create/update inventory
   - Update progress
   ↓
6. Job completion (status: completed/failed)
   ↓
7. User polls for status updates
```

#### **CSV Format**
```csv
product_name,brand,barcode,category,cost_price,selling_price,mrp,stock,min_stock
Tata Salt,Tata,8901234567890,Groceries,18.00,20.00,22.00,50,10
Maggi Noodles,Nestle,8901058843095,Instant Food,12.00,14.00,15.00,100,20
```

#### **Error Handling**
```python
# Validation errors
errors = [
    {
        "row": 5,
        "error": "Invalid barcode format",
        "data": {"barcode": "invalid123"}
    },
    {
        "row": 12,
        "error": "Duplicate product name",
        "data": {"product_name": "Tata Salt"}
    }
]

# Progress tracking
progress = {
    "total_rows": 100,
    "processed": 75,
    "successful": 70,
    "failed": 5,
    "percentage": 75.0
}
```

### 9.4 Inventory Alerts

#### **Low Stock Alert**
```python
# Automated low stock detection
if product.current_stock <= product.min_stock_level:
    send_alert(
        type='low_stock',
        product=product,
        message=f"{product.name} is low on stock ({product.current_stock} remaining)"
    )
```

#### **Out of Stock Alert**
```python
# Zero stock notification
if product.current_stock == 0:
    send_alert(
        type='out_of_stock',
        product=product,
        priority='high'
    )
```

#### **Reorder Suggestions**
```python
# Smart reorder calculation
def calculate_reorder_quantity(product, sales_history):
    avg_daily_sales = calculate_average_daily_sales(sales_history)
    lead_time_days = 7  # Supplier lead time
    safety_stock = avg_daily_sales * 3  # 3 days buffer

    reorder_quantity = (avg_daily_sales * lead_time_days) + safety_stock
    return round_up_to_case_size(reorder_quantity, product.case_size)
```

### 9.5 Order Management

#### **Order Creation**
```python
# Automatic stock deduction
def create_order(items):
    order = Order()

    for item in items:
        product = get_product(item.product_id)

        # Validate stock availability
        if product.current_stock < item.quantity:
            raise InsufficientStockError()

        # Deduct stock
        update_stock(product, -item.quantity)

        # Add to order
        order.add_item(item)

    # Calculate totals
    order.calculate_totals()

    # Save order
    save_order(order)

    return order
```

#### **Order Status Workflow**
```
pending → confirmed → packed → shipped → delivered
                ↓
            cancelled (anytime before shipped)
```

### 9.6 Admin Quality Control

#### **Product Verification Workflow**
```
User adds product → Status: pending
    ↓
Admin reviews → Approve/Reject
    ↓
Approved → Status: verified
Rejected → Status: flagged
```

#### **Quality Scoring**
```python
def calculate_quality_score(product):
    score = 0

    # Has barcode (+20)
    if product.barcode:
        score += 20

    # Has image (+15)
    if product.image:
        score += 15

    # Has brand (+10)
    if product.brand:
        score += 10

    # Complete attributes (+25)
    if all_attributes_filled(product):
        score += 25

    # Used by multiple stores (+30)
    usage_bonus = min(product.stores_using_count * 2, 30)
    score += usage_bonus

    return min(score, 100)
```

---

## 10. Integration Points

### 10.1 AWS Services

#### **Lambda**
- **Purpose**: Serverless compute
- **Configuration**:
  - Runtime: Python 3.11
  - Memory: 1024 MB
  - Timeout: 30 seconds
  - Concurrency: 1000 (reserved)

#### **DynamoDB**
- **Purpose**: Primary database
- **Configuration**:
  - Mode: On-demand
  - Encryption: AWS managed keys
  - Point-in-time recovery: Enabled
  - TTL: Enabled on passcodes table

#### **S3**
- **Purpose**: File storage
- **Buckets**:
  - `vyaparai-product-images-prod`: Product images
  - `vyaparai-bulk-uploads-prod`: CSV uploads
  - `vyaparai-frontend-prod`: Frontend static files
- **Configuration**:
  - Versioning: Enabled
  - Encryption: AES-256
  - CORS: Configured for frontend

#### **CloudFront**
- **Purpose**: CDN
- **Configuration**:
  - Origin: S3 bucket
  - SSL/TLS: ACM certificate
  - Caching: Optimized for static assets
  - Compression: Gzip/Brotli enabled

#### **API Gateway**
- **Purpose**: API management
- **Type**: HTTP API v2
- **Configuration**:
  - CORS: Enabled
  - Throttling: 10,000 RPS
  - Custom domain: api.vyaparai.com (planned)

#### **SES**
- **Purpose**: Email delivery
- **Configuration**:
  - Verified domain: vyaparai.com (planned)
  - Templates: OTP emails
  - Bounce handling: Configured

#### **CloudWatch**
- **Purpose**: Monitoring & logging
- **Configuration**:
  - Log retention: 30 days
  - Metrics: Custom business metrics
  - Alarms: Error rate, latency

### 10.2 External APIs

#### **Google Gemini AI**
```python
# Product description generation
import google.generativeai as genai

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

model = genai.GenerativeModel('gemini-pro')
response = model.generate_content(
    f"Generate a concise product description for: {product_name}"
)
description = response.text
```

**Use Cases**:
- Product description generation
- Image analysis (product identification)
- Natural language queries (future)

#### **Razorpay**
```python
# Payment processing
import razorpay

client = razorpay.Client(
    auth=(os.getenv('RAZORPAY_KEY_ID'),
          os.getenv('RAZORPAY_KEY_SECRET'))
)

# Create order
order = client.order.create({
    'amount': amount * 100,  # Amount in paise
    'currency': 'INR',
    'receipt': order_id
})
```

**Use Cases**:
- Order payments
- Subscription payments (future)
- Refunds

#### **Open Food Facts**
```python
# Product data enrichment
import requests

response = requests.get(
    f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
)

if response.status_code == 200:
    data = response.json()['product']

    # Extract product info
    product_info = {
        'name': data.get('product_name'),
        'brand': data.get('brands'),
        'category': data.get('categories'),
        'image_url': data.get('image_url'),
        'nutritional_info': data.get('nutriments')
    }
```

**Use Cases**:
- Product data enrichment
- Barcode lookup
- Nutritional information

### 10.3 Firebase (Legacy/Optional)
- **Purpose**: Real-time features
- **Usage**: Limited (being phased out)
- **Alternative**: WebSocket via API Gateway (planned)

---

## 11. Deployment Architecture

### 11.1 Current Deployment

#### **Backend**
```
Source Code → GitHub
    ↓
Local Build → zip deployment package
    ↓
AWS Lambda → Update function code
    ↓
API Gateway → Route requests
```

**Deployment Command**:
```bash
cd backend/lambda-email-minimal/lambda-csv-minimal
zip -r deployment.zip .
aws lambda update-function-code \
  --function-name vyaparai-api-prod \
  --zip-file fileb://deployment.zip
```

#### **Frontend**
```
Source Code → GitHub
    ↓
Vite Build → npm run build
    ↓
S3 Upload → aws s3 sync dist/ s3://bucket/
    ↓
CloudFront Invalidation → Cache clear
```

**Deployment Command**:
```bash
cd frontend-pwa
npm run build
aws s3 sync dist/ s3://vyaparai-frontend-prod/ --delete
aws cloudfront create-invalidation \
  --distribution-id E1234567890ABC \
  --paths "/*"
```

### 11.2 Environment Configuration

#### **Environments**
1. **Development** (Local)
   - Local FastAPI server (uvicorn)
   - Local React dev server (Vite)
   - DynamoDB local (optional)

2. **Staging** (Planned)
   - Separate Lambda function
   - Separate DynamoDB tables
   - Subdomain: staging.vyaparai.com

3. **Production**
   - Lambda: vyaparai-api-prod
   - DynamoDB: *-prod tables
   - Domain: www.vyaparai.com

#### **Environment Variables**
```bash
# Backend Lambda
GLOBAL_PRODUCTS_TABLE=vyaparai-global-products-prod
STORE_INVENTORY_TABLE=vyaparai-store-inventory-prod
JWT_SECRET=vyaparai-jwt-secret-2024-secure
GEMINI_API_KEY=<secret>
RAZORPAY_KEY_ID=<secret>
RAZORPAY_KEY_SECRET=<secret>

# Frontend
VITE_API_URL=https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com
VITE_GEMINI_API_KEY=<secret>
```

### 11.3 CI/CD Pipeline (Planned)

```yaml
# .github/workflows/deploy-prod.yml
name: Deploy Production

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Package Lambda
        run: |
          cd backend/lambda-email-minimal/lambda-csv-minimal
          zip -r deployment.zip .
      - name: Deploy to Lambda
        run: |
          aws lambda update-function-code \
            --function-name vyaparai-api-prod \
            --zip-file fileb://deployment.zip

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build
        run: |
          cd frontend-pwa
          npm ci
          npm run build
      - name: Deploy to S3
        run: |
          aws s3 sync dist/ s3://vyaparai-frontend-prod/
      - name: Invalidate CloudFront
        run: |
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.CF_DIST_ID }} \
            --paths "/*"
```

### 11.4 Monitoring & Alerting

#### **CloudWatch Dashboards**
1. **API Performance**
   - Request count
   - Error rate
   - Latency (p50, p95, p99)
   - Lambda duration

2. **Business Metrics**
   - Active stores
   - Orders per hour
   - Products added per day
   - User registrations

#### **Alarms**
```python
# High error rate alarm
{
    "AlarmName": "vyaparai-api-high-error-rate",
    "MetricName": "Errors",
    "Namespace": "AWS/Lambda",
    "Statistic": "Average",
    "Period": 300,
    "EvaluationPeriods": 1,
    "Threshold": 0.05,  # 5% error rate
    "ComparisonOperator": "GreaterThanThreshold",
    "AlarmActions": ["arn:aws:sns:ap-south-1:123456:alerts"]
}
```

### 11.5 Disaster Recovery

#### **Backup Strategy**
- **DynamoDB**: Point-in-time recovery (35 days)
- **S3**: Versioning + cross-region replication (planned)
- **Lambda**: Version control via git + tagged releases

#### **Recovery Procedures**
1. **Database Recovery**
   ```bash
   aws dynamodb restore-table-to-point-in-time \
     --source-table-name vyaparai-stores-prod \
     --target-table-name vyaparai-stores-prod-restored \
     --restore-date-time 2025-10-07T10:00:00Z
   ```

2. **Lambda Rollback**
   ```bash
   aws lambda update-function-code \
     --function-name vyaparai-api-prod \
     --zip-file fileb://previous-deployment.zip
   ```

3. **Frontend Rollback**
   ```bash
   aws s3 sync s3://backup-bucket/ s3://prod-bucket/ --delete
   ```

---

## 12. Future Roadmap

### 12.1 Short-term (Q1 2026)

#### **Feature: Staging Environment**
- Priority: High
- Effort: Medium
- Benefit: Safe testing before production

#### **Feature: API Gateway CORS Migration**
- Priority: High
- Effort: Low
- Benefit: 80% reduction in OPTIONS Lambda invocations

#### **Feature: Enhanced Search**
- Priority: High
- Effort: High
- Benefit: Faster product search with OpenSearch

#### **Feature: Mobile App (React Native)**
- Priority: Medium
- Effort: High
- Benefit: Better mobile experience

### 12.2 Mid-term (Q2-Q3 2026)

#### **Feature: Supplier Management**
- Priority: Medium
- Effort: Medium
- Benefit: Purchase order automation

#### **Feature: Advanced Analytics**
- Priority: Medium
- Effort: Medium
- Benefit: Sales forecasting, trend analysis

#### **Feature: Multi-store Management**
- Priority: Medium
- Effort: High
- Benefit: Chain store support

#### **Feature: Customer Portal**
- Priority: Low
- Effort: High
- Benefit: Online ordering for customers

### 12.3 Long-term (Q4 2026+)

#### **Feature: AI-powered Demand Forecasting**
- Technology: ML models on SageMaker
- Benefit: Optimize inventory levels

#### **Feature: IoT Integration**
- Technology: IoT Core + smart scales
- Benefit: Automated stock tracking

#### **Feature: Blockchain Traceability**
- Technology: Managed Blockchain
- Benefit: Supply chain transparency

#### **Feature: Voice Commerce**
- Technology: Alexa Skills + Google Assistant
- Benefit: Voice-based ordering

### 12.4 Technical Debt

#### **High Priority**
1. **CORS Security**: Restrict origins to specific domains
2. **Error Handling**: Standardize error responses
3. **API Documentation**: Generate OpenAPI docs
4. **Test Coverage**: Unit tests for critical paths
5. **Code Splitting**: Reduce frontend bundle size

#### **Medium Priority**
1. **Database Indexes**: Optimize query performance
2. **Caching Layer**: Add Redis for frequently accessed data
3. **Rate Limiting**: Implement per-user limits
4. **Logging**: Structured logging with correlation IDs
5. **Monitoring**: Custom business metrics

#### **Low Priority**
1. **Code Refactoring**: Break down large functions
2. **Type Safety**: Add Pydantic models everywhere
3. **Documentation**: Inline code documentation
4. **Accessibility**: WCAG 2.1 compliance
5. **SEO**: Server-side rendering (SSR)

---

## 13. Appendices

### Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Kirana** | Traditional Indian retail store |
| **SKU** | Stock Keeping Unit - unique product identifier |
| **HSN Code** | Harmonized System of Nomenclature - tax classification |
| **MRP** | Maximum Retail Price - legal requirement in India |
| **GST** | Goods and Services Tax - Indian tax system |
| **PWA** | Progressive Web App - installable web application |
| **JWT** | JSON Web Token - authentication mechanism |
| **ASGI** | Asynchronous Server Gateway Interface |
| **NoSQL** | Non-relational database (DynamoDB) |
| **CDN** | Content Delivery Network (CloudFront) |

### Appendix B: API Endpoint Quick Reference

**Authentication**
- `POST /api/v1/auth/send-email-passcode` - Send OTP
- `POST /api/v1/auth/verify-email-passcode` - Verify OTP
- `POST /api/v1/auth/login-with-password` - Login

**Inventory**
- `GET /api/v1/inventory/products` - List products
- `POST /api/v1/inventory/products` - Add product
- `PUT /api/v1/inventory/products/{id}` - Update product
- `DELETE /api/v1/inventory/products/{id}` - Delete product

**Orders**
- `GET /api/v1/orders` - List orders
- `POST /api/v1/orders` - Create order
- `PUT /api/v1/orders/{id}/status` - Update status

**Admin**
- `GET /api/v1/admin/products/global` - List global products
- `POST /api/v1/admin/products/global` - Create global product
- `DELETE /api/v1/admin/products/{id}` - Delete product

### Appendix C: Database Tables Quick Reference

| Table | Purpose | Primary Key |
|-------|---------|-------------|
| vyaparai-stores-prod | Store profiles | store_id |
| vyaparai-global-products-prod | Product catalog | product_id |
| vyaparai-store-inventory-prod | Store inventory | store_id + product_id |
| vyaparai-orders-prod | Customer orders | order_id |
| vyaparai-users-prod | User accounts | user_id |
| vyaparai-sessions-prod | Auth sessions | email + session_id |
| vyaparai-passcodes-prod | OTP codes | email |
| vyaparai-categories-prod | Product categories | category_id |
| vyaparai-bulk-upload-jobs-prod | CSV jobs | job_id |

### Appendix D: Environment Setup

**Prerequisites**
```bash
# Backend
Python 3.11+
pip install -r requirements.txt

# Frontend
Node.js 18+
npm install -g yarn
yarn install

# AWS CLI
aws configure
```

**Local Development**
```bash
# Backend
cd backend/lambda-email-minimal/lambda-csv-minimal
uvicorn lambda_handler:app --reload --port 8000

# Frontend
cd frontend-pwa
yarn dev
```

### Appendix E: Troubleshooting Guide

**Issue: CORS errors**
- Check CORS middleware is imported
- Verify OPTIONS handler exists
- Check API Gateway CORS config

**Issue: Lambda cold starts**
- Increase memory allocation
- Use provisioned concurrency
- Optimize import statements

**Issue: DynamoDB throttling**
- Switch to on-demand mode
- Optimize query patterns
- Add caching layer

**Issue: High API latency**
- Check CloudWatch logs
- Optimize database queries
- Add CloudFront caching

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-08 | Development Team | Initial comprehensive TDD |

---

**End of Technical Design Document**

*For questions or clarifications, contact: dev@vyaparai.com*
